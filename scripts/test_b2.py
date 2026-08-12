"""
Test script for UI Zone Editor & Canvas Data Structures.
"""

import sys
from pathlib import Path

# Add repo root to python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import Zone, ZoneRule, load_zones, save_zones
from ui.zone_editor import get_sample_background_image


def test_canvas_structs():
    print("Testing Canvas Data Structure and Image Loader...")

    # Test 1: Background image loader
    img = get_sample_background_image(None)
    assert img is not None and img.shape == (480, 640, 3), f"Unexpected image shape: {img.shape if img is not None else None}"
    print("[OK] Default background image created successfully (640x480).")

    # Test 2: Polygon normalization & Zone creation from drawn points
    # Simulated drawn canvas points on 640x480 image
    drawn_pixel_pts = [(64, 48), (256, 48), (256, 288), (64, 288)]
    norm_pts = [(round(x / 640.0, 4), round(y / 480.0, 4)) for x, y in drawn_pixel_pts]

    rule = ZoneRule(
        allowed_classes=["person"],
        forbidden_classes=["forklift"],
        helmet_required=True,
        vest_required=False,
    )

    drawn_zone = Zone(
        zone_id="zone_canvas_01",
        name="CANVAS ILE CIZILEN BOLGE",
        type="yasakli",
        polygon=norm_pts,
        rules=rule,
    )

    assert drawn_zone.validate() is True, "Drawn zone polygon should be valid"
    assert drawn_zone.polygon == [(0.1, 0.1), (0.4, 0.1), (0.4, 0.6), (0.1, 0.6)]
    print(f"[OK] Polygon normalized points verified: {drawn_zone.polygon}")

    print("SUCCESS: Canvas structure tests passed!")


if __name__ == "__main__":
    test_canvas_structs()
