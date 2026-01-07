"""
ArUco Marker Generator

Utility to generate ArUco markers for the head tracking system.
"""

import cv2
import numpy as np
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


def generate_marker(
    marker_id: int = 0,
    size_px: int = 400,
    dictionary_type: str = None,
    output_path: str = None
) -> np.ndarray:
    """Generate an ArUco marker image."""
    
    dict_mapping = {
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
        "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    }
    
    dict_type = dictionary_type or settings.ARUCO_DICTIONARY
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        dict_mapping.get(dict_type, cv2.aruco.DICT_4X4_50)
    )
    
    marker_image = np.zeros((size_px, size_px), dtype=np.uint8)
    cv2.aruco.generateImageMarker(aruco_dict, marker_id, size_px, marker_image, 1)
    
    # Add white border for better detection
    border_size = size_px // 8
    bordered = np.ones((size_px + 2*border_size, size_px + 2*border_size), dtype=np.uint8) * 255
    bordered[border_size:border_size+size_px, border_size:border_size+size_px] = marker_image
    
    if output_path:
        cv2.imwrite(output_path, bordered)
        print(f"[MARKER] Saved marker {marker_id} to: {output_path}")
    
    return bordered


def main():
    parser = argparse.ArgumentParser(description="Generate ArUco markers")
    parser.add_argument("--id", "-i", type=int, default=0, help="Marker ID")
    parser.add_argument("--size", "-s", type=int, default=400, help="Size in pixels")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output path")
    
    args = parser.parse_args()
    
    output_path = args.output
    if output_path is None:
        settings.MARKERS_DIR.mkdir(exist_ok=True)
        output_path = str(settings.MARKERS_DIR / f"marker_{args.id}.png")
    
    generate_marker(args.id, args.size, output_path=output_path)


if __name__ == "__main__":
    main()
