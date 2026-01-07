"""
Direction Calibrator

Captures RAW MediaPipe rotation for each direction.
Unity will map these direction STRINGS to its own reference points.

Flow:
1. User looks in a direction (e.g., UP)
2. Capture raw rotation [roll, pitch, yaw] in RADIANS
3. Direction detector compares current raw angles to these samples
4. Sends direction STRING to Unity
5. Unity uses its own reference points for camera movement
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


@dataclass
class DirectionReference:
    """Reference pose for a single direction (RAW MediaPipe angles in radians)."""
    name: str
    samples: List[List[float]]  # List of [roll, pitch, yaw] in RADIANS
    mean: List[float] = None
    std: List[float] = None
    
    def compute_stats(self):
        """Compute mean and std from samples."""
        if len(self.samples) > 0:
            arr = np.array(self.samples)
            self.mean = arr.mean(axis=0).tolist()
            self.std = np.maximum(arr.std(axis=0), 0.02).tolist()  # Min std of ~1 degree


class DirectionCalibrator:
    """
    Calibrates reference poses using RAW MediaPipe angles.
    """
    
    DIRECTIONS = ['CENTER', 'UP', 'DOWN', 'LEFT', 'RIGHT', 
                  'UP_LEFT', 'UP_RIGHT', 'DOWN_LEFT', 'DOWN_RIGHT']
    
    KEY_MAPPINGS = {
        ord('c'): 'CENTER',
        ord('u'): 'UP',
        ord('d'): 'DOWN',
        ord('l'): 'LEFT',
        ord('r'): 'RIGHT',
        ord('7'): 'UP_LEFT',
        ord('9'): 'UP_RIGHT',
        ord('1'): 'DOWN_LEFT',
        ord('3'): 'DOWN_RIGHT',
    }
    
    def __init__(self):
        self.references: Dict[str, DirectionReference] = {
            name: DirectionReference(name=name, samples=[])
            for name in self.DIRECTIONS
        }
        self.calibration_file = Path(__file__).parent.parent / "calibration_data" / "direction_calibration.json"
        
    def add_sample(self, direction: str, rotation: np.ndarray) -> int:
        """
        Add a RAW rotation sample for a direction.
        
        Args:
            direction: Direction name
            rotation: [roll, pitch, yaw] in RADIANS from MediaPipe
            
        Returns:
            Number of samples for this direction
        """
        if direction not in self.references:
            return 0
        
        self.references[direction].samples.append(rotation.tolist())
        self.references[direction].compute_stats()
        return len(self.references[direction].samples)
    
    def classify(self, rotation: np.ndarray) -> Tuple[str, float]:
        """
        Classify a rotation using calibrated references.
        
        Args:
            rotation: [roll, pitch, yaw] in RADIANS
            
        Returns:
            (direction_name, confidence)
        """
        best_direction = 'CENTER'
        best_score = float('inf')
        
        for name, ref in self.references.items():
            if ref.mean is None or len(ref.samples) == 0:
                continue
            
            mean = np.array(ref.mean)
            std = np.array(ref.std)
            
            # Weighted distance (pitch and yaw matter more than roll)
            weights = np.array([0.3, 1.0, 1.0])  # [roll, pitch, yaw]
            diff = np.abs(rotation - mean) / std * weights
            score = np.sum(diff)
            
            if score < best_score:
                best_score = score
                best_direction = name
        
        # Convert score to confidence
        confidence = max(0.2, min(1.0, 1.0 - best_score / 6.0))
        
        return best_direction, confidence
    
    def save(self, filepath: str = None) -> bool:
        """Save calibration to JSON file."""
        filepath = filepath or str(self.calibration_file)
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        for ref in self.references.values():
            ref.compute_stats()
        
        data = {name: asdict(ref) for name, ref in self.references.items()}
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n[CALIBRATION] Saved to: {filepath}")
            self._print_summary()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save: {e}")
            return False
    
    def load(self, filepath: str = None) -> bool:
        """Load calibration from JSON file."""
        filepath = filepath or str(self.calibration_file)
        
        if not Path(filepath).exists():
            print(f"[CALIBRATION] No file found, starting fresh")
            return False
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            for name, ref_data in data.items():
                if name in self.references:
                    self.references[name] = DirectionReference(**ref_data)
            
            print(f"[CALIBRATION] Loaded from: {filepath}")
            self._print_summary()
            return True
        except Exception as e:
            print(f"[CALIBRATION] Starting fresh: {e}")
            return False
    
    def _print_summary(self):
        """Print summary of calibrated directions."""
        print("\nCalibrated Directions (RAW radians):")
        print("-" * 60)
        for name, ref in self.references.items():
            n = len(ref.samples)
            if n > 0 and ref.mean:
                mean_deg = np.degrees(ref.mean)
                print(f"  {name:12s}: {n:3d} samples, raw=[roll:{mean_deg[0]:+.1f}°, pitch:{mean_deg[1]:+.1f}°, yaw:{mean_deg[2]:+.1f}°]")
            else:
                print(f"  {name:12s}: Not calibrated")


def run_calibration():
    """Interactive calibration UI using RAW MediaPipe angles."""
    from detection.mediapipe_detector import MediaPipeDetector
    
    print("\n" + "=" * 60)
    print("DIRECTION CALIBRATION (RAW MediaPipe Angles)")
    print("=" * 60)
    print("\nThis captures YOUR head position for each direction.")
    print("Unity will map these directions to its own camera angles.")
    print("\nKeys:")
    print("  c = CENTER, u = UP, d = DOWN, l = LEFT, r = RIGHT")
    print("  7 = UP_LEFT, 9 = UP_RIGHT, 1 = DOWN_LEFT, 3 = DOWN_RIGHT")
    print("  s = Save, q = Quit, x = Clear all")
    print("=" * 60 + "\n")
    
    detector = MediaPipeDetector()
    calibrator = DirectionCalibrator()
    
    # Try loading existing calibration
    calibrator.load()
    
    cap = cv2.VideoCapture(settings.LAPTOP_CAMERA_INDEX)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera")
        return
    
    current_rotation = np.zeros(3)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        pose = detector.detect(frame)
        display = detector.draw_detection(frame, pose)
        
        if pose and pose.face_detected:
            # Use RAW rotation from MediaPipe (radians)
            current_rotation = pose.rotation.copy()
            rot_deg = np.degrees(current_rotation)
            
            # Show RAW angles
            cv2.putText(display, f"RAW: Roll:{rot_deg[0]:+.1f} Pitch:{rot_deg[1]:+.1f} Yaw:{rot_deg[2]:+.1f}", 
                       (10, display.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            # Classify
            direction, conf = calibrator.classify(current_rotation)
            color = (0, 255, 0) if conf > 0.6 else (0, 255, 255) if conf > 0.4 else (0, 165, 255)
            cv2.putText(display, f"{direction} ({conf:.0%})", 
                       (10, display.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        # Sample counts
        y = 100
        for name, ref in calibrator.references.items():
            count = len(ref.samples)
            color = (0, 255, 0) if count >= 3 else (0, 255, 255) if count > 0 else (128, 128, 128)
            cv2.putText(display, f"{name}: {count}", (display.shape[1] - 150, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y += 20
        
        cv2.imshow("Direction Calibration", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            calibrator.save()
        elif key == ord('x'):
            calibrator = DirectionCalibrator()
            print("[CALIBRATION] Cleared all samples")
        elif key in DirectionCalibrator.KEY_MAPPINGS:
            direction = DirectionCalibrator.KEY_MAPPINGS[key]
            count = calibrator.add_sample(direction, current_rotation)
            rot_deg = np.degrees(current_rotation)
            print(f"[+] {direction}: roll={rot_deg[0]:+.1f}°, pitch={rot_deg[1]:+.1f}°, yaw={rot_deg[2]:+.1f}° ({count} samples)")
    
    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    
    # Save on exit
    calibrator.save()


if __name__ == "__main__":
    run_calibration()
