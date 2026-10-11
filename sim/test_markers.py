"""Run from the repository root: python -m unittest sim.test_markers"""
import unittest

import cv2
import numpy as np

from sim.markers import HeadFinder, MarkerDetector, pick_markers

MARKER_BGR = (117, 92, 196)  # #C45C75
SETTINGS = ("#C45C75", 8, 114, 1)


def contours_of(mask):
    return cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]


class PickMarkersTests(unittest.TestCase):
    def test_skips_oversized_blobs_and_the_head_zone(self):
        mask = np.zeros((300, 400), np.uint8)
        cv2.rectangle(mask, (150, 0), (260, 70), 255, -1)    # turban: too big
        cv2.circle(mask, (200, 110), 9, 255, -1)              # lips: inside the head zone
        for x, y in [(60, 200), (200, 210), (340, 200)]:      # markers
            cv2.circle(mask, (x, y), 7, 255, -1)
        points, picked = pick_markers(contours_of(mask), 1, 4000, head=(150, 0, 250, 140))
        self.assertEqual([(round(x), round(y)) for x, y in points], [(60, 200), (200, 210), (340, 200)])
        self.assertEqual(len(picked), 3)

    def test_without_filters_the_big_blobs_win(self):
        mask = np.zeros((300, 400), np.uint8)
        cv2.rectangle(mask, (150, 0), (260, 70), 255, -1)
        cv2.circle(mask, (200, 110), 9, 255, -1)
        for x, y in [(60, 200), (200, 210), (340, 200)]:
            cv2.circle(mask, (x, y), 7, 255, -1)
        points, _ = pick_markers(contours_of(mask), 1, 10 ** 9)
        self.assertIn((200, 110), [(round(x), round(y)) for x, y in points])


class RealFaceTests(unittest.TestCase):
    def test_lips_and_turban_in_marker_color_are_ignored(self):
        frame = cv2.resize(cv2.imread("face/test_photos/photo_001.png"), (640, 330))
        x, y, w, h = HeadFinder().find(frame)
        cx = round(x + w / 2)
        # Lips and a small turban patch, both exactly the marker color.
        cv2.ellipse(frame, (cx, round(y + h * 0.8)), (14, 6), 0, 0, 360, MARKER_BGR, -1)
        cv2.ellipse(frame, (cx, round(y - h * 0.3)), (30, 16), 0, 0, 360, MARKER_BGR, -1)
        # A big turban, too: bigger than any marker.
        cv2.ellipse(frame, (cx, round(y - h * 0.1)), (round(w * 0.6), round(h * 0.35)), 0, 180, 360,
                    MARKER_BGR, -1)
        markers = [(40, 300), (cx, 310), (600, 300)]
        for point in markers:
            cv2.circle(frame, point, 8, MARKER_BGR, -1)

        points, _ = MarkerDetector()(frame, *SETTINGS)
        self.assertEqual([(round(px), round(py)) for px, py in points], markers)

        unfiltered, _ = MarkerDetector(max_area=10 ** 9, ignore_head=False)(frame, *SETTINGS)
        self.assertNotEqual([(round(px), round(py)) for px, py in unfiltered], markers)


if __name__ == "__main__":
    unittest.main()
