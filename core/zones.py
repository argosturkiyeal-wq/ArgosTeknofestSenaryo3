"""
Bolge tanimi ve zones.json yonetim modulu.
"""

import json
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
