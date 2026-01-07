# Setup Guide

Complete installation and setup instructions for VRQ-HeadTracker.

## Prerequisites

### Hardware
- Laptop with built-in webcam
- External USB webcam (for wearable camera)
- Printer (to print ArUco marker)
- Head mount for external camera (optional: can use headband/tape)

### Software
- Python 3.8 or higher
- Unity 2022.3.62f3 or higher
- Git (optional)

## Python Environment Setup

### Step 1: Create Virtual Environment (Recommended)

```bash
# Navigate to project directory
cd d:\Projects\VRQ-HeadTracker

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
cd python
pip install -r requirements.txt
```

This installs:
- OpenCV with ArUco support
- MediaPipe for face mesh
- NumPy and SciPy for calculations
- websockets for Unity communication

### Step 3: Test Installation

```bash
python -c "import cv2; import mediapipe; print('All dependencies OK')"
```

## Camera Setup

### Identifying Camera Indices

Run this to list available cameras:

```bash
python -c "
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f'Camera {i}: Available')
        cap.release()
"
```

### Configure Camera Indices

Edit `python/config/settings.py`:

```python
LAPTOP_CAMERA_INDEX = 0      # Usually 0 for built-in
WEARABLE_CAMERA_INDEX = 1    # Usually 1 for USB camera
```

## Calibration (Optional but Recommended)

For best accuracy, calibrate your cameras:

### Generate Checkerboard Pattern

```bash
cd python
python calibration/calibrate_camera.py --generate-pattern
```

Print the generated pattern from `calibration_patterns/checkerboard.png`.

### Calibrate Laptop Camera

```bash
python calibration/calibrate_camera.py --camera 0 --output laptop_camera_calibration.json
```

Follow on-screen instructions to capture 15 images of the checkerboard.

### Calibrate Wearable Camera

```bash
python calibration/calibrate_camera.py --camera 1 --output wearable_camera_calibration.json
```

## Unity Project Setup

### Step 1: Open in Unity Hub

1. Open Unity Hub
2. Click "Add" or "Open"
3. Navigate to `d:\Projects\VRQ-HeadTracker\unity\VRHeadTracker`
4. Open with Unity 2022.3.62f3

### Step 2: Project Configuration

The project should work out of the box. If you see errors:

1. Go to **Edit → Project Settings → Player**
2. Under **Other Settings**, ensure "Api Compatibility Level" is set to ".NET 4.x" or ".NET Standard 2.1"

### Step 3: Create Scene (If Not Present)

If no scene exists:

1. Create new scene: **File → New Scene**
2. Create empty GameObject named "HeadTracker"
3. Add components:
   - WebSocketClient
   - CameraController
   - HeadTrackingManager
   - DebugOverlay

4. Create empty child "DebugUI"
5. Add DebugOverlay script to it

## Running the System

### Start Order

1. **Start Python first** (must be running before Unity):
   ```bash
   cd python
   python main.py
   ```

2. Wait for "WebSocket Server started" message

3. **Start Unity**:
   - Open the scene
   - Press Play

### Verify Connection

- Python console shows "Client connected"
- Unity debug overlay shows "Connected ✓"
- Moving your head should move the Unity camera

## Configuration Options

### Python Settings (`config/settings.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `ARUCO_MARKER_SIZE_METERS` | 0.10 | Physical marker size |
| `WEBSOCKET_PORT` | 8765 | Server port |
| `KALMAN_PROCESS_NOISE_*` | varies | Smoothing parameters |

### Unity Inspector Settings

| Component | Setting | Default | Description |
|-----------|---------|---------|-------------|
| WebSocketClient | Server URL | ws://localhost:8765 | Python server address |
| CameraController | Position Sensitivity | 1.0 | Movement scale |
| CameraController | Rotation Sensitivity | 1.0 | Rotation scale |
| CameraController | Position Smoothing | 0.8 | Smoothness (0-1) |

## Next Steps

- [Marker Printing Guide](marker_guide.md)
- [Troubleshooting](troubleshooting.md)
