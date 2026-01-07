"""
MediaPipe Face Mesh Head Pose Detector

OPTIMIZED FOR SEATED LAPTOP USER:
- User sits in front of laptop looking straight ahead
- Detects when user turns head left/right, looks up/down
- Outputs rotation as [roll, pitch, yaw] in radians

COORDINATE CONVENTIONS:
- Pitch: Positive = looking DOWN, Negative = looking UP
- Yaw: Positive = turning LEFT, Negative = turning RIGHT
- Roll: Positive = tilting head RIGHT, Negative = tilting LEFT
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


@dataclass
class HeadPose:
    """Represents the detected head pose from MediaPipe."""
    position: np.ndarray
    rotation: np.ndarray  # radians: [roll, pitch, yaw]
    landmarks: Dict[str, np.ndarray]
    confidence: float
    face_detected: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position.tolist(),
            "rotation": self.rotation.tolist(),
            "confidence": self.confidence,
            "face_detected": self.face_detected
        }


class MediaPipeDetector:
    """
    Head pose detection optimized for seated laptop user.
    
    When user looks STRAIGHT at camera: pitch ≈ 0, yaw ≈ 0
    When user looks UP: pitch becomes NEGATIVE
    When user looks DOWN: pitch becomes POSITIVE
    When user turns LEFT: yaw becomes POSITIVE
    When user turns RIGHT: yaw becomes NEGATIVE
    """
    
    # 3D face model points (nose tip as origin)
    # Coordinates in centimeters, Z pointing out of face
    MODEL_POINTS_3D = np.array([
        [0.0, 0.0, 0.0],          # Nose tip (origin)
        [0.0, -3.3, -1.3],        # Chin
        [-2.3, 3.2, -2.4],        # Left eye outer corner
        [2.3, 3.2, -2.4],         # Right eye outer corner
        [-0.7, 3.2, -1.5],        # Left eye inner corner
        [0.7, 3.2, -1.5],         # Right eye inner corner
        [-2.0, -0.5, -0.8],       # Left mouth corner
        [2.0, -0.5, -0.8],        # Right mouth corner
    ], dtype=np.float64)
    
    # MediaPipe landmark indices
    LANDMARK_INDICES = {
        'nose_tip': 1,
        'chin': 152,
        'left_eye_outer': 33,
        'right_eye_outer': 263,
        'left_eye_inner': 133,
        'right_eye_inner': 362,
        'left_mouth': 61,
        'right_mouth': 291,
    }
    
    def __init__(self, detection_confidence: float = None, tracking_confidence: float = None):
        self.detection_confidence = detection_confidence or 0.5
        self.tracking_confidence = tracking_confidence or 0.5
        self.image_width = settings.CAMERA_WIDTH
        self.image_height = settings.CAMERA_HEIGHT
        
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=self.detection_confidence,
            min_tracking_confidence=self.tracking_confidence
        )
        
        self._update_camera_matrix()
        
        # Baseline calibration (looking straight ahead)
        self._baseline_rotation: Optional[np.ndarray] = None
        self._baseline_position: Optional[np.ndarray] = None
        self._baseline_frames: List[np.ndarray] = []
        self._baseline_pos_frames: List[np.ndarray] = []
        self._baseline_established = False
        
        # Smoothing state
        self._prev_rotation = np.zeros(3)
        self._prev_position = np.zeros(3)
        
        self._consecutive_failures = 0
        self._smoothed_confidence = 0.7
        self._frames_processed = 0
        
    def _update_camera_matrix(self) -> None:
        """Create camera intrinsic matrix based on typical webcam FOV."""
        fov_horizontal = np.radians(65)
        fx = self.image_width / (2 * np.tan(fov_horizontal / 2))
        
        self.camera_matrix = np.array([
            [fx, 0, self.image_width / 2],
            [0, fx, self.image_height / 2],
            [0, 0, 1]
        ], dtype=np.float64)
        
        self.dist_coeffs = np.zeros(5, dtype=np.float64)
    
    def detect(self, frame: np.ndarray) -> Optional[HeadPose]:
        """
        Detect head pose from camera frame.
        
        Returns HeadPose with:
        - rotation: [roll, pitch, yaw] in radians
        - position: [x, y, z] normalized
        """
        if frame is None:
            return None
            
        if frame.shape[1] != self.image_width or frame.shape[0] != self.image_height:
            self.image_width, self.image_height = frame.shape[1], frame.shape[0]
            self._update_camera_matrix()
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            self._consecutive_failures += 1
            return self._get_fallback_pose()
        
        face_landmarks = results.multi_face_landmarks[0]
        
        # Extract 2D landmark positions
        landmarks_2d = {}
        for name, idx in self.LANDMARK_INDICES.items():
            lm = face_landmarks.landmark[idx]
            landmarks_2d[name] = np.array([
                lm.x * self.image_width,
                lm.y * self.image_height
            ])
        
        # Build image points for solvePnP
        image_points = np.array([
            landmarks_2d['nose_tip'],
            landmarks_2d['chin'],
            landmarks_2d['left_eye_outer'],
            landmarks_2d['right_eye_outer'],
            landmarks_2d['left_eye_inner'],
            landmarks_2d['right_eye_inner'],
            landmarks_2d['left_mouth'],
            landmarks_2d['right_mouth'],
        ], dtype=np.float64)
        
        # Solve PnP
        success, rvec, tvec = cv2.solvePnP(
            self.MODEL_POINTS_3D,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            self._consecutive_failures += 1
            return self._get_fallback_pose()
        
        # Convert rotation vector to euler angles
        rotation_matrix, _ = cv2.Rodrigues(rvec)
        raw_euler = self._rotation_matrix_to_euler(rotation_matrix)
        
        # Update baseline during first N frames
        self._update_baseline(raw_euler, tvec.flatten())
        
        # Subtract baseline to get relative rotation
        if self._baseline_established:
            euler_angles = raw_euler - self._baseline_rotation
            # Wrap angles to [-π, π]
            euler_angles = np.arctan2(np.sin(euler_angles), np.cos(euler_angles))
        else:
            euler_angles = raw_euler
        
        # Apply adaptive smoothing
        euler_angles = self._smooth_rotation(euler_angles)
        
        # Estimate position
        position = self._estimate_position(landmarks_2d)
        
        if self._baseline_established and self._baseline_position is not None:
            position = position - self._baseline_position
        
        position = self._smooth_position(position)
        
        confidence = self._compute_confidence(landmarks_2d)
        self._consecutive_failures = 0
        self._frames_processed += 1
        
        return HeadPose(
            position=position,
            rotation=euler_angles,
            landmarks=landmarks_2d,
            confidence=confidence,
            face_detected=True
        )
    
    def _rotation_matrix_to_euler(self, R: np.ndarray) -> np.ndarray:
        """
        Convert rotation matrix to Euler angles [roll, pitch, yaw].
        
        For a user facing the camera:
        - Pitch (X rotation): + = looking down, - = looking up
        - Yaw (Y rotation): + = turned left, - = turned right  
        - Roll (Z rotation): + = tilted right, - = tilted left
        """
        # Extract angles using atan2 for robustness
        pitch = np.arctan2(-R[2, 0], np.sqrt(R[0, 0]**2 + R[1, 0]**2))
        
        if np.abs(np.cos(pitch)) > 1e-6:
            yaw = np.arctan2(R[1, 0], R[0, 0])
            roll = np.arctan2(R[2, 1], R[2, 2])
        else:
            # Gimbal lock case
            yaw = 0
            roll = np.arctan2(-R[0, 1], R[1, 1])
        
        return np.array([roll, pitch, yaw])
    
    def _smooth_rotation(self, euler: np.ndarray) -> np.ndarray:
        """Apply adaptive smoothing based on movement speed."""
        delta = np.abs(euler - self._prev_rotation)
        speed = np.sum(delta)
        
        # Fast movement = less smoothing
        if speed > 0.15:
            alpha = 0.15  # Very responsive
        elif speed > 0.05:
            alpha = 0.35  # Responsive
        else:
            alpha = 0.55  # Stable when still
        
        smoothed = alpha * self._prev_rotation + (1 - alpha) * euler
        self._prev_rotation = smoothed.copy()
        return smoothed
    
    def _smooth_position(self, pos: np.ndarray) -> np.ndarray:
        """Smooth position changes."""
        smoothed = 0.4 * self._prev_position + 0.6 * pos
        self._prev_position = smoothed.copy()
        return smoothed
    
    def _estimate_position(self, landmarks_2d: Dict[str, np.ndarray]) -> np.ndarray:
        """Estimate head position from landmarks."""
        nose = landmarks_2d['nose_tip']
        
        # X: horizontal position (-1 to 1, left to right from camera's view)
        x = (nose[0] / self.image_width - 0.5) * 2.0
        
        # Y: vertical position (-1 to 1, bottom to top)
        y = -(nose[1] / self.image_height - 0.5) * 2.0
        
        # Z: depth from eye distance
        left_eye = landmarks_2d['left_eye_outer']
        right_eye = landmarks_2d['right_eye_outer']
        eye_dist = np.linalg.norm(left_eye - right_eye)
        ref_dist = self.image_width * 0.22
        z = (eye_dist / ref_dist - 1.0) * 0.5
        
        return np.array([x, y, z])
    
    def _compute_confidence(self, landmarks_2d: Dict[str, np.ndarray]) -> float:
        """Compute tracking confidence."""
        nose = landmarks_2d['nose_tip']
        
        # Prefer face near center of frame
        dist_from_center = np.sqrt(
            (nose[0] / self.image_width - 0.5)**2 +
            (nose[1] / self.image_height - 0.5)**2
        )
        center_score = max(0, 1.0 - dist_from_center * 2)
        
        # Penalize tracking failures
        failure_score = 1.0 - min(self._consecutive_failures / 10.0, 0.5)
        
        confidence = 0.5 * center_score + 0.5 * failure_score
        self._smoothed_confidence = 0.3 * confidence + 0.7 * self._smoothed_confidence
        return np.clip(self._smoothed_confidence, 0.1, 1.0)
    
    def _update_baseline(self, rotation: np.ndarray, position: np.ndarray) -> None:
        """Establish baseline from first N frames (user looking straight)."""
        if self._baseline_established:
            return
        
        self._baseline_frames.append(rotation.copy())
        self._baseline_pos_frames.append(position.copy())
        
        if len(self._baseline_frames) >= settings.FORWARD_BASELINE_FRAMES:
            self._baseline_rotation = np.median(self._baseline_frames, axis=0)
            self._baseline_position = np.median(self._baseline_pos_frames, axis=0)
            self._baseline_established = True
            print(f"[MEDIAPIPE] Baseline established (looking straight)")
            print(f"  Rotation baseline: {np.degrees(self._baseline_rotation)}")
    
    def _get_fallback_pose(self) -> Optional[HeadPose]:
        """Return last known pose when detection fails."""
        if self._consecutive_failures < 15:
            decay = 0.92
            self._prev_rotation *= decay
            self._prev_position *= decay
            
            return HeadPose(
                position=self._prev_position.copy(),
                rotation=self._prev_rotation.copy(),
                landmarks={},
                confidence=max(0.2, 0.8 - self._consecutive_failures * 0.04),
                face_detected=False
            )
        return None
    
    def reset_baseline(self) -> None:
        """Reset baseline for recalibration."""
        self._baseline_rotation = None
        self._baseline_position = None
        self._baseline_frames = []
        self._baseline_pos_frames = []
        self._baseline_established = False
        self._prev_rotation = np.zeros(3)
        self._prev_position = np.zeros(3)
        print("[MEDIAPIPE] Baseline reset")
    
    def set_baseline_now(self) -> None:
        """Set current pose as baseline immediately."""
        self._baseline_rotation = self._prev_rotation.copy()
        self._baseline_position = self._prev_position.copy()
        self._baseline_established = True
        self._prev_rotation = np.zeros(3)
        self._prev_position = np.zeros(3)
        print("[MEDIAPIPE] Baseline set to current pose")
    
    def draw_detection(self, frame: np.ndarray, pose: Optional[HeadPose] = None) -> np.ndarray:
        """Draw detection overlay."""
        display = frame.copy()
        
        if pose is not None and pose.face_detected:
            for pt in pose.landmarks.values():
                cv2.circle(display, tuple(pt.astype(int)), 2, (0, 255, 0), -1)
            
            rot_deg = np.degrees(pose.rotation)
            # Show formatted rotation
            cv2.putText(display, f"Roll:{rot_deg[0]:+.1f} Pitch:{rot_deg[1]:+.1f} Yaw:{rot_deg[2]:+.1f}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            status = "TRACKING" if self._baseline_established else "CALIBRATING..."
            cv2.putText(display, status, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                       (0, 255, 0) if self._baseline_established else (0, 255, 255), 1)
        else:
            cv2.putText(display, "No face", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        return display
    
    def _get_direction_text(self, pitch_deg: float, yaw_deg: float) -> str:
        """Get text description of head direction."""
        threshold = 8.0
        
        v = ""
        if pitch_deg < -threshold:
            v = "UP"
        elif pitch_deg > threshold:
            v = "DOWN"
        
        h = ""
        if yaw_deg > threshold:
            h = "LEFT"
        elif yaw_deg < -threshold:
            h = "RIGHT"
        
        if v and h:
            return f"{v}-{h}"
        return v or h or "CENTER"
    
    def close(self) -> None:
        """Release resources."""
        self.face_mesh.close()


if __name__ == "__main__":
    detector = MediaPipeDetector()
    cap = cv2.VideoCapture(settings.LAPTOP_CAMERA_INDEX)
    
    print("Head Tracking Test - Press 'r' to reset, 'q' to quit")
    print("Look straight at camera to establish baseline...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        pose = detector.detect(frame)
        display = detector.draw_detection(frame, pose)
        
        if pose and pose.face_detected:
            rot_deg = np.degrees(pose.rotation)
            print(f"\rPitch:{rot_deg[1]:+6.1f}° Yaw:{rot_deg[2]:+6.1f}° Roll:{rot_deg[0]:+6.1f}°  ", end="")
        
        cv2.imshow("Head Tracking", display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            detector.reset_baseline()
    
    cap.release()
    cv2.destroyAllWindows()
    detector.close()
