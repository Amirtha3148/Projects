# VRQ-HeadTracker

A complete, production-ready **dual-camera 6-DoF VR head tracking system** that provides immersive VR-like camera movement using two webcams, sensor fusion, and Unity integration.

## Features

- **Dual Camera Tracking**: Laptop (MediaPipe) + Wearable (ArUco)
- **Sensor Fusion with Kalman Filtering**
- **Real-time Unity Integration** via WebSocket

## Quick Start

```bash
# Install dependencies
cd python
pip install -r requirements.txt

# Run Python tracker
python main.py

# Open Unity project and press Play
```

## Controls

| Key | Action |
|-----|--------|
| R | Recenter |
| B | Reset baseline |
| S | Toggle stats |
| Q | Quit |

## Documentation

- [Setup Guide](setup_guide.md)
- [Marker Guide](marker_guide.md)
- [Troubleshooting](troubleshooting.md)
