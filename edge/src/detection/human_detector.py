"""Stage 2: Human detection using YOLOv5n (ONNX Runtime).

Only runs on frames that passed the motion gate. Costs ~300ms on ARM,
~50-100ms on a laptop CPU.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0  # COCO class 0 = person
INPUT_SIZE = 640


@dataclass
class Detection:
    """A single person detection result."""
    x: int       # top-left x
    y: int       # top-left y
    w: int       # width
    h: int       # height
    confidence: float


class HumanDetector:
    """YOLOv5n person detector using ONNX Runtime."""

    def __init__(self, model_path: str, confidence_threshold: float = 0.6,
                 nms_threshold: float = 0.45):
        self._model_path = model_path
        self._conf_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._session: ort.InferenceSession | None = None
        self._input_name: str = ""
        self._input_dtype: np.dtype = np.float32

    def load(self) -> bool:
        """Load the ONNX model into memory."""
        if not Path(self._model_path).exists():
            logger.error("Model file not found: %s", self._model_path)
            return False
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                self._model_path, opts,
                providers=["CPUExecutionProvider"],
            )
            input_info = self._session.get_inputs()[0]
            self._input_name = input_info.name
            # Detect model's expected input dtype (float16 or float32)
            onnx_type = input_info.type
            if "float16" in onnx_type or "Float16" in onnx_type:
                self._input_dtype = np.float16
            else:
                self._input_dtype = np.float32
            logger.info("Model loaded: %s (input dtype: %s)", self._model_path, self._input_dtype)
            return True
        except Exception:
            logger.exception("Failed to load model")
            return False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run person detection on a frame.

        Args:
            frame: BGR image (any resolution, will be resized)

        Returns:
            List of Detection objects for persons found
        """
        if self._session is None:
            return []

        orig_h, orig_w = frame.shape[:2]
        t0 = time.monotonic()

        # Pre-process: resize, normalize, transpose
        blob = self._preprocess(frame)

        # Inference
        outputs = self._session.run(None, {self._input_name: blob})

        # Post-process: filter person class, NMS, scale to original coords
        detections = self._postprocess(outputs[0], orig_w, orig_h)

        elapsed = (time.monotonic() - t0) * 1000
        if detections:
            logger.debug("YOLO: %d person(s) detected in %.0fms", len(detections), elapsed)

        return detections

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize, normalize, and prepare input tensor."""
        img = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        img = np.expand_dims(img, axis=0)    # add batch dim
        return img.astype(self._input_dtype)

    def _postprocess(self, output: np.ndarray, orig_w: int,
                     orig_h: int) -> list[Detection]:
        """Filter detections: person class only, confidence threshold, NMS."""
        # YOLOv5 output shape: [1, N, 85] (x, y, w, h, obj_conf, 80 class scores)
        # or [N, 85] depending on export
        output = output.astype(np.float32)
        if output.ndim == 3:
            output = output[0]

        boxes = []
        confidences = []

        for row in output:
            obj_conf = row[4]
            if obj_conf < 0.3:
                continue

            class_scores = row[5:]
            class_id = int(np.argmax(class_scores))
            if class_id != PERSON_CLASS_ID:
                continue

            confidence = float(obj_conf * class_scores[class_id])
            if confidence < self._conf_threshold:
                continue

            # Convert from center coords to top-left coords
            cx, cy, bw, bh = row[0], row[1], row[2], row[3]
            x = int((cx - bw / 2) * orig_w / INPUT_SIZE)
            y = int((cy - bh / 2) * orig_h / INPUT_SIZE)
            w = int(bw * orig_w / INPUT_SIZE)
            h = int(bh * orig_h / INPUT_SIZE)

            boxes.append([x, y, w, h])
            confidences.append(confidence)

        if not boxes:
            return []

        # Non-maximum suppression
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self._conf_threshold,
                                    self._nms_threshold)

        detections = []
        for i in indices:
            idx = i if isinstance(i, int) else i[0]
            bx, by, bw, bh = boxes[idx]
            detections.append(Detection(
                x=max(0, bx), y=max(0, by),
                w=bw, h=bh,
                confidence=confidences[idx],
            ))

        return detections

    @property
    def is_loaded(self) -> bool:
        return self._session is not None
