"""
Video analytics module for extracting quantitative visual metrics from ads.

Provides three analysis layers:
1. Visual Physics - cuts, motion, brightness metrics
2. Spatial Telemetry - bounding boxes, screen coverage
3. Color Psychology - hex codes, ratios, contrast

These metrics enable precise replication of ad styles and "vibe search" features.
"""

from __future__ import annotations

import colorsys
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Optional imports with graceful fallback
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore
    PIL_AVAILABLE = False

try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    KMeans = None  # type: ignore
    SKLEARN_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO = None  # type: ignore
    YOLO_AVAILABLE = False

from .visual_analysis import FrameSample

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Visual Physics Analysis (OpenCV)
# ---------------------------------------------------------------------------

def analyse_visual_physics(
    video_path: str,
    storyboard_shots: List[dict],
    duration_seconds: Optional[float] = None,
    optical_flow_sample_rate: int = 5,
) -> dict:
    """
    Calculate mathematical density metrics from video.
    
    Args:
        video_path: Path to video file
        storyboard_shots: List of shot dicts from storyboard analysis
        duration_seconds: Video duration (if known)
        optical_flow_sample_rate: Sample every Nth frame for optical flow
    
    Returns:
        {
            "cuts_per_minute": 48.0,
            "average_shot_duration_s": 1.35,
            "optical_flow_score": 0.85,  # 0-1, frame-to-frame motion
            "motion_vector_direction": "chaotic",  # horizontal|vertical|chaotic|static
            "brightness_variance": 0.9,  # Strobe/flash effect measure
            "total_cuts": 24,
            "duration_seconds": 30.0
        }
    """
    result = _empty_visual_physics_result()
    
    # Calculate cut metrics from storyboard data (works even without video file)
    total_cuts = len(storyboard_shots)
    result["total_cuts"] = total_cuts
    
    if duration_seconds and duration_seconds > 0:
        result["duration_seconds"] = round(duration_seconds, 2)
        if total_cuts > 0:
            result["cuts_per_minute"] = round((total_cuts / duration_seconds) * 60, 1)
            result["average_shot_duration_s"] = round(duration_seconds / total_cuts, 2)
    
    # For optical flow and brightness analysis, we need OpenCV and the video file
    if not CV2_AVAILABLE:
        logger.debug("OpenCV not available, skipping optical flow/brightness analysis")
        return result
    
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        logger.debug("Video file not found: %s (cut metrics still calculated)", video_path)
        return result
    
    # Open video
    cap = cv2.VideoCapture(str(video_path_obj))
    if not cap.isOpened():
        logger.warning("Could not open video: %s", video_path)
        return result
    
    try:
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = duration_seconds or (frame_count / fps if fps > 0 else 0)
        
        # Update duration if not provided
        if not duration_seconds:
            result["duration_seconds"] = round(video_duration, 2)
            if total_cuts > 0 and video_duration > 0:
                result["cuts_per_minute"] = round((total_cuts / video_duration) * 60, 1)
                result["average_shot_duration_s"] = round(video_duration / total_cuts, 2)
        
        # Calculate optical flow and brightness metrics
        optical_flow_scores = []
        flow_x_magnitudes = []
        flow_y_magnitudes = []
        brightness_values = []
        
        prev_gray = None
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness (mean luminance)
            brightness_values.append(float(np.mean(gray)) / 255.0)
            
            # Calculate optical flow every Nth frame
            if frame_idx % optical_flow_sample_rate == 0 and prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                )
                
                # Calculate magnitude and direction
                mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                mean_mag = float(np.mean(mag))
                optical_flow_scores.append(mean_mag)
                
                # Track x and y components for direction analysis
                flow_x_magnitudes.append(float(np.mean(np.abs(flow[..., 0]))))
                flow_y_magnitudes.append(float(np.mean(np.abs(flow[..., 1]))))
            
            if frame_idx % optical_flow_sample_rate == 0:
                prev_gray = gray.copy()
            
            frame_idx += 1
        
        # Calculate optical flow score (normalized 0-1)
        if optical_flow_scores:
            # Normalize: typical range is 0-20, cap at 10 for score calculation
            mean_flow = np.mean(optical_flow_scores)
            result["optical_flow_score"] = round(min(mean_flow / 10.0, 1.0), 2)
        
        # Determine motion direction
        if flow_x_magnitudes and flow_y_magnitudes:
            avg_x = np.mean(flow_x_magnitudes)
            avg_y = np.mean(flow_y_magnitudes)
            
            if avg_x < 0.5 and avg_y < 0.5:
                result["motion_vector_direction"] = "static"
            elif avg_x > avg_y * 1.5:
                result["motion_vector_direction"] = "horizontal"
            elif avg_y > avg_x * 1.5:
                result["motion_vector_direction"] = "vertical"
            else:
                result["motion_vector_direction"] = "chaotic"
        
        # Calculate brightness variance (strobe effect)
        if brightness_values:
            brightness_std = float(np.std(brightness_values))
            # Normalize: typical range 0-0.3, higher = more strobe effect
            result["brightness_variance"] = round(min(brightness_std / 0.3, 1.0), 2)
        
    finally:
        cap.release()
    
    logger.debug(
        "Visual physics: cuts/min=%.1f, flow=%.2f, direction=%s, brightness_var=%.2f",
        result["cuts_per_minute"],
        result["optical_flow_score"],
        result["motion_vector_direction"],
        result["brightness_variance"]
    )
    
    return result


