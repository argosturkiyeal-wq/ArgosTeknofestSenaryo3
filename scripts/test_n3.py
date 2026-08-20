"""
N3 dogrulama betigi: detect_frame() ve detections_to_text().
Kullanim: python scripts/test_n3.py <goruntu_yolu>
Goruntu verilmezse scripts/tmp_test/images.jpg denenir (varsa).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.detection import baret_durumu, detect_frame, detections_to_text, YOLO_MODELS


def test_detect_frame(image_path: str):
    print(f"Model registry: {list(YOLO_MODELS.keys())}")
    print(f"Test goruntusu: {image_path}\n")

    detections = detect_frame(image_path)

    # Kare girdi -> tespit listesi cikti
    assert isinstance(detections, list), "detect_frame() bir liste dondurmeli"
    print(f"[OK] detect_frame() liste dondurdu ({len(detections)} tespit)")

    required_keys = {"label", "confidence", "bbox", "source_model"}
    for det in detections:
        assert required_keys.issubset(det.keys()), f"Eksik anahtar: {det}"
        assert isinstance(det["label"], str)
        assert 0.0 <= det["confidence"] <= 1.0, f"Gecersiz confidence: {det['confidence']}"
        assert len(det["bbox"]) == 4, f"bbox 4 eleman olmali: {det['bbox']}"
    print(f"[OK] Tum tespitler {required_keys} anahtarlarini iceriyor, degerler gecerli")

    text = detections_to_text(detections, "00:15")
    assert isinstance(text, str) and text.startswith("[00:15] Tespitler:")
    print(f"[OK] detections_to_text() dogru formatta: {text}")

    empty_text = detections_to_text([], "00:00")
    assert empty_text == "[00:00] Tespitler: yok"
    print(f"[OK] Bos liste durumu dogru: {empty_text}")

    # Gercek goruntude 3 kafa + 2 baret var -> 2 baretli, 1 baretsiz beklenir
    baretli, baretsiz = baret_durumu(detections)
    assert (baretli, baretsiz) == (2, 1), f"Beklenen (2, 1), gelen ({baretli}, {baretsiz})"
    print(f"[OK] baret_durumu() gercek goruntude dogru: ({baretli} baretli, {baretsiz} baretsiz)")

    print("\nBASARILI: N3 (detect_frame / detections_to_text) testleri hatasiz gecti!\n")


def _det(label: str, bbox: tuple[float, float, float, float]) -> dict:
    return {"label": label, "confidence": 0.9, "bbox": bbox, "source_model": "sh17"}


def test_baret_durumu():
    print("N6 (baret_durumu) sentetik testleri...")

    # Bos liste -> (0, 0)
    assert baret_durumu([]) == (0, 0)
    print("[OK] Bos liste: (0, 0)")

    # Hic baret yok -> tum kafalar baretsiz
    detections = [_det("head", (100, 100, 200, 200)), _det("head", (300, 300, 400, 400))]
    assert baret_durumu(detections) == (0, 2)
    print("[OK] Hic baret yok: (0, 2)")

    # Hic kafa yok -> (0, 0), baretin tek basina bir anlami yok
    detections = [_det("helmet", (100, 90, 200, 150))]
    assert baret_durumu(detections) == (0, 0)
    print("[OK] Hic kafa yok: (0, 0)")

    # 1 kafa + ustunde ortusen baret -> baretli
    detections = [
        _det("head", (100, 100, 200, 200)),
        _det("helmet", (100, 90, 200, 150)),  # merkez y=120, ust %60 sinirinin (160) icinde
    ]
    assert baret_durumu(detections) == (1, 0)
    print("[OK] Ortusen baret: (1, 0)")

    # 1 kafa + hicbir yerde ortusmeyen baret -> baretsiz
    detections = [
        _det("head", (100, 100, 200, 200)),
        _det("helmet", (1000, 1000, 1100, 1100)),
    ]
    assert baret_durumu(detections) == (0, 1)
    print("[OK] Ortusmeyen baret: (0, 1)")

    # Ayni baret iki basa eslenmemeli: iki yakin kafa, tek baret sadece
    # birine eslenmeli, digeri baretsiz sayilmali (dedup guard)
    detections = [
        _det("head", (100, 100, 200, 200)),
        _det("head", (105, 100, 205, 200)),  # ilkiyle buyuk oranda ortusuyor
        _det("helmet", (100, 90, 200, 150)),  # her iki kafayla da eslesme kriterini gecer
    ]
    assert baret_durumu(detections) == (1, 1), "Bir baret birden fazla basa eslenmemeli"
    print("[OK] Dedup guard: tek baret sadece bir kafaya eslendi -> (1, 1)")

    print("\nBASARILI: N6 (baret_durumu) sentetik testleri hatasiz gecti!\n")


def test_detections_to_text_filters_noise():
    print("N6 (detections_to_text noise filtreleme) testi...")

    detections = [
        _det("person", (0, 0, 50, 200)),
        _det("head", (10, 0, 40, 30)),
        _det("helmet", (10, -5, 40, 15)),
        _det("ear", (10, 15, 15, 20)),
        _det("face", (15, 10, 35, 25)),
        _det("hands", (0, 100, 20, 130)),
        _det("shoes", (10, 190, 30, 200)),
        _det("safety-vest", (5, 60, 45, 120)),
    ]
    text = detections_to_text(detections, "00:15")

    assert "baretli" in text and "baretsiz" in text, text
    assert "yelek x1" in text, text
    parts = [p.strip() for p in text.split("Tespitler:", 1)[1].split(",")]
    for noise_label in ("kafa x", "kulak x", "yuz x", "el x", "ayakkabi x"):
        assert not any(p.startswith(noise_label) for p in parts), \
            f"'{noise_label}' gurultu olarak metne sizmis: {text}"
    print(f"[OK] Gurultu siniflari metinden cikarildi, kisi/yelek kaldi: {text}")

    print("\nBASARILI: N6 (detections_to_text noise filtreleme) testi hatasiz gecti!\n")


def test_detections_to_text_includes_forklift():
    print("Forklift entegrasyonu: detections_to_text() formati testi...")

    detections = [
        _det("person", (0, 0, 50, 200)),
        _det("person", (600, 0, 650, 200)),
        _det("head", (10, 0, 40, 30)),
        _det("helmet", (10, -5, 40, 15)),  # sadece ilk kafayla eslesir -> 1 baretli
        _det("head", (610, 0, 640, 30)),   # esleseni yok -> 1 baretsiz
        {**_det("forklift", (200, 100, 400, 300)), "source_model": "forklift"},
    ]
    text = detections_to_text(detections, "00:15")

    expected = "[00:15] Tespitler: kisi x2 (1 baretli, 1 baretsiz), forklift x1"
    assert text == expected, f"Beklenen:\n  {expected}\nGelen:\n  {text}"
    print(f"[OK] detections_to_text() forklift satirini dogru formatta ekliyor: {text}")

    print("\nBASARILI: Forklift / detections_to_text formati testi hatasiz gecti!\n")


def test_forklift_registry():
    print("Forklift entegrasyonu: model registry testi...")

    assert set(YOLO_MODELS.keys()) == {"sh17", "forklift"}, \
        f"Registry ['sh17', 'forklift'] icermeli, gelen: {list(YOLO_MODELS.keys())}"
    print(f"[OK] Registry iki modeli de iceriyor: {list(YOLO_MODELS.keys())}")

    print("\nBASARILI: Forklift registry testi hatasiz gecti!\n")


def test_forklift_detection_on_image():
    print("Forklift entegrasyonu: gercek goruntu testi...")

    forklift_image = REPO_ROOT / "scripts" / "tmp_test" / "forklift.jpg"
    if not forklift_image.exists():
        print(f"[ATLANDI] Forklift test goruntusu bulunamadi: {forklift_image}")
        print("Forklift iceren bir goruntuyu bu yola koyup betigi tekrar calistir.\n")
        return

    detections = detect_frame(str(forklift_image))
    forklift_dets = [d for d in detections if d["label"] == "forklift"]

    assert forklift_dets, f"Goruntude forklift tespit edilmedi: {forklift_image}"
    assert all(d["source_model"] == "forklift" for d in forklift_dets), \
        "forklift etiketli tespitlerin source_model'i 'forklift' olmali"
    print(f"[OK] {len(forklift_dets)} forklift tespit edildi, source_model dogru")

    text = detections_to_text(detections, "00:15")
    assert "forklift x" in text, text
    print(f"[OK] detections_to_text() forklifti metne yansitiyor: {text}")

    print("\nBASARILI: Forklift gercek goruntu testi hatasiz gecti!\n")


if __name__ == "__main__":
    test_baret_durumu()
    test_detections_to_text_filters_noise()
    test_forklift_registry()
    test_detections_to_text_includes_forklift()
    test_forklift_detection_on_image()

    default_image = REPO_ROOT / "scripts" / "tmp_test" / "images.jpg"
    image_arg = sys.argv[1] if len(sys.argv) > 1 else str(default_image)

    if not Path(image_arg).exists():
        print(f"HATA: Goruntu bulunamadi: {image_arg}")
        print("Kullanim: python scripts/test_n3.py <goruntu_yolu>")
        sys.exit(1)

    test_detect_frame(image_arg)
