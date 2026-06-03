"""CLI entrypoint."""
from __future__ import annotations

import argparse
from typing import List

import config as cfg
from kpi import compute_kpis, print_kpi_summary, write_kpi_csv
from scenarios import run_scenario, SimResult
from visualization import plot_lighting_energy_pct_diff


SCENARIOS = ("always_on", "sensor_based", "route_based")


def parse_args():
    p = argparse.ArgumentParser(description="Energy-efficient warehouse simulation.")
    p.add_argument(
        "--scenario",
        choices=SCENARIOS + ("all",),
        default="all",
        help="Which lighting strategy to run.",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=cfg.SHIFT_DURATION_S,
        help="Simulation duration in seconds (default: 8 h).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=cfg.RANDOM_SEED,
        help="Random seed for reproducibility.",
    )
    p.add_argument(
        "--animate",
        action="store_true",
        help="Open a salabim animation window (single-scenario runs only).",
    )
    p.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip generating the comparison PNG.",
    )
    return p.parse_args()


def run_one(scenario: str, duration: float, seed: int, animate: bool, plots: bool = True):
    print(f"\n>>> running scenario: {scenario}  (duration={duration:.0f}s, seed={seed})")
    result: SimResult = run_scenario(
        scenario=scenario,
        duration_s=duration,
        seed=seed,
        animate=animate,
    )
    kpi = compute_kpis(result)
    print_kpi_summary(kpi)
    path = write_kpi_csv(kpi)
    print(f"  -> wrote {path}")
    if plots:
        from visualization import plot_per_scenario_diagnostics
        plot_per_scenario_diagnostics(result)
    return result, kpi


def main():
    args = parse_args()

    if args.scenario == "all":
        if args.animate:
            print("[!] --animate is ignored when running all scenarios; "
                  "pick a single scenario to animate.")
        results = []
        kpis = []
        for s in SCENARIOS:
            r, k = run_one(s, args.duration, args.seed, animate=False)
            results.append(r)
            kpis.append(k)

        if not args.no_plot:
            # Cleaned up and properly formatted local import
            from visualization import plot_scenario_comparison, plot_warehouse_layout

            # Executing the visualizer functions sequentially
            plot_scenario_comparison(kpis)
            plot_lighting_energy_pct_diff(kpis)
            plot_warehouse_layout()
    else:
        run_one(args.scenario, args.duration, args.seed, args.animate)


if __name__ == "__main__":
    main()