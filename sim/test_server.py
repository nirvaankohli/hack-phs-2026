"""Run from the repository root: python -m unittest sim.test_server"""
import math
import threading
import time
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from sim.server import MARKERS, app, serialize_camera, wing_pose
from tracking import api as tracking_api


def values(left_height, right_height, left_distance=100, right_distance=100):
    return {"left_height_relative_to_average": left_height,
            "right_height_relative_to_average": right_height,
            "left_distance_from_center": left_distance,
            "right_distance_from_center": right_distance}


class ServerTests(unittest.TestCase):
    calibrated = SimpleNamespace(span=200, neutral_y=(0.1, 0.1))

    def test_uncalibrated_or_lost_is_inactive(self):
        uncalibrated = SimpleNamespace(span=None, neutral_y=(0, 0))
        self.assertFalse(wing_pose({"dot_count": 3}, values(20, 20), uncalibrated, 1.0)["active"])
        lost = wing_pose({"dot_count": 2}, None, self.calibrated, 1.0)
        self.assertEqual((lost["active"], lost["calibrated"], lost["dots"]), (False, True, 2))

    def test_raised_left_wing_banks_right_relative_to_calibration(self):
        pose = wing_pose({"dot_count": 3}, values(60, 20), self.calibrated, 2.5)
        self.assertTrue(pose["active"])
        self.assertAlmostEqual(pose["left"], 0.2)
        self.assertAlmostEqual(pose["right"], 0.0)
        self.assertAlmostEqual(pose["lift"], 0.1)
        self.assertAlmostEqual(pose["roll"], math.degrees(math.atan2(0.2, 1)))
        self.assertEqual(pose["t"], 2.5)

    def test_folded_wings_shrink_span(self):
        pose = wing_pose({"dot_count": 3}, values(20, 20, 60, 60), self.calibrated, 1.0)
        self.assertAlmostEqual(pose["span"], 2 * math.hypot(60, 20) / 200)
        self.assertAlmostEqual(pose["lift"], 0.0)

    def test_swinging_arms_down_to_flap_is_not_a_tuck(self):
        # Arms 45 degrees below the shoulders: hands come in horizontally, but reach is unchanged.
        reach = 100 / math.sqrt(2)
        pose = wing_pose({"dot_count": 3}, values(-reach, -reach, reach, reach), self.calibrated, 1.0)
        self.assertAlmostEqual(pose["span"], 1.0)
        self.assertLess(pose["lift"], -0.4)

    def test_serves_sim_and_bridge_with_marker_settings(self):
        client = TestClient(app)
        self.assertIn("Skyborne", client.get("/").text)
        self.assertTrue(client.get("/health").json()["ok"])
        self.assertEqual(client.get("/tracking/settings").json(), MARKERS)
        self.assertEqual(tracking_api.settings.color, "#C45C75")
        self.assertEqual(client.get("/js/flight.js").headers["Cache-Control"], "no-cache")


class SlowReleaseCamera:
    """Mimics bridge.Camera: stop flips the flag, the thread releases the device later."""

    def __init__(self):
        self.running = False
        self.thread = None
        self.open_captures = 0
        self.max_open = 0

    def loop(self):
        self.open_captures += 1
        self.max_open = max(self.max_open, self.open_captures)
        while self.running:
            time.sleep(0.01)
        time.sleep(0.3)  # releasing the webcam
        self.open_captures -= 1

    def start(self, index):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.05)  # the bridge gives up waiting, too


class CameraRestartTests(unittest.TestCase):
    def test_refresh_never_opens_two_captures_at_once(self):
        cam = SlowReleaseCamera()
        serialize_camera(cam)
        cam.start(0)
        time.sleep(0.05)
        cam.stop()        # page hidden
        cam.start(0)      # new page loads right away
        time.sleep(0.05)
        self.assertEqual(cam.max_open, 1)
        self.assertTrue(cam.running)
        cam.stop()
        cam.thread.join()


if __name__ == "__main__":
    unittest.main()
