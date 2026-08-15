"""
Nokta-poligon testi ve ayak noktasi kurali dogrulama betigi.
"""

import sys
from pathlib import Path

# Kok dizini Python yoluna ekle
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
    print("Ayak noktasi hesabi test ediliyor...")
    # Bbox: (xmin, ymin, xmax, ymax) = (0.2, 0.1, 0.4, 0.5)
    bbox = (0.2, 0.1, 0.4, 0.5)
    foot_pt = get_foot_point(bbox)
    print(f"Bbox {bbox} -> Ayak Noktasi: {foot_pt}")
    assert foot_pt == (0.3, 0.5), f"Beklenen (0.3, 0.5), alinan {foot_pt}"
    print("[OK] Ayak noktasi hesabi testi gecti!\n")


def test_point_in_polygon():
    print("cv2.pointPolygonTest test ediliyor...")
    poly = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.6), (0.1, 0.6)]

    pt_inside = (0.2, 0.3)
    pt_outside = (0.8, 0.8)

    assert is_point_in_polygon(pt_inside, poly) is True, "Nokta poligon icinde olmaliydi"
    assert is_point_in_polygon(pt_outside, poly) is False, "Nokta poligon disinda olmaliydi"
    print("[OK] Nokta-poligon testi gecti!\n")


def test_zone_violations():
    print("Bolge ihlal mantigi test ediliyor...")
    zones = load_zones(REPO_ROOT / "zones.json")
    zone_01 = zones[0]  # Yasakli bolge, forbidden: ["person"]

    # Senaryo 1: zone_01 icindeki kisi -> forbidden_class ihlali vermeli
    det_person_in = {
        "label": "person",
        "bbox": (0.15, 0.2, 0.35, 0.5),  # Ayak noktasi: (0.25, 0.5) -> zone_01 icinde
        "helmet": False,
    }

    # Senaryo 2: zone_01 disindaki kisi -> Ihlal vermemeli
    det_person_out = {
        "label": "person",
        "bbox": (0.7, 0.7, 0.8, 0.9),  # Ayak noktasi: (0.75, 0.9) -> zone_01 disinda
        "helmet": False,
    }

    viol1 = check_zone_violation(det_person_in, zone_01)
    viol2 = check_zone_violation(det_person_out, zone_01)

    assert viol1 is not None, "Yasakli bolgedeki kisi ihlal tetiklemeliydi"
    assert viol1["violation_type"] == "forbidden_class"
    assert viol2 is None, "Bolge disindaki kisi ihlal tetiklememeliydi"

    print(f"Ihlal Mesaji: {viol1['message']}")
    print("[OK] Bolge ihlali testi gecti!\n")


if __name__ == "__main__":
    test_foot_point_calculation()
    test_point_in_polygon()
    test_zone_violations()
    print("BASARILI: Tum bolge ihlal kontrolleri hatasiz gecti!")