def _empty_visual_physics_result() -> dict:
    """Return empty visual physics result structure."""
    return {
        "cuts_per_minute": 0.0,
        "average_shot_duration_s": 0.0,
        "optical_flow_score": 0.0,
        "motion_vector_direction": "static",
        "brightness_variance": 0.0,
        "total_cuts": 0,
        "duration_seconds": 0.0,
    }


# ---------------------------------------------------------------------------
# Spatial Telemetry Analysis (YOLO)
# ---------------------------------------------------------------------------

# YOLO class names for reference
YOLO_PERSON_CLASS = 0
YOLO_CAR_CLASS = 2
YOLO_PHONE_CLASS = 67  # cell phone
YOLO_TV_CLASS = 62
YOLO_LAPTOP_CLASS = 63

# Classes we're interested in for ad analysis
TRACKED_CLASSES = {
    "person": 0,
    "car": 2,
    "motorcycle": 3,
    "bus": 5,
    "truck": 7,
    "dog": 16,
    "cat": 15,
    "bottle": 39,
    "cup": 41,
    "phone": 67,
    "laptop": 63,
    "tv": 62,
    "remote": 65,
}


def analyse_spatial_telemetry(
    video_path: str,
    frame_samples: Sequence[FrameSample],
    brand_keywords: Optional[List[str]] = None,
    yolo_model: str = "yolov8n.pt",
) -> dict:
    """
    Detect objects with bounding boxes and calculate screen coverage.
    
    Args:
        video_path: Path to video file
        frame_samples: List of FrameSample objects with frame paths
        brand_keywords: Optional brand names for logo detection
        yolo_model: YOLO model to use (yolov8n.pt, yolov8s.pt, yolov8m.pt)
    
    Returns:
        {
            "brand_prominence": {
                "total_screen_coverage_pct": 12.5,
                "center_gravity_dist": 0.2,
                "logo_positions": [[0.8, 0.8]],
                "logo_sizes": [0.05]
            },
            "face_prominence": {
                "max_face_size_pct": 0.4,
                "eye_contact_duration_s": 0.0,
                "face_positions": [[0.5, 0.3]],
                "face_count_max": 3
            },
            "object_heatmap": {
                "person": [[0.5, 0.5, 0.3, 0.6]],
                "car": [],
                "phone": [[0.7, 0.4, 0.1, 0.15]]
            }
        }
    """
    result = _empty_spatial_telemetry_result()
    
    if not YOLO_AVAILABLE:
        logger.warning("Ultralytics YOLO not available, skipping spatial telemetry")
        return result
    
    if not frame_samples:
        logger.warning("No frame samples provided for spatial telemetry")
        return result
    
    try:
        # Load YOLO model
        model = YOLO(yolo_model)
        logger.debug("Loaded YOLO model: %s", yolo_model)
    except Exception as e:
        logger.warning("Failed to load YOLO model %s: %s", yolo_model, str(e)[:100])
        return result
    
    # Track detections across frames
    all_person_boxes: List[List[float]] = []
    all_object_boxes: Dict[str, List[List[float]]] = {cls: [] for cls in TRACKED_CLASSES}
    max_face_size = 0.0
    max_face_count = 0
    
    for sample in frame_samples:
        if not sample.frame_path.exists():
            continue
        
        try:
            # Run YOLO detection
            results = model(str(sample.frame_path), verbose=False)
            
            if not results or len(results) == 0:
                continue
            
            result_obj = results[0]
            boxes = result_obj.boxes
            
            if boxes is None:
                continue
            
            # Get image dimensions for normalization
            img_height, img_width = result_obj.orig_shape[:2]
            
            person_count = 0
            
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                if conf < 0.3:  # Confidence threshold
                    continue
                
                # Get normalized bounding box [x_center, y_center, width, height]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x_center = (x1 + x2) / 2 / img_width
                y_center = (y1 + y2) / 2 / img_height
                width = (x2 - x1) / img_width
                height = (y2 - y1) / img_height
                
                bbox_normalized = [
                    round(x_center, 3),
                    round(y_center, 3),
                    round(width, 3),
                    round(height, 3)
                ]
                
                # Track by class
                for cls_name, cls_idx in TRACKED_CLASSES.items():
                    if cls_id == cls_idx:
                        all_object_boxes[cls_name].append(bbox_normalized)
                        
                        if cls_name == "person":
                            person_count += 1
                            all_person_boxes.append(bbox_normalized)
                            
                            # Track face size (using person box as proxy)
                            face_size = width * height
                            if face_size > max_face_size:
                                max_face_size = face_size
                        break
            
            if person_count > max_face_count:
                max_face_count = person_count
                
        except Exception as e:
            logger.debug("YOLO detection failed for frame: %s", str(e)[:100])
            continue
    
    # Calculate face prominence
    if all_person_boxes:
        result["face_prominence"]["max_face_size_pct"] = round(max_face_size * 100, 1)
        result["face_prominence"]["face_count_max"] = max_face_count
        
        # Get unique positions (deduplicate similar positions)
        unique_positions = _deduplicate_positions(all_person_boxes)
        result["face_prominence"]["face_positions"] = unique_positions[:10]  # Limit to 10
    
    # Build object heatmap
    for cls_name, boxes in all_object_boxes.items():
        if boxes:
            unique_boxes = _deduplicate_positions(boxes)
            result["object_heatmap"][cls_name] = unique_boxes[:20]  # Limit to 20
    
    # Note: Brand/logo detection would require a custom model or OCR
    # For now, we leave brand_prominence with defaults
    # Future: Could use Gemini OCR results to estimate logo positions
    
    logger.debug(
        "Spatial telemetry: face_max=%.1f%%, face_count=%d, persons=%d, objects=%d",
        result["face_prominence"]["max_face_size_pct"],
        result["face_prominence"]["face_count_max"],
        len(all_person_boxes),
        sum(len(v) for v in all_object_boxes.values())
    )
    
    return result


