"""
Zamansal analiz katmani (N7-N10).

core.detection.detect_frame() kare-bazli calisir; bu modul YOLO'nun
zaman icindeki tespitlerini (Ultralytics'in kendi tracker'i, persist=True)
izleyip olcculebilir olay-adayi sinyalleri uretir: hareketsizlik (N9),
yatay konum (N8), tehlikeli yakinlik (N10) - N7 bunlarin dayandigi track
gecmisi katmanidir.

Tasarim ilkesi: bu katman "kaza oldu" demez, sadece olculmus bir gozlem
uretir ("3sn'dir hareketsiz", "bbox orani 1.4"); yorumu VLM yapar. Her
sinyal hangi olcume dayandigini metninde tasir (aciklanabilirlik). Metin
sabit sozluk/format ile uretilir, modele cevirttirilmez.

detect_frame() tek kare arayuzu burada degismez/kullanilmaz - process_video()
video-seviyeli, ayri bir akistir; mevcut testler etkilenmez.
"""

from collections import deque
from pathlib import Path
from typing import Any, Iterator

import cv2
import yaml

from core.detection import _load_model

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_YAML_PATH = BASE_DIR / "config.yaml"


def _load_temporal_config() -> dict:
    with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


TEMPORAL_CONFIG = _load_temporal_config()

HISTORY_WINDOW_SECONDS = TEMPORAL_CONFIG["tracking"]["history_window_seconds"]
STILLNESS_WINDOW_SECONDS = TEMPORAL_CONFIG["stillness"]["window_seconds"]
STILLNESS_PIXEL_TOLERANCE = TEMPORAL_CONFIG["stillness"]["pixel_tolerance"]
HORIZONTAL_ASPECT_RATIO_THRESHOLD = TEMPORAL_CONFIG["horizontal"]["aspect_ratio_threshold"]
PROXIMITY_DISTANCE_RATIO_THRESHOLD = TEMPORAL_CONFIG["proximity"]["distance_ratio_threshold"]
SIGNAL_REPEAT_INTERVAL_SECONDS = TEMPORAL_CONFIG["signals"]["repeat_interval_seconds"]

Bbox = tuple[float, float, float, float]


