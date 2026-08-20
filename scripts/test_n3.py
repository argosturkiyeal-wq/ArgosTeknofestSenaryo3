"""
N3 dogrulama betigi: detect_frame() ve detections_to_text().
Kullanim: python scripts/test_n3.py <goruntu_yolu>
Goruntu verilmezse scripts/tmp_test/images.jpg denenir (varsa).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.detection import detect_frame, detections_to_text, YOLO_MODELS


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

    print("\nBASARILI: N3 (detect_frame / detections_to_text) testleri hatasiz gecti!\n")


if __name__ == "__main__":
    default_image = REPO_ROOT / "scripts" / "tmp_test" / "images.jpg"
    image_arg = sys.argv[1] if len(sys.argv) > 1 else str(default_image)

    if not Path(image_arg).exists():
        print(f"HATA: Goruntu bulunamadi: {image_arg}")
        print("Kullanim: python scripts/test_n3.py <goruntu_yolu>")
        sys.exit(1)

    test_detect_frame(image_arg)
