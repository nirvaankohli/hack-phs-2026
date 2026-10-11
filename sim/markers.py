"""Marker selection for Skyborne that ignores the player's head.

The Cloudbound bridge keeps the three biggest blobs of the marker color. Lips,
skin, hair and headwear can match a reddish marker and are often bigger than
the markers, so they win. This version finds the face, ignores matches on and
around the head (face, mouth, turban or hat above it), and ignores blobs too
big to be a marker, then keeps the three biggest of what's left.

sim/server.py installs it in place of game.bridge.detect_game_points, so the
camera loop and the marker-view preview both use it. Cloudbound is unchanged.
"""

from pathlib import Path
from threading import Lock
from time import monotonic

import cv2

from tracking.wing_tracker import detect_points

FACE_MODEL = Path(__file__).resolve().parent.parent / "face" / "models" / "face_landmarker.task"
# The head zone around the face's forehead-to-chin box, in face heights/widths.
ABOVE = 1.0    # turban, hat or hair above the forehead
BELOW = 0.15   # beard and just under the chin
SIDES = 0.45


def face_finder():
    """Returns find(frame) -> (x, y, w, h) of the largest face, or None.

    Uses the repository's MediaPipe face model (robust to turning and headwear),
    falling back to OpenCV's bundled frontal-face cascade if it's unavailable.
    """
    try:
        import mediapipe as mp
        landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(FACE_MODEL)), num_faces=1))

        def find(frame):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not result.face_landmarks:
                return None
            height, width = frame.shape[:2]
            xs = [p.x * width for p in result.face_landmarks[0]]
            ys = [p.y * height for p in result.face_landmarks[0]]
            return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        return find
    except Exception:  # Missing model or mediapipe: use the simpler detector.
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        def find(frame):
            gray = cv2.cvtColor(cv2.resize(frame, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(24, 24))
            if not len(faces):
                return None
            x, y, w, h = (int(v) * 2 for v in max(faces, key=lambda f: f[2] * f[3]))
            # The cascade box stops near the upper lip; stretch it to the chin.
            return x, y, w, h * 1.15
        return find


class HeadFinder:
    """Finds the largest face, at most every `interval` seconds, and remembers it for `hold`."""

    def __init__(self, interval=0.12, hold=1.0, find=None):
        self.find = find or face_finder()
        self.interval, self.hold = interval, hold
        self.box = None
        self.seen = self.checked = -1e9
        self.lock = Lock()

    def zone(self, frame, now=None):
        """(left, top, right, bottom) to ignore, or None if no face has been seen lately."""
        now = monotonic() if now is None else now
        with self.lock:
            if now - self.checked >= self.interval:
                self.checked = now
                box = self.find(frame)
                if box:
                    self.box, self.seen = box, now
            if self.box is None or now - self.seen > self.hold:
                return None
            x, y, w, h = self.box
            return (x - SIDES * w, y - ABOVE * h, x + (1 + SIDES) * w, y + (1 + BELOW) * h)


def pick_markers(contours, min_area, max_area, head=None):
    """The three biggest blobs within the size limits and outside the head zone."""
    picked = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not min_area <= area <= max_area:
            continue
        m = cv2.moments(contour)
        if not m["m00"]:
            continue
        x, y = m["m10"] / m["m00"], m["m01"] / m["m00"]
        if head and head[0] <= x <= head[2] and head[1] <= y <= head[3]:
            continue
        picked.append((area, cv2.boundingRect(contour)[:2], (x, y), contour))
    # Biggest first, with position as a stable tie-breaker (as the bridge does).
    picked.sort(key=lambda p: (-p[0], *p[1]))
    picked = picked[:3]
    return sorted(p[2] for p in picked), [p[3] for p in picked]


class MarkerDetector:
    """Drop-in replacement for game.bridge.detect_game_points."""

    def __init__(self, max_area=4000, ignore_head=True):
        self.max_area = max_area
        self.head = HeadFinder() if ignore_head else None
        self.last_zone = None

    def __call__(self, frame, color, hue_tolerance, shade_tolerance, min_area):
        _, mask = detect_points(frame, color, hue_tolerance, shade_tolerance, min_area)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.last_zone = self.head.zone(frame) if self.head else None
        return pick_markers(contours, min_area, self.max_area, self.last_zone)
