"""Exclusion zone filtering.

Allows the farmer to define rectangular regions in the camera frame
to ignore (scarecrows, clotheslines, permanent structures). Any
detection whose center falls inside an exclusion zone is discarded.
"""

import logging
from dataclasses import dataclass

from .human_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Zone:
    """A rectangular exclusion zone in pixel coordinates."""
    x: int
    y: int
    w: int
    h: int
    label: str = ""


class ExclusionZoneFilter:
    """Filters out detections that fall within defined exclusion zones."""

    def __init__(self):
        self._zones: dict[str, list[Zone]] = {}  # camera_id -> zones

    def set_zones(self, camera_id: str, zones: list[dict]):
        """Set exclusion zones for a camera.

        Args:
            camera_id: e.g., 'cam_front'
            zones: list of dicts with keys: x, y, w, h, label
        """
        self._zones[camera_id] = [
            Zone(x=z["x"], y=z["y"], w=z["w"], h=z["h"],
                 label=z.get("label", ""))
            for z in zones
        ]
        logger.info("Set %d exclusion zones for %s", len(zones), camera_id)

    def filter(self, camera_id: str,
               detections: list[Detection]) -> list[Detection]:
        """Remove detections whose center falls inside any exclusion zone."""
        zones = self._zones.get(camera_id, [])
        if not zones:
            return detections

        filtered = []
        for det in detections:
            cx = det.x + det.w // 2
            cy = det.y + det.h // 2
            excluded = False
            for zone in zones:
                if (zone.x <= cx <= zone.x + zone.w and
                        zone.y <= cy <= zone.y + zone.h):
                    logger.debug("Detection excluded by zone '%s'", zone.label)
                    excluded = True
                    break
            if not excluded:
                filtered.append(det)

        return filtered

    def get_zones(self, camera_id: str) -> list[Zone]:
        return self._zones.get(camera_id, [])
