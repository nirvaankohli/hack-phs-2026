import unittest

import cv2
import numpy as np

from wing_controller import FlapDetector, KeyAxis, largest_dots, shape, tip_pose, wing_pose
from wing_tracker import measurements


class ControllerTests(unittest.TestCase):
    level = [(40, 100), (100, 100), (200, 100), (300, 100), (360, 100)]

    def test_level_wing_has_no_roll(self):
        roll, height, span = wing_pose(measurements(self.level))
        self.assertAlmostEqual(roll, 0)
        self.assertEqual(height, 100)
        self.assertEqual(span, 260)

    def test_raised_left_wing_rolls_positive(self):
        # Points are mirrored: the wearer's left wing is on the camera's right.
        tilted = [(x, 100 + (200 - x) * 0.3) for x, _ in self.level]
        roll, _, _ = wing_pose(measurements(tilted))
        self.assertGreater(roll, 10)
        mirrored = [(x, 100 - (200 - x) * 0.3) for x, _ in self.level]
        self.assertAlmostEqual(wing_pose(measurements(mirrored))[0], -roll)

    def test_shape_deadzone_and_clamp(self):
        self.assertEqual(shape(0.1, 0.15), 0)
        self.assertEqual(shape(-3, 0.15), -1)
        self.assertAlmostEqual(shape(0.575, 0.15), 0.5)

    def test_key_axis_duty_cycle_matches_value(self):
        axis = KeyAxis("left", "right")
        presses = [axis.step(0.5) for _ in range(100)]
        self.assertEqual(presses.count("right"), 50)
        self.assertNotIn("left", presses)
        self.assertEqual([axis.step(-1) for _ in range(5)], ["left"] * 5)
        self.assertEqual([axis.step(0) for _ in range(5)], [None] * 5)

    def test_flap_needs_fast_downward_swing(self):
        flaps = FlapDetector(drop=0.25)
        # Slow drift down over a second is pitch, not a flap.
        self.assertFalse(any(flaps.update(t / 30, 100 + t * 2, 200) for t in range(30)))
        # A 60 px drop in 0.1 s on a 200 px span is a flap; cooldown blocks a repeat.
        flaps.update(2.0, 100, 200)
        self.assertTrue(flaps.update(2.1, 160, 200))
        flaps.update(2.15, 100, 200)
        self.assertFalse(flaps.update(2.2, 170, 200))

    def test_specks_and_small_blobs_are_dropped(self):
        mask = np.zeros((240, 400), np.uint8)
        for x, y in self.level:
            cv2.circle(mask, (x, y), 10, 255, -1)
        for x, y in ((20, 20), (380, 220), (200, 200)):
            cv2.circle(mask, (x, y), 5, 255, -1)  # Smaller false matches.
        cv2.circle(mask, (5, 230), 1, 255, -1)  # Below the minimum area.
        points, found = largest_dots(mask, min_area=10)
        self.assertEqual(found, 8)
        self.assertEqual([(round(x), round(y)) for x, y in points], self.level)

    def test_two_tip_dots_match_five_dot_roll(self):
        self.assertEqual(tip_pose([(360, 100), (40, 100)]), (0, 100, 320))
        tilted = [(x, 100 + (200 - x) * 0.3) for x, _ in self.level]
        roll, _, _ = tip_pose([tilted[0], tilted[4]])
        self.assertAlmostEqual(roll, wing_pose(measurements(tilted))[0])


if __name__ == "__main__":
    unittest.main()
