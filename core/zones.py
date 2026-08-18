"""
Bolge tanimi ve zones.json yonetim modulu.
"""

import json
import cv2
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Dict, Any


@dataclass
class ZoneRule:
    allowed_classes: List[str] = field(default_factory=list)
    forbidden_classes: List[str] = field(default_factory=list)
    helmet_required: bool = False
    vest_required: bool = False
    speed_limit_kmh: float | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneRule":
        return cls(
            allowed_classes=data.get("allowed_classes", []),
            forbidden_classes=data.get("forbidden_classes", []),
            helmet_required=bool(data.get("helmet_required", False)),
            vest_required=bool(data.get("vest_required", False)),
            speed_limit_kmh=data.get("speed_limit_kmh", data.get("hiz_limiti")),
        )

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "allowed_classes": self.allowed_classes,
            "forbidden_classes": self.forbidden_classes,
            "helmet_required": self.helmet_required,
            "vest_required": self.vest_required,
        }
        if self.speed_limit_kmh is not None:
            res["speed_limit_kmh"] = self.speed_limit_kmh
        return res


@dataclass
class Zone:
    zone_id: str
    name: str
    type: str  # yasakli, yaya_yolu, arac_yolu, yukleme_alani
    polygon: List[Tuple[float, float]]  # [(x1, y1), (x2, y2), ...] normalize 0.0-1.0
    rules: ZoneRule = field(default_factory=ZoneRule)

    def validate(self) -> bool:
        # Poligonun en az 3 noktadan olustugunu kontrol et
        if len(self.polygon) < 3:
            return False

        # Koordinatlarin [0.0, 1.0] araliginda oldugunu kontrol et
        for pt in self.polygon:
            if not (0.0 <= pt[0] <= 1.0 and 0.0 <= pt[1] <= 1.0):
                return False

        return True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Zone":
        raw_poly = data.get("polygon", [])
        polygon = [(float(pt[0]), float(pt[1])) for pt in raw_poly]
        rules = ZoneRule.from_dict(data.get("rules", {}))

        zone = cls(
            zone_id=str(data.get("zone_id", "")),
            name=str(data.get("name", "")),
            type=str(data.get("type", "yasakli")),
            polygon=polygon,
            rules=rules,
        )

        if not zone.validate():
            raise ValueError(f"Gecersiz poligon veya koordinat (Zone ID: {zone.zone_id})")

        return zone

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "type": self.type,
            "polygon": [[pt[0], pt[1]] for pt in self.polygon],
            "rules": self.rules.to_dict(),
        }


