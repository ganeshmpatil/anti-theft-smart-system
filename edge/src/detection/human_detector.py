"""Stage 2: Human detection using YOLOv5n.

Supports two inference backends selected via config:
  - "onnx"   : ONNX Runtime  (default, needs onnxruntime)
  - "tflite" : TensorFlow Lite (needs tflite-runtime, works on ARMv7 32-bit)

Only runs on frames that passed the motion gate. Costs ~300ms on ARM,
~50-100ms on a laptop CPU.
"""

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0  # COCO class 0 = person

# Default 320 for Pi 3 / low-RAM SBCs (~400-500ms inference)
# Set to 640 for Orange Pi Zero 3 / x86 (~100-300ms inference)
# Override via env YOLO_INPUT_SIZE or constructor input_size param
DEFAULT_INPUT_SIZE = 320


@dataclass
class Detection:
    """A single person detection result."""
    x: int       # top-left x
    y: int       # top-left y
    w: int       # width
    h: int       # height
    confidence: float


class _OnnxBackend:
    """ONNX Runtime inference backend."""

    def __init__(self):
        self._session = None
        self._input_name: str = ""
        self._input_dtype: np.dtype = np.float32

    def load(self, model_path: str) -> bool:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        num_cores = os.cpu_count() or 2
        opts.intra_op_num_threads = num_cores
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            model_path, opts,
            providers=["CPUExecutionProvider"],
        )
        input_info = self._session.get_inputs()[0]
        self._input_name = input_info.name
        onnx_type = input_info.type
        if "float16" in onnx_type or "Float16" in onnx_type:
            self._input_dtype = np.float16
        else:
            self._input_dtype = np.float32
        logger.info("ONNX model loaded: %s (input dtype: %s)", model_path, self._input_dtype)
        return True

    @property
    def input_dtype(self) -> np.dtype:
        return self._input_dtype

    def run(self, blob: np.ndarray) -> np.ndarray:
        outputs = self._session.run(None, {self._input_name: blob})
        return outputs[0]

    @property
    def is_loaded(self) -> bool:
        return self._session is not None


class _TFLiteBackend:
    """TensorFlow Lite inference backend."""

    def __init__(self):
        self._interpreter = None
        self._input_index: int = 0
        self._output_index: int = 0
        self._input_dtype: np.dtype = np.float32

    def load(self, model_path: str) -> bool:
        from tflite_runtime.interpreter import Interpreter

        num_cores = os.cpu_count() or 2
        self._interpreter = Interpreter(model_path=model_path, num_threads=num_cores)
        self._interpreter.allocate_tensors()

        input_details = self._interpreter.get_input_details()[0]
        output_details = self._interpreter.get_output_details()[0]

        self._input_index = input_details["index"]
        self._output_index = output_details["index"]
        self._input_dtype = input_details["dtype"]
        logger.info("TFLite model loaded: %s (input dtype: %s)", model_path, self._input_dtype)
        return True

    @property
    def input_dtype(self) -> np.dtype:
        return self._input_dtype

    def run(self, blob: np.ndarray) -> np.ndarray:
        self._interpreter.set_tensor(self._input_index, blob)
        self._interpreter.invoke()
        return self._interpreter.get_tensor(self._output_index)

    @property
    def is_loaded(self) -> bool:
        return self._interpreter is not None


