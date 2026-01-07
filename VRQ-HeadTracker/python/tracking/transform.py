"""
Coordinate Transformation for Head Tracking

Transforms pose from MediaPipe (camera space) to Unity (game space).

ROTATION CONVENTIONS:
From MediaPipe:
- Pitch: + = looking DOWN, - = looking UP
- Yaw: + = turned LEFT, - = turned RIGHT
- Roll: + = tilted RIGHT, - = tilted LEFT

To Unity:
- X (pitch): + = look DOWN, - = look UP (SAME as MediaPipe)
- Y (yaw): + = turn RIGHT, - = turn LEFT (OPPOSITE of MediaPipe)
- Z (roll): minimal, + = tilt RIGHT
"""

import numpy as np
from typing import Tuple


class CoordinateTransform:
    """Handles coordinate transformations for head tracking."""
    
    def __init__(self):
        self._position_baseline = np.zeros(3)
        self._rotation_baseline = np.zeros(3)
        self._baseline_set = False
        
    def camera_to_unity(self, position: np.ndarray, rotation: np.ndarray
                        ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert camera coordinates to Unity coordinates.
        
        Args:
            position: [x, y, z] from camera
            rotation: [roll, pitch, yaw] in radians from MediaPipe
            
        Returns:
            (unity_position, unity_rotation) with rotation in degrees
        """
        # Position mapping
        # Camera: X+ right, Y+ down, Z+ forward (into screen)
        # Unity: X+ right, Y+ up, Z+ forward
        unity_pos = np.array([
            position[0],       # X: left/right (same)
            -position[1],      # Y: invert (camera down -> Unity up)
            position[2]        # Z: forward/back (same)
        ])
        
        # Rotation mapping (radians to degrees)
        roll_rad = rotation[0]
        pitch_rad = rotation[1]
        yaw_rad = rotation[2]
        
        # Unity rotation:
        # X = pitch: MediaPipe pitch -> Unity X (same sign: + = look down)
        # Y = yaw: MediaPipe yaw is + for LEFT, Unity Y+ is RIGHT, so NEGATE
        # Z = roll: minimal
        unity_rot = np.array([
            np.degrees(pitch_rad),      # X: pitch (+ = down, - = up)
            np.degrees(-yaw_rad),       # Y: yaw (negate: left becomes negative)
            np.degrees(roll_rad) * 0.3  # Z: roll (damped)
        ])
        
        return unity_pos, unity_rot
    
    def set_baseline(self, position: np.ndarray, rotation: np.ndarray) -> None:
        """Set current pose as neutral forward position."""
        self._position_baseline = position.copy()
        self._rotation_baseline = rotation.copy()
        self._baseline_set = True
        print(f"[TRANSFORM] Baseline set")
    
    def apply_baseline(self, position: np.ndarray, rotation: np.ndarray
                       ) -> Tuple[np.ndarray, np.ndarray]:
        """Subtract baseline to get relative movement."""
        if not self._baseline_set:
            return position.copy(), rotation.copy()
        
        relative_pos = position - self._position_baseline
        relative_rot = self._wrap_angles(rotation - self._rotation_baseline)
        return relative_pos, relative_rot
    
    def reset_baseline(self) -> None:
        """Clear baseline."""
        self._position_baseline = np.zeros(3)
        self._rotation_baseline = np.zeros(3)
        self._baseline_set = False
    
    def full_transform(self, position: np.ndarray, rotation: np.ndarray,
                       apply_baseline: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Complete transformation to Unity coordinates.
        
        Args:
            position: Camera-space position [x, y, z]
            rotation: Camera-space rotation [roll, pitch, yaw] in radians
            apply_baseline: Whether to subtract baseline
            
        Returns:
            (unity_position, unity_rotation) ready for Unity camera
        """
        pos, rot = position.copy(), rotation.copy()
        
        if apply_baseline and self._baseline_set:
            pos, rot = self.apply_baseline(pos, rot)
        
        return self.camera_to_unity(pos, rot)
    
    @staticmethod
    def _wrap_angles(angles: np.ndarray) -> np.ndarray:
        """Wrap angles to [-π, π] range."""
        return np.arctan2(np.sin(angles), np.cos(angles))
    
    @property
    def has_baseline(self) -> bool:
        return self._baseline_set


def test_mappings():
    """Test that coordinate mappings are intuitive."""
    transform = CoordinateTransform()
    
    print("Testing coordinate mappings:")
    print("-" * 50)
    
    # Test: Look UP (pitch negative from MediaPipe)
    _, rot = transform.camera_to_unity(np.zeros(3), np.array([0, -0.3, 0]))
    print(f"Look UP: Unity X={rot[0]:.1f}° (should be NEGATIVE)")
    
    # Test: Look DOWN (pitch positive from MediaPipe)
    _, rot = transform.camera_to_unity(np.zeros(3), np.array([0, 0.3, 0]))
    print(f"Look DOWN: Unity X={rot[0]:.1f}° (should be POSITIVE)")
    
    # Test: Turn LEFT (yaw positive from MediaPipe)
    _, rot = transform.camera_to_unity(np.zeros(3), np.array([0, 0, 0.3]))
    print(f"Turn LEFT: Unity Y={rot[1]:.1f}° (should be NEGATIVE)")
    
    # Test: Turn RIGHT (yaw negative from MediaPipe)
    _, rot = transform.camera_to_unity(np.zeros(3), np.array([0, 0, -0.3]))
    print(f"Turn RIGHT: Unity Y={rot[1]:.1f}° (should be POSITIVE)")


if __name__ == "__main__":
    test_mappings()
