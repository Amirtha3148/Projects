"""
Calibration Adustment Script

Updates the calibration file to fix UP, DOWN, and DIAGONAL values 
while preserving the correct CENTER, LEFT, and RIGHT values.

This applies standard offsets where the original calibration was likely ambiguous.
"""

import json
from pathlib import Path
import numpy as np

def adjust_calibration():
    calib_file = Path("calibration_data/direction_calibration.json")
    
    if not calib_file.exists():
        print("Error: Calibration file not found!")
        return
    
    # Load existing data
    with open(calib_file, 'r') as f:
        data = json.load(f)
    
    print("Loaded existing calibration.")
    
    # Define corrections (in DEGREES, matching your file format)
    # modifying only mean values
    
    corrections = {
        # Fix UP (should be negative pitch)
        "UP": [-25.0, 0.0],
        
        # Fix DOWN (should be positive pitch)
        "DOWN": [25.0, 0.0],
        
        # Fix Diagonals (combinations)
        "UP_LEFT": [-20.0, -25.0],
        "UP_RIGHT": [-20.0, 25.0],
        "DOWN_LEFT": [20.0, -25.0],
        "DOWN_RIGHT": [20.0, 25.0]
    }
    
    updated_count = 0
    
    for name, new_mean in corrections.items():
        if name in data:
            print(f"Updating {name}...")
            # Update mean
            data[name]['mean'] = new_mean
            # Reset std to reasonable default
            data[name]['std'] = [5.0, 5.0]
            # Clear samples to avoid confusion (since we manually set mean)
            data[name]['samples'] = []
            updated_count += 1
    
    # Save back
    with open(calib_file, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"\nSuccess! Updated {updated_count} directions.")
    print("LEFT, RIGHT, and CENTER were preserved.")

if __name__ == "__main__":
    adjust_calibration()
