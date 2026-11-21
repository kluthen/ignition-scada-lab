# KPIs, graphs and the daily production export

Three things share one calculation:

| Piece | Where | What |
|---|---|---|
| KPI functions | `db/init/20-kpi.sql`, schema `mes` | OEE, downtime, rejects, production, hourly counts, order list for any period |
| KPI screen and graphs | Perspective `plant`: page `/kpi`, trends on `/cell/:cell` ([hmi.md](hmi.md)) | live figures, refreshed every 30 s |
| Daily export | service `exporter` (`exporter/daily_export.py`) | one folder per production day: PDF report, XLSX, CSVs, manifest |

The screens and the export read the same functions, so a figure in the PDF
equals the figure on the screen for the same period (MES-RPT-01: "figures
equal the MES screens").

## Definitions

Standard OEE (oee.com, MES-OEE-01..04):

| Term | Here |
|---|---|
| Planned production time | time covered by the PackML state log in the period. The lab runs 24/7: no shift calendar, no planned breaks yet. Maintenance mode is not logged yet, so it is not excluded (MES-OEE-01, to do) |
| Run time | time in Execute (state 6) |
| Availability | run time / planned production time |
| Performance | Σ (ideal cycle time of the part's product × parts) / run time. Ideal cycle times are in `mes.product`. Not capped: values above 100 % stay visible (MES-OEE-03) |
| Quality | good / (good + reject + scrapped) |
| OEE | A × P × Q |
| Downtime | every non-Execute interval, classified by the controller's StopReason through `mes.downtime_reason` (URS mapping, MES-DT-03): Changeover (Order complete until the next Execute) is Planned, Reject bin full is Process, StopReason 0 outside Execute is "No order", command stops are Unclassified |
| Stop | a run of consecutive non-Execute intervals with the same reason |

Parts count by their PLC timestamp (`produced_at`). For OEE, parts made before
a cell's first state-log row are left out: they have no time base. This only
concerns the start of the lab's history on 2026-11-21.

### Production day

`mes.site` holds the site's time zone and the start of the production day
(`day_start`, 00:00 = calendar day). `mes.day_bounds(date)` turns a day into
`[from, to)` in local time, so the days of the DST changes last 23 h and 25 h.
When the shift calendar is decided (docs/README.md decision 7), a 06:00 start
is a change of this one row:

```sql
UPDATE mes.site SET day_start = '06:00';
```

## KPI functions (schema `mes`)

All take a half-open period `[p_from, p_to)` and never count time after `now()`,
so the current day can be asked for like a closed one.

| Function | Returns |
|---|---|
| `day_bounds(date)`, `production_day(timestamptz)` | production day ↔ period |
| `period_bounds(text)` | named periods of the screens: `today`, `yesterday`, `last_hour`, `last_8h`, `last_24h` |
| `state_intervals(from, to)` | the state log cut to the period, with state name, downtime category and reason |
| `oee(from, to)` | per cell and for the area (`cell = 'FIN'`): planned, run and down seconds, good, rejects, scrapped, ideal seconds, A, P, Q, OEE (fractions) |
| `oee_trend(from, to, step)` | `oee` per bucket (e.g. 1 hour) |
| `downtime(from, to)` | per cell, category and reason: seconds and stops (Pareto, MES-DT-05) |
| `rejects(from, to)` | per cell and defect code (`mes.defect`) |
| `production(from, to)` | per cell and product: good, rejects, scrapped, reject %, first and last part |
| `hourly(from, to)`, `hourly_area(from, to)` | good and not good per hour and cell (zero rows included), and the area total (MES-CNT-04) |
| `orders(from, to)` | orders worked in the period: MES counts for the whole order and for the period, PLC counts, start, end, duration |

Lookup tables added with them: `mes.site`, `mes.packml_state`,
`mes.downtime_reason` (MVP content of the URS reason table), `mes.defect`.

```sql
-- OEE of today, per cell and area
SELECT o.* FROM mes.period_bounds('today') b, mes.oee(b.t_from, b.t_to) o;
-- a given production day
SELECT o.* FROM mes.day_bounds('2026-11-21') b, mes.oee(b.t_from, b.t_to) o;
-- downtime Pareto of the last 8 hours, all cells
SELECT reason, round(sum(seconds) / 60) AS minutes, sum(stops) AS stops
FROM mes.period_bounds('last_8h') b, mes.downtime(b.t_from, b.t_to) GROUP BY reason ORDER BY 2 DESC;
```

## Screens

The named queries `Kpi/*` of project `plant` wrap the functions for the
screens. They take `period` (a name for `period_bounds`) and `cell` (`''` = all
cells):

| Query | Used by |
|---|---|
| `Kpi/Oee` | KPI tiles (row `FIN` or the selected cell), OEE per cell table, cell page tiles |
| `Kpi/OeeTrend` | OEE / A / P / Q per hour (line chart) |
| `Kpi/Hourly` | production per hour (stacked columns), KPI page and cell page |
| `Kpi/Downtime` | downtime Pareto (columns) |
| `Kpi/Rejects` | rejects by defect (columns) |
| `Kpi/Production` | production per cell and product (table) |

- **`/kpi`** (view `Kpi/Area`): period selector (Today, Yesterday, Last 8 hours,
  Last hour, Last 24 hours) and cell selector (All cells or one cell). Tiles:
  OEE, Availability, Performance, Quality, good, not good, downtime minutes.
  Charts: OEE per hour, production per hour, downtime Pareto, rejects by defect.
  Tables: OEE per cell, production per cell and product. Every query polls every 30 s.
- **`/cell/:cell`**, new "Trends" row: a Time Series chart of the last 30 min
  from the tag history (active power, machine speed, measured bore; three
  plots, one axis each, refreshed every 10 s), today's OEE / A / P / Q for the
  cell, and its production per hour.

Charts are the Perspective XY Chart (`ia.chart.xy`, amCharts) for categories
and hours, and the Time Series Chart (`ia.chart.timeseries`) for tag history.
The tag history is read by a script transform on the chart's data,
`system.tag.queryTagHistory(paths=[...], returnFormat='Wide', aggregationMode='Average')`,
with the normal tag paths `[default]ANN/FIN/C03/UT01/Status/ActivePower`.
The Power Chart (`ia.chart.powerchart`) would let operators pick pens and
zoom on their own, with no script. It is the next thing to try in the Designer.

## Daily production export

The service `exporter` (compose) writes one folder per production day:

```
exports/daily/2026-11-22/
  FIN_2026-11-22_report.pdf        A4 report: headline KPIs, OEE per cell, production per cell and product,
                                   production per hour (chart), downtime Pareto top 5, rejects by defect,
                                   orders summary per cell and product, definitions
  FIN_2026-11-22_production.xlsx   sheet About, then one sheet per table (oee, production, hourly,
                                   downtime, rejects, orders), header filters, local times
  FIN_2026-11-22_oee.csv           one CSV per table, UTF-8, comma, ISO 8601 timestamps with offset
  FIN_2026-11-22_production.csv
  FIN_2026-11-22_hourly.csv
  FIN_2026-11-22_downtime.csv
  FIN_2026-11-22_rejects.csv
  FIN_2026-11-22_orders.csv
  FIN_2026-11-22_parts.csv         every part record of the day (traceability, MES-TRC-03), about 15 MB a day
  manifest.json                    see below
```

### When it runs

- Each production day is exported `EXPORT_DELAY_MIN` (10) minutes after its
  end, so at 00:10 for the calendar day.
- The service checks every 5 minutes. On start it also fills the gaps of the
  last `EXPORT_CATCHUP_DAYS` (7) days: a day missed while the stack was down
  is exported when it comes back.
- A folder is written under a temporary name (`.2026-11-22.tmp-<pid>`) and
  renamed when every file is there. **A folder with a `manifest.json` is
  complete and can be shipped.** A pickup job ignores names starting with a dot.
- Re-exporting a day replaces its folder in the same way.

### manifest.json

```json
{
  "format": "fin-daily-export/1",
  "site": "ANN", "area": "FIN", "production_day": "2026-11-22",
  "period": {"from": "2026-11-22T00:00:00+01:00", "to": "2026-11-23T00:00:00+01:00", "timezone": "Europe/Paris"},
  "complete": true,
  "data_until": "2026-11-23T00:00:00+01:00",
  "generated_at": "2026-11-23T00:10:02+01:00",
  "generator": "exporter/daily_export.py 1.0",
  "kpi": {"oee_pct": 73.6, "availability_pct": 81.3, "performance_pct": 94.3, "quality_pct": 96.0,
          "good": 14813, "rejects": 605, "scrapped": 6, "total": 15424, "planned_h": 14.48,
          "run_h": 11.77, "down_min": 162.8},
  "files": [{"name": "FIN_2026-11-22_report.pdf", "content": "daily report", "bytes": 8579,
             "rows": null, "sha256": "…"}, "…"]
}
```

`complete: false` marks a partial export (a day not finished yet, made by
hand). The scheduler replaces it with the complete one after the day ends.
The receiver checks the files against `bytes` and `sha256`.

### By hand

```bash
docker compose run --rm exporter python daily_export.py run              # yesterday (skips it if already complete)
docker compose run --rm exporter python daily_export.py run 2026-11-21 --force
docker compose run --rm exporter python daily_export.py run today        # partial, complete: false
rtk proxy docker compose logs exporter                                    # "exported <day> (complete) ..."
```

Settings are in `compose.yaml` (service `exporter`): `EXPORT_DELAY_MIN`,
`EXPORT_CATCHUP_DAYS`, `EXPORT_PARTS_CSV` (`0` leaves out the part records).
Exports are never deleted by the service. Clean `exports/daily/` by hand, or
let the shipping step move folders away.

### Shipping

"Ready to ship" here means a finished folder on the host, `exports/daily/<date>/`
(git-ignored). The next step depends on the receiver and is not built yet:

| Channel | How it would plug in |
|---|---|
| folder pickup (file share, sync tool) | point it at `exports/daily/`, take folders that have a `manifest.json` |
| e-mail | Ignition's SMTP profile and `system.net.sendEmail`, or a mail step in the exporter; needs an SMTP server and recipients |
| SFTP | an upload step after the rename, `manifest.json` last; needs a target and a key |

### Why a separate service and not the Reporting module

Ignition's Reporting module (included in Maker) is the usual tool for a PDF
report scheduled on the gateway. In 8.3, a report is a project resource whose
design, data sources and schedule are stored in a binary `data.bin`, editable
only in the Designer. It cannot be written or reviewed as code, as with gateway
event scripts ([mes.md](mes.md)). The lab therefore builds the export in code
(Python: psycopg, openpyxl, reportlab), on the same SQL functions as the
screens. A Designer-built report on these functions (data source "Named Query"
`Kpi/*` or SQL query, schedule action "Save File" to a mounted folder) is a
good Designer exercise and the usual choice on a customer system with Reporting.

## Limits and next steps

- Shift calendar (decision 7): OEE per shift, shift report 10 min after each
  shift end (MES-RPT-01), shift comparison.
- Maintenance mode and planned breaks out of planned time (MES-OEE-01).
- Closed periods are recomputed from the logs on each query. MES-OEE-05 asks to
  store the values of closed shifts. The daily manifest already keeps the
  day's figures.
- Not yet in the report: alarm count (no alarms configured), energy per good
  part (from the `UT01/Status/EnergyTotal` history), shift-lead comments
  (MES-RPT-02), the order report (MES-RPT-03).
- The exporter connects with the database owner role from `.env`. A customer
  system would give it a read-only role.
