using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace VRQHeadTracker
{
    /// <summary>
    /// WebSocket client for receiving pose data from Python backend.
    /// </summary>
    public class WebSocketClient : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string serverAddress = "localhost";
        [SerializeField] private int serverPort = 8765;
        [SerializeField] private float reconnectDelay = 2.0f;
        
        // Events
        public event Action<PoseData> OnPoseReceived;
        public event Action OnConnected;
        public event Action OnDisconnected;
        
        // State
        private ClientWebSocket webSocket;
        private CancellationTokenSource cancellationSource;
        private ConcurrentQueue<string> messageQueue = new ConcurrentQueue<string>();
        private bool isConnecting = false;
        
        public bool IsConnected => webSocket?.State == WebSocketState.Open;
        
        private void Start()
        {
            ConnectAsync();
        }
        
        private void Update()
        {
            // Process messages on main thread
            while (messageQueue.TryDequeue(out string message))
            {
                ProcessMessage(message);
            }
        }
        
        private void OnDestroy()
        {
            Disconnect();
        }
        
        private async void ConnectAsync()
        {
            if (isConnecting) return;
            isConnecting = true;
            
            cancellationSource = new CancellationTokenSource();
            
            while (!cancellationSource.Token.IsCancellationRequested)
            {
                try
                {
                    webSocket = new ClientWebSocket();
                    Uri uri = new Uri($"ws://{serverAddress}:{serverPort}");
                    
                    Debug.Log($"[WebSocket] Connecting to {uri}...");
                    await webSocket.ConnectAsync(uri, cancellationSource.Token);
                    
                    Debug.Log("[WebSocket] Connected!");
                    OnConnected?.Invoke();
                    
                    // Start receiving
                    await ReceiveLoop();
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[WebSocket] Connection failed: {e.Message}");
                    OnDisconnected?.Invoke();
                }
                
                if (!cancellationSource.Token.IsCancellationRequested)
                {
                    Debug.Log($"[WebSocket] Reconnecting in {reconnectDelay}s...");
                    await Task.Delay((int)(reconnectDelay * 1000));
                }
            }
            
            isConnecting = false;
        }
        
        private async Task ReceiveLoop()
        {
            byte[] buffer = new byte[4096];
            
            while (webSocket.State == WebSocketState.Open && !cancellationSource.Token.IsCancellationRequested)
            {
                try
                {
                    WebSocketReceiveResult result = await webSocket.ReceiveAsync(
                        new ArraySegment<byte>(buffer), cancellationSource.Token);
                    
                    if (result.MessageType == WebSocketMessageType.Text)
                    {
                        string message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                        messageQueue.Enqueue(message);
                    }
                    else if (result.MessageType == WebSocketMessageType.Close)
                    {
                        Debug.Log("[WebSocket] Server closed connection");
                        break;
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[WebSocket] Receive error: {e.Message}");
                    break;
                }
            }
            
            OnDisconnected?.Invoke();
        }
        
        private void ProcessMessage(string json)
        {
            try
            {
                PoseData pose = PoseData.FromJson(json);
                if (pose != null && pose.IsValid())
                {
                    OnPoseReceived?.Invoke(pose);
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[WebSocket] Parse error: {e.Message}");
            }
        }
        
        public async void SendCommand(string command)
        {
            if (!IsConnected) return;
            
            try
            {
                byte[] data = Encoding.UTF8.GetBytes(command);
                await webSocket.SendAsync(new ArraySegment<byte>(data), 
                    WebSocketMessageType.Text, true, CancellationToken.None);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[WebSocket] Send error: {e.Message}");
            }
        }
        
        public void Disconnect()
        {
            cancellationSource?.Cancel();
            
            if (webSocket != null && webSocket.State == WebSocketState.Open)
            {
                try
                {
                    webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None);
                }
                catch { }
            }
            
            webSocket?.Dispose();
            webSocket = null;
        }
    }
}
