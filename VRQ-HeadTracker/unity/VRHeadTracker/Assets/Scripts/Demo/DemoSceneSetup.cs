using UnityEngine;

namespace VRQHeadTracker
{
    /// <summary>
    /// Creates a VR-like demo environment for testing head tracking.
    /// Attach to an empty GameObject and press Play.
    /// </summary>
    public class DemoSceneSetup : MonoBehaviour
    {
        [Header("Player Settings")]
        [SerializeField] private float playerHeight = 1.7f;
        
        [Header("Environment")]
        [SerializeField] private float roomSize = 20f;
        [SerializeField] private Color floorColor = new Color(0.25f, 0.25f, 0.3f);
        
        private void Start()
        {
            SetupCamera();
            SetupLighting();
            CreateEnvironment();
            Debug.Log($"[DemoScene] Created. Player height: {playerHeight}m. Press R to recenter.");
        }
        
        private void SetupCamera()
        {
            // Get or create main camera
            Camera mainCam = Camera.main;
            if (mainCam == null)
            {
                GameObject camObj = new GameObject("Main Camera");
                camObj.tag = "MainCamera";
                mainCam = camObj.AddComponent<Camera>();
            }
            
            // Position at player eye level, looking forward
            mainCam.transform.position = new Vector3(0, playerHeight, 0);
            mainCam.transform.rotation = Quaternion.identity;
            mainCam.nearClipPlane = 0.1f;
            mainCam.farClipPlane = 100f;
            mainCam.clearFlags = CameraClearFlags.SolidColor;
            mainCam.backgroundColor = new Color(0.1f, 0.1f, 0.15f);
            
            // Add head tracking components
            AddComponent<WebSocketClient>(mainCam.gameObject);
            AddComponent<CameraController>(mainCam.gameObject);
            AddComponent<HeadTrackingManager>(mainCam.gameObject);
            
            // Add debug overlay
            if (FindObjectOfType<DebugOverlay>() == null)
            {
                new GameObject("DebugOverlay").AddComponent<DebugOverlay>();
            }
        }
        
        private void SetupLighting()
        {
            RenderSettings.ambientLight = new Color(0.2f, 0.2f, 0.25f);
            
            GameObject light = new GameObject("Directional Light");
            Light l = light.AddComponent<Light>();
            l.type = LightType.Directional;
            l.color = Color.white;
            l.intensity = 1f;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);
        }
        
        private void CreateEnvironment()
        {
            // Floor
            GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Floor";
            floor.transform.localScale = new Vector3(roomSize / 10f, 1, roomSize / 10f);
            floor.GetComponent<Renderer>().material.color = floorColor;
            
            // Reference objects at eye level (for parallax effect)
            Color[] colors = { Color.red, Color.green, Color.blue, Color.yellow, Color.cyan, Color.magenta };
            
            for (int i = 0; i < 8; i++)
            {
                float angle = i * 45f * Mathf.Deg2Rad;
                float radius = 4f;
                float height = playerHeight + (i % 2 == 0 ? -0.3f : 0.3f);
                
                Vector3 pos = new Vector3(Mathf.Sin(angle) * radius, height, Mathf.Cos(angle) * radius);
                
                GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.name = $"Cube_{i}";
                cube.transform.position = pos;
                cube.transform.localScale = Vector3.one * 0.5f;
                cube.GetComponent<Renderer>().material.color = colors[i % colors.Length];
                
                // Add rotation
                Rotator rot = cube.AddComponent<Rotator>();
                rot.speed = new Vector3(20, 40, 0);
            }
            
            // Front reference point
            GameObject frontRef = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            frontRef.name = "FrontReference";
            frontRef.transform.position = new Vector3(0, playerHeight, 5f);
            frontRef.transform.localScale = Vector3.one * 0.3f;
            frontRef.GetComponent<Renderer>().material.color = Color.white;
            
            // Ground boxes for depth reference
            for (int x = -2; x <= 2; x++)
            {
                for (int z = 1; z <= 3; z++)
                {
                    if (x == 0 && z == 1) continue;
                    
                    GameObject box = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    box.name = $"GroundBox_{x}_{z}";
                    box.transform.position = new Vector3(x * 2f, 0.25f, z * 2f);
                    box.transform.localScale = new Vector3(0.8f, 0.5f, 0.8f);
                    box.GetComponent<Renderer>().material.color = Color.Lerp(Color.gray, Color.white, 0.3f);
                }
            }
        }
        
        private void AddComponent<T>(GameObject obj) where T : Component
        {
            if (obj.GetComponent<T>() == null)
                obj.AddComponent<T>();
        }
    }
    
    /// <summary>
    /// Simple rotation animation component.
    /// </summary>
    public class Rotator : MonoBehaviour
    {
        public Vector3 speed = new Vector3(0, 30, 0);
        
        private void Update()
        {
            transform.Rotate(speed * Time.deltaTime);
        }
    }
}
