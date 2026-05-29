# Warehouse Smart-Lighting Simulation

A discrete-event simulation comparing three lighting strategies for an
I-shape e-commerce warehouse operated by 3 AGVs:

1. **always_on** — baseline: every fixture is energised for the full 8-hour shift.
2. **sensor_based** — each segment lights up when an AGV enters and goes dark
   `SwitchOffDelay` (= 20 s) after the last AGV leaves. The timer restarts if
   another AGV re-enters before it expires.
3. **route_based** — at order assignment, every light on the AGV's planned
   out-and-back route is turned on; all of them turn off when the AGV returns
   to base.

Built on [`salabim`](https://www.salabim.org/) for the discrete-event engine,
NetworkX for the routing graph, matplotlib + pandas for the analysis layer.

## Project layout

```
warehouse_sim/
├── README.md
├── requirements.txt
├── config.py              # all global parameters
├── layout.py              # warehouse geometry, segments, lights, sensors
├── routing.py             # Manhattan shortest-path on a NetworkX graph
├── components/            # salabim Components
│   ├── light.py           #   Light (energy-accounting only, not a Component)
│   ├── order.py           #   Order (dataclass)
│   ├── order_generator.py #   TOrderGenerator
│   ├── pickup_location.py #   TPickupLocation
│   ├── sls.py             #   TSLS (smart lighting controller)
│   └── agv.py             #   TAGV
├── scenarios.py           # wires everything together for one run
├── kpi.py                 # KPI computation + CSV writer
├── visualization.py       # matplotlib plots + salabim animation hook
├── main.py                # CLI
└── results/               # CSV + PNG output (created automatically)
```

## Quick start

```bash
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

Run a single scenario:

```bash
python main.py --scenario always_on
python main.py --scenario sensor_based
python main.py --scenario route_based
```

Run all three and produce the comparison plot:

```bash
python main.py --scenario all
```

Open the salabim animation window for one scenario (requires a graphical
environment — Tk/Pyglet under salabim):

```bash
python main.py --scenario sensor_based --animate
```

Other CLI options:

| flag | default | description |
|------|---------|-------------|
| `--duration <sec>` | 28800 (8 h) | simulated horizon |
| `--seed <int>`     | 42          | random seed (drives both inter-arrival times and pickup choice) |
| `--no-plot`        | off         | skip generating the comparison PNG when running `all` |

## Output

For each scenario the simulator writes:

- `results/<scenario>_<timestamp>.csv` — headline KPIs (energy, throughput,
  distance, cost) plus per-AGV rows.
- `results/diagnostics_<scenario>.png` — histogram of per-light on-time and
  per-AGV utilisation.

After `--scenario all`, additionally:

- `results/scenario_comparison.png` — stacked bar of lighting vs AGV energy
  alongside throughput-time per scenario.
- `results/warehouse_layout.png` — static layout with all 73 lights overlaid.

## Sample numbers (seed 42, 8-h shift)

| scenario       | orders | lighting Wh | AGV Wh   | total Wh | avg cycle (s) |
|----------------|--------|-------------|----------|----------|---------------|
| always_on      | 315    | 87 600      | 100 180  | 187 780  | 106.2         |
| sensor_based   | 315    |  5 921      | 100 180  | 106 101  | 106.2         |
| route_based    | 315    | 11 553      | 100 180  | 111 733  | 106.2         |

### Interpreting the result

- Lighting energy in `always_on` matches the closed-form expectation exactly:
  73 fixtures × 150 W × 8 h = 87 600 Wh. AGV energy
  (`27 076 m × 3.7 Wh / m = 100 180 Wh`) is the same in every scenario
  because lighting strategy doesn't affect AGV travel.
- **`sensor_based` beats `route_based` in this model** (5.9 kWh vs 11.6 kWh).
  This may look counter-intuitive — the report's section 8.2 expected route-
  based to be the most efficient. The reason is subtle: under the spec, the
  route-based controller turns every light on the planned route ON at
  departure and OFF only at return, so a far-aisle light stays lit for the
  full ~106 s cycle. Sensor-based keeps each light on only for the brief
  window the AGV is actually inside that segment plus a 20 s cooldown
  (≈ 24 s per traversal). For a 3-AGV / 8-h workload the cooldown-only
  model wins.

  To make route-based the most efficient, you would need *progressive*
  lighting (turn each light on just before the AGV reaches it and back off
  shortly after it passes). The spec explicitly asks for the simpler
  whole-route-at-departure model, so that's what's implemented.
- Throughput is identical across scenarios because lighting doesn't gate
  AGV movement in this model. Distance and AGV energy are identical for the
  same reason.

### Known asymmetry: AGV utilisation

The diagnostics plot shows AGVs do not share load evenly (≈ 50% / 29% / 15%
of shift time). This is because the `OrderGenerator` wakes the first passive
AGV it finds in its list — and after AGV 1 finishes a trip it almost always
beats AGV 2/3 to the next dequeue. Adding round-robin or least-busy
dispatch would balance load, but it doesn't change the lighting comparison
(every scenario uses the same dispatch and same total order count) so it's
left as a future extension.

## Modelling choices (and where they deviate from the spec)

The PDL in §6 of the system report has some bugs and approximations.
The corrections the user asked for (queue ownership, sensor-along-path,
restartable timer, per-light energy, distance + time travelled, multi-pickup
ready, etc.) are all applied. A few additional choices worth flagging:

- **Light count**: spec says "31 main lights inside picking aisles". With 14
  aisles × 2 segments = 28 natural slots and a need for base-area
  illumination, the model places **28 picking-aisle lights + 3 base
  lights + 42 cross-aisle lights = 73 total** (matches the spec total even
  though the "main" count is split). See `layout.build_layout()`.
- **Rack/aisle pattern**: implemented as `R A R A … R A` starting at
  x = 7 m, so Rack 1 abuts the base and Aisle 14 abuts the right wall.
- **Pickup count**: 14 aisles × 2 segments × 12 indices = **336 unique
  routing locations**. The spec's "672 pickup points" counts left and right
  sides of each rack separately; both sides share the same picking-aisle
  centerline, so they're routing-equivalent and collapsed.
- **Base access**: a single base node connects to the middle-cross-aisle
  entry at (7, 17.5). The report's worked example assumes the AGV can also
  re-enter the base via the bottom cross-aisle for a 67.25 m mixed-loop
  route. With a single entry node the shortest round trip to that same
  pickup is ~85 m instead. Functionally equivalent for the KPI comparison
  but worth flagging if you cross-check numbers against the report.
- **Right-hand traffic / AGV collisions**: not modeled — multiple AGVs may
  occupy the same segment. With 3 AGVs and 71 segments the probability is
  low; flagged with a comment in `routing.py` for future extension.

## How sensor / route activation work in code

- `components/sls.py` owns the segment's `OccupancyCount` (sensor path) and
  `route_holders` set (route path).
- Sensor path: `AGV._traverse()` calls `sls.sensor_enter()` at every
  segment transition and `sls.sensor_exit()` when leaving it. The SLS
  cancels any in-flight `_ShutoffTimer` on each enter and re-creates it
  when `occupancy` returns to zero — that's the restartable-delay
  behaviour.
- Route path: at order assignment the AGV computes `segments_touched()`
  over the full out-and-back route and calls `route_activate(agv_id)` once
  per segment. On return it calls `route_release(agv_id)`. Lights only
  drop when no AGV holds the segment any more.

## License / origin

Built to the spec in *System Analysis and Simulation (TU Delft assignment)*.
