# HMI: Perspective project `plant`

First screens of the finishing area, in the Perspective project `plant`
(`ignition/data/projects/plant/com.inductiveautomation.perspective/`). They
were first written as JSON from code. From now on they belong to the Designer:
open project `plant`, edit, save. The files in git follow.

URL: http://127.0.0.1:8088/data/perspective/client/plant (no login, lab).
On Maker Edition, each new session first shows a "Personal Use Only" notice:
accept it once ("Agree & close").

Why Perspective: Ignition has two HMI modules. Perspective serves screens as
web pages (any browser, tablet or phone, responsive layouts, views stored as
JSON). Vision is the older one: Java desktop client windows, fixed pixel
layouts. It is still common on existing sites, but it is not part of Maker
Edition. Both are built in the Designer.

## Pages

| URL | View | Content |
|---|---|---|
| `/` | `Area/Overview` | floor layout: upstream band, one tile per cell (flex repeater over `mes.cell`), packing band; today's production per cell and the order queue (named queries, from PostgreSQL) |
| `/kpi` | `Kpi/Area` | KPI screen: period and cell selectors, tiles (OEE, A, P, Q, good, not good, downtime), OEE per hour, production per hour, downtime Pareto, rejects by defect, OEE per cell, production per cell and product ([kpi.md](kpi.md)) |
| `/cell/:cell` (e.g. `/cell/C03`) | `Cell/Detail` | cell mimic (CV01, QS01, RB01, RJ01, CV02, SF01/UT01 with live values), PackML state, command buttons enabled only in the states that accept them, last command result, autopilot toggle, active order with progress; trends: last 30 min of power, machine speed and measured bore from the tag history, today's OEE / A / P / Q and production per hour; last 25 parts, orders of the cell |
| `/instructor` | `Sim/Instructor` | per cell: feed interval, reject rate, upstream feed, auto-empty bin, autopilot (flex repeater of `Sim/CellRow`) |
| top dock | `Shared/Header` | title, navigation, clock |

## How the views are built

- **One view per cell, parameterised.** `Cell/Tile`, `Cell/Detail` and
  `Sim/CellRow` take a `cell` parameter (`C03`). Their tag bindings are
  indirect: `[default]ANN/FIN/{cell}/Status/StateCurrent`, with `{cell}` bound
  to `view.params.cell`. Together with the UDT, this is the Ignition equivalent
  of a Panorama E2 class with its instances and mimic template
  ([panorama-e2-to-ignition.md](panorama-e2-to-ignition.md)).
- **View custom properties hold the tag values** (`view.custom.state`,
  `view.custom.good`...). Components bind to expressions over them. A tag is
  subscribed once per view, and expressions stay readable.
- **Cell lists come from the database.** The overview and instructor flex
  repeaters take their instances from the named query `Area/Cells` (`mes.cell`,
  loaded from docs/cells.csv). A new cell shows up without editing a view.
- **Colours** follow a high-performance HMI style (ISA-101): grey background
  and equipment, colour only for states: green Execute, blue-grey Idle/Complete,
  amber Suspended (starved/blocked), orange Held, red Aborted.
- **Commands** write `Command/CntrlCmd` (`system.tag.writeBlocking` in a button
  script); the controller answers with `CmdResult` / `CmdCounter`, shown under
  the buttons (MES-DSP-05).
- **Charts.** XY Chart (`ia.chart.xy`) for hourly bars, the OEE trend and the
  Paretos: a query binding with `returnFormat: json` fills
  `props.dataSources.<name>`, and each series names its source and x / y
  fields. Time Series Chart (`ia.chart.timeseries`) for tag history: an
  expression binding `now(10000)` with a script transform that calls
  `system.tag.queryTagHistory` returns a dataset into `props.series[0].data`.
  Colours: categorical slot 1 blue `#2a78d6` for the main series, orange
  `#eb6834` for "not good"; one axis per plot.
- **KPI figures** come from the SQL functions in schema `mes`, through the
  `Kpi/*` named queries. The daily PDF / XLSX export uses the same functions
  ([kpi.md](kpi.md)).

## Named queries (project `plant`, database `mes`)

| Query | Parameters | Used by |
|---|---|---|
| `Area/Cells` | none | flex repeaters (overview, instructor) |
| `Area/TodayByCell` | none | overview: good, rejects, reject %, orders done, last part, since local midnight |
| `Area/OrderQueue` | none | overview: Running, Dispatched, Released orders |
| `Cell/LastParts` | `cell` (String) | cell page |
| `Cell/Orders` | `cell` (String) | cell page |
| `Kpi/Oee`, `Kpi/OeeTrend`, `Kpi/Hourly`, `Kpi/Downtime`, `Kpi/Rejects`, `Kpi/Production` | `period` (String: `today`, `yesterday`, `last_hour`, `last_8h`, `last_24h`), `cell` (String, `''` = all cells) | KPI page, cell page ([kpi.md](kpi.md)) |

Files: `ignition/data/projects/plant/ignition/named-query/<path>/query.sql`
plus `resource.json` (database, parameters, caching).

## Checking the screens without a browser at hand

Perspective is a web app on a websocket: a plain `google-chrome --headless
--screenshot` captures only the loading screen. A Playwright script with real
waits works (run with `uv run`, it pulls Playwright, and uses the installed Chrome):

```python
# /// script
# dependencies = ["playwright"]
# ///
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    page = b.new_page(viewport={"width": 1500, "height": 950})
    page.goto("http://127.0.0.1:8088/data/perspective/client/plant/cell/C03")
    page.wait_for_timeout(9000)
    if page.get_by_text("Agree & close").count():  # Maker Edition notice
        page.get_by_text("Agree & close").click()
        page.wait_for_timeout(500)
    page.screenshot(path="cell_C03.png", full_page=True)
```

## Next

- Power Chart on the cell page (pens and range chosen by the user) next to,
  or instead of, the fixed 30-min trend.
- Alarm status table when alarms are configured.
- MES operator screens (order list, release, dispatch by hand, close short).
- Login and roles (operator, shift lead, instructor) before any of this leaves the lab.
