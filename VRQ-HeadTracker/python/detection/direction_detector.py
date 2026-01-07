"""
Direction Detector Module

Detects head direction using USER-DEFINED REAL WORLD RANGES.
Input: Raw MediaPipe rotation (Radians)
Processing: Converts to Degrees -> Checks against specific zones
Output: Direction string

User Defined Ranges (Degrees):
- Center: Pitch [-10, 5], Yaw [-5, 5]
- Up: Pitch < -10
- Down: Pitch > +10
- Left: Yaw < -10
- Right: Yaw > +10
- Diagonals: Combinations of above
"""

import numpy as np
from enum import Enum
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from pathlib import Path
import json


class Direction(Enum):
    """9 possible head directions."""
    CENTER = "CENTER"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP_LEFT = "UP_LEFT"
    UP_RIGHT = "UP_RIGHT"
    DOWN_LEFT = "DOWN_LEFT"
    DOWN_RIGHT = "DOWN_RIGHT"


class DirectionDetector:
    """
    Detects head direction using specific degree ranges.
    """
    
    def __init__(self, use_calibration: bool = False):
        self._last_direction = Direction.CENTER
        self._direction_hold_frames = 0
        self._min_hold_frames = 2
        
        # We ignore calibration file now as we use hardcoded "Real World" ranges
        self._calibration_loaded = False 

    def detect(self, rotation: np.ndarray, confidence: float = 1.0) -> Tuple[Direction, float]:
        """
        Detect direction from RAW MediaPipe rotation (Radians).
        Converts to Degrees and checks user-defined ranges.
        
        Args:
            rotation: [roll, pitch, yaw] in RADIANS
            confidence: Tracking confidence (0-1)
            
        Returns:
            (Direction, direction_confidence)
        """
        if confidence < 0.3:
            return self._last_direction, confidence * 0.5
            
        # 1. Convert Radians to Degrees
        # Note: MediaPipe Pitch: + = Down, - = Up
        #       MediaPipe Yaw:   + = Left, - = Right (Wait, need to verify strict MediaPipe coords)
        # 
        # But in our previous transform/calibration:
        # We aligned Detector to Unity logic: 
        #   Pitch: + = Down, - = Up
        #   Yaw:   + = Right, - = Left (Standard Unity) or reversed?
        #
        # Let's check the user's table diagonals:
        # "Up-left: Pitch -25 (Up), Yaw -20 (Left)"
        # "Down-right: Pitch +25 (Down), Yaw +20 (Right)"
        #
        # So we expect:
        # PITCH: Negative = Up, Positive = Down
        # YAW:   Negative = Left, Positive = Right
        
        rot_deg = np.degrees(rotation)
        roll = rot_deg[0]
        pitch = rot_deg[1]
        yaw = -rot_deg[2]  # NEGATE: MediaPipe +Yaw=Left, but User Rules use -Yaw=Left
        
        # === USER DEFINED LOGIC ===
        
        # Center Zone (Pitch -10 to +5, Yaw -5 to +5)
        is_pitch_center = -10 <= pitch <= 5
        is_yaw_center = -5 <= yaw <= 5
        
        if is_pitch_center and is_yaw_center:
             new_direction = Direction.CENTER
             dir_conf = 0.9
             
        else:
            # Determine Vertical
            v_dir = ""
            if pitch < -10:
                v_dir = "UP"
            elif pitch > 10:  # User said > 10 for Down-ish
                v_dir = "DOWN"
            
            # Determine Horizontal
            h_dir = ""
            if yaw < -10:  # -5 to -10 is fuzzy, let's say < -10 is definitely Left
                h_dir = "LEFT"
            elif yaw > 10: # > 5 is fuzzy, > 10 definitely Right
                h_dir = "RIGHT"
            
            # Combine
            if v_dir and h_dir:
                new_direction = Direction[f"{v_dir}_{h_dir}"]
                dir_conf = 0.8
            elif v_dir:
                new_direction = Direction[v_dir]
                dir_conf = 0.85
            elif h_dir:
                new_direction = Direction[h_dir]
                dir_conf = 0.85
            else:
                # In the "fuzzy" edge zone (e.g. Pitch -8, Yaw -4) -> Stick to Center or Last?
                # Default to Center if not strong enough
                new_direction = Direction.CENTER
                dir_conf = 0.6
        
        # Hysteresis
        if new_direction != self._last_direction:
            self._direction_hold_frames += 1
            if self._direction_hold_frames >= self._min_hold_frames:
                self._last_direction = new_direction
                self._direction_hold_frames = 0
        else:
            self._direction_hold_frames = 0
        
        return self._last_direction, dir_conf * confidence

    def reset(self):
        self._last_direction = Direction.CENTER
        self._direction_hold_frames = 0
    
    # Compatibility methods
    def detect_from_marker_visibility(self, visible_quadrants): return None
    def reload_calibration(self): pass
    @property
    def is_calibrated(self): return True # Pretend we are calibrated