def _deduplicate_positions(
    boxes: List[List[float]], 
    threshold: float = 0.1
) -> List[List[float]]:
    """Remove duplicate bounding boxes that are too similar."""
    if not boxes:
        return []
    
    unique = [boxes[0]]
    for box in boxes[1:]:
        is_duplicate = False
        for existing in unique:
            # Check if centers are close
            dist = math.sqrt(
                (box[0] - existing[0]) ** 2 + 
                (box[1] - existing[1]) ** 2
            )
            if dist < threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(box)
    
    return unique


def _empty_spatial_telemetry_result() -> dict:
    """Return empty spatial telemetry result structure."""
    return {
        "brand_prominence": {
            "total_screen_coverage_pct": 0.0,
            "center_gravity_dist": 0.5,
            "logo_positions": [],
            "logo_sizes": [],
        },
        "face_prominence": {
            "max_face_size_pct": 0.0,
            "eye_contact_duration_s": 0.0,
            "face_positions": [],
            "face_count_max": 0,
        },
        "object_heatmap": {cls: [] for cls in TRACKED_CLASSES},
    }


# ---------------------------------------------------------------------------
# Color Psychology Analysis (Pillow + K-means)
# ---------------------------------------------------------------------------

# Color name mapping based on hue ranges
COLOR_NAMES = {
    (0, 15): "Red",
    (15, 45): "Orange",
    (45, 75): "Yellow",
    (75, 150): "Green",
    (150, 210): "Cyan",
    (210, 270): "Blue",
    (270, 330): "Purple",
    (330, 360): "Red",
}


