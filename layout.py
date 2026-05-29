"""Warehouse layout: aisles, cross-aisles, pickup points, lights and sensors.

The layout follows the I-shape design described in the report:
    - Base zone occupies x in [0, 7], full height in y.
    - Rack/aisle area occupies x in [7, 70].
    - Pattern (left-to-right): R A R A ... R A (14 racks alternating with 14 aisles).
    - Three horizontal cross-aisles (bottom, middle, top) of 3.5 m height each.
    - Two rack segments (bottom, top) of 12.25 m height each.

Coordinate convention:
    x = horizontal position along the 70 m length (0 at left wall / base)
    y = vertical position along the 35 m width   (0 at bottom wall)

Numbering convention:
    aisles    1..14 (left-to-right)
    cross-aisles "bottom", "middle", "top"
    rack segments "bottom", "top"   (bottom = y < middle cross-aisle)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import config as cfg


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def aisle_center_x(aisle_idx: int) -> float:
    """Return the centerline x-coordinate of picking aisle `aisle_idx` (1-based).

    Pattern R A R A ... starting at x = RACK_AREA_X_START:
        Rack k:  x in [start + (k-1)*(R+A),  start + (k-1)*(R+A) + R]
        Aisle k: x in [start + (k-1)*(R+A) + R,  start + k*(R+A)]
    So aisle k's center = start + (k-1)*(R+A) + R + A/2.
    """
    if not (1 <= aisle_idx <= cfg.N_AISLES):
        raise ValueError(f"aisle_idx {aisle_idx} out of range")
    step = cfg.RACK_WIDTH + cfg.AISLE_WIDTH
    return (
        cfg.RACK_AREA_X_START
        + (aisle_idx - 1) * step
        + cfg.RACK_WIDTH
        + cfg.AISLE_WIDTH / 2
    )


# Cross-aisle centerlines along y
CROSS_AISLE_NAMES: Tuple[str, ...] = ("bottom", "middle", "top")
CROSS_AISLE_Y = {
    "bottom": cfg.CROSS_AISLE_WIDTH / 2,                               # 1.75
    "middle": cfg.CROSS_AISLE_WIDTH + cfg.RACK_SEGMENT_HEIGHT
              + cfg.CROSS_AISLE_WIDTH / 2,                              # 17.5
    "top": cfg.WAREHOUSE_WIDTH - cfg.CROSS_AISLE_WIDTH / 2,            # 33.25
}

# y-range for each rack segment (where pickup points live)
RACK_SEGMENT_Y_RANGES = {
    # segment name -> (y_min, y_max)
    "bottom": (
        cfg.CROSS_AISLE_WIDTH,
        cfg.CROSS_AISLE_WIDTH + cfg.RACK_SEGMENT_HEIGHT,
    ),
    "top": (
        cfg.CROSS_AISLE_WIDTH + cfg.RACK_SEGMENT_HEIGHT + cfg.CROSS_AISLE_WIDTH,
        cfg.WAREHOUSE_WIDTH - cfg.CROSS_AISLE_WIDTH,
    ),
}


# ---------------------------------------------------------------------------
# Pickup points
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PickupPoint:
    pickup_id: int
    aisle: int                    # 1..14
    segment: str                  # "bottom" or "top"
    index_in_segment: int         # 1..12
    x: float
    y: float


def build_pickup_points() -> List[PickupPoint]:
    """Build the canonical list of unique pickup (x,y) locations.

    Each (aisle, segment, index) tuple is unique. The 'side' of the rack
    (left vs right) is irrelevant for routing since both sides share the
    same picking-aisle centerline, so we collapse them. 14 aisles x
    2 segments x 12 indices = 336 routing-distinct pickup locations.
    """
    points: List[PickupPoint] = []
    pid = 0
    for aisle in range(1, cfg.N_AISLES + 1):
        x = aisle_center_x(aisle)
        for segment in ("bottom", "top"):
            y_min, y_max = RACK_SEGMENT_Y_RANGES[segment]
            slot = (y_max - y_min) / cfg.PICKUP_POINTS_PER_SIDE_PER_SEGMENT
            for i in range(1, cfg.PICKUP_POINTS_PER_SIDE_PER_SEGMENT + 1):
                y = y_min + (i - 0.5) * slot
                pid += 1
                points.append(
                    PickupPoint(
                        pickup_id=pid,
                        aisle=aisle,
                        segment=segment,
                        index_in_segment=i,
                        x=x,
                        y=y,
                    )
                )
    return points


# ---------------------------------------------------------------------------
# Segments — used as both lighting zones and sensor zones.
# ---------------------------------------------------------------------------
@dataclass
class Segment:
    """A logical zone of the warehouse covered by one sensor / one+ lights.

    A segment groups together (a) a geometric region that an AGV can traverse,
    (b) the sensor that fires when an AGV enters it, and (c) the lights that
    illuminate that region.
    """
    seg_id: str                   # unique key, e.g. "aisle_3_top" or "xa_middle_5"
    kind: str                     # "base" | "cross_aisle" | "picking_aisle"
    # geometry hints for animation / debug
    x_range: Tuple[float, float]
    y_range: Tuple[float, float]
    # back-references; populated during build
    lights: List["Light"] = field(default_factory=list)
    # entry/exit nodes in the routing graph (set later by routing module)
    entry_nodes: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Lights
# ---------------------------------------------------------------------------
@dataclass
class Light:
    light_id: str
    kind: str                     # "main" | "cross_aisle" | "base"
    power_w: float
    lumen: float
    x: float
    y: float
    segment_id: str               # which segment this light covers


def _seg_id_picking(aisle: int, segment: str) -> str:
    return f"aisle_{aisle}_{segment}"


def _seg_id_cross(xa_name: str, sub_idx: int) -> str:
    return f"xa_{xa_name}_{sub_idx}"


SEG_ID_BASE = "base"


def build_layout() -> Tuple[List[Segment], List[Light], List[PickupPoint]]:
    """Construct segments, lights and pickup points for the warehouse.

    Returns
    -------
    segments : List[Segment]
    lights   : List[Light]
    pickups  : List[PickupPoint]
    """
    segments: List[Segment] = []
    lights: List[Light] = []

    # --- Base segment: covers x in [0, 7], full height -----------------------
    base_seg = Segment(
        seg_id=SEG_ID_BASE,
        kind="base",
        x_range=(0.0, cfg.BASE_WIDTH),
        y_range=(0.0, cfg.WAREHOUSE_WIDTH),
    )
    segments.append(base_seg)

    # 3 base lights, distributed along y at the base centerline x.
    base_x = cfg.BASE_WIDTH / 2
    for i in range(cfg.N_BASE_LIGHTS):
        y = (i + 1) / (cfg.N_BASE_LIGHTS + 1) * cfg.WAREHOUSE_WIDTH
        light = Light(
            light_id=f"base_light_{i+1}",
            kind="base",
            power_w=cfg.BASE_LIGHT_POWER_W,
            lumen=cfg.BASE_LIGHT_LUMEN,
            x=base_x,
            y=y,
            segment_id=SEG_ID_BASE,
        )
        lights.append(light)
        base_seg.lights.append(light)

    # --- Picking-aisle segments (28 total) -----------------------------------
    for aisle in range(1, cfg.N_AISLES + 1):
        ax = aisle_center_x(aisle)
        for seg_name in ("bottom", "top"):
            y_min, y_max = RACK_SEGMENT_Y_RANGES[seg_name]
            seg = Segment(
                seg_id=_seg_id_picking(aisle, seg_name),
                kind="picking_aisle",
                x_range=(ax - cfg.AISLE_WIDTH / 2, ax + cfg.AISLE_WIDTH / 2),
                y_range=(y_min, y_max),
            )
            # one light centered in the segment
            light = Light(
                light_id=f"main_aisle{aisle}_{seg_name}",
                kind="main",
                power_w=cfg.MAIN_LIGHT_POWER_W,
                lumen=cfg.MAIN_LIGHT_LUMEN,
                x=ax,
                y=(y_min + y_max) / 2,
                segment_id=seg.seg_id,
            )
            lights.append(light)
            seg.lights.append(light)
            segments.append(seg)

    # --- Cross-aisle sub-segments (42 total) ---------------------------------
    # Each cross-aisle is split into 14 sub-segments, one centered on each
    # picking-aisle column. Each sub-segment has 1 light + 1 sensor.
    sub_seg_x_half = (cfg.RACK_WIDTH + cfg.AISLE_WIDTH) / 2  # 2.25 m
    for xa_name in CROSS_AISLE_NAMES:
        y_center = CROSS_AISLE_Y[xa_name]
        y_min = y_center - cfg.CROSS_AISLE_WIDTH / 2
        y_max = y_center + cfg.CROSS_AISLE_WIDTH / 2
        for sub_idx in range(1, cfg.N_AISLES + 1):
            ax = aisle_center_x(sub_idx)
            seg = Segment(
                seg_id=_seg_id_cross(xa_name, sub_idx),
                kind="cross_aisle",
                x_range=(ax - sub_seg_x_half, ax + sub_seg_x_half),
                y_range=(y_min, y_max),
            )
            light = Light(
                light_id=f"xa_{xa_name}_{sub_idx}",
                kind="cross_aisle",
                power_w=cfg.CROSS_AISLE_LIGHT_POWER_W,
                lumen=cfg.CROSS_AISLE_LIGHT_LUMEN,
                x=ax,
                y=y_center,
                segment_id=seg.seg_id,
            )
            lights.append(light)
            seg.lights.append(light)
            segments.append(seg)

    pickups = build_pickup_points()
    return segments, lights, pickups


# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------
def segments_by_id(segments: List[Segment]) -> dict[str, Segment]:
    return {s.seg_id: s for s in segments}


if __name__ == "__main__":  # smoke test
    segs, lts, pks = build_layout()
    print(f"segments: {len(segs)}")
    print(f"lights:   {len(lts)}  (base={sum(1 for l in lts if l.kind=='base')}, "
          f"main={sum(1 for l in lts if l.kind=='main')}, "
          f"xa={sum(1 for l in lts if l.kind=='cross_aisle')})")
    print(f"pickups:  {len(pks)}")
    print(f"aisle 1 center x  = {aisle_center_x(1):.2f}")
    print(f"aisle 14 center x = {aisle_center_x(14):.2f}")
    print(f"CROSS_AISLE_Y     = {CROSS_AISLE_Y}")
