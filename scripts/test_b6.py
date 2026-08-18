"""
Dort temel ihlal tipi dogrulama betigi.
1. yaya alan disinda (pedestrian_outside_safe_zone)
2. arac yaya alaninda (vehicle_in_pedestrian_zone)
3. yaya arac bandinda (pedestrian_in_vehicle_lane)
4. yolda engel (obstacle_on_road)
"""

import sys
from pathlib import Path

# Kok dizini Python yoluna ekle
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import Zone, ZoneRule, check_zone_violation, check_all_zones_violations


def test_four_violation_types():
    print("Dort temel ihlal tipi test ediliyor...")

    # Test bolgeleri olustur
    pedestrian_zone = Zone(
        zone_id="zone_p1",
        name="GUVENLI YAYA YOLU",
        type="yaya_yolu",
        polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
        rules=ZoneRule(allowed_classes=["person"]),
    )

    vehicle_lane = Zone(
        zone_id="zone_v1",
        name="ANA ARAC YOLU",
        type="arac_yolu",
        polygon=[(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)],
        rules=ZoneRule(allowed_classes=["car", "truck", "forklift"]),
    )

    zones = [pedestrian_zone, vehicle_lane]

    # 1. Test: Arac yaya alaninda
    det_vehicle_in_ped_zone = {
        "label": "forklift",
        "bbox": (0.1, 0.1, 0.3, 0.3),  # Ayak noktasi: (0.2, 0.3) -> yaya_yolu icinde
    }
    viol_1 = check_zone_violation(det_vehicle_in_ped_zone, pedestrian_zone)
    assert viol_1 is not None, "Yaya alanina giren arac ihlal tetiklemeliydi"
    assert viol_1["violation_type"] == "vehicle_in_pedestrian_zone"
    print(f"[OK] 1. Arac yaya alaninda ihlali gecti: {viol_1['message']}")

    # 2. Test: Yaya arac bandinda
    det_person_in_vehicle_lane = {
        "label": "person",
        "bbox": (0.6, 0.6, 0.8, 0.8),  # Ayak noktasi: (0.7, 0.8) -> arac_yolu icinde
    }
    viol_2 = check_zone_violation(det_person_in_vehicle_lane, vehicle_lane)
    assert viol_2 is not None, "Arac yoluna giren yaya ihlal tetiklemeliydi"
    assert viol_2["violation_type"] == "pedestrian_in_vehicle_lane"
    print(f"[OK] 2. Yaya arac bandinda ihlali gecti: {viol_2['message']}")

    # 3. Test: Yolda engel
    det_obstacle_on_road = {
        "label": "box",
        "bbox": (0.6, 0.6, 0.7, 0.7),  # Ayak noktasi: (0.65, 0.7) -> arac_yolu icinde
    }
    viol_3 = check_zone_violation(det_obstacle_on_road, vehicle_lane)
    assert viol_3 is not None, "Yoldaki engel ihlal tetiklemeliydi"
    assert viol_3["violation_type"] == "obstacle_on_road"
    print(f"[OK] 3. Yolda engel ihlali gecti: {viol_3['message']}")

    # 4. Test: Yaya alan disinda
    det_person_outside = {
        "label": "person",
        "bbox": (0.8, 0.1, 0.9, 0.3),  # Ayak noktasi: (0.85, 0.3) -> yaya_yolu disinda
    }
    all_viols = check_all_zones_violations([det_person_outside], zones)
    viol_4 = next((v for v in all_viols if v["violation_type"] == "pedestrian_outside_safe_zone"), None)
    assert viol_4 is not None, "Guvenli yaya yolu disindaki yaya ihlal tetiklemeliydi"
    print(f"[OK] 4. Yaya alan disinda ihlali gecti: {viol_4['message']}")

    print("\nBASARILI: Tum 4 ihlal tipi testi hatasiz gecti!\n")


if __name__ == "__main__":
    test_four_violation_types()
