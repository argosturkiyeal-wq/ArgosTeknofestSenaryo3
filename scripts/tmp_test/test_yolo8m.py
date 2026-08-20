"""
Gecici test scripti - SH17 uzerinde egitilmis yolo8m.pt agirligini test eder.
Bu dosya sadece manuel test icindir, commit edilmemesi/gitignore'a
eklenmesi tavsiye edilir (scripts/tmp_test/ klasoru gecici tutulur).

Kullanim:
    python test_yolo8m.py <goruntu_yolu> [--conf 0.25]

Ornek:
    python test_yolo8m.py "C:\\Users\\Beyza\\Desktop\\test.jpg"
"""

import sys
import argparse
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    print("ultralytics bulunamadi, kuruluyor...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics"])
    from ultralytics import YOLO

# SH17 veri seti - 17 sinif (model bilgisi kullanicidan)
SH17_CLASSES = [
    "person", "head", "face", "glasses", "face-mask", "face-guard",
    "ear", "ear-mufs", "hands", "gloves", "foot", "shoes",
    "safety-vest", "tool", "helmet", "medical-suit", "safety-suit",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "model" / "yolo8m.pt"
OUTPUT_DIR = Path(__file__).parent / "yolo_test_output"


def main():
    parser = argparse.ArgumentParser(description="YOLO8m (SH17) test scripti")
    parser.add_argument("image", help="Test edilecek goruntu dosyasinin yolu")
    parser.add_argument("--conf", type=float, default=0.25, help="Guven esigi (varsayilan: 0.25)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"HATA: Goruntu bulunamadi: {image_path}")
        sys.exit(1)

    if not MODEL_PATH.exists():
        print(f"HATA: Model bulunamadi: {MODEL_PATH}")
        sys.exit(1)

    print(f"Model yukleniyor: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))

    # Modelin kendi sinif isimleri varsa onu goster, yoksa SH17 varsayimini kullan
    model_names = model.names
    print(f"\nModelin sinif sayisi: {len(model_names)}")
    print(f"Modelin sinif isimleri: {model_names}")
    if len(model_names) == len(SH17_CLASSES):
        print("(SH17 17-sinif seti ile eslesiyor)")
    else:
        print(f"UYARI: Model {len(model_names)} sinif iceriyor, beklenen SH17 seti 17 sinif.")

    print(f"\nGoruntu isleniyor: {image_path}")
    results = model.predict(source=str(image_path), conf=args.conf)

    OUTPUT_DIR.mkdir(exist_ok=True)

    for i, result in enumerate(results):
        boxes = result.boxes
        print(f"\n--- Tespit sonuclari ({len(boxes)} nesne) ---")
        if len(boxes) == 0:
            print("Hicbir nesne tespit edilmedi.")
        for box in boxes:
            cls_id = int(box.cls[0])
            cls_name = model_names.get(cls_id, f"sinif_{cls_id}") if isinstance(model_names, dict) else model_names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            print(f"  Sinif: {cls_name:15s} | Guven: {conf:.3f} | BBox(x1,y1,x2,y2): ({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f})")

        out_path = OUTPUT_DIR / f"detected_{image_path.stem}.jpg"
        result.save(filename=str(out_path))
        print(f"\nKutulu goruntu kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