def analyse_color_psychology(
    video_path: str,
    frame_samples: Sequence[FrameSample],
    n_colors: int = 5,
) -> dict:
    """
    Extract dominant colors with hex codes and ratios.
    
    Args:
        video_path: Path to video file (unused, uses frame_samples)
        frame_samples: List of FrameSample objects with frame paths
        n_colors: Number of dominant colors to extract
    
    Returns:
        {
            "dominant_hex": ["#FF4500", "#00FFFF", "#000000"],
            "ratios": [0.3, 0.2, 0.5],
            "contrast_ratio": 21.0,
            "saturation_mean": 0.8,
            "brightness_mean": 0.4,
            "color_temperature": "warm",
            "color_names": ["Orange Red", "Cyan", "Black"]
        }
    """
    result = _empty_color_psychology_result()
    
    if not PIL_AVAILABLE or not SKLEARN_AVAILABLE:
        logger.warning("Pillow or scikit-learn not available, skipping color analysis")
        return result
    
    if not frame_samples:
        logger.warning("No frame samples provided for color analysis")
        return result
    
    # Collect pixels from all frames
    all_pixels = []
    
    for sample in frame_samples:
        if not sample.frame_path.exists():
            continue
        
        try:
            # Load and resize image for speed
            img = Image.open(sample.frame_path).convert("RGB")
            img_small = img.resize((100, 100), Image.Resampling.LANCZOS)
            
            # Get pixels as numpy array
            pixels = np.array(img_small).reshape(-1, 3)
            all_pixels.append(pixels)
            
        except Exception as e:
            logger.debug("Failed to load frame for color analysis: %s", str(e)[:100])
            continue
    
    if not all_pixels:
        return result
    
    # Combine all pixels
    combined_pixels = np.vstack(all_pixels)
    
    # Run K-means clustering
    try:
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(combined_pixels)
        
        # Get cluster centers (dominant colors)
        centers = kmeans.cluster_centers_.astype(int)
        
        # Calculate ratios based on cluster sizes
        labels = kmeans.labels_
        unique, counts = np.unique(labels, return_counts=True)
        total = len(labels)
        
        # Sort by frequency
        sorted_indices = np.argsort(-counts)
        
        dominant_hex = []
        ratios = []
        color_names = []
        saturations = []
        brightnesses = []
        
        for idx in sorted_indices:
            r, g, b = centers[idx]
            
            # Convert to hex
            hex_code = f"#{r:02X}{g:02X}{b:02X}"
            dominant_hex.append(hex_code)
            
            # Calculate ratio
            ratio = round(counts[idx] / total, 2)
            ratios.append(ratio)
            
            # Get color name
            color_name = _get_color_name(r, g, b)
            color_names.append(color_name)
            
            # Calculate HSV values
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            saturations.append(s)
            brightnesses.append(v)
        
        result["dominant_hex"] = dominant_hex
        result["ratios"] = ratios
        result["color_names"] = color_names
        
        # Calculate mean saturation and brightness
        result["saturation_mean"] = round(np.mean(saturations), 2)
        result["brightness_mean"] = round(np.mean(brightnesses), 2)
        
        # Calculate contrast ratio (WCAG formula between lightest and darkest)
        if len(centers) >= 2:
            luminances = [_relative_luminance(c[0], c[1], c[2]) for c in centers]
            max_lum = max(luminances)
            min_lum = min(luminances)
            contrast = (max_lum + 0.05) / (min_lum + 0.05)
            result["contrast_ratio"] = round(contrast, 1)
        
        # Determine color temperature
        result["color_temperature"] = _get_color_temperature(centers, counts)
        
    except Exception as e:
        logger.warning("K-means clustering failed: %s", str(e)[:100])
        return result
    
    logger.debug(
        "Color psychology: %d colors, contrast=%.1f, temp=%s, sat=%.2f",
        len(dominant_hex),
        result["contrast_ratio"],
        result["color_temperature"],
        result["saturation_mean"]
    )
    
    return result


