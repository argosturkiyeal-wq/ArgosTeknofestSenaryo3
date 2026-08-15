"""
Bolge ihlalleri titreme filtresi (ZoneDebouncer) test betigi.
Tek karelik gürültülerin filtrelendigini ve sadece N ardisik kare boyunca devam eden ihlallerin onaylandigini dogrular.
"""

import sys
from pathlib import Path

# Kok dizini Python yoluna ekle
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import ZoneDebouncer


def test_zone_debouncer():
    print("ZoneDebouncer titreme filtresi test ediliyor (N=3 ardisik kare)...")

    debouncer = ZoneDebouncer(consecutive_threshold=3)

    raw_violation = {
        "zone_id": "zone_01",
        "zone_name": "YUKLEME ALANI YASAKLI BOLGE",
        "violation_type": "forbidden_class",
        "detection": {"label": "person", "track_id": 101, "bbox": (0.15, 0.2, 0.35, 0.5)},
    }

    # Kare 1: 1. ihlal tespiti -> Gürültü olarak filtrelenmeli (0 onayli)
    conf_frame1 = debouncer.process_frame_violations([raw_violation])
    print(f"Kare 1 -> Ham: 1, Onayli: {len(conf_frame1)}")
    assert len(conf_frame1) == 0, "1. karedeki anlik titreme filtrelenmeliydi"

    # Kare 2: 2. ardisik ihlal tespiti -> Henüz esige ulasmadi (0 onayli)
    conf_frame2 = debouncer.process_frame_violations([raw_violation])
    print(f"Kare 2 -> Ham: 1, Onayli: {len(conf_frame2)}")
    assert len(conf_frame2) == 0, "2. karede esik (N=3) beklenmeliydi"

    # Kare 3: 3. ardisik ihlal tespiti -> Onaylandi! (1 onayli)
    conf_frame3 = debouncer.process_frame_violations([raw_violation])
    print(f"Kare 3 -> Ham: 1, Onayli: {len(conf_frame3)}")
    assert len(conf_frame3) == 1, "3. karede esige ulasilip ihlal onaylanmaliydi"
    assert conf_frame3[0]["is_confirmed"] is True
    assert conf_frame3[0]["consecutive_count"] == 3
    print(f"Onaylanan Ihlal: {conf_frame3[0].get('zone_name')} (Ardisik Kare Sayisi: {conf_frame3[0].get('consecutive_count')})")

    # Kare 4: Nesne bolgeden cikti -> 0 ihlal -> Sayac sifirlanmali
    conf_frame4 = debouncer.process_frame_violations([])
    print(f"Kare 4 (Ihlal yok) -> Onayli: {len(conf_frame4)}")
    assert len(conf_frame4) == 0

    # Kare 5: Nesne tekrar girdi (sifirlama sonrasi 1. kare) -> Filtrelenmeli
    conf_frame5 = debouncer.process_frame_violations([raw_violation])
    print(f"Kare 5 (Sifirlama sonrasi) -> Onayli: {len(conf_frame5)}")
    assert len(conf_frame5) == 0, "Sifirlama sonrasi ilk karede sayac 1'den tekrar baslamaliydi"

    print("[OK] Tum titreme filtresi (debouncer) testleri basariyla gecti!\n")


if __name__ == "__main__":
    test_zone_debouncer()
