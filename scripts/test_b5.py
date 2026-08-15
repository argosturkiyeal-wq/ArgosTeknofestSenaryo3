"""
Test script for zone violation debouncer (flicker filter).
Verifies that single-frame flicker noise is filtered and only N-consecutive frame violations trigger confirmed alarms.
"""

import sys
from pathlib import Path

# Add repo root to python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.zones import ZoneDebouncer


def test_zone_debouncer():
    print("Testing ZoneDebouncer flicker filter (N=3 consecutive frames)...")

    debouncer = ZoneDebouncer(consecutive_threshold=3)

    raw_violation = {
        "zone_id": "zone_01",
        "zone_name": "YUKLEME ALANI YASAKLI BOLGE",
        "violation_type": "forbidden_class",
        "detection": {"label": "person", "track_id": 101, "bbox": (0.15, 0.2, 0.35, 0.5)},
    }

    # Frame 1: 1st violation occurrence -> Filtered out (0 confirmed)
    conf_frame1 = debouncer.process_frame_violations([raw_violation])
    print(f"Frame 1 -> Raw: 1, Confirmed: {len(conf_frame1)}")
    assert len(conf_frame1) == 0, "Frame 1 single-frame flicker should be filtered out"

    # Frame 2: 2nd consecutive occurrence -> Filtered out (0 confirmed)
    conf_frame2 = debouncer.process_frame_violations([raw_violation])
    print(f"Frame 2 -> Raw: 1, Confirmed: {len(conf_frame2)}")
    assert len(conf_frame2) == 0, "Frame 2 should still be waiting for threshold=3"

    # Frame 3: 3rd consecutive occurrence -> Confirmed! (1 confirmed)
    conf_frame3 = debouncer.process_frame_violations([raw_violation])
    print(f"Frame 3 -> Raw: 1, Confirmed: {len(conf_frame3)}")
    assert len(conf_frame3) == 1, "Frame 3 should reach threshold and confirm violation"
    assert conf_frame3[0]["is_confirmed"] is True
    assert conf_frame3[0]["consecutive_count"] == 3
    print(f"Confirmed violation message: {conf_frame3[0].get('zone_name')} (consecutive: {conf_frame3[0].get('consecutive_count')})")

    # Frame 4: Object leaves zone -> 0 raw violations -> Reset counter
    conf_frame4 = debouncer.process_frame_violations([])
    print(f"Frame 4 (no violation) -> Confirmed: {len(conf_frame4)}")
    assert len(conf_frame4) == 0

    # Frame 5: Object enters again (1st occurrence after reset) -> Filtered out
    conf_frame5 = debouncer.process_frame_violations([raw_violation])
    print(f"Frame 5 (after reset) -> Confirmed: {len(conf_frame5)}")
    assert len(conf_frame5) == 0, "Frame 5 after reset should restart count from 1"

    print("[OK] All flicker filter (debouncer) tests passed successfully!\n")


if __name__ == "__main__":
    test_zone_debouncer()
