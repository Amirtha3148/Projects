using UnityEngine;

namespace VRQHeadTracker
{
    /// <summary>
    /// Debug overlay showing connection status, pose data, and DIRECTION.
    /// Uses OnGUI for simplicity (no UI package dependency).
    /// </summary>
    public class DebugOverlay : MonoBehaviour
    {
        [Header("Settings")]
        [SerializeField] private bool showOverlay = true;
        [SerializeField] private int fontSize = 14;
        [SerializeField] private bool showDirectionLarge = true;
        
        private HeadTrackingManager manager;
        private GUIStyle boxStyle;
        private GUIStyle labelStyle;
        private GUIStyle connectedStyle;
        private GUIStyle disconnectedStyle;
        private GUIStyle directionStyle;
        private bool stylesInitialized;
        
        private void Awake()
        {
            manager = FindObjectOfType<HeadTrackingManager>();
        }
        
        private void InitStyles()
        {
            if (stylesInitialized) return;
            
            boxStyle = new GUIStyle(GUI.skin.box);
            Texture2D bgTex = new Texture2D(1, 1);
            bgTex.SetPixel(0, 0, new Color(0, 0, 0, 0.85f));
            bgTex.Apply();
            boxStyle.normal.background = bgTex;
            
            labelStyle = new GUIStyle(GUI.skin.label);
            labelStyle.fontSize = fontSize;
            labelStyle.normal.textColor = Color.white;
            
            connectedStyle = new GUIStyle(labelStyle);
            connectedStyle.normal.textColor = Color.green;
            
            disconnectedStyle = new GUIStyle(labelStyle);
            disconnectedStyle.normal.textColor = Color.red;
            
            directionStyle = new GUIStyle(labelStyle);
            directionStyle.fontSize = 28;
            directionStyle.fontStyle = FontStyle.Bold;
            directionStyle.alignment = TextAnchor.MiddleCenter;
            
            stylesInitialized = true;
        }
        
        private void OnGUI()
        {
            if (!showOverlay) return;
            
            InitStyles();
            
            float width = 300;
            float height = showDirectionLarge ? 180 : 130;
            Rect box = new Rect(10, 10, width, height);
            
            GUI.Box(box, "", boxStyle);
            
            float y = 15;
            float x = 15;
            float lineHeight = 22;
            
            // Connection status
            bool connected = manager != null && manager.IsConnected;
            string statusText = connected ? "Status: Connected ✓" : "Status: Disconnected ✗";
            GUIStyle statusStyle = connected ? connectedStyle : disconnectedStyle;
            GUI.Label(new Rect(x, y, width - 20, 20), statusText, statusStyle);
            y += lineHeight;
            
            // Direction display (LARGE)
            if (showDirectionLarge && manager != null && manager.LastPose != null)
            {
                var p = manager.LastPose;
                string dir = p.GetDirection();
                float dirConf = p.direction_confidence;
                
                // Color based on confidence
                if (dirConf > 0.6f)
                    directionStyle.normal.textColor = Color.green;
                else if (dirConf > 0.4f)
                    directionStyle.normal.textColor = Color.yellow;
                else
                    directionStyle.normal.textColor = new Color(1f, 0.6f, 0.2f); // Orange
                
                // Draw direction with arrow
                string dirDisplay = GetDirectionWithArrow(dir);
                GUI.Label(new Rect(x, y, width - 20, 40), dirDisplay, directionStyle);
                y += 45;
                
                // Direction confidence
                GUI.Label(new Rect(x, y, width - 20, 20), 
                    $"Direction Confidence: {dirConf:P0}", labelStyle);
                y += lineHeight;
            }
            
            // Pose data
            if (manager != null && manager.LastPose != null)
            {
                var p = manager.LastPose;
                GUI.Label(new Rect(x, y, width - 20, 20), 
                    $"Rot: P:{p.pitch:F1}° Y:{p.yaw:F1}° R:{p.roll:F1}°", labelStyle);
                y += lineHeight;
                
                GUI.Label(new Rect(x, y, width - 20, 20),
                    $"Confidence: {p.confidence:P0}", labelStyle);
            }
            else
            {
                GUI.Label(new Rect(x, y, width - 20, 20), "Waiting for data...", labelStyle);
                y += lineHeight * 2;
            }
            y += lineHeight;
            
            // FPS
            if (manager != null)
            {
                GUI.Label(new Rect(x, y, width - 20, 20),
                    $"FPS: {manager.CurrentFPS:F0} | Updates/s: {manager.PoseUpdatesPerSecond}", labelStyle);
            }
        }
        
        /// <summary>
        /// Get direction text with a Unicode arrow.
        /// </summary>
        private string GetDirectionWithArrow(string direction)
        {
            switch (direction)
            {
                case "UP": return "↑ UP";
                case "DOWN": return "↓ DOWN";
                case "LEFT": return "← LEFT";
                case "RIGHT": return "→ RIGHT";
                case "UP_LEFT": return "↖ UP-LEFT";
                case "UP_RIGHT": return "↗ UP-RIGHT";
                case "DOWN_LEFT": return "↙ DOWN-LEFT";
                case "DOWN_RIGHT": return "↘ DOWN-RIGHT";
                case "CENTER": 
                default: return "● CENTER";
            }
        }
        
        public void SetVisible(bool visible)
        {
            showOverlay = visible;
        }
    }
}
