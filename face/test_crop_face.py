"""Regression checks against the six real input poses."""

from pathlib import Path
import unittest

import cv2
import numpy as np

from face import crop_face


class FaceCutoutTests(unittest.TestCase):
    def test_all_poses_have_transparent_background(self):
        photos = sorted((Path(__file__).parent / "test_photos").glob("*.png"))
        self.assertGreaterEqual(len(photos), 6)
        for photo in photos:
            with self.subTest(photo=photo.name):
                result = crop_face(photo)
                self.assertEqual(result.shape[2], 4)
                alpha = result[:, :, 3]
                self.assertTrue(np.any(alpha == 0))
                self.assertTrue(np.any(alpha == 255))
                self.assertTrue(np.any((alpha > 0) & (alpha < 255)))
                self.assertTrue(np.all(result[alpha == 0] == 0))
                # Reject a tiny background-person crop in these fixtures.
                self.assertGreater(min(result.shape[:2]), 150)
                if photo.name == "photo_001.png":
                    # The white headwear was entirely lost with the oval mask.
                    bright = np.all(result[:, :, :3] > 180, axis=2) & (alpha == 255)
                    self.assertGreater(np.count_nonzero(bright), 500)
                ok, encoded = cv2.imencode(".png", result)
                self.assertTrue(ok)
                decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
                np.testing.assert_array_equal(decoded, result)

    def test_blank_image_has_no_face(self):
        with self.assertRaisesRegex(ValueError, "No face detected"):
            crop_face(np.zeros((256, 256, 3), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