def _bbox_center(bbox: Bbox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


class TrackHistory:
    """
    N7: track_id -> zaman damgali bbox gecmisi (kayan pencere).

    window_seconds'tan eski noktalar her add() cagrisinda otomatik atilir;
    bellek video suresiyle orantili sinirsiz buyumez.
    """

    def __init__(self, window_seconds: float = HISTORY_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self._data: dict[int, deque[tuple[float, Bbox]]] = {}

    def add(self, track_id: int, timestamp_sec: float, bbox: Bbox) -> None:
        dq = self._data.setdefault(track_id, deque())
        dq.append((timestamp_sec, bbox))
        while dq and timestamp_sec - dq[0][0] > self.window_seconds:
            dq.popleft()

    def get(self, track_id: int) -> list[tuple[float, Bbox]]:
        return list(self._data.get(track_id, ()))

    def prune_stale(self, now_sec: float, max_age_seconds: float) -> None:
        """Uzun suredir hic guncellenmeyen (kaybolmus) track'leri bellekten siler."""
        stale = [tid for tid, dq in self._data.items() if dq and now_sec - dq[-1][0] > max_age_seconds]
        for tid in stale:
            del self._data[tid]


class SignalThrottle:
    """
    Ayni (anahtar) icin sinyalin en erken ne zaman tekrar yayinlanabilecegini
    takip eder. process_video() her karede calistigi icin, hareketsiz/yatay
    gibi durumlar suresince ayni sinyal her karede tekrar uretilmesin diye
    kullanilir - VLM prompt'unu ayni satirla bogmamak icin.

    Durum degisiminde (should_emit(..., state_changed=True)) bekleme
    atlanir; degisim her zaman hemen raporlanir.
    """

    def __init__(self, repeat_interval_seconds: float = SIGNAL_REPEAT_INTERVAL_SECONDS):
        self.repeat_interval_seconds = repeat_interval_seconds
        self._last_emit: dict[Any, float] = {}
        self._last_state: dict[Any, bool] = {}

    def should_emit(self, key: Any, now_sec: float, active: bool) -> bool:
        if not active:
            self._last_state[key] = False
            return False

        state_changed = not self._last_state.get(key, False)
        self._last_state[key] = True

        last = self._last_emit.get(key)
        if state_changed or last is None or now_sec - last >= self.repeat_interval_seconds:
            self._last_emit[key] = now_sec
            return True
        return False


def is_horizontal(bbox: Bbox, threshold: float = HORIZONTAL_ASPECT_RATIO_THRESHOLD) -> bool:
    """N8: bbox en/boy orani esigi geciyor mu (yatay konum ipucu, tek basina karar degil)."""
    x1, y1, x2, y2 = bbox
    height = y2 - y1
    if height <= 0:
        return False
    return (x2 - x1) / height > threshold


def _window_points(history: list[tuple[float, Bbox]], now_sec: float, window_seconds: float) -> list[tuple[float, Bbox]]:
    return [(t, b) for t, b in history if now_sec - t <= window_seconds]


def _spread(window_points: list[tuple[float, Bbox]]) -> float:
    """
    Pencere icindeki tum merkez noktalarinin kapladigi alanin kosegeni.

    Sadece ilk/son nokta arasindaki mesafeye bakmak yanlis pozitif "hareketsiz"
    uretir: birisi 3sn icinde one-arkaya sallanip baslangica yakin bir yere
    donerse, uc noktalar arasi mesafe kucuk olur ama kisi aslinda hareket
    ediyordur. Bounding-box yayilimi bu salinimi da yakalar.
    """
    centers = [_bbox_center(b) for _, b in window_points]
    xs = [c[0] for c in centers]
    ys = [c[1] for c in centers]
    range_x = max(xs) - min(xs)
    range_y = max(ys) - min(ys)
    return (range_x ** 2 + range_y ** 2) ** 0.5


def is_still(
    history: list[tuple[float, Bbox]],
    now_sec: float,
    window_seconds: float = STILLNESS_WINDOW_SECONDS,
    pixel_tolerance: float = STILLNESS_PIXEL_TOLERANCE,
) -> bool | None:
    """
    N9: son window_seconds icinde ayni track'in merkezi, kuculuk bir alanin
    (pixel_tolerance kosegenli) disina hic cikmadiysa hareketsiz.

    Returns:
        True: hareketsiz. False: hareketli. None: karar icin yeterli
        gecmis yok (video basi, track yeni goruldu, ya da track bir
        kopukluktan sonra yeniden goruldu ve pencere henuz dolmadi) -
        bu durumda "hareketsiz" bayragi kaldirilmamali.
    """
    window_points = _window_points(history, now_sec, window_seconds)
    if len(window_points) < 2:
        return None

    observed_span = window_points[-1][0] - window_points[0][0]
    if observed_span < window_seconds * 0.8:
        return None

    return _spread(window_points) <= pixel_tolerance


def stillness_drift(history: list[tuple[float, Bbox]], now_sec: float, window_seconds: float = STILLNESS_WINDOW_SECONDS) -> float | None:
    """is_still() ile ayni pencereden yayilim miktarini (px) doner - kanit metni icin."""
    window_points = _window_points(history, now_sec, window_seconds)
    if len(window_points) < 2:
        return None
    return _spread(window_points)


def proximity_ratio(bbox_a: Bbox, bbox_b: Bbox, frame_width: float) -> float:
    """N10: iki bbox merkezi arasi mesafe, goruntu genisligine oranla (piksel degil)."""
    ax, ay = _bbox_center(bbox_a)
    bx, by = _bbox_center(bbox_b)
    dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    return dist / frame_width if frame_width > 0 else float("inf")


def is_dangerous_proximity(
    bbox_a: Bbox, bbox_b: Bbox, frame_width: float, threshold: float = PROXIMITY_DISTANCE_RATIO_THRESHOLD
) -> bool:
    return proximity_ratio(bbox_a, bbox_b, frame_width) <= threshold


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def process_video(
    video_path: str,
    models: tuple[str, ...] = ("sh17", "forklift"),
) -> Iterator[str]:
    """
    Videoyu Ultralytics'in yerlesik tracker'i (persist=True) ile isler,
    N7-N10 sinyallerini zaman damgali Turkce kanit satirlari olarak
    sirayla uretir (generator). VLM prompt'una ek baglam olarak eklenmek
    uzere tasarlandi (bkz. core.detection.detect_frame docstring'i).

    Kritik kombinasyon: yatay konum + hareketsiz (>= stillness pencere
    suresi dogrulanmis) birlikte gorulursa ayrica "yerde hareketsiz kisi
    adayi" satiri uretilir - ikisi de tek basina yeterli degildir.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1.0
    cap.release()

    trackers = {
        name: _load_model(name).track(source=video_path, persist=True, stream=True, verbose=False)
        for name in models
    }
    histories = {name: TrackHistory() for name in models}
    throttle = SignalThrottle()

    frame_idx = 0
    for frame_results in zip(*trackers.values()):
        timestamp_sec = frame_idx / fps
        ts_label = _format_timestamp(timestamp_sec)

        frame_dets: dict[str, list[dict[str, Any]]] = {}
        for model_name, result in zip(models, frame_results):
            names = result.names
            dets = []
            if result.boxes is not None and result.boxes.id is not None:
                for box, tid in zip(result.boxes, result.boxes.id):
                    dets.append({
                        "label": names[int(box.cls[0])],
                        "bbox": tuple(box.xyxy[0].tolist()),
                        "track_id": int(tid),
                    })
                    histories[model_name].add(int(tid), timestamp_sec, dets[-1]["bbox"])
            frame_dets[model_name] = dets

        person_dets = [d for d in frame_dets.get("sh17", []) if d["label"] == "person"]
        forklift_dets = [d for d in frame_dets.get("forklift", []) if d["label"] == "forklift"]

        for p in person_dets:
            label_id = f"kisi#{p['track_id']}"
            history = histories["sh17"].get(p["track_id"])

            horizontal = is_horizontal(p["bbox"])
            still = is_still(history, timestamp_sec)

            if throttle.should_emit(("yatay", p["track_id"]), timestamp_sec, horizontal):
                x1, y1, x2, y2 = p["bbox"]
                ratio = (x2 - x1) / max(y2 - y1, 1e-6)
                yield f"[{ts_label}] {label_id} yatay konumda (bbox orani {ratio:.1f})"

            if throttle.should_emit(("hareketsiz", p["track_id"]), timestamp_sec, bool(still)):
                drift = stillness_drift(history, timestamp_sec) or 0.0
                yield f"[{ts_label}] {label_id} son {STILLNESS_WINDOW_SECONDS:.1f} sn'dir hareketsiz (kayma {drift:.0f}px)"

            if throttle.should_emit(("kritik", p["track_id"]), timestamp_sec, bool(horizontal and still)):
                yield f"[{ts_label}] {label_id} yerde hareketsiz kisi adayi (yatay + {STILLNESS_WINDOW_SECONDS:.1f}sn+ hareketsiz)"

            for f in forklift_dets:
                ratio = proximity_ratio(p["bbox"], f["bbox"], frame_width)
                key = ("yakinlik", p["track_id"], f["track_id"])
                if throttle.should_emit(key, timestamp_sec, ratio <= PROXIMITY_DISTANCE_RATIO_THRESHOLD):
                    yield f"[{ts_label}] forklift#{f['track_id']} ile {label_id} tehlikeli yakinlikta (mesafe %{ratio * 100:.0f} kadraj)"

        frame_idx += 1
