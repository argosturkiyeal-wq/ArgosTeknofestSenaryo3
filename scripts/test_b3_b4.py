"""
Test script for point-in-polygon test and foot-point rule verification.
"""

import sys
from pathlib import Path

# Add repo root to python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import (
    load_zones,
    get_foot_point,
    is_point_in_polygon,
    check_zone_violation,
    check_all_zones_violations,
)


def test_foot_point_calculation():
    print("Testing foot point calculation...")
    # Bbox: (xmin, ymin, xmax, ymax) = (0.2, 0.1, 0.4, 0.5)
    bbox = (0.2, 0.1, 0.4, 0.5)
    foot_pt = get_foot_point(bbox)
    print(f"Bbox {bbox} -> Foot Point: {foot_pt}")
    assert foot_pt == (0.3, 0.5), f"Expected (0.3, 0.5), got {foot_pt}"
    print("[OK] Foot point calculation test passed!\n")


def test_point_in_polygon():
    print("Testing cv2.pointPolygonTest...")
    poly = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.6), (0.1, 0.6)]

    pt_inside = (0.2, 0.3)
    pt_outside = (0.8, 0.8)

    assert is_point_in_polygon(pt_inside, poly) is True, "Point should be inside"
    assert is_point_in_polygon(pt_outside, poly) is False, "Point should be outside"
    print("[OK] Point-in-polygon test passed!\n")


def test_zone_violations():
    print("Testing zone violation logic...")
    zones = load_zones(REPO_ROOT / "zones.json")
    zone_01 = zones[0]  # Yasakli bolge, forbidden: ["person"]

    # Case 1: Person inside zone_01 -> Should trigger forbidden_class violation
    det_person_in = {
        "label": "person",
        "bbox": (0.15, 0.2, 0.35, 0.5),  # Foot point: (0.25, 0.5) -> Inside zone_01
        "helmet": False,
    }

    # Case 2: Person outside zone_01 -> No violation
    det_person_out = {
        "label": "person",
        "bbox": (0.7, 0.7, 0.8, 0.9),  # Foot point: (0.75, 0.9) -> Outside zone_01
        "helmet": False,
    }

    viol1 = check_zone_violation(det_person_in, zone_01)
    viol2 = check_zone_violation(det_person_out, zone_01)

    assert viol1 is not None, "Person inside forbidden zone should trigger violation"
    assert viol1["violation_type"] == "forbidden_class"
    assert viol2 is None, "Person outside zone should not trigger violation"

    print(f"Violation Message: {viol1['message']}")
    print("[OK] Zone violation test passed!\n")


if __name__ == "__main__":
    test_foot_point_calculation()
    test_point_in_polygon()
    test_zone_violations()
    print("SUCCESS: All zone violation tests passed cleanly!")