def _get_color_name(r: int, g: int, b: int) -> str:
    """Get approximate color name from RGB values."""
    # Handle near-black and near-white
    if r < 30 and g < 30 and b < 30:
        return "Black"
    if r > 225 and g > 225 and b > 225:
        return "White"
    if abs(r - g) < 20 and abs(g - b) < 20 and abs(r - b) < 20:
        if r < 100:
            return "Dark Gray"
        elif r > 180:
            return "Light Gray"
        else:
            return "Gray"
    
    # Convert to HSV for hue-based naming
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue_degrees = h * 360
    
    # Low saturation = grayish
    if s < 0.2:
        return "Gray"
    
    # Find color name based on hue
    for (low, high), name in COLOR_NAMES.items():
        if low <= hue_degrees < high:
            # Add modifiers
            if v < 0.3:
                return f"Dark {name}"
            elif v > 0.8 and s > 0.5:
                return f"Bright {name}"
            return name
    
    return "Unknown"


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance for WCAG contrast ratio."""
    def adjust(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def _get_color_temperature(centers: np.ndarray, counts: np.ndarray) -> str:
    """Determine overall color temperature (warm/cool/neutral)."""
    warm_weight = 0.0
    cool_weight = 0.0
    total = np.sum(counts)
    
    for i, (r, g, b) in enumerate(centers):
        weight = counts[i] / total
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hue_degrees = h * 360
        
        # Skip very desaturated colors
        if s < 0.1:
            continue
        
        # Warm: red, orange, yellow (0-60, 330-360)
        if hue_degrees < 60 or hue_degrees > 330:
            warm_weight += weight * s
        # Cool: cyan, blue, purple (180-300)
        elif 180 <= hue_degrees <= 300:
            cool_weight += weight * s
    
    if warm_weight > cool_weight * 1.5:
        return "warm"
    elif cool_weight > warm_weight * 1.5:
        return "cool"
    else:
        return "neutral"


def _empty_color_psychology_result() -> dict:
    """Return empty color psychology result structure."""
    return {
        "dominant_hex": [],
        "ratios": [],
        "contrast_ratio": 1.0,
        "saturation_mean": 0.0,
        "brightness_mean": 0.5,
        "color_temperature": "neutral",
        "color_names": [],
    }


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "analyse_visual_physics",
    "analyse_spatial_telemetry",
    "analyse_color_psychology",
    "CV2_AVAILABLE",
    "YOLO_AVAILABLE",
    "PIL_AVAILABLE",
    "SKLEARN_AVAILABLE",
]

