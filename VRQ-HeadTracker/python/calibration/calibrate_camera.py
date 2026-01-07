"""
Interactive Camera Calibration Tool

This module provides a command-line tool for calibrating webcams using a
checkerboard pattern. Calibration computes the camera's intrinsic parameters
which are essential for accurate 3D pose estimation.

Usage:
    python calibrate_camera.py --camera 0 --output laptop_camera_calibration.json
    python calibrate_camera.py --camera 1 --output wearable_camera_calibration.json
"""

import cv2
import numpy as np
import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from calibration.calibration_data import CalibrationData, save_calibration


class CameraCalibrator:
    """
    Interactive camera calibration using checkerboard pattern.
    """
    
    def __init__(
        self,
        camera_index: int,
        board_size: Tuple[int, int] = None,
        square_size: float = None
    ):
        self.camera_index = camera_index
        self.board_size = board_size or (
            settings.CHECKERBOARD_ROWS, 
            settings.CHECKERBOARD_COLS
        )
        self.square_size = square_size or settings.CHECKERBOARD_SQUARE_SIZE
        
        self.object_points: List[np.ndarray] = []
        self.image_points: List[np.ndarray] = []
        self.image_size: Optional[Tuple[int, int]] = None
        
        self.objp = np.zeros((self.board_size[0] * self.board_size[1], 3), np.float32)
        self.objp[:, :2] = np.mgrid[
            0:self.board_size[0], 
            0:self.board_size[1]
        ].T.reshape(-1, 2) * self.square_size
        
    def run_calibration(
        self, 
        num_images: int = None,
        output_file: str = None
    ) -> Optional[CalibrationData]:
        num_images = num_images or settings.CALIBRATION_IMAGES_COUNT
        
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print(f"[ERROR] Could not open camera {self.camera_index}")
            return None
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_HEIGHT)
        
        print("\n" + "="*60)
        print("CAMERA CALIBRATION TOOL")
        print("="*60)
        print(f"Camera Index: {self.camera_index}")
        print(f"Checkerboard: {self.board_size[0]}x{self.board_size[1]} inner corners")
        print(f"Images to capture: {num_images}")
        print("Press SPACE to capture, 'q' to quit early, ESC to cancel")
        print("="*60 + "\n")
        
        window_name = f"Calibration - Camera {self.camera_index}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        captured_count = 0
        
        while captured_count < num_images:
            ret, frame = cap.read()
            if not ret:
                break
                
            if self.image_size is None:
                self.image_size = (frame.shape[1], frame.shape[0])
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(
                gray, self.board_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            )
            
            display = frame.copy()
            
            if found:
                corners_refined = cv2.cornerSubPix(
                    gray, corners, (11, 11), (-1, -1),
                    (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                )
                cv2.drawChessboardCorners(display, self.board_size, corners_refined, found)
                cv2.putText(display, "READY - Press SPACE", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(display, "Position checkerboard...", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            cv2.putText(display, f"Captured: {captured_count}/{num_images}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow(window_name, display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' ') and found:
                self.object_points.append(self.objp.copy())
                self.image_points.append(corners_refined)
                captured_count += 1
                print(f"[CALIBRATION] Captured {captured_count}/{num_images}")
            elif key == ord('q'):
                break
            elif key == 27:
                cap.release()
                cv2.destroyAllWindows()
                return None
        
        cap.release()
        cv2.destroyAllWindows()
        
        if len(self.object_points) < 3:
            print("[ERROR] Not enough calibration images")
            return None
            
        return self._compute_calibration(output_file)
    
    def _compute_calibration(self, output_file: str = None) -> CalibrationData:
        print(f"\n[CALIBRATION] Computing from {len(self.object_points)} images...")
        
        ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            self.object_points, self.image_points, self.image_size, None, None
        )
        
        calib_data = CalibrationData(
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs.flatten(),
            image_size=self.image_size,
            reprojection_error=ret
        )
        
        print(f"[CALIBRATION] Reprojection Error: {ret:.4f} pixels")
        
        if output_file:
            save_calibration(calib_data, output_file)
        
        return calib_data


def generate_checkerboard_image(
    board_size: Tuple[int, int] = None,
    square_size_px: int = 50,
    output_path: str = None
) -> np.ndarray:
    board_size = board_size or (settings.CHECKERBOARD_ROWS, settings.CHECKERBOARD_COLS)
    rows = board_size[0] + 1
    cols = board_size[1] + 1
    
    img_height = rows * square_size_px
    img_width = cols * square_size_px
    pattern = np.zeros((img_height, img_width), dtype=np.uint8)
    
    for i in range(rows):
        for j in range(cols):
            if (i + j) % 2 == 0:
                y1, y2 = i * square_size_px, (i + 1) * square_size_px
                x1, x2 = j * square_size_px, (j + 1) * square_size_px
                pattern[y1:y2, x1:x2] = 255
    
    if output_path:
        cv2.imwrite(output_path, pattern)
        print(f"[CALIBRATION] Saved checkerboard to: {output_path}")
    
    return pattern


def main():
    parser = argparse.ArgumentParser(description="Camera calibration tool")
    parser.add_argument("--camera", "-c", type=int, default=0)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--images", "-n", type=int, default=settings.CALIBRATION_IMAGES_COUNT)
    parser.add_argument("--generate-pattern", action="store_true")
    
    args = parser.parse_args()
    
    if args.generate_pattern:
        output_path = str(settings.BASE_DIR / "calibration_patterns" / "checkerboard.png")
        Path(output_path).parent.mkdir(exist_ok=True)
        generate_checkerboard_image(output_path=output_path)
        return
    
    output_file = args.output or f"camera_{args.camera}_calibration.json"
    calibrator = CameraCalibrator(camera_index=args.camera)
    calibrator.run_calibration(num_images=args.images, output_file=output_file)


if __name__ == "__main__":
    main()
