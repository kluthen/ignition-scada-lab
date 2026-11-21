# MES (first slice) and lab autopilot

The MES runs inside Ignition, on the gateway, with PostgreSQL as its database.
This first slice covers the plumbing that every later MES screen builds on:
orders, dispatch to the cells, part-level traceability, and the cell state log.
Requirement ids refer to [../mes-requirements.md](../mes-requirements.md).

## Pieces

| Piece | Where | Role |
|---|---|---|
| Tables | `db/init/10-mes.sql` (schema `mes`), KPI functions `db/init/20-kpi.sql`, applied by `scripts/db_apply.py` | data model below |
| Script library `mes.cell` | `ignition/data/projects/plant/ignition/script-python/mes/cell/code.py` (Jython 2.7) | MES functions of one cell |
| Script library `labsim.autopilot` | `…/script-python/labsim/autopilot/code.py` | lab stand-in for the planner and the operator |
| Triggers | members of the UDT `PIC200_Cell` (`scripts/generate_tags.py`) | tag event scripts call the library |
| Gateway scripting project | `plant` (`gateway-config/system-properties.patch.json`) | lets tag event scripts (gateway scope, no project) call the `plant` library |
| DB connection | `mes` (`scripts/create_db_connection.py`) | all queries name their schema (`mes.work_order`) |

Gateway event scripts (timer, startup) would be the textbook trigger, but they
are kept in a binary project resource (`data.bin`, like the project properties
seen on 8.3), which cannot be reviewed or written as code. Tag event scripts
live in the tag JSON, and they come with every UDT instance, so the cycle is driven
from the UDT:

| UDT member | Event | Calls |
|---|---|---|
| `MES/Tick` (expression `now(1000)`) | value changed, every second | `mes.cell.tick(base)`: traceability fallback, order status, then `labsim.autopilot.step()` if `MES/AutoRun` |
| `Traceability/DataReady` | value changed to true | `mes.cell.store_record(base)` |
| `Status/StateCurrent` | value changed | `mes.cell.log_state(base, value)` |
| `MES/AutoRun` (memory, default true) | none | switches the autopilot for the cell |

`base` is the UDT instance path, e.g. `[default]ANN/FIN/C03`; the instance name
is the cell id. Every write is idempotent (`ON CONFLICT DO NOTHING`, status
checks), so a tick and an event that handle the same record do no harm.

## Data model (schema `mes`)

| Table / view | Content | Requirement |
|---|---|---|
| `product` | HSG-A20 / B32 / C45 = part types 1..3, nominal, tolerance, ideal cycle | MES-ORD-05 |
| `cell` | C01..C05, bay, `qualified_part_types`, notes (from docs/cells.csv) | |
| `work_order` | order id, product, target, dispatch `seq`, status (Planned, Released, Dispatched, Running, Completed, ClosedShort, Cancelled), cell, PLC good/reject at completion, timestamps | MES-ORD-01/02 |
| `order_event` | every status change with user and time | MES-ORD-02 |
| `part_result` | one row per finished part: cell, controller `startup_time` + `sequence` (primary key), part id (unique), order, product, measured bore, result, defect, PLC timestamp | MES-TRC-01 |
| `cell_state` | PackML state log: cell, start time (PLC source timestamp), state, stop reason, active order | basis for downtime and OEE |
| `event` | warnings and notable events (not written yet) | MES-DSP-03, MES-CNT-03 |
| `hourly_production` (view) | good / not good per cell and hour | MES-CNT-04 (without the shift calendar) |
| `site` | time zone and start of the production day (00:00) | day boundary of KPIs and export |
| `packml_state`, `downtime_reason`, `defect` | state names, StopReason → downtime category and reason (URS table), defect names | MES-DT-03 (content only, no editing screen yet) |
| KPI functions | `oee`, `oee_trend`, `downtime`, `rejects`, `production`, `hourly`, `orders` per period (`db/init/20-kpi.sql`, [kpi.md](kpi.md)) | MES-OEE-01..04, MES-DT-05, MES-CNT-04 |

## MES functions (`mes.cell`)

- **Traceability (MES-TRC-01).** When `DataReady` is true, read the presented
  record, insert it, and only then write `AckSequence` = `Sequence`. Records
  reach the database about 0.2 s after the part is placed.
