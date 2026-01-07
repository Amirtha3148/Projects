"""
ArUco Marker Detector for Wearable Camera

Detects ArUco markers and computes the 6-DoF pose of the camera
relative to the marker. Includes quadrant visibility tracking for
direction confirmation.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from calibration.calibration_data import CalibrationData


@dataclass
class MarkerQuadrants:
    """Tracks visibility of marker quadrants (for direction confirmation)."""
    top_visible: bool = True
    bottom_visible: bool = True
    left_visible: bool = True
    right_visible: bool = True
    
    def to_dict(self) -> Dict[str, bool]:
        return {
            'top': self.top_visible,
            'bottom': self.bottom_visible,
            'left': self.left_visible,
            'right': self.right_visible
        }
    
    def infer_direction(self) -> Optional[str]:
        """
        Infer direction based on which quadrant disappeared.
        When user turns RIGHT, LEFT edge of marker disappears last.
        """
        if not self.right_visible and self.left_visible:
            return "RIGHT"
        if not self.left_visible and self.right_visible:
            return "LEFT"
        if not self.top_visible and self.bottom_visible:
            return "DOWN"
        if not self.bottom_visible and self.top_visible:
            return "UP"
        return None


@dataclass
class ArucoPose:
    """Represents the detected ArUco marker pose."""
    position: np.ndarray
    rotation: np.ndarray
    rotation_matrix: np.ndarray
    confidence: float
    marker_id: int
    corners: np.ndarray
    quadrants: MarkerQuadrants = field(default_factory=MarkerQuadrants)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position.tolist(),
            "rotation": self.rotation.tolist(),
            "confidence": self.confidence,
            "marker_id": self.marker_id,
            "quadrants": self.quadrants.to_dict()
        }


class ArucoDetector:
    """Detects ArUco markers and computes 6-DoF pose with quadrant tracking."""
    
    ARUCO_DICT_MAPPING = {
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
        "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
        "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    }
    
    def __init__(
        self, 
        calibration: CalibrationData,
        marker_size: float = None,
        dictionary_type: str = None,
        target_marker_id: int = None
    ):
        self.calibration = calibration
        self.marker_size = marker_size or settings.ARUCO_MARKER_SIZE_METERS
        self.target_marker_id = target_marker_id
        
        dict_type = dictionary_type or settings.ARUCO_DICTIONARY
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            self.ARUCO_DICT_MAPPING.get(dict_type, cv2.aruco.DICT_4X4_50)
        )
        
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)
        
        self._consecutive_failures = 0
        self._smoothed_confidence = 0.0
        self._last_corners = None
        self._last_quadrants = MarkerQuadrants()
        
    def detect(self, frame: np.ndarray) -> Optional[ArucoPose]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        
        if ids is None or len(ids) == 0:
            self._consecutive_failures += 1
            # Update quadrant visibility based on where marker was last seen
            if self._last_corners is not None:
                self._update_quadrant_visibility_on_loss(frame.shape)
            return None
        
        marker_idx = 0
        if self.target_marker_id is not None:
            for i, mid in enumerate(ids.flatten()):
                if mid == self.target_marker_id:
                    marker_idx = i
                    break
        
        detected_id = ids[marker_idx][0]
        marker_corners = corners[marker_idx]
        self._last_corners = marker_corners
        
        half_size = self.marker_size / 2
        object_points = np.array([
            [-half_size,  half_size, 0],
            [ half_size,  half_size, 0],
            [ half_size, -half_size, 0],
            [-half_size, -half_size, 0],
        ], dtype=np.float32)
        
        image_points = marker_corners.reshape(-1, 2).astype(np.float32)
        
        success, rvec, tvec = cv2.solvePnP(
            object_points, image_points,
            self.calibration.camera_matrix,
            self.calibration.dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        
        if not success:
            self._consecutive_failures += 1
            return None
        
        rotation_matrix, _ = cv2.Rodrigues(rvec)
        euler_angles = self._rotation_matrix_to_euler(rotation_matrix)
        confidence = self._compute_confidence(marker_corners, frame.shape)
        quadrants = self._compute_quadrant_visibility(marker_corners, frame.shape)
        
        self._consecutive_failures = 0
        self._last_quadrants = quadrants
        
        return ArucoPose(
            position=tvec.flatten(),
            rotation=euler_angles,
            rotation_matrix=rotation_matrix,
            confidence=confidence,
            marker_id=detected_id,
            corners=marker_corners,
            quadrants=quadrants
        )
    
    def _compute_quadrant_visibility(self, corners: np.ndarray, 
                                      image_shape: Tuple) -> MarkerQuadrants:
        """
        Determine which quadrants of the marker are visible in frame.
        
        Marker corners are ordered: [top-left, top-right, bottom-right, bottom-left]
        """
        h, w = image_shape[:2]
        margin = 10  # Pixels from edge to consider "at edge"
        
        pts = corners.reshape(-1, 2)
        # Corners: 0=top-left, 1=top-right, 2=bottom-right, 3=bottom-left
        
        # Top edge (corners 0 and 1)
        top_y = (pts[0][1] + pts[1][1]) / 2
        top_visible = top_y > margin
        
        # Bottom edge (corners 2 and 3)
        bottom_y = (pts[2][1] + pts[3][1]) / 2
        bottom_visible = bottom_y < h - margin
        
        # Left edge (corners 0 and 3)
        left_x = (pts[0][0] + pts[3][0]) / 2
        left_visible = left_x > margin
        
        # Right edge (corners 1 and 2)
        right_x = (pts[1][0] + pts[2][0]) / 2
        right_visible = right_x < w - margin
        
        return MarkerQuadrants(
            top_visible=top_visible,
            bottom_visible=bottom_visible,
            left_visible=left_visible,
            right_visible=right_visible
        )
    
    def _update_quadrant_visibility_on_loss(self, image_shape: Tuple) -> None:
        """When marker is lost, infer which direction it went based on last position."""
        if self._last_corners is None:
            return
        
        h, w = image_shape[:2]
        pts = self._last_corners.reshape(-1, 2)
        center = np.mean(pts, axis=0)
        
        # Determine which edge the marker was closest to
        dist_left = center[0]
        dist_right = w - center[0]
        dist_top = center[1]
        dist_bottom = h - center[1]
        
        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
        
        # Mark the closest edge as no longer visible
        self._last_quadrants = MarkerQuadrants()
        if min_dist == dist_left:
            self._last_quadrants.left_visible = False
        elif min_dist == dist_right:
            self._last_quadrants.right_visible = False
        elif min_dist == dist_top:
            self._last_quadrants.top_visible = False
        else:
            self._last_quadrants.bottom_visible = False
    
    def get_last_quadrants(self) -> MarkerQuadrants:
        """Get the last known quadrant visibility state."""
        return self._last_quadrants
    
    def _rotation_matrix_to_euler(self, R: np.ndarray) -> np.ndarray:
        sy = np.sqrt(R[0, 0]**2 + R[1, 0]**2)
        singular = sy < 1e-6
        
        if not singular:
            roll = np.arctan2(R[2, 1], R[2, 2])
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = np.arctan2(R[1, 0], R[0, 0])
        else:
            roll = np.arctan2(-R[1, 2], R[1, 1])
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = 0
            
        return np.array([roll, pitch, yaw])
    
    def _compute_confidence(self, corners: np.ndarray, image_shape: Tuple) -> float:
        corners_2d = corners.reshape(-1, 2)
        marker_area = cv2.contourArea(corners_2d.astype(np.float32))
        image_area = image_shape[0] * image_shape[1]
        size_ratio = marker_area / image_area
        
        size_score = 1.0 if 0.01 < size_ratio < 0.30 else 0.5
        tracking_score = 1.0 - min(self._consecutive_failures / 10.0, 0.5)
        
        confidence = 0.6 * size_score + 0.4 * tracking_score
        alpha = settings.CONFIDENCE_SMOOTHING_FACTOR
        self._smoothed_confidence = alpha * confidence + (1 - alpha) * self._smoothed_confidence
        
        return np.clip(self._smoothed_confidence, 0.0, 1.0)
    
    def draw_detection(self, frame: np.ndarray, pose: Optional[ArucoPose] = None) -> np.ndarray:
        display = frame.copy()
        
        if pose is not None:
            corners = pose.corners.reshape(-1, 2).astype(np.int32)
            cv2.polylines(display, [corners], True, (0, 255, 0), 2)
            
            # Draw quadrant indicators
            q = pose.quadrants
            colors = {True: (0, 255, 0), False: (0, 0, 255)}
            
            # Mark corners with quadrant status
            labels = ['TL', 'TR', 'BR', 'BL']
            for i, (label, pt) in enumerate(zip(labels, corners)):
                cv2.putText(display, label, tuple(pt), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1)
            
            center = np.mean(corners, axis=0).astype(np.int32)
            cv2.putText(display, f"ID: {pose.marker_id}", (center[0] - 20, center[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Direction hint from quadrants
            dir_hint = q.infer_direction()
            if dir_hint:
                cv2.putText(display, f"Dir: {dir_hint}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            pos, rot = pose.position, np.degrees(pose.rotation)
            cv2.putText(display, f"Pos: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(display, f"Rot: ({rot[0]:.1f}, {rot[1]:.1f}, {rot[2]:.1f})",
                       (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(display, f"Conf: {pose.confidence:.2f}",
                       (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            cv2.putText(display, "No marker detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            # Show inferred direction when marker lost
            dir_hint = self._last_quadrants.infer_direction()
            if dir_hint:
                cv2.putText(display, f"Last Dir: {dir_hint}", (10, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
        
        return display


if __name__ == "__main__":
    from calibration.calibration_data import get_default_calibration
    
    calib = get_default_calibration()
    detector = ArucoDetector(calib)
    
    cap = cv2.VideoCapture(settings.WEARABLE_CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Could not open camera {settings.WEARABLE_CAMERA_INDEX}")
        exit(1)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        pose = detector.detect(frame)
        display = detector.draw_detection(frame, pose)
        cv2.imshow("ArUco Detector", display)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
