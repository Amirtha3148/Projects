using UnityEngine;

namespace VRQHeadTracker
{
    /// <summary>
    /// Central manager for head tracking system.
    /// Coordinates WebSocket client and camera controller.
    /// </summary>
    public class HeadTrackingManager : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private WebSocketClient webSocketClient;
        [SerializeField] private CameraController cameraController;
        
        [Header("Controls")]
        [SerializeField] private KeyCode recenterKey = KeyCode.R;
        [SerializeField] private KeyCode resetKey = KeyCode.T;
        
        // Status
        private PoseData lastPose;
        private int poseCount;
        private float poseCountTimer;
        private int posesPerSecond;
        
        public bool IsConnected => webSocketClient != null && webSocketClient.IsConnected;
        public PoseData LastPose => lastPose;
        public int PoseUpdatesPerSecond => posesPerSecond;
        public float CurrentFPS => 1f / Time.deltaTime;
        
        private void Awake()
        {
            // Get components
            if (webSocketClient == null)
                webSocketClient = GetComponent<WebSocketClient>();
            if (cameraController == null)
                cameraController = GetComponent<CameraController>();
        }
        
        private void OnEnable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnPoseReceived += OnPoseReceived;
                webSocketClient.OnConnected += OnConnected;
                webSocketClient.OnDisconnected += OnDisconnected;
            }
        }
        
        private void OnDisable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnPoseReceived -= OnPoseReceived;
                webSocketClient.OnConnected -= OnConnected;
                webSocketClient.OnDisconnected -= OnDisconnected;
            }
        }
        
        private void Update()
        {
            // Handle input
            if (Input.GetKeyDown(recenterKey))
            {
                Recenter();
            }
            if (Input.GetKeyDown(resetKey))
            {
                Reset();
            }
            
            // Track poses per second
            poseCountTimer += Time.deltaTime;
            if (poseCountTimer >= 1f)
            {
                posesPerSecond = poseCount;
                poseCount = 0;
                poseCountTimer = 0f;
            }
        }
        
        private void OnPoseReceived(PoseData pose)
        {
            lastPose = pose;
            poseCount++;
            
            if (cameraController != null)
            {
                cameraController.UpdatePose(pose);
            }
        }
        
        private void OnConnected()
        {
            Debug.Log("[HeadTrackingManager] Connected to Python backend");
        }
        
        private void OnDisconnected()
        {
            Debug.Log("[HeadTrackingManager] Disconnected from Python backend");
        }
        
        public void Recenter()
        {
            if (cameraController != null)
            {
                cameraController.Recenter();
            }
            
            // Also tell Python to recenter
            if (webSocketClient != null && webSocketClient.IsConnected)
            {
                webSocketClient.SendCommand(WebSocketCommand.Recenter());
            }
        }
        
        public void Reset()
        {
            if (cameraController != null)
            {
                cameraController.Reset();
            }
            
            if (webSocketClient != null && webSocketClient.IsConnected)
            {
                webSocketClient.SendCommand(WebSocketCommand.Reset());
            }
        }
    }
}
