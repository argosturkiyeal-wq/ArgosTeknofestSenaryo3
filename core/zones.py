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
    polygon: List[Tuple[float, float]]  # [(x1, y1), (x2, y2), ...] normalized 0.0-1.0
    rules: ZoneRule = field(default_factory=ZoneRule)

    def validate(self) -> bool:
        # Check polygon has at least 3 points
        if len(self.polygon) < 3:
            return False

        # Check coordinates are in range [0.0, 1.0]
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
            raise ValueError(f"Invalid polygon or coordinate for zone: {zone.zone_id}")

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
    Task B4: Calculate bottom-center (foot point) of bounding box.
    bbox: (xmin, ymin, xmax, ymax)
    Returns: (x_center, y_bottom)
    """
    xmin, ymin, xmax, ymax = bbox
    x_center = round((xmin + xmax) / 2.0, 6)
    y_bottom = round(float(ymax), 6)
    return (x_center, y_bottom)


def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Task B3: Check if point (x, y) is inside or on boundary of polygon using cv2.pointPolygonTest.
    Coordinates can be normalized (0.0-1.0) or pixel coords.
    """
    poly_np = np.array(polygon, dtype=np.float32)
    pt = (float(point[0]), float(point[1]))
    res = cv2.pointPolygonTest(poly_np, pt, measureDist=False)
    return res >= 0


def check_zone_violation(detection: Dict[str, Any], zone: Zone) -> Dict[str, Any] | None:
    """
    Task B3 + B4: Check if detection foot point violates rules of given zone.
    detection keys: {"label": str, "bbox": (xmin, ymin, xmax, ymax), "helmet": bool, "vest": bool, ...}
    Returns violation dict if violation detected, else None.
    """
    bbox = detection.get("bbox")
    if not bbox or len(bbox) != 4:
        return None

    foot_pt = get_foot_point(bbox)
    if not is_point_in_polygon(foot_pt, zone.polygon):
        return None

    label = detection.get("label", "unknown")
    rules = zone.rules

    # 1. Check forbidden classes
    if label in rules.forbidden_classes:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "forbidden_class",
            "foot_point": foot_pt,
            "message": f"Yasakli sinif ihlali: '{label}' nesnesi '{zone.name}' bolgesinde yasak.",
            "detection": detection,
        }

    # 2. Check allowed classes if defined
    if rules.allowed_classes and label not in rules.allowed_classes:
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "unauthorized_class",
            "foot_point": foot_pt,
            "message": f"Izin verilmeyen sinif ihlali: '{label}' nesnesinin '{zone.name}' bolgesine giris izni yok.",
            "detection": detection,
        }

    # 3. Check helmet requirement for person
    if label == "person" and rules.helmet_required and not detection.get("helmet", True):
        return {
            "zone_id": zone.zone_id,
            "zone_name": zone.name,
            "violation_type": "missing_helmet",
            "foot_point": foot_pt,
            "message": f"Baretsiz kisi ihlali: '{zone.name}' bolgesinde baret takilmasi zorunludur.",
            "detection": detection,
        }

    # 4. Check vest requirement for person
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
    """Check list of detections against all zones."""
    violations = []
    for det in detections:
        for z in zones:
            viol = check_zone_violation(det, z)
            if viol:
                violations.append(viol)
    return violations


def load_zones(filepath: str | Path) -> List[Zone]:
    """Read zones from JSON file."""
    path = Path(filepath)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("zones.json must contain a list of zone objects")

    return [Zone.from_dict(item) for item in data]


def save_zones(zones: List[Zone], filepath: str | Path) -> None:
    """Save zones list to JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [z.to_dict() for z in zones]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

