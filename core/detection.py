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

from typing import Any


def detect_frame(image_path: str) -> list[dict[str, Any]]:
    """
    Verilen kare görseli üzerinde YOLO tespiti çalıştırır.

    Args:
        image_path: Tespit yapılacak kare görselinin dosya yolu.

    Returns:
        Her biri en az {"label": str, "confidence": float, "bbox": tuple}
        anahtarlarını içeren tespit sözlüklerinin listesi.
    """
    raise NotImplementedError

def detections_to_text(detections: list[dict[str, Any]], timestamp: str) -> str:
    """
    Ham YOLO tespitlerini, ajan prompt'una eklenebilecek tek satırlık
    Türkçe bir özet metnine çevirir.

    Args:
        detections: detect_frame(...) tarafından üretilen tespit listesi.
        timestamp: Tespitin ait olduğu zaman damgası, "MM:SS" formatında.

    Returns:
        Örnek: "[00:15] Tespitler: kisi x3 (2 baretli, 1 baretsiz), forklift x1"
    """
    raise NotImplementedError
