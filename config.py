"""Global parameters for the warehouse simulation.

All locked-in values from the system spec live here so every other module
imports from a single source of truth.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Simulation horizon
# ---------------------------------------------------------------------------
SHIFT_DURATION_S: float = 8 * 3600.0          # 8-hour shift in seconds
RANDOM_SEED: int = 42                         # for reproducibility

# ---------------------------------------------------------------------------
# Warehouse geometry (metres). x = length axis (0..70), y = width axis (0..35).
# ---------------------------------------------------------------------------
WAREHOUSE_LENGTH: float = 70.0
WAREHOUSE_WIDTH: float = 35.0

# Base
BASE_WIDTH: float = 7.0                       # base spans x in [0, 7]
BASE_CENTER = (3.5, 17.5)                     # AGV start/end point

# Rack/aisle area (x in [7, 70])
RACK_AREA_X_START: float = BASE_WIDTH
RACK_WIDTH: float = 2.0
AISLE_WIDTH: float = 2.5
N_AISLES: int = 14
N_RACKS: int = 14                             # pattern: R A R A ... R A

# Cross-aisles (horizontal). Pattern bottom_xa | seg_bot | mid_xa | seg_top | top_xa
CROSS_AISLE_WIDTH: float = 3.5
RACK_SEGMENT_HEIGHT: float = 12.25
N_CROSS_AISLES: int = 3                       # bottom, middle, top
N_RACK_SEGMENTS: int = 2                      # bottom, top

# Pickup-point granularity (per rack side per segment)
PICKUP_POINTS_PER_SIDE_PER_SEGMENT: int = 12

# ---------------------------------------------------------------------------
# AGV
# ---------------------------------------------------------------------------
N_AGVS: int = 3
AGV_SPEED: float = 1.0                        # m/s
AGV_ENERGY_PER_KM: float = 3.7                # kWh / km
AGV_ENERGY_PER_M: float = AGV_ENERGY_PER_KM * 1000 / 1000  # = 3.7 Wh / m
# (3.7 kWh per km == 3700 Wh per 1000 m == 3.7 Wh per metre)

# ---------------------------------------------------------------------------
# Lighting
# ---------------------------------------------------------------------------
# Main lights placed in picking aisles (1 per aisle-segment) plus base lights.
MAIN_LIGHT_POWER_W: float = 150.0
MAIN_LIGHT_LUMEN: float = 16000.0

CROSS_AISLE_LIGHT_POWER_W: float = 150.0
CROSS_AISLE_LIGHT_LUMEN: float = 2500.0

# Base lights: 3 lights covering the base zone. They are 'main' fixtures too.
N_BASE_LIGHTS: int = 3
BASE_LIGHT_POWER_W: float = 150.0
BASE_LIGHT_LUMEN: float = 16000.0

# Sensor / smart-lighting behaviour
SWITCH_OFF_DELAY_S: float = 20.0

# ---------------------------------------------------------------------------
# Order generation
# ---------------------------------------------------------------------------
# Inter-arrival time: exponential with mean 1.5477 minutes (see report sec 9.3).
INTER_ARRIVAL_MEAN_S: float = 1.5477 * 60.0   # convert to seconds
PICKUP_TIME_S: float = 15.0                   # constant; swap for a dist later

# ---------------------------------------------------------------------------
# Energy pricing (used only for cost KPIs)
# ---------------------------------------------------------------------------
ELECTRICITY_PRICE_PER_KWH: float = 0.23       # EUR

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
RESULTS_DIR: str = "results"
