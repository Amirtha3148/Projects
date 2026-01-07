using System;
using UnityEngine;

namespace VRQHeadTracker
{
    /// <summary>
    /// Pose data received from Python backend via WebSocket.
    /// Now includes direction detection.
    /// </summary>
    [Serializable]
    public class PoseData
    {
        // Position (in Unity units)
        public float x;
        public float y;
        public float z;
        
        // Rotation (in degrees, Unity convention: X=pitch, Y=yaw, Z=roll)
        public float roll;
        public float pitch;
        public float yaw;
        
        // Tracking quality
        public float confidence;
        
        // Direction detection (NEW)
        public string direction;  // CENTER, UP, DOWN, LEFT, RIGHT, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT
        public float direction_confidence;
        
        // Timestamp from Python
        public double timestamp;
        
        public static PoseData FromJson(string json)
        {
            return JsonUtility.FromJson<PoseData>(json);
        }
        
        public Vector3 GetPosition()
        {
            return new Vector3(x, y, z);
        }
        
        public Vector3 GetEulerAngles()
        {
            return new Vector3(pitch, yaw, roll);
        }
        
        public Quaternion GetRotation()
        {
            return Quaternion.Euler(pitch, yaw, roll);
        }
        
        public bool IsValid()
        {
            return !float.IsNaN(x) && !float.IsNaN(y) && !float.IsNaN(z) &&
                   !float.IsNaN(pitch) && !float.IsNaN(yaw) && !float.IsNaN(roll) &&
                   confidence > 0.1f;
        }
        
        /// <summary>
        /// Get the detected head direction.
        /// </summary>
        public string GetDirection()
        {
            return string.IsNullOrEmpty(direction) ? "CENTER" : direction;
        }
        
        /// <summary>
        /// Check if direction is a diagonal (combination of two axes).
        /// </summary>
        public bool IsDiagonal()
        {
            return direction != null && direction.Contains("_");
        }
        
        public override string ToString()
        {
            return $"Pos({x:F2},{y:F2},{z:F2}) Rot({pitch:F1}°,{yaw:F1}°,{roll:F1}°) Dir:{GetDirection()} Conf:{confidence:P0}";
        }
    }
    
    /// <summary>
    /// Commands to send to Python backend.
    /// </summary>
    [Serializable]
    public class WebSocketCommand
    {
        public string command;
        
        public static string Recenter()
        {
            return JsonUtility.ToJson(new WebSocketCommand { command = "recenter" });
        }
        
        public static string Reset()
        {
            return JsonUtility.ToJson(new WebSocketCommand { command = "reset" });
        }
        
        public static string Ping()
        {
            return JsonUtility.ToJson(new WebSocketCommand { command = "ping" });
        }
    }
}
