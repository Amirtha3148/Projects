"""
Sensor Fusion Engine

STRATEGY:
1. PRIMARY: Laptop camera (MediaPipe face tracking) - used for ALL tracking
2. SECONDARY: Wearable camera (ArUco marker) - ONLY for:
   - Direction confirmation when ambiguous
   - Fallback when laptop camera loses tracking
"""

import numpy as np
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from tracking.kalman_filter import PoseKalmanFilter
from tracking.transform import CoordinateTransform
from detection.direction_detector import DirectionDetector, Direction


@dataclass
class FusedPose:
    """Represents the final fused pose output with direction."""
    position: np.ndarray
    rotation: np.ndarray
    position_unity: np.ndarray
    rotation_unity: np.ndarray
    confidence: float
    direction: str
    direction_confidence: float
    source: str  # 'laptop', 'wearable', or 'both'
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        # rotation_unity from transform.py is [pitch, yaw, roll] in degrees
        return {
            "x": float(self.position_unity[0]),
            "y": float(self.position_unity[1]),
            "z": float(self.position_unity[2]),
            "pitch": float(self.rotation_unity[0]),  # X rotation (look up/down)
            "yaw": float(self.rotation_unity[1]),    # Y rotation (turn left/right)
            "roll": float(self.rotation_unity[2]),   # Z rotation (tilt)
            "confidence": float(self.confidence),
            "direction": self.direction,
            "direction_confidence": float(self.direction_confidence),
            "source": self.source,
            "timestamp": self.timestamp
        }


