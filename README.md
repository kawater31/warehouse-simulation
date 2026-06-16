# Warehouse Smart-Lighting Simulation

A discrete-event simulation (salabim) comparing three lighting strategies for an
I-shape e-commerce warehouse with 3 AGVs over an 8-hour shift:

- **always_on** — every fixture stays on the whole shift (baseline).
- **sensor_based** — a segment lights up when an AGV enters and switches off 20 s
  after the last AGV leaves; the timer restarts on re-entry.
- **route_based** — at order assignment the whole planned route is lit, and
  switched off when the AGV returns to base.

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate      # Windows  (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
```

## Usage

```bash
python main.py --scenario always_on        # one scenario
python main.py --scenario all               # all three + comparison plots
python main.py --scenario sensor_based --animate   # with animation window
```

Options: `--duration <s>` (default 28800), `--seed <int>` (default 42),
`--no-plot`, `--trace` (write an event log), `--no-verify` (skip invariant checks).

## Layout

```
config.py        global parameters
layout.py        geometry: segments, lights, pickup points
routing.py       shortest-path routing on a NetworkX graph
components/       salabim components (agv, sls, order, order_generator,
                 pickup_location, recorder) + light, the energy record
scenarios.py     builds and runs one scenario
verification.py  post-run invariant checks
kpi.py           KPI computation + CSV output
visualization.py matplotlib plots + animation
main.py          CLI
results/         CSV and PNG output (created automatically)
```

## Output

Per scenario: a KPI CSV and a diagnostics PNG in `results/`. Running `all` also
writes the scenario comparison, the lighting-energy difference, and a layout plot.
