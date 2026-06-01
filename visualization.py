"""Static plots + salabim animation hooks.

Static plotting (matplotlib) is implemented eagerly so we can sanity-check
results. The animation function `attach_animation` is implemented further
down and is only invoked when --animate is passed.
"""
from __future__ import annotations

import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for static plots
import matplotlib.patches as patches
import matplotlib.pyplot as plt

import config as cfg
from kpi import KPIBundle
from scenarios import SimResult


# =========================================================================
# Static plots
# =========================================================================
def plot_scenario_comparison(kpis: List[KPIBundle], out_dir: str = cfg.RESULTS_DIR) -> str:
    os.makedirs(out_dir, exist_ok=True)
    scenarios = [k.scenario for k in kpis]
    lighting = [k.lighting_energy_wh for k in kpis]
    agv = [k.agv_energy_wh for k in kpis]
    tput = [k.avg_throughput_time_s for k in kpis]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))

    # (a) Stacked energy
    ax = axes[0]
    x = range(len(scenarios))
    ax.bar(x, lighting, label="Lighting", color="#f4b942")
    ax.bar(x, agv, bottom=lighting, label="AGV", color="#3a86ff")
    ax.set_xticks(list(x))
    ax.set_xticklabels(scenarios)
    ax.set_ylabel("Energy (Wh)")
    ax.set_title("Energy consumption per scenario")
    ax.legend()
    for i, (lt, av) in enumerate(zip(lighting, agv)):
        ax.text(i, lt + av, f"{lt+av:.0f}", ha="center", va="bottom", fontsize=9)

    # (b) Avg throughput time
    ax = axes[1]
    ax.bar(x, tput, color="#2a9d8f")
    ax.set_xticks(list(x))
    ax.set_xticklabels(scenarios)
    ax.set_ylabel("Average throughput time (s)")
    ax.set_title("Throughput time per scenario")
    for i, t in enumerate(tput):
        ax.text(i, t, f"{t:.1f}s", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    path = os.path.join(out_dir, "scenario_comparison.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  -> wrote {path}")
    return path


def plot_per_scenario_diagnostics(result: SimResult, out_dir: str = cfg.RESULTS_DIR) -> str:
    """Light on-time distribution + per-AGV utilization for a single scenario."""
    os.makedirs(out_dir, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # (a) histogram of light on-time per light
    on_times = [l.total_on_time_s for l in result.lights]
    axes[0].hist(on_times, bins=30, color="#f4b942", edgecolor="black")
    axes[0].set_xlabel("Total on-time per light (s)")
    axes[0].set_ylabel("Count of lights")
    axes[0].set_title(f"Light on-time distribution — {result.scenario}")

    # (b) per-AGV utilization (busy time / shift)
    busy = [a.total_time_travelled_s / result.duration_s * 100 for a in result.agvs]
    labels = [f"AGV {a.agv_id}" for a in result.agvs]
    axes[1].bar(labels, busy, color="#3a86ff")
    axes[1].set_ylabel("Travel time (% of shift)")
    axes[1].set_title(f"AGV utilization — {result.scenario}")
    axes[1].set_ylim(0, 100)
    for i, b in enumerate(busy):
        axes[1].text(i, b, f"{b:.0f}%", ha="center", va="bottom")

    plt.tight_layout()
    path = os.path.join(out_dir, f"diagnostics_{result.scenario}.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  -> wrote {path}")
    return path


def plot_warehouse_layout(out_dir: str = cfg.RESULTS_DIR) -> str:
    """Render the static warehouse layout (racks, aisles, lights) once for reference."""
    import layout as L

    os.makedirs(out_dir, exist_ok=True)
    segments, lights, pickups = L.build_layout()

    fig, ax = plt.subplots(figsize=(12, 6))

    # Outer warehouse
    ax.add_patch(patches.Rectangle((0, 0), cfg.WAREHOUSE_LENGTH, cfg.WAREHOUSE_WIDTH,
                                   fill=False, edgecolor="black", linewidth=2))

    # Base zone
    ax.add_patch(patches.Rectangle((0, 0), cfg.BASE_WIDTH, cfg.WAREHOUSE_WIDTH,
                                   facecolor="#fff3cd", edgecolor="gray"))
    ax.text(cfg.BASE_WIDTH / 2, cfg.WAREHOUSE_WIDTH / 2, "BASE",
            ha="center", va="center", fontsize=10)

    # Racks
    step = cfg.RACK_WIDTH + cfg.AISLE_WIDTH
    for k in range(1, cfg.N_RACKS + 1):
        rx0 = cfg.RACK_AREA_X_START + (k - 1) * step
        ax.add_patch(patches.Rectangle(
            (rx0, cfg.CROSS_AISLE_WIDTH),
            cfg.RACK_WIDTH, cfg.RACK_SEGMENT_HEIGHT,
            facecolor="#cce5ff", edgecolor="gray"))
        ax.add_patch(patches.Rectangle(
            (rx0, cfg.CROSS_AISLE_WIDTH + cfg.RACK_SEGMENT_HEIGHT + cfg.CROSS_AISLE_WIDTH),
            cfg.RACK_WIDTH, cfg.RACK_SEGMENT_HEIGHT,
            facecolor="#cce5ff", edgecolor="gray"))

    # Lights
    main_x = [l.x for l in lights if l.kind == "main"]
    main_y = [l.y for l in lights if l.kind == "main"]
    base_x = [l.x for l in lights if l.kind == "base"]
    base_y = [l.y for l in lights if l.kind == "base"]
    xa_x   = [l.x for l in lights if l.kind == "cross_aisle"]
    xa_y   = [l.y for l in lights if l.kind == "cross_aisle"]
    ax.scatter(main_x, main_y, c="#ffd23f", s=70, edgecolor="black",
               label=f"Main lights (n={len(main_x)})", zorder=5)
    ax.scatter(base_x, base_y, c="#ff7700", s=70, edgecolor="black",
               label=f"Base lights (n={len(base_x)})", zorder=5)
    ax.scatter(xa_x, xa_y, c="#90ee90", s=30, edgecolor="black",
               label=f"Cross-aisle lights (n={len(xa_x)})", zorder=5)

    ax.set_xlim(-1, cfg.WAREHOUSE_LENGTH + 1)
    ax.set_ylim(-1, cfg.WAREHOUSE_WIDTH + 1)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Warehouse layout (lights overlaid)")
    ax.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    path = os.path.join(out_dir, "warehouse_layout.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  -> wrote {path}")
    return path


# =========================================================================
# Animation (optional)
# =========================================================================
def attach_animation(env, agvs, energy_lights, sls_by_seg):
    """Draw the warehouse layout + AGVs + light states using salabim's animation.

    World coordinates: we map the 70 m x 35 m warehouse to a window with
    a small margin. salabim then handles px-conversion internally so we
    can pass values straight in metres.
    """
    import salabim as sim
    import layout as L

    # World coordinate system: warehouse 70 x 35, with a 5 m margin.
    env.animation_parameters(
        animate=True,
        speed=20.0,                # 20x real-time
        modelname="Warehouse Smart Lighting",
        background_color="white",
        x0=-5, y0=-5, x1=75,
        width=1100, height=560,
        show_fps=False,
        show_time=True,
    )

    # --- background: outer warehouse rectangle -------------------------------
    sim.AnimateRectangle(
        spec=(0, 0, L.cfg.WAREHOUSE_LENGTH, L.cfg.WAREHOUSE_WIDTH),
        fillcolor="white",
        linecolor="black",
        linewidth=0.2,
    )

    # Base zone
    sim.AnimateRectangle(
        spec=(0, 0, L.cfg.BASE_WIDTH, L.cfg.WAREHOUSE_WIDTH),
        fillcolor="#fff3cd",
        linecolor="gray",
    )

    # Racks (re-derive layout.py geometry)
    rack_step = L.cfg.RACK_WIDTH + L.cfg.AISLE_WIDTH
    bottom_top_y = L.cfg.CROSS_AISLE_WIDTH + L.cfg.RACK_SEGMENT_HEIGHT + L.cfg.CROSS_AISLE_WIDTH
    for k in range(1, L.cfg.N_RACKS + 1):
        rx0 = L.cfg.RACK_AREA_X_START + (k - 1) * rack_step
        rx1 = rx0 + L.cfg.RACK_WIDTH
        sim.AnimateRectangle(
            spec=(rx0, L.cfg.CROSS_AISLE_WIDTH,
                  rx1, L.cfg.CROSS_AISLE_WIDTH + L.cfg.RACK_SEGMENT_HEIGHT),
            fillcolor="#cce5ff",
            linecolor="gray",
        )
        sim.AnimateRectangle(
            spec=(rx0, bottom_top_y,
                  rx1, bottom_top_y + L.cfg.RACK_SEGMENT_HEIGHT),
            fillcolor="#cce5ff",
            linecolor="gray",
        )

    # --- lights: yellow when on, gray when off -------------------------------
    layout_lights_by_id = {ll.light_id: ll for ll in L.build_layout()[1]}

    def make_color(el):
        # capture el by argument to avoid late-binding
        return lambda t: "#ffd23f" if el.state == "on" else "#bbbbbb"

    for light_id, el in energy_lights.items():
        ll = layout_lights_by_id[light_id]
        s = 0.6 if ll.kind != "cross_aisle" else 0.35  # half-width in metres
        sim.AnimateRectangle(
            spec=(ll.x - s, ll.y - s, ll.x + s, ll.y + s),
            fillcolor=make_color(el),
            linecolor="black",
            linewidth=0.05,
        )

    # AGVs: different color
    colores = ["#e63946", "#457b9d", "#2a9d8f"] # Rojo, Azul, Verde

    for agv in agvs:
        
        color_agv = colores[agv.agv_id % len(colores)]
    
        sim.AnimateCircle(
            radius=0.8,
            x=lambda t, a=agv: a.x,
            y=lambda t, a=agv: a.y,
            fillcolor=color_agv,
            linecolor="black"
        )

    start_x = 10 
    y_leyenda = -3

    for i, color in enumerate(colores):
    # Colored circles
        sim.AnimateCircle(
            radius=0.75,
            x=start_x + (i * 10), 
            y=y_leyenda,
            fillcolor=color
        )  
    # Text
        sim.AnimateText(
            text=f"AGV {i+1}",
            x=start_x + (i * 10) + 1.5,
            y=y_leyenda,
            fontsize=2.5
        )