class HumanDetector:
    """YOLOv5n person detector with pluggable inference backend."""

    def __init__(self, model_path: str, confidence_threshold: float = 0.6,
                 nms_threshold: float = 0.45, backend: str = "onnx",
                 input_size: int = 0):
        self._model_path = model_path
        self._conf_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._backend_name = backend
        self._input_size = input_size or int(os.environ.get("YOLO_INPUT_SIZE", DEFAULT_INPUT_SIZE))
        self._backend: _OnnxBackend | _TFLiteBackend | None = None

    def load(self) -> bool:
        """Load the model using the configured backend."""
        if not Path(self._model_path).exists():
            logger.error("Model file not found: %s", self._model_path)
            return False
        try:
            if self._backend_name == "tflite":
                self._backend = _TFLiteBackend()
            else:
                self._backend = _OnnxBackend()
            return self._backend.load(self._model_path)
        except Exception:
            logger.exception("Failed to load model with %s backend", self._backend_name)
            self._backend = None
            return False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run person detection on a frame.

        Args:
            frame: BGR image (any resolution, will be resized)

        Returns:
            List of Detection objects for persons found
        """
        if self._backend is None or not self._backend.is_loaded:
            return []

        orig_h, orig_w = frame.shape[:2]
        t0 = time.monotonic()

        # Pre-process: resize, normalize, transpose
        blob = self._preprocess(frame)

        # Inference
        output = self._backend.run(blob)

        # Post-process: filter person class, NMS, scale to original coords
        detections = self._postprocess(output, orig_w, orig_h)

        elapsed = (time.monotonic() - t0) * 1000
        if detections:
            logger.debug("YOLO: %d person(s) detected in %.0fms", len(detections), elapsed)

        return detections

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize, normalize, and prepare input tensor."""
        img = cv2.resize(frame, (self._input_size, self._input_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        if self._backend_name != "tflite":
            img = np.transpose(img, (2, 0, 1))  # HWC -> CHW (ONNX expects NCHW)
        img = np.expand_dims(img, axis=0)    # add batch dim
        return img.astype(self._backend.input_dtype)

    def _postprocess(self, output: np.ndarray, orig_w: int,
                     orig_h: int) -> list[Detection]:
        """Filter detections: person class only, confidence threshold, NMS.

        Handles two YOLOv5 output formats:
          - v5 classic: [1, N, 85] — x,y,w,h, obj_conf, 80 class scores
          - v5u (ultralytics): [1, 84, N] — x,y,w,h, 80 class scores (no obj_conf)
        """
        output = output.astype(np.float32)

        # Squeeze batch dim
        if output.ndim == 3:
            output = output[0]

        # Detect v5u format: shape [84, N] where 84 < N — transpose to [N, 84]
        if output.shape[0] < output.shape[1] and output.shape[0] in (84, 85):
            output = output.T

        num_attrs = output.shape[1]
        has_obj_conf = (num_attrs == 85)  # v5 classic has obj_conf, v5u does not

        boxes = []
        confidences = []

        for row in output:
            if has_obj_conf:
                # v5 classic: obj_conf * class_score
                obj_conf = row[4]
                if obj_conf < 0.3:
                    continue
                class_scores = row[5:]
                class_id = int(np.argmax(class_scores))
                if class_id != PERSON_CLASS_ID:
                    continue
                confidence = float(obj_conf * class_scores[class_id])
            else:
                # v5u: class scores directly (no obj_conf)
                class_scores = row[4:]
                class_id = int(np.argmax(class_scores))
                if class_id != PERSON_CLASS_ID:
                    continue
                confidence = float(class_scores[class_id])

            if confidence < self._conf_threshold:
                continue

            # Convert from center coords to top-left coords
            cx, cy, bw, bh = row[0], row[1], row[2], row[3]
            x = int((cx - bw / 2) * orig_w / self._input_size)
            y = int((cy - bh / 2) * orig_h / self._input_size)
            w = int(bw * orig_w / self._input_size)
            h = int(bh * orig_h / self._input_size)

            boxes.append([x, y, w, h])
            confidences.append(confidence)

        if not boxes:
            return []

        # Non-maximum suppression
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self._conf_threshold,
                                    self._nms_threshold)

        detections = []
        for i in indices:
            idx = int(i)
            bx, by, bw, bh = boxes[idx]
            detections.append(Detection(
                x=max(0, bx), y=max(0, by),
                w=bw, h=bh,
                confidence=confidences[idx],
            ))

        return detections

    @property
    def is_loaded(self) -> bool:
        return self._backend is not None and self._backend.is_loaded
