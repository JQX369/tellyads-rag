"""
Physics Engine - Production-grade video analytics extraction.

Extracts objective mathematical metrics from video advertisements:
- Visual Physics: Scene detection, cuts/minute, motion energy, brightness variance
- Audio Physics: BPM, loudness
- Object Detection: YOLO inference on keyframes
- Color Analysis: K-means dominant colors

Memory-safe: Processes frame-by-frame, never loads full video into RAM.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None  # type: ignore
    LIBROSA_AVAILABLE = False

logger = logging.getLogger(__name__)

PHYSICS_VERSION = "1.0"


class PhysicsExtractor:
    """
    Production-grade video physics extraction.
    
    Extracts objective metrics from video files:
    - Scene boundaries via frame histogram differencing
    - Cuts per minute, motion energy, brightness variance
    - Keyframe extraction at scene midpoints
    - Dominant colors via K-means clustering
    - Object detection via YOLOv8 (keyframes only)
    - Audio analysis: BPM and loudness
    
    Memory-safe: Processes frame-by-frame using cv2.VideoCapture.
    """
    
    def __init__(
        self,
        video_path: str,
        output_dir: str,
        ad_id: Optional[str] = None,
        yolo_model: str = "yolov8n.pt",
        scene_threshold: float = 30.0,
        motion_sample_rate: int = 5,
        keyframe_height: int = 640,
        color_clusters: int = 3,
        upload_to_s3: bool = False,
        cleanup_local: bool = True,
    ):
        """
        Initialize the PhysicsExtractor.
        
        Args:
            video_path: Path to input video file
            output_dir: Directory to save keyframe images
            ad_id: Ad identifier (used for S3 key construction)
            yolo_model: YOLO model name (default: yolov8n.pt for speed)
            scene_threshold: Histogram difference threshold for scene detection
            motion_sample_rate: Sample every Nth frame for optical flow
            keyframe_height: Height to resize keyframes (aspect ratio preserved)
            color_clusters: Number of dominant colors to extract (K-means k)
            upload_to_s3: If True, upload keyframes to S3 and return URLs
            cleanup_local: If True and upload_to_s3=True, delete local files after upload
        """
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.ad_id = ad_id or self.video_path.stem
        self.yolo_model_name = yolo_model
        self.scene_threshold = scene_threshold
        self.motion_sample_rate = motion_sample_rate
        self.keyframe_height = keyframe_height
        self.color_clusters = color_clusters
        self.upload_to_s3 = upload_to_s3
        self.cleanup_local = cleanup_local
        
        # Lazy-loaded resources
        self._yolo_model = None
        self._storage_manager = None
        self._video_id = self.video_path.stem
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def yolo_model(self):
        """Lazy-load YOLO model on first use."""
        if self._yolo_model is None and YOLO_AVAILABLE:
            try:
                self._yolo_model = YOLO(self.yolo_model_name)
                logger.debug("Loaded YOLO model: %s", self.yolo_model_name)
            except Exception as e:
                logger.warning("Failed to load YOLO model: %s", str(e)[:100])
        return self._yolo_model
    
    @property
    def storage_manager(self):
        """Lazy-load StorageManager on first use (only if upload_to_s3=True)."""
        if self._storage_manager is None and self.upload_to_s3:
            try:
                from .storage_manager import StorageManager
                self._storage_manager = StorageManager()
                logger.debug("Initialized StorageManager for S3 uploads")
            except Exception as e:
                logger.warning("Failed to initialize StorageManager: %s", str(e)[:100])
                self.upload_to_s3 = False  # Disable S3 upload on failure
        return self._storage_manager
    
    def extract(self) -> dict:
        """
        Main entry point - extract all physics metrics from video.
        
        Returns:
            Dictionary containing all physics data in standardized format.
        """
        result = self._empty_result()
        
        if not CV2_AVAILABLE:
            logger.error("OpenCV not available, cannot extract physics")
            return result
        
        if not self.video_path.exists():
            logger.error("Video file not found: %s", self.video_path)
            return result
        
        # Open video
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            logger.error("Could not open video: %s", self.video_path)
            return result
        
        try:
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.debug(
                "Video: %.1fs, %d frames, %.1f fps, %dx%d",
                duration, frame_count, fps, width, height
            )
            
            result["visual_physics"]["duration"] = round(duration, 2)
            
            # Stage 1: Detect scenes and collect metrics
            scenes, brightness_values, motion_scores = self._process_video_frames(
                cap, fps, frame_count
            )
            
            # Stage 2: Calculate visual metrics
            cut_count = len(scenes)
            result["visual_physics"]["cut_count"] = cut_count
            
            if duration > 0 and cut_count > 0:
                result["visual_physics"]["cuts_per_minute"] = round(
                    (cut_count / duration) * 60, 1
                )
            
            if brightness_values:
                result["visual_physics"]["brightness_variance"] = round(
                    float(np.std(brightness_values)), 2
                )
            
            if motion_scores:
                # Normalize motion score to 0-1 range
                mean_motion = float(np.mean(motion_scores))
                motion_score = round(min(mean_motion / 10.0, 1.0), 2)
                result["visual_physics"]["motion_energy_score"] = motion_score
                result["visual_physics"]["optical_flow_score"] = motion_score  # Alias
            
            # Store scene boundaries for analysis
            result["visual_physics"]["scenes"] = [
                {"start": s[0], "end": s[1]} for s in scenes
            ]
            
            # Stage 3: Extract keyframes at scene midpoints
            keyframes_saved, dominant_colors = self._extract_keyframes(
                cap, scenes, fps
            )
            result["keyframes_saved"] = keyframes_saved
            result["visual_physics"]["dominant_colors"] = dominant_colors
            
            # Stage 4: Run YOLO on keyframes
            objects_detected, spatial_data = self._run_yolo_on_keyframes(keyframes_saved)
            result["objects_detected"] = objects_detected
            result["spatial_data"] = spatial_data
            
        finally:
            cap.release()
        
        # Stage 5: Extract audio metrics (separate try block)
        audio_physics = self._extract_audio_metrics()
        result["audio_physics"] = audio_physics
        
        # Stage 6: Upload keyframes to S3 (optional)
        if self.upload_to_s3 and keyframes_saved:
            keyframe_urls = self._upload_keyframes_to_s3(keyframes_saved)
            result["keyframes_urls"] = keyframe_urls
            
            # Cleanup local files if requested
            if self.cleanup_local:
                for local_path in keyframes_saved:
                    try:
                        os.remove(local_path)
                    except OSError:
                        pass
        
        return result
    
    def _upload_keyframes_to_s3(self, keyframes_saved: List[str]) -> List[str]:
        """
        Upload extracted keyframes to S3/R2.
        
        Args:
            keyframes_saved: List of local keyframe paths
        
        Returns:
            List of public URLs for uploaded frames
        """
        if not self.storage_manager:
            logger.warning("StorageManager not available, skipping S3 upload")
            return keyframes_saved  # Return local paths as fallback
        
        frame_urls = []
        
        for i, local_path in enumerate(keyframes_saved):
            try:
                url = self.storage_manager.upload_frame(local_path, self.ad_id, i)
                frame_urls.append(url)
                logger.debug("Uploaded frame %d: %s", i, url)
            except Exception as e:
                logger.warning("Failed to upload frame %d: %s", i, str(e)[:100])
                frame_urls.append(local_path)  # Keep local path as fallback
        
        logger.info(
            "Uploaded %d/%d keyframes to S3 for ad %s",
            len([u for u in frame_urls if u.startswith("http")]),
            len(keyframes_saved),
            self.ad_id
        )
        
        return frame_urls
    
    def _process_video_frames(
        self,
        cap,
        fps: float,
        frame_count: int,
    ) -> Tuple[List[Tuple[int, int]], List[float], List[float]]:
        """
        Process video frame-by-frame to detect scenes and collect metrics.
        
        Memory-safe: Only keeps one frame in memory at a time.
        
        Returns:
            (scenes, brightness_values, motion_scores)
        """
        scenes: List[Tuple[int, int]] = []
        brightness_values: List[float] = []
        motion_scores: List[float] = []
        
        prev_hist = None
        prev_gray = None
        scene_start = 0
        frame_idx = 0
        
        # Reset to beginning
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness (mean luminance)
            brightness_values.append(float(np.mean(gray)))
            
            # Calculate histogram for scene detection
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            
            # Scene detection via histogram comparison
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                # Bhattacharyya distance: 0 = identical, 1 = completely different
                # Scale to match threshold (typical values 0-0.5 become 0-50)
                diff_scaled = diff * 100
                
                if diff_scaled > self.scene_threshold:
                    # Scene cut detected
                    scenes.append((scene_start, frame_idx - 1))
                    scene_start = frame_idx
            
            # Optical flow for motion energy (sample every Nth frame)
            if frame_idx % self.motion_sample_rate == 0 and prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_scores.append(float(np.mean(mag)))
            
            # Store for next iteration
            prev_hist = hist
            if frame_idx % self.motion_sample_rate == 0:
                prev_gray = gray.copy()
            
            frame_idx += 1
        
        # Add final scene
        if scene_start < frame_count - 1:
            scenes.append((scene_start, frame_count - 1))
        
        # If no scenes detected (very static video), create one scene for whole video
        if not scenes:
            scenes.append((0, frame_count - 1))
        
        logger.debug(
            "Detected %d scenes, %d brightness samples, %d motion samples",
            len(scenes), len(brightness_values), len(motion_scores)
        )
        
        return scenes, brightness_values, motion_scores
    
    def _extract_keyframes(
        self,
        cap,
        scenes: List[Tuple[int, int]],
        fps: float,
    ) -> Tuple[List[str], List[str]]:
        """
        Extract keyframe at midpoint of each scene.
        
        Returns:
            (list of saved keyframe paths, list of dominant colors as hex)
        """
        keyframes_saved: List[str] = []
        all_colors: List[List[int]] = []  # Collect colors from all keyframes
        
        for i, (start_frame, end_frame) in enumerate(scenes):
            # Get middle frame of scene
            mid_frame = (start_frame + end_frame) // 2
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Resize to target height (maintain aspect ratio)
            h, w = frame.shape[:2]
            if h != self.keyframe_height:
                scale = self.keyframe_height / h
                new_w = int(w * scale)
                frame = cv2.resize(frame, (new_w, self.keyframe_height))
            
            # Save keyframe
            keyframe_path = self.output_dir / f"{self._video_id}_scene_{i}.jpg"
            cv2.imwrite(str(keyframe_path), frame)
            keyframes_saved.append(str(keyframe_path))
            
            # Extract colors from this keyframe
            colors = self._extract_colors_from_frame(frame)
            all_colors.extend(colors)
        
        # Get dominant colors across all keyframes
        dominant_colors = self._get_dominant_colors(all_colors)
        
        logger.debug(
            "Extracted %d keyframes, dominant colors: %s",
            len(keyframes_saved), dominant_colors
        )
        
        return keyframes_saved, dominant_colors
    
    def _extract_colors_from_frame(self, frame: np.ndarray) -> List[List[int]]:
        """Extract pixel colors from frame for clustering."""
        # Resize to small size for speed
        small = cv2.resize(frame, (100, 100))
        # Convert BGR to RGB
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        # Flatten to list of pixels
        pixels = rgb.reshape(-1, 3).tolist()
        return pixels
    
    def _get_dominant_colors(
        self,
        all_colors: List[List[int]],
    ) -> List[str]:
        """Use K-means to find dominant colors and return as hex codes."""
        if not SKLEARN_AVAILABLE or not all_colors:
            return []
        
        try:
            # Convert to numpy array
            pixels = np.array(all_colors, dtype=np.float32)
            
            # K-means clustering
            k = min(self.color_clusters, len(pixels))
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # Get cluster centers (dominant colors)
            centers = kmeans.cluster_centers_.astype(int)
            
            # Sort by cluster size (most dominant first)
            labels = kmeans.labels_
            unique, counts = np.unique(labels, return_counts=True)
            sorted_indices = np.argsort(-counts)
            
            # Convert to hex
            hex_colors = []
            for idx in sorted_indices:
                r, g, b = centers[idx]
                hex_code = f"#{r:02X}{g:02X}{b:02X}"
                hex_colors.append(hex_code)
            
            return hex_colors
            
        except Exception as e:
            logger.warning("K-means color extraction failed: %s", str(e)[:100])
            return []
    
    def _run_yolo_on_keyframes(
        self,
        keyframe_paths: List[str],
    ) -> Tuple[List[str], dict]:
        """
        Run YOLO inference on keyframes only (not every frame).
        
        Returns:
            (list of unique object names, spatial_data dict)
        """
        objects_detected: Dict[str, float] = {}  # class_name -> max_confidence
        max_box: Optional[List[float]] = None
        max_box_area = 0.0
        
        if not self.yolo_model or not keyframe_paths:
            return [], {"max_object_box": None}
        
        for keyframe_path in keyframe_paths:
            if not Path(keyframe_path).exists():
                continue
            
            try:
                results = self.yolo_model(keyframe_path, verbose=False)
                
                if not results or len(results) == 0:
                    continue
                
                result = results[0]
                boxes = result.boxes
                
                if boxes is None:
                    continue
                
                # Get image dimensions
                img_h, img_w = result.orig_shape[:2]
                
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = result.names[cls_id]
                    
                    # Track max confidence per class
                    if class_name not in objects_detected or conf > objects_detected[class_name]:
                        objects_detected[class_name] = conf
                    
                    # Track largest bounding box
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    w = (x2 - x1) / img_w
                    h = (y2 - y1) / img_h
                    area = w * h
                    
                    if area > max_box_area:
                        max_box_area = area
                        # Normalize to [x, y, w, h] format
                        max_box = [
                            round(x1 / img_w, 3),
                            round(y1 / img_h, 3),
                            round(w, 3),
                            round(h, 3),
                        ]
                        
            except Exception as e:
                logger.debug("YOLO inference failed on %s: %s", keyframe_path, str(e)[:100])
                continue
        
        # Return sorted list of object names (by confidence)
        sorted_objects = sorted(
            objects_detected.keys(),
            key=lambda x: objects_detected[x],
            reverse=True
        )
        
        spatial_data = {"max_object_box": max_box}
        
        logger.debug(
            "YOLO detected %d unique objects, max box area: %.2f",
            len(sorted_objects), max_box_area
        )
        
        return sorted_objects, spatial_data
    
    def _extract_audio_metrics(self) -> Optional[dict]:
        """
        Extract audio metrics using librosa.
        
        Returns None if audio extraction fails (e.g., silent video).
        """
        if not LIBROSA_AVAILABLE:
            logger.debug("Librosa not available, skipping audio metrics")
            return None
        
        # Extract audio to temp file using ffmpeg
        audio_path = None
        temp_dir = None
        
        try:
            temp_dir = tempfile.mkdtemp(prefix="physics_audio_")
            audio_path = Path(temp_dir) / "audio.wav"
            
            # Use ffmpeg to extract audio
            cmd = [
                "ffmpeg", "-y", "-i", str(self.video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
            )
            
            if result.returncode != 0 or not audio_path.exists():
                logger.debug("Audio extraction failed: no audio track or ffmpeg error")
                return None
            
            # Load audio with librosa
            y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
            
            if len(y) == 0:
                logger.debug("Audio track is empty")
                return None
            
            # Calculate tempo (BPM)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            # tempo can be a numpy array in newer versions
            if hasattr(tempo, '__iter__'):
                tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
            else:
                tempo = float(tempo)
            
            # Calculate loudness (RMS-based approximation)
            rms = librosa.feature.rms(y=y)[0]
            mean_rms = float(np.mean(rms))
            
            # Convert RMS to dB (approximate LUFS)
            if mean_rms > 0:
                loudness_db = 20 * np.log10(mean_rms)
            else:
                loudness_db = -60.0  # Silent
            
            audio_physics = {
                "tempo_bpm": round(tempo, 0),
                "bpm": round(tempo, 0),  # Alias
                "loudness_db": round(loudness_db, 1),
                "loudness_lu": round(loudness_db, 1),  # Alias (approx LUFS)
                "rms_db": round(loudness_db, 1),  # Legacy alias
            }
            
            logger.debug(
                "Audio metrics: BPM=%.0f, loudness=%.1f dB",
                tempo, loudness_db
            )
            
            return audio_physics
            
        except subprocess.TimeoutExpired:
            logger.warning("Audio extraction timed out")
            return None
        except Exception as e:
            logger.debug("Audio analysis failed: %s", str(e)[:100])
            return None
        finally:
            # Cleanup
            if audio_path and audio_path.exists():
                try:
                    audio_path.unlink()
                except:
                    pass
            if temp_dir:
                try:
                    Path(temp_dir).rmdir()
                except:
                    pass
    
    def _empty_result(self) -> dict:
        """Return empty result structure."""
        return {
            "physics_version": PHYSICS_VERSION,
            "visual_physics": {
                "duration": 0.0,
                "cut_count": 0,
                "cuts_per_minute": 0.0,
                "motion_energy_score": 0.0,
                "optical_flow_score": 0.0,  # Alias for motion_energy_score
                "brightness_variance": 0.0,
                "dominant_colors": [],
                "scenes": [],  # Scene boundaries [(start_frame, end_frame), ...]
            },
            "audio_physics": None,
            "objects_detected": [],
            "spatial_data": {
                "max_object_box": None,
            },
            "keyframes_saved": [],
        }


# ---------------------------------------------------------------------------
# Convenience function for pipeline integration
# ---------------------------------------------------------------------------

def extract_physics(
    video_path: str,
    output_dir: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Convenience function to extract physics from a video.
    
    Args:
        video_path: Path to video file
        output_dir: Directory for keyframes (default: temp directory)
        **kwargs: Additional arguments passed to PhysicsExtractor
    
    Returns:
        Physics data dictionary
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="physics_")
    
    extractor = PhysicsExtractor(video_path, output_dir, **kwargs)
    return extractor.extract()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "PhysicsExtractor",
    "extract_physics",
    "PHYSICS_VERSION",
    "CV2_AVAILABLE",
    "YOLO_AVAILABLE",
    "LIBROSA_AVAILABLE",
    "SKLEARN_AVAILABLE",
    "PIL_AVAILABLE",
]

