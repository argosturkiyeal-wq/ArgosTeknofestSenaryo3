"""
Nesne tespiti modülü (YOLO tabanlı).

Bu modül, video karelerinde bir YOLO modeli çalıştırıp ham tespitleri
(bounding box + sınıf + confidence) üretmekten ve bu tespitleri ajanın
prompt'una eklenebilecek Türkçe metin satırlarına çevirmekten sorumlu
olacak. Amaç, VLM'e her kareyi "kör" göstermek yerine, önceden tespit
edilmiş nesneleri (kişi, forklift, baret var/yok vb.) metin olarak da
vermek.

Beklenen çıktı formatı örneği:
    "[00:15] Tespitler: kisi x3 (2 baretli, 1 baretsiz), forklift x1"

Bu satırlar, core.vision.run_analysis_generator içindeki zaman damgalı
kare metinlerine (bkz. "[Zaman Damgası: {ts}] Kare Görseli:") ek bir
bağlam satırı olarak eklenmesi planlanıyor.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent

# Model registry: {isim: agirlik dosyasi yolu}. Her egitim tamamlandiginda
# (forklift, yaya_yolu vb.) buraya tek satir eklemek yeterli; detect_frame()
# ve onu cagiran kod degismeden yeni model devreye girer.
YOLO_MODELS: dict[str, Path] = {
    "sh17": BASE_DIR / "model" / "sh17.pt",  # KKD: baret, yelek, eldiven vb. (17 sinif)
    # "forklift": BASE_DIR / "model" / "forklift.pt",    # egitimi bitince eklenecek
    # "yaya_yolu": BASE_DIR / "model" / "yaya_yolu.pt",  # egitimi bitince eklenecek
}

DEFAULT_CONF = 0.25

# SH17 sinif isimlerinin Turkce karsiliklari (detections_to_text icin).
# Bilinmeyen/yeni model etiketleri oldugu gibi (Ingilizce) yazilir.
LABEL_TR = {
    "person": "kisi", "head": "kafa", "face": "yuz", "glasses": "gozluk",
    "face-mask": "yuz maskesi", "face-guard": "yuz koruyucu", "ear": "kulak",
    "ear-mufs": "kulaklik", "hands": "el", "gloves": "eldiven", "foot": "ayak",
    "shoes": "ayakkabi", "safety-vest": "yelek", "tool": "alet", "helmet": "baret",
    "medical-suit": "tibbi tulum", "safety-suit": "is tulumu",
}


@lru_cache(maxsize=None)
def _load_model(model_name: str) -> YOLO:
    return YOLO(str(YOLO_MODELS[model_name]))


def detect_frame(
    image_path: str,
    models: tuple[str, ...] | None = None,
    conf: float = DEFAULT_CONF,
) -> list[dict[str, Any]]:
    """
    Verilen kare görseli üzerinde, registry'deki bir veya birden fazla
    YOLO modelini çalıştırıp tespitleri birleştirir.

    Args:
        image_path: Tespit yapılacak kare görselinin dosya yolu.
        models: Çalıştırılacak model adları (YOLO_MODELS anahtarları).
            None verilirse registry'deki tüm modeller sırayla çalışır.
        conf: Güven eşiği.

    Returns:
        Her biri {"label": str, "confidence": float, "bbox": tuple,
        "source_model": str} anahtarlarını içeren tespit sözlüklerinin
        listesi. "source_model" hangi modelin (sh17, forklift, ...) bu
        tespiti ürettiğini belirtir.
    """
    model_names = models if models is not None else tuple(YOLO_MODELS.keys())

    detections: list[dict[str, Any]] = []
    for model_name in model_names:
        yolo = _load_model(model_name)
        results = yolo.predict(source=image_path, conf=conf, verbose=False)
        for result in results:
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0])
                detections.append({
                    "label": names[cls_id],
                    "confidence": float(box.conf[0]),
                    "bbox": tuple(box.xyxy[0].tolist()),
                    "source_model": model_name,
                })
    return detections

def detections_to_text(detections: list[dict[str, Any]], timestamp: str) -> str:
    """
    Ham YOLO tespitlerini, ajan prompt'una eklenebilecek tek satırlık
    Türkçe bir özet metnine çevirir.

    Args:
        detections: detect_frame(...) tarafından üretilen tespit listesi.
        timestamp: Tespitin ait olduğu zaman damgası, "MM:SS" formatında.

    Returns:
        Örnek: "[00:15] Tespitler: kisi x3, baret x2, forklift x1"
    """
    if not detections:
        return f"[{timestamp}] Tespitler: yok"

    counts: dict[str, int] = {}
    for det in detections:
        label = det["label"]
        counts[label] = counts.get(label, 0) + 1

    parts = [f"{LABEL_TR.get(label, label)} x{count}" for label, count in counts.items()]
    return f"[{timestamp}] Tespitler: " + ", ".join(parts)
