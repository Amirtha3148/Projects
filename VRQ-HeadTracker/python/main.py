"""
VRQ-HeadTracker Main Application

Main entry point for the dual-camera 6-DoF head tracking system.
Now includes direction detection display.
"""

import cv2
import numpy as np
import argparse
import time
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from calibration.calibration_data import load_laptop_calibration, load_wearable_calibration
from detection.aruco_detector import ArucoDetector, ArucoPose
from detection.mediapipe_detector import MediaPipeDetector, HeadPose
from tracking.fusion_engine import SensorFusionEngine, FusedPose
from communication.websocket_server import WebSocketServer


class HeadTracker:
    """Main head tracking application with direction detection."""
    
    def __init__(self, laptop_camera_index: int = None,
                 wearable_camera_index: int = None, show_debug: bool = True):
        self.laptop_index = laptop_camera_index or settings.LAPTOP_CAMERA_INDEX
        self.wearable_index = wearable_camera_index or settings.WEARABLE_CAMERA_INDEX
        self.show_debug = show_debug
        
        self.laptop_cap: Optional[cv2.VideoCapture] = None
        self.wearable_cap: Optional[cv2.VideoCapture] = None
        self.mediapipe_detector: Optional[MediaPipeDetector] = None
        self.aruco_detector: Optional[ArucoDetector] = None
        self.fusion: Optional[SensorFusionEngine] = None
        self.websocket: Optional[WebSocketServer] = None
        
        self.frame_count = 0
        self.fps = 0.0
        self.fps_timer = time.time()
        self.fps_frame_count = 0
        self.show_stats = True
        self.running = False
        
    def initialize(self) -> bool:
        print("\n" + "="*60)
        print("VRQ-HeadTracker - Dual Camera 6-DoF Head Tracking")
        print("="*60)
        
        print("\n[INIT] Opening cameras...")
        self.laptop_cap = cv2.VideoCapture(self.laptop_index)
        if not self.laptop_cap.isOpened():
            print(f"[ERROR] Could not open laptop camera (index {self.laptop_index})")
            return False
        self._configure_camera(self.laptop_cap, "Laptop")
        
        self.wearable_cap = cv2.VideoCapture(self.wearable_index)
        if not self.wearable_cap.isOpened():
            print(f"[INFO] No wearable camera, continuing with laptop only")
            self.wearable_cap = None
        else:
            self._configure_camera(self.wearable_cap, "Wearable")
        
        print("\n[INIT] Loading calibrations...")
        laptop_calib = load_laptop_calibration()
        wearable_calib = load_wearable_calibration()
        
        print("\n[INIT] Initializing detectors...")
        self.mediapipe_detector = MediaPipeDetector()
        if self.wearable_cap is not None:
            self.aruco_detector = ArucoDetector(wearable_calib)
        
        print("\n[INIT] Initializing sensor fusion...")
        self.fusion = SensorFusionEngine(dt=1.0/30.0)
        
        print("\n[INIT] Starting WebSocket server...")
        self.websocket = WebSocketServer()
        self.websocket.start()
        
        print("\n" + "="*60)
        print("INITIALIZATION COMPLETE")
        print("Controls: 'r'=Recenter, 'b'=Reset, 's'=Stats, 'q'=Quit")
        print("="*60 + "\n")
        
        return True
    
    def _configure_camera(self, cap: cv2.VideoCapture, name: str) -> None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, settings.CAMERA_FPS)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INIT] {name} camera: {w}x{h}")
    
    def run(self) -> None:
        self.running = True
        
        while self.running:
            laptop_frame = wearable_frame = None
            
            if self.laptop_cap:
                ret, laptop_frame = self.laptop_cap.read()
                if not ret:
                    laptop_frame = None
            
            if self.wearable_cap:
                ret, wearable_frame = self.wearable_cap.read()
                if not ret:
                    wearable_frame = None
            
            laptop_pose = self.mediapipe_detector.detect(laptop_frame) if laptop_frame is not None else None
            wearable_pose = self.aruco_detector.detect(wearable_frame) if wearable_frame is not None and self.aruco_detector else None
            
            # Get marker quadrants for direction confirmation
            marker_quadrants = None
            if wearable_pose is not None:
                marker_quadrants = wearable_pose.quadrants.to_dict()
            elif self.aruco_detector:
                # Use last known quadrants even when marker lost
                marker_quadrants = self.aruco_detector.get_last_quadrants().to_dict()
            
            # Pass marker quadrants to fusion for direction confirmation
            fused_pose = self.fusion.update(
                laptop_pose.position if laptop_pose else None,
                laptop_pose.rotation if laptop_pose else None,
                laptop_pose.confidence if laptop_pose else 0.0,
                wearable_pose.position if wearable_pose else None,
                wearable_pose.rotation if wearable_pose else None,
                wearable_pose.confidence if wearable_pose else 0.0,
                marker_quadrants=marker_quadrants  # NEW
            )
            
            self.websocket.send_pose(fused_pose.to_dict())
            self._update_fps()
            
            if self.show_debug:
                self._show_debug(laptop_frame, laptop_pose, wearable_frame, wearable_pose, fused_pose)
            
            key = cv2.waitKey(1) & 0xFF
            self._handle_key(key)
            self.frame_count += 1
        
        self.cleanup()
    
    def _update_fps(self) -> None:
        self.fps_frame_count += 1
        elapsed = time.time() - self.fps_timer
        if elapsed >= 1.0:
            self.fps = self.fps_frame_count / elapsed
            self.fps_frame_count = 0
            self.fps_timer = time.time()
    
    def _show_debug(self, laptop_frame, laptop_pose, wearable_frame, wearable_pose, fused_pose):
        if laptop_frame is not None:
            display = self.mediapipe_detector.draw_detection(laptop_frame, laptop_pose)
            cv2.imshow("Laptop Camera", display)
        
        if wearable_frame is not None and self.aruco_detector:
            display = self.aruco_detector.draw_detection(wearable_frame, wearable_pose)
            cv2.imshow("Wearable Camera", display)
        
        if self.show_stats:
            stats = np.zeros((220, 350, 3), dtype=np.uint8)
            stats[:] = (30, 30, 30)
            
            # FPS and clients
            cv2.putText(stats, f"FPS: {self.fps:.1f}", (10, 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(stats, f"Clients: {self.websocket.client_count}", (150, 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Direction (LARGE)
            direction = fused_pose.direction
            dir_conf = fused_pose.direction_confidence
            color = (0, 255, 0) if dir_conf > 0.6 else (0, 255, 255) if dir_conf > 0.4 else (0, 165, 255)
            cv2.putText(stats, f"DIR: {direction}", (10, 65), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
            cv2.putText(stats, f"({dir_conf:.0%})", (250, 65), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Pose info
            pos = fused_pose.position_unity
            rot = fused_pose.rotation_unity
            cv2.putText(stats, f"Pos: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})", 
                       (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(stats, f"Rot: ({rot[0]:.1f}, {rot[1]:.1f}, {rot[2]:.1f})", 
                       (10, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(stats, f"Conf: {fused_pose.confidence:.0%}", 
                       (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            
            # Direction visualization (arrows)
            self._draw_direction_indicator(stats, direction, 280, 150)
            
            cv2.imshow("Status", stats)
    
    def _draw_direction_indicator(self, img, direction: str, cx: int, cy: int):
        """Draw a visual arrow indicating the direction."""
        size = 30
        color = (0, 255, 0)
        thickness = 2
        
        # Direction vectors
        dirs = {
            "CENTER": (0, 0),
            "UP": (0, -1),
            "DOWN": (0, 1),
            "LEFT": (-1, 0),
            "RIGHT": (1, 0),
            "UP_LEFT": (-0.7, -0.7),
            "UP_RIGHT": (0.7, -0.7),
            "DOWN_LEFT": (-0.7, 0.7),
            "DOWN_RIGHT": (0.7, 0.7),
        }
        
        dx, dy = dirs.get(direction, (0, 0))
        
        # Draw circle for center
        cv2.circle(img, (cx, cy), 5, (100, 100, 100), -1)
        
        if dx != 0 or dy != 0:
            end_x = int(cx + dx * size)
            end_y = int(cy + dy * size)
            cv2.arrowedLine(img, (cx, cy), (end_x, end_y), color, thickness, tipLength=0.3)
    
    def _handle_key(self, key: int) -> None:
        if key == ord('q'):
            self.running = False
        elif key == ord('r'):
            self.fusion.recenter()
            print("[INPUT] Recentered")
        elif key == ord('b'):
            self.fusion.reset()
            self.mediapipe_detector.reset_baseline()
            print("[INPUT] Reset baseline")
        elif key == ord('s'):
            self.show_stats = not self.show_stats
            if not self.show_stats:
                cv2.destroyWindow("Status")
    
    def cleanup(self) -> None:
        print("\n[CLEANUP] Shutting down...")
        if self.websocket:
            self.websocket.stop()
        if self.mediapipe_detector:
            self.mediapipe_detector.close()
        if self.laptop_cap:
            self.laptop_cap.release()
        if self.wearable_cap:
            self.wearable_cap.release()
        cv2.destroyAllWindows()
        print("[CLEANUP] Done")


def main():
    parser = argparse.ArgumentParser(description="VRQ-HeadTracker")
    parser.add_argument("--laptop", "-l", type=int, default=None)
    parser.add_argument("--wearable", "-w", type=int, default=None)
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()
    
    tracker = HeadTracker(args.laptop, args.wearable, not args.no_debug)
    
    if tracker.initialize():
        try:
            tracker.run()
        except KeyboardInterrupt:
            tracker.cleanup()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
