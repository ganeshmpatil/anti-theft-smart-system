#!/bin/bash
# Download YOLOv5n ONNX model for the Anti-Theft Smart System
#
# This downloads the official ultralytics YOLOv5n model exported to ONNX format.
# Model size: ~3.9 MB
# Classes: 80 (COCO) — we only use class 0 (person)

set -e

MODEL_DIR="models"
MODEL_FILE="$MODEL_DIR/yolov5n.onnx"

if [ -f "$MODEL_FILE" ]; then
    echo "Model already exists at $MODEL_FILE"
    exit 0
fi

mkdir -p "$MODEL_DIR"

echo "Downloading YOLOv5n ONNX model..."

# Method 1: Download from ultralytics GitHub releases
YOLO_URL="https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx"
if command -v wget &> /dev/null; then
    wget -q --show-progress -O "$MODEL_FILE" "$YOLO_URL"
elif command -v curl &> /dev/null; then
    curl -L -o "$MODEL_FILE" "$YOLO_URL"
else
    echo "Error: wget or curl is required to download the model"
    exit 1
fi

echo "Model downloaded to $MODEL_FILE"
echo "Size: $(du -h "$MODEL_FILE" | cut -f1)"
