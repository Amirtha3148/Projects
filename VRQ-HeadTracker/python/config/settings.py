"""
VRQ-HeadTracker Settings

Central configuration for all tracking parameters.
"""

from pathlib import Path

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# CAMERA SETTINGS
# =============================================================================
LAPTOP_CAMERA_INDEX = 0
WEARABLE_CAMERA_INDEX = 1
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# =============================================================================
# CALIBRATION SETTINGS
# =============================================================================
CHECKERBOARD_ROWS = 6       # Number of inner corners (not squares)
CHECKERBOARD_COLS = 9       # Number of inner corners
CHECKERBOARD_SQUARE_SIZE = 0.025  # Square size in meters (2.5cm)
CALIBRATION_IMAGES_COUNT = 15     # Number of images to capture

# =============================================================================
# ARUCO MARKER SETTINGS
# =============================================================================
ARUCO_DICTIONARY = "DICT_4X4_50"
ARUCO_MARKER_SIZE_METERS = 0.05  # 5cm marker

# =============================================================================
# WEBSOCKET SETTINGS
# =============================================================================
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765

# =============================================================================
# KALMAN FILTER SETTINGS
# =============================================================================
KALMAN_INITIAL_UNCERTAINTY = 1.0
KALMAN_PROCESS_NOISE_POSITION = 0.01
KALMAN_PROCESS_NOISE_ROTATION = 0.02
KALMAN_PROCESS_NOISE_VELOCITY = 0.1
KALMAN_PROCESS_NOISE_ANGULAR_VEL = 0.2
KALMAN_MEASUREMENT_NOISE_POSITION = 0.02
KALMAN_MEASUREMENT_NOISE_ROTATION = 0.03

# =============================================================================
# SENSOR FUSION SETTINGS
# =============================================================================
LAPTOP_ORIENTATION_WEIGHT = 0.7
WEARABLE_POSITION_WEIGHT = 0.8
RECOVERY_SMOOTHING_FRAMES = 10
FORWARD_BASELINE_FRAMES = 30
CONFIDENCE_SMOOTHING_FACTOR = 0.3

# =============================================================================
# MEDIAPIPE SETTINGS
# =============================================================================
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5
FACE_DETECTION_CONFIDENCE = 0.5
FACE_TRACKING_CONFIDENCE = 0.5

# =============================================================================
# SMOOTHING SETTINGS
# =============================================================================
POSITION_SMOOTHING_FACTOR = 0.7
ROTATION_SMOOTHING_FACTOR = 0.7
ROTATION_DEAD_ZONE_DEGREES = 3.0
ROLL_DEAD_ZONE_DEGREES = 8.0

# =============================================================================
# COORDINATE TRANSFORM
# =============================================================================
POSITION_SCALE_FACTOR = 1.0
ROTATION_SCALE_FACTOR = 1.0
