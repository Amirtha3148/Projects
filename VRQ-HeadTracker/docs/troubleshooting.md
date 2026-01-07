# Troubleshooting Guide

## Connection Issues

### Python WebSocket won't start
- Check port 8765 isn't in use: `netstat -ano | findstr 8765`
- Try different port in `settings.py`

### Unity can't connect
- Ensure Python is running first
- Check firewall settings
- Verify URL matches (`ws://localhost:8765`)

## Camera Issues

### Camera not detected
- Check camera index in `settings.py`
- Try different indices (0, 1, 2...)
- Ensure camera isn't used by another app

### Low FPS
- Reduce resolution in `settings.py`
- Close other camera-using apps
- Check CPU usage

## Tracking Issues

### Jittery tracking
- Improve lighting conditions
- Adjust Kalman filter noise in `settings.py`
- Increase smoothing in Unity

### Marker not detected
- Ensure marker is fully visible
- Check marker size (minimum 10cm)
- Improve lighting on marker
- Avoid shiny/reflective surfaces

### Face not detected
- Look directly at laptop camera
- Improve face lighting
- Check MediaPipe confidence thresholds

## Unity Issues

### Extreme camera movement
- Reduce sensitivity in CameraController
- Increase smoothing values
- Check coordinate mapping in transform.py

### Delayed response
- Check network latency
- Reduce smoothing for quicker response
- Ensure consistent FPS on Python side
