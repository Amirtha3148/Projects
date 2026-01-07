"""
Pose Kalman Filter

Implements a standard 12-state Kalman filter for smoothing and projecting 6-DoF pose.
State: [x, y, z, roll, pitch, yaw, vx, vy, vz, v_roll, v_pitch, v_yaw]
"""

import numpy as np
from typing import Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


class PoseKalmanFilter:
    """Standard Kalman filter for 6-DoF pose estimation."""
    
    STATE_DIM = 12
    MEAS_DIM = 6
    
    def __init__(self, dt: float = 1.0 / 30.0):
        self.dt = dt
        self.x = np.zeros(self.STATE_DIM)
        self.P = np.eye(self.STATE_DIM) * settings.KALMAN_INITIAL_UNCERTAINTY
        
        # Process Noise Covariance (Q)
        self.Q = np.zeros((self.STATE_DIM, self.STATE_DIM))
        self.Q[0:3, 0:3] = np.eye(3) * settings.KALMAN_PROCESS_NOISE_POSITION ** 2
        self.Q[3:6, 3:6] = np.eye(3) * settings.KALMAN_PROCESS_NOISE_ROTATION ** 2
        self.Q[6:9, 6:9] = np.eye(3) * settings.KALMAN_PROCESS_NOISE_VELOCITY ** 2
        self.Q[9:12, 9:12] = np.eye(3) * settings.KALMAN_PROCESS_NOISE_ANGULAR_VEL ** 2
        
        # Measurement Noise Covariance (R) - can be adaptive
        self.R = np.zeros((self.MEAS_DIM, self.MEAS_DIM))
        self.R[0:3, 0:3] = np.eye(3) * settings.KALMAN_MEASUREMENT_NOISE_POSITION ** 2
        self.R[3:6, 3:6] = np.eye(3) * settings.KALMAN_MEASUREMENT_NOISE_ROTATION ** 2
        
        # State Transition Matrix (F)
        self.F = np.eye(self.STATE_DIM)
        self.F[0, 6] = self.F[1, 7] = self.F[2, 8] = self.dt
        self.F[3, 9] = self.F[4, 10] = self.F[5, 11] = self.dt
        
        # Measurement Matrix (H)
        self.H = np.zeros((self.MEAS_DIM, self.STATE_DIM))
        self.H[:6, :6] = np.eye(6)
        
        self.I = np.eye(self.STATE_DIM)
        self._initialized = False
    
    def initialize(self, position: np.ndarray, rotation: np.ndarray) -> None:
        self.x[:3] = position
        self.x[3:6] = rotation
        self.x[6:] = 0
        self.P = np.eye(self.STATE_DIM) * settings.KALMAN_INITIAL_UNCERTAINTY
        self._initialized = True
        
    def predict(self, dt: float = None) -> Tuple[np.ndarray, np.ndarray]:
        if dt is not None and dt != self.dt:
            self.dt = dt
            self.F[0, 6] = self.F[1, 7] = self.F[2, 8] = self.dt
            self.F[3, 9] = self.F[4, 10] = self.F[5, 11] = self.dt
            
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        return self.x[:3].copy(), self.x[3:6].copy()
    
    def update(self, position: np.ndarray, rotation: np.ndarray, 
               confidence: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        if not self._initialized:
            self.initialize(position, rotation)
            return position.copy(), rotation.copy()
        
        z = np.concatenate([position, rotation])
        
        # Adapt measurement noise based on confidence
        # Lower confidence = higher noise = trust measurement less
        R_adaptive = self.R.copy()
        if confidence < 1.0:
            scale = 1.0 + (1.0 - confidence) * 10.0
            R_adaptive *= scale
        
        y = z - self.H @ self.x
        
        # Handle angle wrapping for rotation errors
        y[3:6] = self._wrap_angles(y[3:6])
        
        S = self.H @ self.P @ self.H.T + R_adaptive
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        self.x = self.x + K @ y
        self.x[3:6] = self._wrap_angles(self.x[3:6]) # Wrap state angles
        self.P = (self.I - K @ self.H) @ self.P
        
        return self.x[:3].copy(), self.x[3:6].copy()
    
    def _wrap_angles(self, angles: np.ndarray) -> np.ndarray:
        return (angles + np.pi) % (2 * np.pi) - np.pi
    
    def get_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.x[:3].copy(), self.x[3:6].copy()
    
    def reset(self) -> None:
        self.x = np.zeros(self.STATE_DIM)
        self.P = np.eye(self.STATE_DIM) * settings.KALMAN_INITIAL_UNCERTAINTY
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
