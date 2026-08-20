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
from typing import Any

from ultralytics import YOLO

import config

# Model registry ve model basina guven esikleri config.py'de tutulur (kod
# icine gomulmez). Yeni bir model egitimi bittiginde (ör. yaya_yolu)
# config.YOLO_MODEL_PATHS / config.YOLO_MODEL_CONF'a tek satir eklemek
# yeterli; detect_frame() ve onu cagiran kod degismeden devreye girer.
YOLO_MODELS = config.YOLO_MODEL_PATHS

DEFAULT_CONF = 0.25

# SH17 sinif isimlerinin Turkce karsiliklari (detections_to_text icin).
# Bilinmeyen/yeni model etiketleri oldugu gibi (Ingilizce) yazilir.
LABEL_TR = {
    "person": "kisi", "head": "kafa", "face": "yuz", "glasses": "gozluk",
    "face-mask": "yuz maskesi", "face-guard": "yuz koruyucu", "ear": "kulak",
    "ear-mufs": "kulaklik", "hands": "el", "gloves": "eldiven", "foot": "ayak",
    "shoes": "ayakkabi", "safety-vest": "yelek", "tool": "alet", "helmet": "baret",
    "medical-suit": "tibbi tulum", "safety-suit": "is tulumu", "forklift": "forklift",
}

# detections_to_text() icin metne yazilacak siniflar. Bunun disindaki
# siniflar (el, kulak, yuz, ayakkabi, gozluk vb.) VLM prompt'unu gereksiz
# yere sisirdigi icin metinden cikarilir - tespit edilmeye devam ederler,
# sadece Turkce ozete girmezler. "head" bilerek burada yok: baret_durumu()
# tarafindan tuketiliyor, ayri bir satir olarak gorunmemesi gerekiyor.
RAPORLANACAK = {"person", "helmet", "safety-vest", "forklift"}


@lru_cache(maxsize=None)
def _load_model(model_name: str) -> YOLO:
    return YOLO(str(YOLO_MODELS[model_name]))


def detect_frame(
    image_path: str,
    models: tuple[str, ...] | None = None,
    conf: float | None = None,
) -> list[dict[str, Any]]:
    """
    Verilen kare görseli üzerinde, registry'deki bir veya birden fazla
    YOLO modelini çalıştırıp tespitleri birleştirir.

    Args:
        image_path: Tespit yapılacak kare görselinin dosya yolu.
        models: Çalıştırılacak model adları (YOLO_MODELS anahtarları).
            None verilirse registry'deki tüm modeller sırayla çalışır.
        conf: Güven eşiği. None ise her model config.YOLO_MODEL_CONF'daki
            kendi eşiğini kullanır (örn. sh17=0.25, forklift=0.40); bir
            değer verilirse tüm modeller için o eşik zorlanır.

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
        model_conf = conf if conf is not None else config.YOLO_MODEL_CONF.get(model_name, DEFAULT_CONF)
        results = yolo.predict(source=image_path, conf=model_conf, verbose=False)
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

def _iou(box_a: tuple[float, ...], box_b: tuple[float, ...]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _helmet_matches_head(
    head_bbox: tuple[float, ...],
    helmet_bbox: tuple[float, ...],
    iou_threshold: float,
    top_region_ratio: float,
) -> bool:
    if _iou(head_bbox, helmet_bbox) < iou_threshold:
        return False

    _, hy1, _, hy2 = head_bbox
    top_region_y2 = hy1 + (hy2 - hy1) * top_region_ratio

    _, ey1, _, ey2 = helmet_bbox
    helmet_center_y = (ey1 + ey2) / 2
    return helmet_center_y <= top_region_y2


def baret_durumu(
    detections: list[dict[str, Any]],
    iou_threshold: float = config.HEAD_HELMET_IOU_THRESHOLD,
    top_region_ratio: float = config.HEAD_HELMET_TOP_REGION_RATIO,
) -> tuple[int, int]:
    """
    head ve helmet kutularını eşleştirip (baretli, baretsiz) sayısı döner.

    SH17 modelinde ayrı bir "baretsiz kişi" sınıfı yok; bu geometrik
    çıkarım head + helmet kutularından türetilir. Her head kutusu için,
    henüz eşleşmemiş helmet kutuları arasında IoU'su iou_threshold'un
    üzerinde OLAN ve merkezi head kutusunun üst top_region_ratio'luk
    bölgesinde kalan ilk helmet aranır. Bulunursa o helmet listeden
    çıkarılır (bir baret birden fazla başa eşlenmez) ve baretli sayılır;
    bulunamazsa o head baretsiz sayılır.

    Args:
        detections: detect_frame(...) tarafından üretilen tespit listesi.
        iou_threshold: head/helmet kutuları arası minimum örtüşme oranı.
        top_region_ratio: helmet merkezinin head kutusunun üstünden
            itibaren kalması gereken oran (0.6 = üst %60).

    Returns:
        (baretli, baretsiz) - tespit edilen head sayısı kadar toplam.
    """
    heads = [d["bbox"] for d in detections if d["label"] == "head"]
    helmets = [d["bbox"] for d in detections if d["label"] == "helmet"]

    baretli = 0
    baretsiz = 0
    for head_bbox in heads:
        match_idx = next(
            (
                i for i, helmet_bbox in enumerate(helmets)
                if _helmet_matches_head(head_bbox, helmet_bbox, iou_threshold, top_region_ratio)
            ),
            None,
        )
        if match_idx is None:
            baretsiz += 1
        else:
            baretli += 1
            helmets.pop(match_idx)

    return baretli, baretsiz

def detections_to_text(detections: list[dict[str, Any]], timestamp: str) -> str:
    """
    Ham YOLO tespitlerini, ajan prompt'una eklenebilecek tek satırlık
    Türkçe bir özet metnine çevirir. Gürültü sınıfları (RAPORLANACAK
    dışındakiler) ve head/helmet ayrı satırları metne girmez; baret bilgisi
    kişi satırının parantezinde özetlenir.

    Args:
        detections: detect_frame(...) tarafından üretilen tespit listesi.
        timestamp: Tespitin ait olduğu zaman damgası, "MM:SS" formatında.

    Returns:
        Örnek: "[00:15] Tespitler: kisi x3 (2 baretli, 1 baretsiz), yelek x1"
    """
    if not detections:
        return f"[{timestamp}] Tespitler: yok"

    baretli, baretsiz = baret_durumu(detections)
    person_count = sum(1 for d in detections if d["label"] == "person")

    counts: dict[str, int] = {}
    for det in detections:
        label = det["label"]
        if label not in RAPORLANACAK or label in ("person", "helmet"):
            continue
        counts[label] = counts.get(label, 0) + 1

    parts: list[str] = []
    if person_count:
        if baretli or baretsiz:
            parts.append(f"kisi x{person_count} ({baretli} baretli, {baretsiz} baretsiz)")
        else:
            parts.append(f"kisi x{person_count}")
    parts.extend(f"{LABEL_TR.get(label, label)} x{count}" for label, count in counts.items())

    if not parts:
        return f"[{timestamp}] Tespitler: yok"

    return f"[{timestamp}] Tespitler: " + ", ".join(parts)
