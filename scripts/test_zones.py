"""
Isolated test script for zones loading and validation (Task B1).
"""

import sys
from pathlib import Path

# Add repo root to python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import load_zones, Zone


def test_b1_zones():
    json_path = REPO_ROOT / "zones.json"
    print(f"Testing zones loading from: {json_path}")

    zones = load_zones(json_path)
    print(f"Successfully loaded {len(zones)} zones.\n")

    for z in zones:
        print(f"Zone ID:   {z.zone_id}")
        print(f"Name:      {z.name}")
        print(f"Type:      {z.type}")
        print(f"Points:    {len(z.polygon)} coordinates")
        print(f"Forbidden: {z.rules.forbidden_classes}")
        print(f"Helmet Req:{z.rules.helmet_required}")
        print("-" * 40)

    assert len(zones) == 2, "Expected 2 zones in zones.json"
    assert zones[0].zone_id == "zone_01"
    assert zones[0].rules.helmet_required is True
    print("\nSUCCESS: All Task B1 checks passed!")


if __name__ == "__main__":
    test_b1_zones()
