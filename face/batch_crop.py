"""Crop images in test_photos into test_photos_output."""

from pathlib import Path

import cv2

from crop_face import crop_face


def main() -> None:
    folder = Path(__file__).resolve().parent
    output = folder / "test_photos_output"
    output.mkdir(exist_ok=True)
    for photo in sorted((folder / "test_photos").iterdir()):
        if not photo.is_file() or photo.suffix.lower() not in {
            ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"
        }:
            continue
        try:
            cropped = crop_face(photo)
            destination = output / (photo.stem + ".png")
            if not cv2.imwrite(str(destination), cropped):
                raise OSError("Could not save cropped image")
            print(f"Saved {destination.name}")
        except (ValueError, RuntimeError, OSError, cv2.error) as error:
            print(f"Skipped {photo.name}: {error}")


if __name__ == "__main__":
    main()
