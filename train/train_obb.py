#Multi-GPU Training on YOLO
import comet_ml
import torch
import time
import logging
import psutil
import GPUtil
from tqdm import tqdm
from ultralytics import YOLO
import utils
import json
import omegaconf
import os

os.environ['COMET_EVAL_LOG_CONFUSION_MATRIX'] = 'true'


# Initialize Logging
logging.basicConfig(filename='training_log.log', level=logging.INFO)

comet_ml.init(project_name='Logo_exposure')

if torch.cuda.is_available():
    num_gpus = torch.cuda.device_count()
    print(f"CUDA is available with {num_gpus} GPU{'s' if num_gpus > 1 else ''}.")

    for i in range(torch.cuda.device_count()):
        GPU_name = print(f"Device {i}: {torch.cuda.get_device_name(i)}")
else:
    print("CUDA is not available.")


# Load hyperparameters from the JSON file
with open('/home/mehdihou/D1/YOLO-Train/Train/hyperparameters.json', 'r') as f:
    hyperparameters = json.load(f)

# Combine model paths and load flags into a single dictionary
models_to_load = {
    'YOLOv11m_obb': {'path': 'OBB/yolo11m-obb.pt', 'load': True},
    'YOLOv11l_obb': {'path': 'OBB/yolo11l-obb.pt', 'load': False},
    'YOLOv8m_obb': {'path': 'OBB/yolov8m-obb.pt', 'load': False},
}

# Find the model to load
selected_model_path = next((model['path'] for model in models_to_load.values() if model['load']), None)

# Check if a model was found
if selected_model_path:
    logging.info(f"Loading model from: {selected_model_path}")
    print(f"Loading model from: {selected_model_path}")
    model = YOLO(selected_model_path)
    model.info()

    start_time = time.time()

    # Check CPU and GPU usage
    cpu_usage = psutil.cpu_percent()
    gpu_usage = GPUtil.getGPUs()[0].load
    logging.info(f"Trinining will be started with {GPU_name} ")

    
    # Train the model using hyperparameters from the JSON file
    results = model.train(**hyperparameters)
    
    end_time = time.time()
    execution_time_minutes = (end_time - start_time) / 60
    logging.info(f"Training completed in {execution_time_minutes:.2f} minutes.")

else:
    print("No model selected!")




