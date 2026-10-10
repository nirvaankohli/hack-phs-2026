"""Exercise image upload, real inference, and transparent PNG responses."""

from pathlib import Path
import unittest

import cv2
import numpy as np
from fastapi.testclient import TestClient

from .api import MAX_UPLOAD_BYTES, app


class FaceApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_photo_returns_transparent_png(self):
        path = Path(__file__).parent / "test_photos" / "photo_001.png"
        response = self.client.post("/crop", files={"file": (path.name, path.read_bytes(), "image/png")})
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else "")
        self.assertEqual(response.headers["content-type"], "image/png")
        image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_UNCHANGED)
        self.assertEqual(image.shape[2], 4)
        self.assertTrue(np.any(image[:, :, 3] == 0))
        self.assertTrue(np.any(image[:, :, 3] == 255))
        self.assertTrue(np.all(image[image[:, :, 3] == 0] == 0))
        bright = np.all(image[:, :, :3] > 180, axis=2) & (image[:, :, 3] == 255)
        self.assertGreater(np.count_nonzero(bright), 500)

    def test_invalid_or_empty_image(self):
        for data in (b"not an image", b""):
            with self.subTest(data=data):
                response = self.client.post("/crop", files={"file": ("bad.png", data, "image/png")})
                self.assertEqual(response.status_code, 400)

    def test_no_face(self):
        _, image = cv2.imencode(".png", np.zeros((256, 256, 3), dtype=np.uint8))
        response = self.client.post("/crop", files={"file": ("blank.png", image.tobytes(), "image/png")})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "No face detected in image")

    def test_oversized_upload(self):
        response = self.client.post("/crop", files={"file": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1))})
        self.assertEqual(response.status_code, 413)

    def test_missing_upload(self):
        self.assertEqual(self.client.post("/crop").status_code, 422)


if __name__ == "__main__":
    unittest.main()
