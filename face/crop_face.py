"""Extract the largest face as a tightly cropped, transparent BGRA image."""

import argparse
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

# Ordered MediaPipe face oval: forehead, temples, cheeks, and jaw.
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


def _detector():
    model = Path(__file__).parent / "models" / "face_landmarker.task"
    if not model.is_file():
        raise FileNotFoundError(f"Missing face model: {model}. See face/README.md.")
    return mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            num_faces=10,
        )
    )


def remove_background(image: np.ndarray) -> np.ndarray:
    """Remove the background from a BGR portrait crop; return uint8 BGRA."""
    model = Path(__file__).parent / "models" / "selfie_multiclass_256x256.tflite"
    if not model.is_file():
        raise FileNotFoundError(f"Missing background model: {model}. See face/README.md.")
    options = mp.tasks.vision.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        output_confidence_masks=True,
    )
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    with mp.tasks.vision.ImageSegmenter.create_from_options(options) as segmenter:
        result = segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        # Keep hair, skin, and accessories; remove background and clothing.
        confidence = sum(result.confidence_masks[i].numpy_view()
                         for i in (1, 2, 3, 5)).squeeze(axis=2).copy()
    alpha = np.rint(np.clip((confidence - 0.15) / 0.7, 0, 1) * 255).astype(np.uint8)
    # Remove isolated pixels and thin collar remnants from the model boundary.
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype(np.uint8))
    if count < 2:
        raise ValueError("Could not separate the face from the background")
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    alpha[labels != largest] = 0
    cutout = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    cutout[:, :, 3] = alpha
    cutout[alpha == 0] = 0
    return cutout


def crop_face(image: str | Path | np.ndarray, padding: float = 0) -> np.ndarray:
    """Extract the largest face and headwear, excluding the neck (uint8 BGRA).

    Accepts a file path or OpenCV BGR uint8 array. Padding adds transparent
    space around the result, as a fraction of its width/height. The close crop
    preserves glasses and headwear, with the lower edge following the jaw.
    Raises ValueError for invalid input or no detected face, and
    FileNotFoundError for an unreadable file or missing model.
    """
    if not np.isfinite(padding) or padding < 0:
        raise ValueError("padding must be a finite, non-negative number")
    if isinstance(image, (str, Path)):
        path = Path(image)
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"Could not read image: {path}")
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 3 or image.size == 0):
        raise ValueError("image must be a non-empty BGR uint8 array with 3 channels")

    height, width = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    with _detector() as detector:
        result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.face_landmarks:
        raise ValueError("No face detected in image")
    outlines = [np.array([(face[i].x * width, face[i].y * height)
                         for i in FACE_OVAL], dtype=np.float32)
                for face in result.face_landmarks]
    outline = max(outlines, key=lambda points: abs(cv2.contourArea(points)))

    x, y, w, h = cv2.boundingRect(outline)
    # Leave room above the forehead for tall headwear. Keep the crop local
    # to the selected face so the background model can resolve its edges.
    margin_x = round(max(w, h) * 0.3)
    x0, y0 = max(0, x - margin_x), max(0, y - h)
    x1, y1 = min(width, x + w + margin_x), min(height, y + h + round(h * 0.1))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Detected face is outside the image")
    cutout = remove_background(image[y0:y1, x0:x1])
    # Follow the actual jaw, including tilted poses; leave the area above
    # the temples open so segmentation can preserve headwear and hair.
    jaw = outline[8:29] - np.array([x0, y0], dtype=np.float32)
    crop_width = cutout.shape[1]
    polygon = np.vstack(([[0, 0], [crop_width - 1, 0],
                          [crop_width - 1, jaw[0, 1]]], jaw,
                         [[0, jaw[-1, 1]]]))
    head_mask = np.zeros(cutout.shape[:2], dtype=np.uint8)
    cv2.fillPoly(head_mask, [np.rint(polygon * 16).astype(np.int32)], 255,
                 lineType=cv2.LINE_AA, shift=4)
    cutout[:, :, 3] = np.minimum(cutout[:, :, 3], head_mask)
    cutout[cutout[:, :, 3] == 0] = 0
    bounds = cv2.findNonZero(cutout[:, :, 3])
    if bounds is None:
        raise ValueError("Could not separate the face from the background")
    x, y, w, h = cv2.boundingRect(bounds)
    cutout = cutout[y:y + h, x:x + w].copy()
    pad_x, pad_y = round(w * padding), round(h * padding)
    return cv2.copyMakeBorder(cutout, pad_y, pad_y, pad_x, pad_x,
                              cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a face onto a transparent PNG.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--padding", type=float, default=0)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".png":
        parser.error("output must be .png to preserve transparency")
    try:
        cropped = crop_face(args.input, padding=args.padding)
        if not cv2.imwrite(str(args.output), cropped):
            raise OSError(f"Could not write image: {args.output}")
    except (ValueError, RuntimeError, OSError, cv2.error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
