# Transparent face cutouts

From the project root:

```sh
pip install -r face/requirements.txt
python face/crop_face.py input.jpg face.png
python face/batch_crop.py
```

The batch script reads `face/test_photos` and writes transparent PNGs into
`face/test_photos_output`, keeping each filename stem. Files with the same
stem overwrite the same output. Images with no detected face are skipped.

```python
from face import crop_face
import cv2

cutout = crop_face("input.jpg")
cv2.imwrite("face.png", cutout)
```

The function accepts a path or OpenCV BGR uint8 array and returns a new BGRA
uint8 array. It finds the largest face, crops with extra room above the
forehead, then runs portrait segmentation. A landmark mask follows the jaw
to remove the neck while leaving the upper head open for hair and headwear.
Background and clothing become transparent. Glasses and headwear are kept;
ears may be clipped where they extend below the face boundary. Headwear that
extends beyond the source image or crop cannot be recovered.
`padding=0.15` adds transparent space around the result; the default is tight.
Use PNG for output.

Edges are estimated by a model. Extreme profiles, occlusion, and busy
backgrounds may still leave imperfect edges.
Unreadable files raise FileNotFoundError; missing faces raise ValueError.
Inference runs locally, and model resources are released after each call.

The model at `models/face_landmarker.task` is the official
[MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker),
float16 version 1. Background removal uses the official
[Selfie Multiclass segmenter](https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter),
float32 version 1. Both models are stored locally (about 20 MB total).
To restore them if missing:

```sh
mkdir -p face/models
curl -fL https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task -o face/models/face_landmarker.task
curl -fL https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite -o face/models/selfie_multiclass_256x256.tflite
```

Run the test-photo regression checks:

```sh
python -m unittest face.test_crop_face
```