def get_foot_point(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    """
    Bounding box nesnesinin alt-orta (ayak) noktasini hesaplar.
    bbox: (xmin, ymin, xmax, ymax)
    Dönüş: (x_center, y_bottom)
    """
    xmin, ymin, xmax, ymax = bbox
    x_center = round((xmin + xmax) / 2.0, 6)
    y_bottom = round(float(ymax), 6)
    return (x_center, y_bottom)


def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    cv2.pointPolygonTest kullanarak noktanin poligon icinde veya sinirinda olup olmadigini kontrol eder.
    """
    poly_np = np.array(polygon, dtype=np.float32)
    pt = (float(point[0]), float(point[1]))
    res = cv2.pointPolygonTest(poly_np, pt, measureDist=False)
    return res >= 0


def check_zone_violation(detection: Dict[str, Any], zone: Zone) -> Dict[str, Any] | None:
    """
    Tespit edilen nesnenin ayak noktasinin bolge kurallarini ihlal edip etmedigini kontrol eder.
    """
    bbox = detection.get("bbox")
    if not bbox or len(bbox) != 4:
        return None

    foot_pt = get_foot_point(bbox)
    if not is_point_in_polygon(foot_pt, zone.polygon):
        return None

    label = detection.get("label", "unknown")
    rules = zone.rules

    # 1. Arac yaya alaninda ihlali
    if zone.type == "yaya_yolu" and label in ["car", "truck", "forklift", "vehicle"]:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "vehicle_in_pedestrian_zone",
            "foot_point": foot_pt,
            "message": f"Arac yaya alaninda: '{label}' araci '{zone.name}' yaya yolunda tespit edildi.",
            "detection": detection,
        }

    # 2. Yaya arac bandinda ihlali
    if zone.type in ["arac_yolu", "yukleme_alani"] and label == "person":
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "pedestrian_in_vehicle_lane",
            "foot_point": foot_pt,
            "message": f"Yaya arac bandinda: Person nesnesi '{zone.name}' arac yolunda tespit edildi.",
            "detection": detection,
        }

    # 3. Yolda engel ihlali
    if zone.type == "arac_yolu" and label in ["box", "obstacle", "debris", "pallet"]:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "obstacle_on_road",
            "foot_point": foot_pt,
            "message": f"Yolda engel tespiti: '{label}' nesnesi '{zone.name}' arac yolunu engelliyor.",
            "detection": detection,
        }

    # 4. Yasakli siniflari kontrol et
    if label in rules.forbidden_classes:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "forbidden_class",
            "foot_point": foot_pt,
            "message": f"Yasakli sinif ihlali: '{label}' nesnesi '{zone.name}' bolgesinde yasak.",
            "detection": detection,
        }

    # 5. Izin verilen siniflari kontrol et (tanimlandiysa)
    if rules.allowed_classes and label not in rules.allowed_classes:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "unauthorized_class",
            "foot_point": foot_pt,
            "message": f"Izin verilmeyen sinif ihlali: '{label}' nesnesinin '{zone.name}' bolgesine giris izni yok.",
            "detection": detection,
        }

    # 6. Kisi icin baret zorunlulugunu kontrol et
    if label == "person" and rules.helmet_required and not detection.get("helmet", True):
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "missing_helmet",
            "foot_point": foot_pt,
            "message": f"Baretsiz kisi ihlali: '{zone.name}' bolgesinde baret takilmasi zorunludur.",
            "detection": detection,
        }

    # 7. Kisi icin yelek zorunlulugunu kontrol et
    if label == "person" and rules.vest_required and not detection.get("vest", True):
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "missing_vest",
            "foot_point": foot_pt,
            "message": f"Yeleksiz kisi ihlali: '{zone.name}' bolgesinde yelek giyilmesi zorunludur.",
            "detection": detection,
        }

    return None


def check_all_zones_violations(detections: List[Dict[str, Any]], zones: List[Zone]) -> List[Dict[str, Any]]:
    """Tespit edilen tum nesneleri tum bolgelere karsi kontrol eder."""
    violations = []
    pedestrian_zones = [z for z in zones if z.type == "yaya_yolu"]

    for det in detections:
        bbox = det.get("bbox")
        label = det.get("label", "unknown")

        # 4. Yaya alan disinda ihlali kontrolu
        if bbox and len(bbox) == 4 and label == "person" and pedestrian_zones:
            foot_pt = get_foot_point(bbox)
            in_safe_zone = any(is_point_in_polygon(foot_pt, z.polygon) for z in pedestrian_zones)
            if not in_safe_zone:
                violations.append({
                    "zone_id": "outside_zone",
                    "zone_name": "GUVENLI YAYA ALANI DISI",
                    "violation_type": "pedestrian_outside_safe_zone",
                    "foot_point": foot_pt,
                    "message": "Yaya alan disinda: Person nesnesi guvenli yaya yolu disinda tespit edildi.",
                    "detection": det,
                })

        for z in zones:
            viol = check_zone_violation(det, z)
            if viol:
                violations.append(viol)

    return violations


class ZoneDebouncer:
    """
    Bolge ihlalleri icin titreme (debounce) filtresi.
    Tek karelik gürültüleri filtrelemek icin alarm vermeden once N ardisik kare boyunca ihlal sartini arar.
    """

    def __init__(self, consecutive_threshold: int = 3):
        self.consecutive_threshold = max(1, consecutive_threshold)
        self.counters: Dict[str, int] = {}

    def _get_violation_key(self, viol: Dict[str, Any]) -> str:
        det = viol.get("detection", {})
        track_id = det.get("track_id", det.get("label", "unknown"))
        zone_id = viol.get("zone_id", "unknown_zone")
        viol_type = viol.get("violation_type", "unknown_type")
        return f"{zone_id}_{viol_type}_{track_id}"

    def process_frame_violations(self, raw_violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mevcut karedeki ihlalleri isler.
        N ardisik kare sartini saglayan onaylanmis ihlalleri doner.
        """
        current_keys = set()
        confirmed_violations = []

        for viol in raw_violations:
            key = self._get_violation_key(viol)
            current_keys.add(key)

            self.counters[key] = self.counters.get(key, 0) + 1

            if self.counters[key] >= self.consecutive_threshold:
                viol_copy = dict(viol)
                viol_copy["is_confirmed"] = True
                viol_copy["consecutive_count"] = self.counters[key]
                confirmed_violations.append(viol_copy)

        # Bu karede aktif olmayan ihlallerin sayaclarini sifirla
        missing_keys = set(self.counters.keys()) - current_keys
        for mk in missing_keys:
            self.counters[mk] = 0

        return confirmed_violations

    def reset(self) -> None:
        """Dahili ihlal sayaclarini sifirlar."""
        self.counters.clear()


def load_zones(filepath: str | Path) -> List[Zone]:
    """Bolgeleri JSON dosyasindan okur."""
    path = Path(filepath)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("zones.json bir bolge nesneleri listesi icermelidir")

    return [Zone.from_dict(item) for item in data]


def save_zones(zones: List[Zone], filepath: str | Path) -> None:
    """Bolge listesini JSON dosyasina kaydeder."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [z.to_dict() for z in zones]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
