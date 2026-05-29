"""KPI computation + CSV output."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List

import config as cfg
from scenarios import SimResult


@dataclass
class KPIBundle:
    scenario: str
    duration_s: float
    orders_created: int
    orders_completed: int
    avg_throughput_time_s: float
    lighting_energy_wh: float
    agv_energy_wh: float
    total_energy_wh: float
    total_distance_m: float
    energy_cost_eur: float
    per_agv: list


def compute_kpis(result: SimResult) -> KPIBundle:
    lighting_energy_wh = sum(l.total_energy_wh for l in result.lights)
    total_distance_m = sum(a.total_distance_m for a in result.agvs)
    agv_energy_wh = total_distance_m * cfg.AGV_ENERGY_PER_M  # Wh
    total_energy_wh = lighting_energy_wh + agv_energy_wh

    completed = result.completed_orders
    if completed:
        avg_tput = sum(o.cycle_time for o in completed) / len(completed)
    else:
        avg_tput = 0.0

    per_agv = [
        {
            "agv_id": a.agv_id,
            "orders_served": a.orders_served,
            "distance_m": a.total_distance_m,
            "time_travelled_s": a.total_time_travelled_s,
            "energy_wh": a.total_distance_m * cfg.AGV_ENERGY_PER_M,
        }
        for a in result.agvs
    ]

    return KPIBundle(
        scenario=result.scenario,
        duration_s=result.duration_s,
        orders_created=result.orders_created,
        orders_completed=result.orders_completed,
        avg_throughput_time_s=avg_tput,
        lighting_energy_wh=lighting_energy_wh,
        agv_energy_wh=agv_energy_wh,
        total_energy_wh=total_energy_wh,
        total_distance_m=total_distance_m,
        energy_cost_eur=total_energy_wh / 1000.0 * cfg.ELECTRICITY_PRICE_PER_KWH,
        per_agv=per_agv,
    )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_kpi_csv(kpi: KPIBundle, results_dir: str = cfg.RESULTS_DIR) -> str:
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"{kpi.scenario}_{_timestamp()}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "unit"])
        w.writerow(["scenario", kpi.scenario, "-"])
        w.writerow(["duration", kpi.duration_s, "s"])
        w.writerow(["orders_created", kpi.orders_created, "count"])
        w.writerow(["orders_completed", kpi.orders_completed, "count"])
        w.writerow(["avg_throughput_time", kpi.avg_throughput_time_s, "s"])
        w.writerow(["lighting_energy", kpi.lighting_energy_wh, "Wh"])
        w.writerow(["agv_energy", kpi.agv_energy_wh, "Wh"])
        w.writerow(["total_energy", kpi.total_energy_wh, "Wh"])
        w.writerow(["total_agv_distance", kpi.total_distance_m, "m"])
        w.writerow(["energy_cost", kpi.energy_cost_eur, "EUR"])
        w.writerow([])
        w.writerow(["agv_id", "orders_served", "distance_m", "time_travelled_s", "energy_wh"])
        for row in kpi.per_agv:
            w.writerow([row["agv_id"], row["orders_served"], row["distance_m"],
                        row["time_travelled_s"], row["energy_wh"]])
    return path


def print_kpi_summary(kpi: KPIBundle) -> None:
    print(f"\n=== KPI summary: {kpi.scenario} ===")
    print(f"  duration:              {kpi.duration_s/3600:.2f} h")
    print(f"  orders created:        {kpi.orders_created}")
    print(f"  orders completed:      {kpi.orders_completed}")
    print(f"  avg throughput time:   {kpi.avg_throughput_time_s:.1f} s")
    print(f"  lighting energy:       {kpi.lighting_energy_wh:>10.1f} Wh")
    print(f"  AGV energy:            {kpi.agv_energy_wh:>10.1f} Wh")
    print(f"  total energy:          {kpi.total_energy_wh:>10.1f} Wh "
          f"({kpi.total_energy_wh/1000:.2f} kWh)")
    print(f"  total AGV distance:    {kpi.total_distance_m:.1f} m")
    print(f"  energy cost:           EUR {kpi.energy_cost_eur:.2f}")
    print(f"  per-AGV:")
    for r in kpi.per_agv:
        print(f"    AGV {r['agv_id']}: orders={r['orders_served']}, "
              f"distance={r['distance_m']:.1f} m, "
              f"travelled_time={r['time_travelled_s']:.1f} s")
