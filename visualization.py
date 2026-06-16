"""Static matplotlib plots and the salabim animation."""
from __future__ import annotations

import os
from typing import List

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
def attach_animation(env, agvs, energy_lights, sls_by_seg, order_gen=None, recorder=None,
                     scenario=""):
    """Draw the warehouse, AGVs, light states and a live stats panel."""
    import salabim as sim
    import layout as L

    # Coordinates are in metres. Extra window height leaves a band above the
    # warehouse (y > 35) for the stats panel; modelname is blank to avoid overlap.
    env.animation_parameters(
        animate=True,
        speed=20.0,                # 20x real-time
        modelname="",
        background_color="white",
        x0=-5, y0=-5, x1=75,
        width=1100, height=820,
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

    # Racks
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

    # sensor zones: outline every segment, highlight active ones in orange
    segments = L.build_layout()[0]

    def _zone_line(s):
        return lambda t: "#ff7700" if (s.occupancy > 0 or s.route_active) else "#dddddd"

    def _zone_fill(s):
        return lambda t: ("#ffa500", 70) if (s.occupancy > 0 or s.route_active) else ""

    for seg in segments:
        if seg.kind == "base":
            continue
        sls = sls_by_seg.get(seg.seg_id)
        if sls is None:
            continue
        x0, x1 = seg.x_range
        y0_, y1_ = seg.y_range
        sim.AnimateRectangle(
            spec=(x0, y0_, x1, y1_),
            fillcolor=_zone_fill(sls),
            linecolor=_zone_line(sls),
            linewidth=0.08,
        )

    # lights: yellow when on, gray when off
    layout_lights_by_id = {ll.light_id: ll for ll in L.build_layout()[1]}

    def make_color(el):
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

    # AGVs as coloured circles (AGV 1 -> colors[0] to match the legend)
    colors = ["#e63946", "#457b9d", "#2a9d8f"]

    for agv in agvs:
        sim.AnimateCircle(
            radius=1,
            x=lambda t, a=agv: a.x,
            y=lambda t, a=agv: a.y,
            fillcolor=colors[(agv.agv_id - 1) % len(colors)],
            linecolor="black",
        )

    # legend
    legend_x = 10
    legend_y = -3
    for i, color in enumerate(colors):
        sim.AnimateCircle(radius=0.75, x=legend_x + i * 10, y=legend_y, fillcolor=color)
        sim.AnimateText(text=f"AGV {i+1}", x=legend_x + i * 10 + 1.5, y=legend_y,
                        fontsize=2.5)

    # live stats panel, in the band above the warehouse
    sim.AnimateText(text=f"scenario: {scenario}", x=0.5, y=53, text_anchor="w",
                    fontsize=2.0, textcolor="black")

    def _line_flow(t):
        # `t` is the smooth animation time (env.now() only advances at events)
        now = t
        created = order_gen.next_order_id if order_gen is not None else 0
        completed = sum(a.orders_served for a in agvs)
        if order_gen is not None:
            cts = [o.cycle_time for o in order_gen.orders_created
                   if o.completion_time is not None]
            tput = sum(cts) / len(cts) if cts else 0.0
        else:
            tput = 0.0
        return (f"t = {now:.0f} s    orders: {completed}/{created} done    "
                f"avg throughput: {tput:.0f} s")

    def _line_energy(t):
        now = t
        lit = sum(1 for el in energy_lights.values() if el.state == "on")
        light_wh = sum(el.live_energy_wh(now) for el in energy_lights.values())
        agv_wh = sum(a.total_distance_m for a in agvs) * cfg.AGV_ENERGY_PER_M
        return (f"lights on: {lit}/{len(energy_lights)}    "
                f"lighting: {light_wh:.0f} Wh    AGV: {agv_wh:.0f} Wh    "
                f"total: {light_wh + agv_wh:.0f} Wh")

    sim.AnimateText(text=_line_flow, x=0.5, y=50.5, text_anchor="w",
                    fontsize=1.4, textcolor="black")
    sim.AnimateText(text=_line_energy, x=0.5, y=48.5, text_anchor="w",
                    fontsize=1.4, textcolor="black")

    def _agv_stats(a):
        def f(t):
            return f"AGV {a.agv_id}:  {a.total_distance_m:.0f} m   {a.orders_served} orders"
        return f

    for i, agv in enumerate(agvs):
        sim.AnimateText(text=_agv_stats(agv), x=0.5, y=46 - i * 2.0,
                        text_anchor="w", fontsize=1.4,
                        textcolor=colors[(agv.agv_id - 1) % len(colors)])

    # live graph: number of lit fixtures over time
    if recorder is not None:
        sim.AnimateMonitor(
            recorder.lights_on,
            x=300, y=-3, width=650, height=70,
            horizontal_scale=0.02,
            vertical_scale=0.8,
            linecolor="#f4b942", linewidth=1,
            title="lights on (live)", titlecolor="black",
        )


def plot_lighting_energy_pct_diff(kpis: List[KPIBundle], out_dir: str = cfg.RESULTS_DIR) -> str:
    """Bar chart of lighting energy % difference vs the always_on baseline."""
    os.makedirs(out_dir, exist_ok=True)

    baseline = next((k for k in kpis if k.scenario == "always_on"), None)
    if baseline is None or baseline.lighting_energy_wh == 0:
        print("  [!] plot_lighting_energy_pct_diff: no always_on baseline found, skipping.")
        return ""

    comparators = [k for k in kpis if k.scenario != "always_on"]
    labels   = [k.scenario for k in comparators]
    pct_diff = [
        (k.lighting_energy_wh - baseline.lighting_energy_wh)
        / baseline.lighting_energy_wh * 100
        for k in comparators
    ]
    abs_wh   = [k.lighting_energy_wh for k in comparators]

    colors = ["#2a9d8f", "#e76f51", "#457b9d", "#f4b942"]  # extend if >4 scenarios
    bar_colors = colors[: len(comparators)]

    fig, ax = plt.subplots(figsize=(7, 5))

    bars = ax.bar(labels, pct_diff, color=bar_colors, zorder=3)
    ax.axhline(0, color="gray", linewidth=1.2, linestyle="--", zorder=2,
               label=f"always_on baseline ({baseline.lighting_energy_wh:.0f} Wh)")

    ax.set_ylabel("Lighting energy vs always_on (%)")
    ax.set_title("Lighting energy % difference vs always_on baseline")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%+.1f%%"))
    ax.set_ylim(min(pct_diff) * 1.25 - 5, max(max(pct_diff) * 1.25, 5))
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)

    # Annotate each bar with both % and absolute Wh
    for bar, pct, wh in zip(bars, pct_diff, abs_wh):
        va   = "top"    if pct < 0 else "bottom"
        ypos = bar.get_y() + bar.get_height() if pct < 0 else bar.get_y() + bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            ypos,
            f"{pct:+.1f}%\n({wh:.0f} Wh)",
            ha="center", va=va, fontsize=9,
        )

    plt.tight_layout()
    path = os.path.join(out_dir, "lighting_energy_pct_diff.png")
    plt.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  -> wrote {path}")
    return path
