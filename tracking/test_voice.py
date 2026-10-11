import tempfile
import unittest
from unittest import mock

import voice


class FakeVoice:
    def __init__(self):
        self.said = []
        self.errors = []

    def say(self, text):
        self.said.append(text)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class VoiceTests(unittest.TestCase):
    def test_fetch_calls_api_once_then_uses_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            speaker = voice.Voice("test-key", cache_dir=folder)
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"RIFFwav")) as urlopen:
                first = speaker.fetch("Pull up!")
                second = speaker.fetch("Pull up!")
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), b"RIFFwav")
            self.assertEqual(urlopen.call_count, 1)
            request = urlopen.call_args[0][0]
            self.assertEqual(request.get_header("Xi-api-key"), "test-key")
            self.assertIn(voice.DEFAULT_VOICE, request.full_url)
            self.assertIn("output_format=wav_22050", request.full_url)
            self.assertNotEqual(speaker.path_for("Pull up!"), speaker.path_for("Got you again."))

    def test_missing_key_explains_setup(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ELEVENLABS_API_KEY"):
                voice.from_environment()


class CalloutTests(unittest.TestCase):
    def setUp(self):
        self.voice = FakeVoice()
        self.callouts = voice.Callouts(self.voice)

    def test_pull_up_needs_sustained_dive_and_has_cooldown(self):
        self.callouts.engaged(0)
        for t in range(0, 14):  # Brief dive: 1.3 s is not enough.
            self.callouts.update(t / 10, True, 0, 0, -1)
        self.callouts.update(1.4, True, 0, 0, 0)
        self.assertNotIn(voice.LINES["pull_up"], self.voice.said)
        for t in range(20, 100):  # 8 s continuous dive: once, then again after the 6 s cooldown.
            self.callouts.update(t / 10, True, 0, 0, -1)
        self.assertEqual(self.voice.said.count(voice.LINES["pull_up"]), 2)

    def test_lost_and_regained_are_announced_once(self):
        self.callouts.engaged(0)
        for t in range(10):
            self.callouts.update(t / 10, False, 0, 0, 0)
        self.callouts.update(1.0, True, 0, 0, 0)
        self.callouts.update(1.1, True, 0, 0, 0)
        self.assertEqual(self.voice.said, [voice.LINES["engaged"], voice.LINES["lost"],
                                           voice.LINES["regained"]])

    def test_pause_summary_reports_time_and_steepest_bank(self):
        self.callouts.engaged(10)
        self.callouts.update(20, True, -34.4, -1, 0)
        self.callouts.update(30, True, 12, 0.3, 0)
        self.callouts.paused(85)
        self.assertEqual(self.voice.said[-1], "Controls paused. You flew for 1 minute and 15 seconds, "
                                              "with a steepest bank of 34 degrees.")
        self.callouts.paused(90)
        self.assertEqual(len(self.voice.said), 2, "No summary without a new flight")


if __name__ == "__main__":
    unittest.main()
