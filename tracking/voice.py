"""ElevenLabs voice callouts for the wing controller.

Each line is generated once through the ElevenLabs API and cached as a WAV
file, so repeated callouts play instantly and keep working if the network
drops. Set ELEVENLABS_API_KEY before running wing_controller.py --voice.
"""

import hashlib
import json
import os
import threading
import urllib.request
from pathlib import Path

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=wav_22050"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_MODEL = "eleven_flash_v2_5"  # Lowest-latency model, for live lines.
CACHE_DIR = Path(__file__).with_name("voice_cache")

LINES = {
    "countdown": "Get ready. Hold your wings level.",
    "engaged": "Wings calibrated. You have control.",
    "pull_up": "Pull up! Pull up!",
    "steep_bank": "Easy on that bank.",
    "lost": "I've lost sight of your wings.",
    "regained": "Got you again.",
}


def play_wav(path):
    import winsound
    # Async so the camera loop never waits; a new line cuts off the previous one.
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


class Voice:
    def __init__(self, api_key, voice_id=DEFAULT_VOICE, model=DEFAULT_MODEL,
                 cache_dir=CACHE_DIR, player=play_wav):
        self.api_key, self.voice_id, self.model = api_key, voice_id, model
        self.cache_dir, self.player = Path(cache_dir), player
        self.cache_dir.mkdir(exist_ok=True)
        self.errors = []

    def path_for(self, text):
        key = hashlib.sha1(f"{self.voice_id}|{self.model}|{text}".encode()).hexdigest()[:16]
        return self.cache_dir / f"{key}.wav"

    def fetch(self, text):
        """Return the cached WAV for text, generating it on a cache miss."""
        path = self.path_for(text)
        if not path.exists():
            request = urllib.request.Request(
                API_URL.format(voice_id=self.voice_id),
                data=json.dumps({"text": text, "model_id": self.model}).encode(),
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=15) as response:
                audio = response.read()
            # Write then rename so a half-finished download is never played.
            partial = path.with_suffix(".part")
            partial.write_bytes(audio)
            partial.replace(path)
        return path

    def say(self, text):
        """Speak text in the background; network or audio errors never stop the controller."""
        def run():
            try:
                self.player(self.fetch(text))
            except Exception as error:  # Shown in the tracker panel instead of crashing.
                self.errors.append(f"Voice error: {error}")
        threading.Thread(target=run, daemon=True).start()

    def warm_up(self):
        """Generate every fixed line ahead of time so the first callouts aren't delayed."""
        def run():
            for text in LINES.values():
                try:
                    self.fetch(text)
                except Exception as error:
                    self.errors.append(f"Voice error: {error}")
                    return
        threading.Thread(target=run, daemon=True).start()


class Callouts:
    """Decide when to speak, based on the controller's state each frame."""

    def __init__(self, voice):
        self.voice = voice
        self.next_allowed = {}
        self.since = {}
        self.lost_announced = False
        self.flight_start = None
        self.max_bank = 0.0

    def say(self, name, now, cooldown=0.0, text=None):
        if now >= self.next_allowed.get(name, 0.0):
            self.next_allowed[name] = now + cooldown
            self.voice.say(text or LINES[name])

    def held(self, name, condition, now, seconds):
        """True once condition has stayed true for the given number of seconds."""
        if not condition:
            self.since.pop(name, None)
            return False
        return now - self.since.setdefault(name, now) >= seconds

    def countdown(self, now):
        self.say("countdown", now)

    def engaged(self, now):
        self.flight_start, self.max_bank, self.lost_announced = now, 0.0, False
        self.since.clear()
        self.say("engaged", now)

    def paused(self, now):
        if self.flight_start is None:
            return
        seconds = round(now - self.flight_start)
        duration = plural(seconds, "second")
        if seconds >= 60:
            duration = f"{plural(seconds // 60, 'minute')} and {plural(seconds % 60, 'second')}"
        self.say("summary", now, text=f"Controls paused. You flew for {duration}, "
                                      f"with a steepest bank of {round(self.max_bank)} degrees.")
        self.flight_start = None

    def update(self, now, tracking, roll_degrees, roll_axis, pitch_axis):
        """Call every frame while flying. Axes are -1..1; negative pitch is nose down."""
        if self.held("lost", not tracking, now, 0.7) and not self.lost_announced:
            self.lost_announced = True
            self.say("lost", now)
        if tracking and self.lost_announced:
            self.lost_announced = False
            self.say("regained", now)
        if not tracking:
            return
        self.max_bank = max(self.max_bank, abs(roll_degrees))
        if self.held("pull_up", pitch_axis <= -0.8, now, 1.5):
            self.say("pull_up", now, cooldown=6.0)
        if self.held("steep_bank", abs(roll_axis) >= 0.95, now, 2.0):
            self.say("steep_bank", now, cooldown=8.0)


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def from_environment(voice_id=DEFAULT_VOICE):
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("Set ELEVENLABS_API_KEY first, e.g. in PowerShell: "
                           '$env:ELEVENLABS_API_KEY = "your key"')
    return Voice(api_key, voice_id)