class SensorFusionEngine:
    """
    Sensor fusion with LAPTOP CAMERA as PRIMARY source.
    
    Wearable camera is only used for:
    1. Direction confirmation when laptop confidence is low
    2. Fallback when laptop camera fails to detect face
    """
    
    def __init__(self, dt: float = 1.0 / 30.0):
        self.dt = dt
        self.kalman = PoseKalmanFilter(dt=dt)
        self.transform = CoordinateTransform()
        self.direction_detector = DirectionDetector()
        
        self._laptop_available = False
        self._wearable_available = False
        self._laptop_confidence = 0.0
        self._wearable_confidence = 0.0
        
        # Tracking state
        self._laptop_failure_frames = 0
        self._baseline_pending = True
        self._frames_since_start = 0
        self._last_fusion_time = time.time()
        
        # Direction confirmation from marker
        self._marker_direction_hint: Optional[str] = None
        
    def update(
        self,
        laptop_position: Optional[np.ndarray] = None,
        laptop_rotation: Optional[np.ndarray] = None,
        laptop_confidence: float = 0.0,
        wearable_position: Optional[np.ndarray] = None,
        wearable_rotation: Optional[np.ndarray] = None,
        wearable_confidence: float = 0.0,
        marker_quadrants: Optional[Dict[str, bool]] = None
    ) -> FusedPose:
        current_time = time.time()
        actual_dt = min(current_time - self._last_fusion_time, 0.1)
        self._last_fusion_time = current_time
        
        # Check availability
        self._laptop_available = laptop_position is not None and laptop_confidence > 0.1
        self._wearable_available = wearable_position is not None and wearable_confidence > 0.1
        self._laptop_confidence = laptop_confidence if self._laptop_available else 0.0
        self._wearable_confidence = wearable_confidence if self._wearable_available else 0.0
        
        # Store marker direction hint for confirmation
        if marker_quadrants:
            hint = self.direction_detector.detect_from_marker_visibility(marker_quadrants)
            if hint:
                self._marker_direction_hint = hint.value if isinstance(hint, Direction) else hint
        
        # === DECIDE TRACKING SOURCE ===
        position, rotation, source, confidence = self._select_tracking_source(
            laptop_position, laptop_rotation, laptop_confidence,
            wearable_position, wearable_rotation, wearable_confidence
        )
        
        # If no valid source, use Kalman prediction
        if position is None or rotation is None:
            position, rotation = self.kalman.get_pose()
            source = "prediction"
            confidence = 0.3
        
        # Kalman filtering
        if self.kalman.is_initialized:
            self.kalman.predict(dt=actual_dt)
        
        filtered_position, filtered_rotation = self.kalman.update(
            position, rotation, confidence
        )
        
        # Update baseline
        self._update_baseline(filtered_position, filtered_rotation)
        
        # Transform to Unity coordinates
        unity_position, unity_rotation = self.transform.full_transform(
            filtered_position, filtered_rotation, apply_baseline=True
        )
        
        # Detect direction using RAW rotation (radians) - matches calibration format
        direction, dir_confidence = self._detect_direction(
            filtered_rotation,  # [roll, pitch, yaw] in radians
            confidence
        )
        
        self._frames_since_start += 1
        
        return FusedPose(
            position=filtered_position,
            rotation=filtered_rotation,
            position_unity=unity_position,
            rotation_unity=unity_rotation,
            confidence=confidence,
            direction=direction,
            direction_confidence=dir_confidence,
            source=source,
            timestamp=current_time
        )
    
    def _select_tracking_source(
        self,
        laptop_pos, laptop_rot, laptop_conf,
        wearable_pos, wearable_rot, wearable_conf
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], str, float]:
        """
        Select tracking source with LAPTOP as PRIMARY.
        
        Strategy:
        1. Use laptop if available (confidence > 0.3)
        2. Fall back to wearable only if laptop fails for 10+ frames
        """
        
        # === PRIMARY: LAPTOP CAMERA ===
        if self._laptop_available and laptop_conf >= 0.3:
            self._laptop_failure_frames = 0
            return laptop_pos, laptop_rot, "laptop", laptop_conf
        
        # Laptop failed this frame
        self._laptop_failure_frames += 1
        
        # === FALLBACK: WEARABLE CAMERA ===
        # Only use wearable if laptop has failed for several frames
        if self._wearable_available and self._laptop_failure_frames >= 5:
            return wearable_pos, wearable_rot, "wearable", wearable_conf * 0.8
        
        # Laptop available but low confidence - still prefer it
        if self._laptop_available:
            return laptop_pos, laptop_rot, "laptop_low", laptop_conf
        
        # No tracking available
        return None, None, "none", 0.0
    
    def _detect_direction(self, rotation: np.ndarray, 
                          confidence: float) -> Tuple[str, float]:
        """Detect direction using raw rotation array."""
        direction, dir_conf = self.direction_detector.detect(rotation, confidence)
        
        # If direction is ambiguous and we have marker hint, use it
        if dir_conf < 0.5 and self._marker_direction_hint:
            hint = self._marker_direction_hint
            if isinstance(hint, Direction):
                hint = hint.value
            
            # Boost confidence if marker agrees
            if hint and hint in direction.value:
                dir_conf = min(1.0, dir_conf + 0.3)
        
        return direction.value, dir_conf
    
    def _update_baseline(self, position: np.ndarray, rotation: np.ndarray) -> None:
        """Establish forward baseline from first N frames."""
        if not self._baseline_pending:
            return
        if self._frames_since_start >= settings.FORWARD_BASELINE_FRAMES:
            self.transform.set_baseline(position, rotation)
            self._baseline_pending = False
            print("[FUSION] Baseline calibrated")
    
    def recenter(self) -> None:
        """Set current pose as new center."""
        position, rotation = self.kalman.get_pose()
        self.transform.set_baseline(position, rotation)
        self.direction_detector.reset()
        self._baseline_pending = False
        print("[FUSION] Recentered")
    
    def reset(self) -> None:
        """Full reset."""
        self.kalman.reset()
        self.transform.reset_baseline()
        self.direction_detector.reset()
        self._laptop_available = self._wearable_available = False
        self._laptop_confidence = self._wearable_confidence = 0.0
        self._laptop_failure_frames = 0
        self._baseline_pending = True
        self._frames_since_start = 0
        self._marker_direction_hint = None
        print("[FUSION] Reset")
    
    def get_source_status(self) -> Dict[str, Any]:
        """Get current tracking source status."""
        return {
            "laptop": {
                "available": self._laptop_available,
                "confidence": self._laptop_confidence
            },
            "wearable": {
                "available": self._wearable_available,
                "confidence": self._wearable_confidence,
                "direction_hint": self._marker_direction_hint
            },
            "laptop_failure_frames": self._laptop_failure_frames,
            "baseline_set": not self._baseline_pending
        }
