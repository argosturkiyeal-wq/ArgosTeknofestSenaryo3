"""
Değerlendirme / benchmark modülü.

Bu modül, elde önceden etiketlenmiş (ground truth) klipler üzerinde
ajanın ürettiği olay tespitlerini ve tetiklediği tool call'ları referans
etiketlerle karşılaştırıp Precision / Recall / F1 metrikleri hesaplamaktan
sorumlu olacak.

Planlanan akış:
    1. load_ground_truth ile etiket dosyası (örn. klip başına beklenen
       events + triggered_tools) belleğe alınır.
    2. run_evaluation, clips_dir altındaki her klip için mevcut analiz
       pipeline'ını (core.sampler + core.vision + core.agent) çalıştırıp
       üretilen sonucu ground truth ile karşılaştırır.
    3. Olay tespiti için P/R/F1 ve tool-call doğruluğu (doğru
       tool + doğru argüman) için ayrı bir doğruluk oranı döner.

Kök dizindeki eski benchmark.py (Kod/benchmark_report.json üretiyordu)
bu modülün öncülü; burada yeniden yazılacak.
"""

from typing import Any


def load_ground_truth(path: str) -> dict[str, Any]:
    """
    Etiketlenmiş referans (ground truth) verisini diskten okur.

    Args:
        path: Ground truth JSON/YAML dosyasının yolu.

    Returns:
        Klip adına göre anahtarlanmış, her klip için beklenen events ve
        triggered_tools listelerini içeren bir sözlük.
    """
    raise NotImplementedError

def run_evaluation(clips_dir: str, ground_truth: dict[str, Any]) -> dict[str, Any]:
    """
    clips_dir altındaki klipler için ajanı çalıştırır ve sonuçları
    ground_truth ile karşılaştırarak metrik hesaplar.

    Args:
        clips_dir: Değerlendirilecek video kliplerinin bulunduğu dizin.
        ground_truth: load_ground_truth(...) tarafından üretilen referans veri.

    Returns:
        Örn. {"event_precision": float, "event_recall": float, "event_f1": float,
              "tool_call_accuracy": float}
    """
    raise NotImplementedError
