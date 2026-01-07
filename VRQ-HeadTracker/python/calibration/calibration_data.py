"""
Camera Calibration Data

Handles loading, saving, and managing camera calibration data.
"""

import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class CalibrationData:
    """Stores camera calibration parameters."""
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    image_size: tuple
    reprojection_error: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.tolist(),
            "image_size": list(self.image_size),
            "reprojection_error": self.reprojection_error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationData":
        return cls(
            camera_matrix=np.array(data["camera_matrix"]),
            dist_coeffs=np.array(data["dist_coeffs"]),
            image_size=tuple(data["image_size"]),
            reprojection_error=data.get("reprojection_error", 0.0)
        )


def get_default_calibration(width: int = 640, height: int = 480) -> CalibrationData:
    """Returns a reasonable default calibration for a typical webcam."""
    focal_length = width * 0.8
    cx, cy = width / 2, height / 2
    
    camera_matrix = np.array([
        [focal_length, 0, cx],
        [0, focal_length, cy],
        [0, 0, 1]
    ], dtype=np.float64)
    
    dist_coeffs = np.zeros(5, dtype=np.float64)
    
    return CalibrationData(
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=(width, height),
        reprojection_error=1.0
    )


def load_calibration(filepath: str) -> Optional[CalibrationData]:
    """Load calibration from JSON file."""
    path = Path(filepath)
    if not path.exists():
        return None
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        calib = CalibrationData.from_dict(data)
        print(f"[CALIBRATION] Loaded calibration from: {filepath}")
        print(f"[CALIBRATION] Reprojection error: {calib.reprojection_error:.4f}")
        return calib
    except Exception as e:
        print(f"[CALIBRATION] Error loading {filepath}: {e}")
        return None


def save_calibration(calibration: CalibrationData, filepath: str) -> bool:
    """Save calibration to JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(path, 'w') as f:
            json.dump(calibration.to_dict(), f, indent=2)
        print(f"[CALIBRATION] Saved calibration to: {filepath}")
        return True
    except Exception as e:
        print(f"[CALIBRATION] Error saving {filepath}: {e}")
        return False


def load_laptop_calibration() -> CalibrationData:
    """Load laptop camera calibration or use default."""
    calib_dir = Path(__file__).parent.parent / "calibration_data"
    calib_file = calib_dir / "laptop_camera_calibration.json"
    
    calib = load_calibration(str(calib_file))
    if calib is None:
        print("[CALIBRATION] Using default laptop calibration")
        calib = get_default_calibration()
    return calib


def load_wearable_calibration() -> CalibrationData:
    """Load wearable camera calibration or use default."""
    calib_dir = Path(__file__).parent.parent / "calibration_data"
    calib_file = calib_dir / "wearable_camera_calibration.json"
    
    calib = load_calibration(str(calib_file))
    if calib is None:
        print("[CALIBRATION] Using default wearable calibration")
        calib = get_default_calibration()
    return calib
