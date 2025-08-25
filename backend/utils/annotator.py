import cv2
import numpy as np

class FrameAnnotator:
    def __init__(self, class_names, color_palette):
        self.class_names = class_names
        self.color_palette = color_palette

    def annotate_frame(self, frame, results):
        """Annotate a frame with detection results."""
        if results is None:
            return frame
        
        frame = frame.copy()
        for result in results:
            obb = result.obb
            if obb is None:
                continue
            
            for i in range(len(obb.conf)):
                conf = float(obb.conf[i])
                cls = int(obb.cls[i])
                class_name = self.class_names[cls]
                label = f'{class_name}: {conf:.2f}'
                
                if hasattr(obb, 'xyxyxyxy'):
                    polygon = obb.xyxyxyxy[i]
                    if hasattr(polygon, 'cpu'):
                        polygon = polygon.cpu().numpy()
                    
                    points = polygon.reshape(4, 2)
                    is_normalized = np.all(points <= 1.0)
                    
                    if is_normalized:
                        points[:, 0] *= frame.shape[1]
                        points[:, 1] *= frame.shape[0]
                    else:
                        if np.max(points) > max(frame.shape):
                            scale_factor = min(frame.shape[1] / np.max(points[:, 0]), 
                                              frame.shape[0] / np.max(points[:, 1]))
                            points = points * scale_factor
                    
                    points = points.astype(np.int32)
                    x_center = int(points[:, 0].mean())
                    y_center = int(points[:, 1].mean())
                    color = self.color_palette[cls % len(self.color_palette)]
                    
                    cv2.drawContours(frame, [points], 0, color, 2)
                    
                    (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    text_x = max(0, x_center - text_width // 2)
                    text_y = max(0, y_center - text_height - baseline - 5)
                    
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (text_x, text_y), (text_x + text_width, text_y + text_height + baseline), color, thickness=cv2.FILLED)
                    alpha = 0.6
                    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                    cv2.putText(frame, label, (text_x, text_y + text_height), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return frame
