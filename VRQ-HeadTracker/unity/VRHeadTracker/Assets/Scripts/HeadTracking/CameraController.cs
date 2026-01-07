using UnityEngine;
using System.Collections.Generic;

namespace VRQHeadTracker
{
    /// <summary>
    /// Controls camera based on Python's direction detection.
    /// Uses reference points for each direction with optional coordinate refinement.
    /// 
    /// Mode:
    /// 1. DIRECTION-BASED (Primary): Uses detected direction (UP, LEFT, etc.)
    /// 2. COORDINATE-REFINED: Blends direction with actual pitch/yaw for smoother movement
    /// </summary>
    public class CameraController : MonoBehaviour
    {
        [Header("Target Camera")]
        [SerializeField] private Camera targetCamera;
        
        [Header("Control Mode")]
        [Tooltip("Use direction only, or blend with coordinates")]
        [SerializeField] private bool useCoordinateRefinement = true;
        [Range(0f, 1f)]
        [SerializeField] private float coordinateInfluence = 0.3f; // 0=direction only, 1=coordinates only
        
        [Header("Reference Points (degrees)")]
        [Tooltip("Reference rotation for each direction")]
        [SerializeField] private DirectionReference[] directionReferences = new DirectionReference[]
        {
            new DirectionReference("CENTER", 0f, 0f),
            new DirectionReference("UP", -25f, 0f),
            new DirectionReference("DOWN", 25f, 0f),
            new DirectionReference("LEFT", 0f, -30f),
            new DirectionReference("RIGHT", 0f, 30f),
            new DirectionReference("UP_LEFT", -20f, -25f),
            new DirectionReference("UP_RIGHT", -20f, 25f),
            new DirectionReference("DOWN_LEFT", 20f, -25f),
            new DirectionReference("DOWN_RIGHT", 20f, 25f),
        };
        
        [Header("Smoothing")]
        [Range(0.1f, 0.95f)]
        [SerializeField] private float smoothing = 0.6f;
        
        [Header("Confidence")]
        [SerializeField] private float minConfidence = 0.3f;
        [SerializeField] private float minDirectionConfidence = 0.4f;
        
        // Runtime
        private Dictionary<string, DirectionReference> directionMap;
        private Vector3 targetRotation;
        private Vector3 currentRotation;
        private float currentConfidence;
        private string currentDirection = "CENTER";
        
        public float CurrentConfidence => currentConfidence;
        public Vector3 CurrentRotation => currentRotation;
        public string CurrentDirection => currentDirection;
        
        [System.Serializable]
        public class DirectionReference
        {
            public string name;
            public float pitch; // X rotation (up/down)
            public float yaw;   // Y rotation (left/right)
            
            public DirectionReference(string name, float pitch, float yaw)
            {
                this.name = name;
                this.pitch = pitch;
                this.yaw = yaw;
            }
            
            public Vector3 ToRotation()
            {
                return new Vector3(pitch, yaw, 0f);
            }
        }
        
        private void Awake()
        {
            if (targetCamera == null)
                targetCamera = Camera.main ?? GetComponent<Camera>();
            
            BuildDirectionMap();
            currentRotation = targetRotation = Vector3.zero;
        }
        
        private void BuildDirectionMap()
        {
            directionMap = new Dictionary<string, DirectionReference>();
            foreach (var dir in directionReferences)
            {
                if (!string.IsNullOrEmpty(dir.name))
                    directionMap[dir.name.ToUpper()] = dir;
            }
        }
        
        private void Update()
        {
            // Smooth interpolation
            float t = 1f - Mathf.Pow(smoothing, Time.deltaTime * 60f);
            currentRotation = Vector3.Lerp(currentRotation, targetRotation, t);
            ApplyToCamera();
        }
        
        /// <summary>
        /// Update camera from Python pose data.
        /// Uses direction as primary control, coordinates for refinement.
        /// </summary>
        public void UpdatePose(PoseData pose)
        {
            if (pose == null)
                return;
            
            currentConfidence = pose.confidence;
            
            if (currentConfidence < minConfidence)
                return;
            
            // Get direction and confidence from Python
            string direction = pose.GetDirection().ToUpper();
            float dirConf = pose.direction_confidence;
            currentDirection = direction;
            
            // Get reference rotation for this direction
            Vector3 directionRotation = Vector3.zero;
            if (dirConf >= minDirectionConfidence && directionMap.TryGetValue(direction, out var dirRef))
            {
                directionRotation = dirRef.ToRotation();
            }
            
            // === CALCULATE TARGET ROTATION ===
            if (useCoordinateRefinement && dirConf >= minDirectionConfidence)
            {
                // Blend direction reference with actual coordinates
                // Direction provides the base, coordinates add refinement
                Vector3 coordRotation = new Vector3(pose.pitch, pose.yaw, 0f);
                
                // Limit coordinate influence based on setting
                Vector3 coordOffset = (coordRotation - directionRotation) * coordinateInfluence;
                targetRotation = directionRotation + coordOffset;
            }
            else if (dirConf >= minDirectionConfidence)
            {
                // Direction only
                targetRotation = directionRotation;
            }
            else
            {
                // Low confidence - move toward center
                targetRotation = Vector3.Lerp(targetRotation, Vector3.zero, 0.1f);
            }
        }
        
        /// <summary>
        /// Get reference rotation for a direction.
        /// </summary>
        public Vector3 GetDirectionReference(string direction)
        {
            if (directionMap.TryGetValue(direction.ToUpper(), out var dirRef))
                return dirRef.ToRotation();
            return Vector3.zero;
        }
        
        /// <summary>
        /// Set reference point for a direction at runtime.
        /// </summary>
        public void SetDirectionReference(string direction, float pitch, float yaw)
        {
            string key = direction.ToUpper();
            if (directionMap.ContainsKey(key))
            {
                directionMap[key].pitch = pitch;
                directionMap[key].yaw = yaw;
                Debug.Log($"[CameraController] Set {key} reference: pitch={pitch}, yaw={yaw}");
            }
        }
        
        public void Recenter()
        {
            targetRotation = Vector3.zero;
            currentRotation = Vector3.zero;
            currentDirection = "CENTER";
            Debug.Log("[CameraController] Recentered");
        }
        
        public void Reset()
        {
            Recenter();
        }
        
        private void ApplyToCamera()
        {
            if (targetCamera == null) return;
            targetCamera.transform.localRotation = Quaternion.Euler(currentRotation);
        }
        
        /// <summary>
        /// Print all direction references (for debugging).
        /// </summary>
        [ContextMenu("Print Direction References")]
        public void PrintDirectionReferences()
        {
            Debug.Log("=== Direction Reference Points ===");
            foreach (var kvp in directionMap)
            {
                Debug.Log($"  {kvp.Key}: Pitch={kvp.Value.pitch}°, Yaw={kvp.Value.yaw}°");
            }
        }
    }
}
