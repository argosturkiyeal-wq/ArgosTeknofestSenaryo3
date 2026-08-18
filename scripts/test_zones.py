"""
Bolge yukleme ve sema dogrulama test betigi.
"""

import sys
from pathlib import Path

# Kok dizini Python yoluna ekle
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import load_zones, Zone


def test_zones():
    json_path = REPO_ROOT / "zones.json"
    print(f"Bolgeler yukleniyor: {json_path}")

    zones = load_zones(json_path)
    print(f"{len(zones)} bolge basariyla yuklendi.\n")

    for z in zones:
        print(f"Bolge ID:   {z.zone_id}")
        print(f"Ad:         {z.name}")
        print(f"Tip:        {z.type}")
        print(f"Noktalar:   {len(z.polygon)} koordinat")
        print(f"Yasaklilar: {z.rules.forbidden_classes}")
        print(f"Baret Zor.: {z.rules.helmet_required}")
        print("-" * 40)

    assert len(zones) >= 2, "zones.json icinde en az 2 bolge bekleniyordu"
    assert zones[0].zone_id == "zone_01"
    assert zones[0].rules.helmet_required is True
    print("\nBASARILI: Tum bolge sema kontrolleri gecti!")


if __name__ == "__main__":
    test_zones()
