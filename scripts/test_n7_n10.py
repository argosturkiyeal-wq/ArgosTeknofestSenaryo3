"""
N7-N10 dogrulama betigi: zamansal analiz katmani (core/tracking.py).
Sentetik bbox dizileriyle mantigi dogrular - gercek video/tracker
gerektirmez (process_video() ayri, gercek video ile manuel/entegrasyon
testi gerektirir).

Kullanim: python scripts/test_n7_n10.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.tracking import (
    TrackHistory,
    SignalThrottle,
    is_horizontal,
    is_still,
    proximity_ratio,
    is_dangerous_proximity,
)


def test_track_history():
    print("N7 (TrackHistory) testleri...")

    hist = TrackHistory(window_seconds=5.0)

    # Bos gecmis -> bos liste
    assert hist.get(1) == []
    print("[OK] Bilinmeyen track_id: bos liste")

    # Noktalar eklenince sirali donuyor
    hist.add(1, 0.0, (0, 0, 10, 10))
    hist.add(1, 1.0, (5, 0, 15, 10))
    assert hist.get(1) == [(0.0, (0, 0, 10, 10)), (1.0, (5, 0, 15, 10))]
    print("[OK] Noktalar eklenip sirayla donuyor")

    # Pencereden eski noktalar otomatik atiliyor (sinirsiz buyumemeli)
    hist2 = TrackHistory(window_seconds=3.0)
    for t in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]:
        hist2.add(9, t, (0, 0, 10, 10))
    remaining_times = [t for t, _ in hist2.get(9)]
    assert all(5.0 - t <= 3.0 for t in remaining_times), remaining_times
    assert 0.0 not in remaining_times, "3sn penceresinden eski nokta silinmeliydi"
    print(f"[OK] Pencere disindaki noktalar atildi, kalan zamanlar: {remaining_times}")

    # prune_stale: uzun suredir gorunmeyen track bellekten silinmeli
    hist3 = TrackHistory(window_seconds=10.0)
    hist3.add(1, 0.0, (0, 0, 10, 10))
    hist3.add(2, 9.0, (0, 0, 10, 10))
    hist3.prune_stale(now_sec=9.0, max_age_seconds=5.0)
    assert hist3.get(1) == [], "5sn'den uzun suredir gorunmeyen track silinmeliydi"
    assert hist3.get(2) != [], "yakin zamanda gorulen track silinmemeliydi"
    print("[OK] prune_stale eski track'i temizledi, yeniyi korudu")

    print("\nBASARILI: N7 (TrackHistory) testleri hatasiz gecti!\n")


def test_is_horizontal():
    print("N8 (is_horizontal) testleri...")

    # Ayakta kisi: dar ve uzun bbox (en/boy ~0.4) -> yatay degil
    standing = (100, 100, 140, 300)  # 40 genis, 200 yuksek -> oran 0.2
    assert is_horizontal(standing, threshold=1.2) is False
    print("[OK] Ayakta bbox: yatay degil")

    # Yatan kisi: genis ve kisa bbox (en/boy > 1.2) -> yatay
    lying = (100, 100, 340, 180)  # 240 genis, 80 yuksek -> oran 3.0
    assert is_horizontal(lying, threshold=1.2) is True
    print("[OK] Yatan bbox: yatay")

    # Sinir deger: esigin hemen ustunde/altinda
    assert is_horizontal((0, 0, 120, 100), threshold=1.2) is False  # oran tam 1.2, > degil
    assert is_horizontal((0, 0, 121, 100), threshold=1.2) is True   # oran 1.21
    print("[OK] Esik siniri dogru davraniyor (>, >= degil)")

    # Sifir yukseklik -> bolme hatasi degil, False
    assert is_horizontal((0, 0, 100, 0), threshold=1.2) is False
    print("[OK] Sifir yukseklik: guvenli False, exception yok")

    print("\nBASARILI: N8 (is_horizontal) testleri hatasiz gecti!\n")


def test_is_still():
    print("N9 (is_still) testleri...")

    # Hareketsiz track: 3.5sn boyunca merkez neredeyse sabit (< 20px kayma)
    still_history = [
        (0.0, (100, 100, 140, 200)),
        (1.0, (102, 100, 142, 200)),
        (2.0, (104, 101, 144, 201)),
        (3.5, (105, 102, 145, 202)),
    ]
    result = is_still(still_history, now_sec=3.5, window_seconds=3.0, pixel_tolerance=20)
    assert result is True, f"Hareketsiz track True donmeliydi, gelen: {result}"
    print("[OK] Hareketsiz track: True")

    # Hareketli track: ayni sure icinde buyuk kayma (> 20px)
    moving_history = [
        (0.0, (100, 100, 140, 200)),
        (1.0, (150, 100, 190, 200)),
        (2.0, (250, 100, 290, 200)),
        (3.5, (400, 100, 440, 200)),
    ]
    result = is_still(moving_history, now_sec=3.5, window_seconds=3.0, pixel_tolerance=20)
    assert result is False, f"Hareketli track False donmeliydi, gelen: {result}"
    print("[OK] Hareketli track: False")

    # Salinim yapan track: pencere ici ilk/son nokta birbirine yakin
    # (net kayma kucuk) ama arada buyuk bir gidip-gelme var - gercek
    # videoda gozlemlenen false-positive: "hareketli kisi yanlislikla
    # hareketsiz sayiliyor" hatasini yakalar.
    oscillating_history = [
        (0.0, (100, 100, 140, 200)),  # merkez (120, 150)
        (1.0, (150, 100, 190, 200)),  # merkez (170, 150) - 50px sagda
        (2.0, (200, 100, 240, 200)),  # merkez (220, 150) - 100px sagda
        (3.5, (105, 100, 145, 200)),  # merkez (125, 150) - baslangica yakin donus
    ]
    result = is_still(oscillating_history, now_sec=3.5, window_seconds=3.0, pixel_tolerance=20)
    assert result is False, f"Salinan track False donmeliydi (ilk/son yakin ama arada hareket var), gelen: {result}"
    print("[OK] Salinim yapan track (ilk/son yakin, arada buyuk hareket): False")

    # Tek kare gecmisi: karar verilemez -> None
    single_point = [(3.5, (100, 100, 140, 200))]
    result = is_still(single_point, now_sec=3.5, window_seconds=3.0, pixel_tolerance=20)
    assert result is None, f"Tek nokta icin None donmeliydi, gelen: {result}"
    print("[OK] Tek kare gecmisi: None (karar yok)")

    # Video basi / yetersiz gecmis: pencere henuz dolmamis -> None
    early_history = [(0.0, (100, 100, 140, 200)), (0.5, (101, 100, 141, 200))]
    result = is_still(early_history, now_sec=0.5, window_seconds=3.0, pixel_tolerance=20)
    assert result is None, f"Yetersiz gecmis icin None donmeliydi, gelen: {result}"
    print("[OK] Video basinda yetersiz gecmis: None (karar yok)")

    # Track kaybolup donerse: eski kume + kopukluk + yeni (kisa) kume ->
    # pencere filtresi eski noktalari eler, yeni kume tek basina pencereyi
    # doldurmadigi icin hala None donmeli (erken karar verilmemeli)
    gapped_history = [
        (0.0, (100, 100, 140, 200)),
        (1.0, (100, 100, 140, 200)),
        # 2.0 - 9.0 arasi track kayboldu (kopukluk)
        (9.0, (300, 100, 340, 200)),
        (9.3, (300, 100, 340, 200)),
    ]
    result = is_still(gapped_history, now_sec=9.3, window_seconds=3.0, pixel_tolerance=20)
    assert result is None, f"Kopukluk sonrasi kisa gecmis icin None donmeliydi, gelen: {result}"
    print("[OK] Track kaybolup donduysa (kisa yeni gecmis): None (karar yok)")

    print("\nBASARILI: N9 (is_still) testleri hatasiz gecti!\n")


def test_proximity():
    print("N10 (proximity_ratio / is_dangerous_proximity) testleri...")

    frame_width = 1000.0

    # Yakin nesneler: merkezler arasi mesafe kadrajin kucuk bir orani
    person = (100, 100, 140, 200)     # merkez (120, 150)
    forklift_close = (150, 100, 250, 200)  # merkez (200, 150) -> mesafe 80px = %8
    ratio = proximity_ratio(person, forklift_close, frame_width)
    assert abs(ratio - 0.08) < 1e-6, ratio
    assert is_dangerous_proximity(person, forklift_close, frame_width, threshold=0.15) is True
    print(f"[OK] Yakin nesneler: oran {ratio:.3f}, tehlikeli=True")

    # Uzak nesneler: kadrajin buyuk bir orani kadar mesafe
    forklift_far = (800, 100, 900, 200)  # merkez (850, 150) -> mesafe 730px = %73
    ratio_far = proximity_ratio(person, forklift_far, frame_width)
    assert is_dangerous_proximity(person, forklift_far, frame_width, threshold=0.15) is False
    print(f"[OK] Uzak nesneler: oran {ratio_far:.3f}, tehlikeli=False")

    # Sifir genislik -> bolme hatasi degil, sonsuz (asla tehlikeli degil)
    ratio_zero = proximity_ratio(person, forklift_close, 0.0)
    assert ratio_zero == float("inf")
    print("[OK] Sifir goruntu genisligi: guvenli sonsuz deger, exception yok")

    print("\nBASARILI: N10 (proximity) testleri hatasiz gecti!\n")


def test_signal_throttle():
    print("Sinyal spam koruma (SignalThrottle) testleri...")

    throttle = SignalThrottle(repeat_interval_seconds=2.0)

    # Ilk aktif goruldugunde hemen yayinlanmali
    assert throttle.should_emit(("hareketsiz", 5), 0.0, True) is True
    print("[OK] Ilk aktif durum: hemen yayinlanir")

    # Bekleme suresi dolmadan tekrar aktif -> bastirilmali (spam onleme)
    assert throttle.should_emit(("hareketsiz", 5), 0.5, True) is False
    assert throttle.should_emit(("hareketsiz", 5), 1.9, True) is False
    print("[OK] Bekleme suresi dolmadan tekrarlar bastiriliyor")

    # Bekleme suresi dolunca tekrar yayinlanmali
    assert throttle.should_emit(("hareketsiz", 5), 2.0, True) is True
    print("[OK] Bekleme suresi dolunca tekrar yayinlanir")

    # Pasif olunca sessiz, durum sifirlanir
    assert throttle.should_emit(("hareketsiz", 5), 2.1, False) is False
    print("[OK] Pasif durumda yayinlanmaz")

    # Tekrar aktif olmak bir durum degisimi - bekleme suresini beklemeden hemen yayinlanmali
    assert throttle.should_emit(("hareketsiz", 5), 2.2, True) is True
    print("[OK] Pasiften aktife gecis (durum degisimi) beklemeden hemen yayinlanir")

    # Farkli anahtarlar (farkli track_id / sinyal turu) birbirini etkilemez
    assert throttle.should_emit(("yatay", 5), 2.2, True) is True
    assert throttle.should_emit(("hareketsiz", 6), 2.2, True) is True
    print("[OK] Farkli anahtarlar bagimsiz calisiyor")

    print("\nBASARILI: SignalThrottle testleri hatasiz gecti!\n")


if __name__ == "__main__":
    test_track_history()
    test_is_horizontal()
    test_is_still()
    test_proximity()
    test_signal_throttle()
    print("TUM N7-N10 TESTLERI BASARILI!\n")