- **State log.** On each state change, insert a `cell_state` row stamped with
  the PLC's source timestamp. Stop reason, state name and order are read from
  the controller itself (`system.opc.readValues` on the connection named like the
  cell), because the `Admin/*` members sit in the 1 s tag group and lag behind
  the 250 ms state. A gateway restart does not duplicate rows (same state as
  the last row: no insert).
- **Order status (MES-DSP-04).** Dispatched → Running when the cell's
  `Order/Active/OrderStatus` reaches 2, → Completed at 3, storing the PLC's good
  and reject counts. Orders the MES does not know (the smoke test's `TEST-…`)
  are ignored.
- **Replaced orders (MES-ORD-08, simplified).** A Running order that is no
  longer the cell's active order is closed short, with the good and reject
  counts from `part_result`. This happens when someone loads another order by
  hand, and after a controller restart (the controller forgets its order; the
  autopilot then dispatches a new one). Verified 2026-11-21: 5 controllers
  restarted mid-order, 5 orders ClosedShort, production resumed. A dedicated
  "controller restart" event (MES-CNT-03, change of `Admin/StartUpTime`) and
  re-dispatching the remaining quantity are still to do.
- If an OPC UA member the cycle needs is not Good, the cycle is skipped and a
  warning is logged every 5 min (`m.cell` logger). Modbus members are optional
  (`RJ01/Status/Full`), as the driver stops when a standard-edition trial
  expires.

## Lab autopilot (`labsim.autopilot`)

Not a customer requirement: it stands in for the people of the plant so that
the cells produce without anyone at the screens.

| Role | Behaviour |
|---|---|
| Planner (shift lead) | keeps 2 Released orders per product (sizes 50 to 300) in `work_order`, numbered `OF-<year>-<n>` |
| Operator: dispatch (MES-DSP-01/02) | cell Idle without a runnable order: claims the oldest Released order of a part type the cell is qualified for (`FOR UPDATE SKIP LOCKED`), writes `Order/Request/*` + `LoadRequest`; LoadResult 2 puts it back to Released, 3..5 cancels it |
| Operator: start | order loaded: Start after 3 to 15 s |
| Operator: changeover | Complete: Reset after 20 to 90 s |
| Operator: reject bin | Held on "reject bin full": after 1 to 4 min, `BinEmptied`, then Unhold |
| Operator: recovery | Stopped: Reset; Aborted: Clear |

Delays are drawn at random on each state entry. The same command is not
repeated within 5 s. Switch the autopilot off per cell with `MES/AutoRun`
(HMI cell page or instructor page) to drive the cell yourself or run the smoke
test; the MES functions keep running.

## Looking at the data

```sql
-- production per cell
SELECT cell, count(*) FILTER (WHERE result = 1) AS good, count(*) FILTER (WHERE result <> 1) AS rejects
FROM mes.part_result GROUP BY cell ORDER BY cell;

-- MES count vs PLC count per completed order (MES-CNT-03)
SELECT w.order_id, w.cell, w.good_qty AS plc_good, count(r.*) FILTER (WHERE r.result = 1) AS mes_good
FROM mes.work_order w LEFT JOIN mes.part_result r USING (order_id)
WHERE w.status = 'Completed' GROUP BY w.order_id, w.cell, w.good_qty ORDER BY w.order_id;

-- time per state per cell over the last hour (downtime picture)
SELECT cell, state_name, round(sum(extract(epoch FROM coalesce(next_at, now()) - started_at))) AS seconds
FROM (SELECT *, lead(started_at) OVER (PARTITION BY cell ORDER BY started_at) AS next_at FROM mes.cell_state) s
WHERE started_at > now() - interval '1 hour' GROUP BY cell, state_name ORDER BY cell, seconds DESC;

-- tag history (SQL Historian, schema historian): tag ids and the current partition
SELECT id, tagpath FROM historian.sqlth_te ORDER BY tagpath;
SELECT pname, to_timestamp(start_time / 1000) FROM historian.sqlth_partitions;
```

## Not done yet (next MES steps)

- Operator and shift-lead screens: order list, release, close short (MES-ORD-03/04/08), dispatch by hand.
- Product master check after load (MES-DSP-03), reconciliation events (MES-CNT-03), controller restart detection.
- Shift calendar and OEE per shift (OEE per cell and day, downtime reasons from
  StopReason, KPI screen and daily export are done: [kpi.md](kpi.md)).
- Downtime classification by the operator (MES-DT-04), reason table editing.
- Alarms and the alarm journal.
