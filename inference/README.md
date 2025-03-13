# YOLO Inference Guide

This guide explains how to use the `inference.py` script to perform object detection on images and videos using a YOLO model.

## Prerequisites

- Python 3.x
- Required Python packages: `opencv-python`, `torch`, `ultralytics`, `numpy`
- A trained YOLO model (`best.pt` file) located in `../train-result/yolov11-m-finetuned/weights/`
- Class names file (`classes.txt`) in the same directory as `inference.py`

## Setup

1. Install the required Python packages:
   ```bash
   pip install opencv-python torch ultralytics numpy
   ```

2. Ensure the model weights and class names file are in the correct locations as specified above.

## Usage

Run the script with the following command:

```bash
python inference.py <mode> <path>
```

- `<mode>`: Specify `image` or `video` depending on the input type.
- `<path>`: Path to the image or video file. For video streams, provide the URL.

### Examples

- To process an image:
  ```bash
  python inference.py image path/to/image.jpg
  ```

- To process a video:
  ```bash
  python inference.py video path/to/video.mp4
  ```

- To process a video stream:
  ```bash
  python inference.py video http://example.com/stream.m3u8
  ```

## Output

- The annotated image will be saved as `output.jpg`.
- The annotated video will be saved as `output.mp4`.

## Example Detection

![Example Detection](example-detection1.gif)
