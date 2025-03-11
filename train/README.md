# SponsorSpotlight: Logo Detection Training

## Overview
This repository contains training code for oriented bounding box (OBB) logo detection using YOLO models. The system is designed to detect and localize brand logos in images with rotated bounding boxes for improved accuracy.

## Models
The training supports multiple YOLO models for oriented bounding box detection:
- YOLOv11m-obb (default)
- YOLOv11l-obb
- YOLOv8m-obb

## Training Setup

### Requirements
- PyTorch with CUDA support
- Ultralytics YOLO
- CometML for experiment tracking
- Additional dependencies: psutil, GPUtil, tqdm, omegaconf

### Dataset
The training uses a custom dataset with oriented bounding box annotations for logo detection, containing multiple brand logos across various categories.

### Hyperparameters
Key training parameters:
- Image size: 1280px
- Batch size: 50
- Epochs: 200
- Learning rate: 0.0001
- Patience: 50
- Multi-GPU training (devices 1-5)
- Data augmentation enabled

## Monitoring
- Training progress is logged to CometML under the "Logo_exposure" project
- Local logging to training_log.log
- Confusion matrix evaluation
- Performance metrics tracking

## Usage
To train the model:
```bash
python train/train_obb.py
```

The training will automatically select the model marked as 'load: True' in the configuration.

## Model Selection
Models can be configured in the training script by modifying the 'models_to_load' dictionary.
