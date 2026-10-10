
import argparse
import json
import math
import mimetypes
from pathlib import Path
import sys
import unittest

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracking.api import app


PICTURES = Path(__file__).with_name("test_api_pictures")
DEFAULT_SETTINGS = {"color": "#034E57", "hue_tolerance": 15,
                    "shade_tolerance": 160, "min_dot_area": 30}
VARIABLES = {"average_height", "left_distance_from_center", "right_distance_from_center",
             "left_height_relative_to_average", "right_height_relative_to_average"}


def check_result(result, expected):
    if not result["tracking"] or result["dot_count"] != 5 or len(result["dots"]) != 5:
        raise AssertionError(f"Expected 5 tracked dots; got {result['dot_count']}")
    values = result["variables"]
    if set(values) != VARIABLES or not all(isinstance(v, (int, float)) and math.isfinite(v)
                                         for v in values.values()):
        raise AssertionError("Expected all five finite measurements")
    dots = result["dots"]
    right, center, left = dots[:2], dots[2], dots[3:]
    average = sum(dot["y"] for dot in dots) / 5
    calculated = {
        "average_height": average,
        "left_distance_from_center": sum(dot["x"] for dot in left) / 2 - center["x"],
        "right_distance_from_center": center["x"] - sum(dot["x"] for dot in right) / 2,
        "left_height_relative_to_average": average - sum(dot["y"] for dot in left) / 2,
        "right_height_relative_to_average": average - sum(dot["y"] for dot in right) / 2,
    }
    for name, value in calculated.items():
        if not math.isclose(values[name], value, abs_tol=0.01):
            raise AssertionError(f"Incorrect measurement: {name}")
    if expected:
        if len(expected) != 5:
            raise AssertionError("Fixture must specify five expected dots")
        for dot, (x, y) in zip(dots, sorted(expected)):
            if math.hypot(dot["x"] - x, dot["y"] - y) > 12:
                raise AssertionError(f"Wrong marker location: {dot}, expected near {(x, y)}")


def run_images(client, folder):
    images = sorted(p for p in folder.iterdir()
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"})
    if not images:
        raise ValueError(f"No images in {folder}")
    response = client.get("/settings")
    response.raise_for_status()
    original_settings = response.json()
    failures = 0
    try:
        for path in images:
            print(f"\n--- {path.name} ---", flush=True)
            try:
                sidecar = path.with_suffix(".json")
                fixture = json.loads(sidecar.read_text()) if sidecar.exists() else {}
                settings = DEFAULT_SETTINGS | fixture.get("settings", {})
                response = client.post("/settings", json=settings)
                response.raise_for_status()
                print("Settings:", json.dumps(response.json()))
                with path.open("rb") as image:
                    response = client.post("/track", files={"file": (
                        path.name, image, mimetypes.guess_type(path.name)[0] or "application/octet-stream")})
                print(f"HTTP {response.status_code}")
                response.raise_for_status()
                result = response.json()
                print(json.dumps(result, indent=2))
                check_result(result, fixture.get("expected_dots"))
                print("PASS: five markers and all measurements verified")
            except (httpx.HTTPError, AssertionError, ValueError, KeyError, TypeError, OSError) as error:
                failures += 1
                print(f"FAIL: {error}")
    finally:
        response = client.post("/settings", json=original_settings)
        response.raise_for_status()
    print(f"\nResults: {len(images) - failures}/{len(images)} passed; {failures} failed")
    return failures


class PictureApiTests(unittest.TestCase):
    def test_folder_images(self):
        with TestClient(app) as client:
            self.assertEqual(run_images(client, PICTURES), 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Running API URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--pictures", type=Path, default=PICTURES)
    args = parser.parse_args()
    client = httpx.Client(base_url=args.url.rstrip("/"), timeout=30) if args.url else TestClient(app)
    print(f"API: {args.url or 'in-process FastAPI (no server needed)'}")
    try:
        with client:
            raise SystemExit(1 if run_images(client, args.pictures) else 0)
    except (httpx.HTTPError, OSError, ValueError) as error:
        raise SystemExit(f"Unable to run image tests: {error}") from error
