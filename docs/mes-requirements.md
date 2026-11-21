# Customer requirements: Cell 01 MES (Brevent Hydraulics)

| | |
|---|---|
| Customer | Brevent Hydraulics SAS (fictional), Annecy plant |
| Document | User requirements specification (URS), small MES for Cell 01 |
| Version | 0.1 draft for discussion with the integrator |
| Scope | Finishing area, Cell 01 (pilot); later the 3 other finishing cells |
| Platform imposed | Inductive Automation Ignition 8.3 (standard modules), PostgreSQL |

## 1. Context

Brevent machines aluminium valve housings for agricultural machinery makers (about 85 staff,
2 shifts, 5 days a week). Cell 01 inspects and sorts housings (see
[`scenario.md`](scenario.md)). Today:

- production counts are written on paper at the end of each shift;
- rejects are logged in a spreadsheet;
- nobody knows the real OEE of the cell;
- the main customer (a tractor maker) now requires part-level traceability, kept 10 years:
  for every housing serial, the order, the date and time, the measured bore and the result.

The plant wants a small MES on Ignition, the SCADA it has chosen. The aims are to replace the paper
records, to measure OEE and downtime, and to provide that traceability. ERP integration
will come later; the MVP must not depend on it.

### 1.1 ISA-95 positioning

| Level | Scope here | System |
|---|---|---|
| 4 Business planning | Sales orders, production orders, stock | Existing ERP (out of scope; stubbed by an order inbox table) |
| 3 Manufacturing operations | Order execution, counting, OEE, downtime, traceability, shift reports | **This MES**: Ignition (Perspective, SQL Bridge, Reporting, Alarm Journal, Historian) + PostgreSQL |
| 2 Supervision | HMI, alarms, trends | Ignition (same gateway) |
| 1 Control | Cell PLC, robot controller, camera | Simulated: OPC UA server and Modbus TCP (registry) |
| 0 Process | Sensors, drives, conveyors | Simulated |

The MES/cell interface is the one defined in [`opcua-registry.md`](opcua-registry.md). The
MES must not require any signal beyond it.

### 1.2 Shift calendar (customer reality)

| Shift | Time (Europe/Paris) | Planned break |
|---|---|---|
| A (morning) | Mon-Fri 06:00-14:00 | 10:00-10:30 |
| B (afternoon) | Mon-Fri 14:00-22:00 | 18:00-18:30 |

No production is planned at night or on weekends. For the lab, the calendar must be editable, so
that a 24/7 calendar (3 × 8 h, same break pattern) can be set.

## 2. Stakeholders and personas

| Persona | Role | Needs from the MES | Typical device |
|---|---|---|---|
| Lucie, cell operator | Runs the cell, empties the reject bin, reacts to stops | Clear cell state, what to do next, start the next order without paperwork, classify stops quickly | 22" touch panel at the cell |
| Marc, shift lead | Responsible for output of the shift, 4 cells later | Order list and sequence, live progress versus target, shift report without typing | Desktop PC, tablet |
| Nadia, quality engineer | Owns inspection, customer complaints | Find any part by serial, reject analysis, measurement trends, put production on quality hold | Desktop PC |
| Karim, maintenance technician | Fixes faults | Alarm history, fault frequency per equipment, maintenance mode | Tablet, desktop |
| Philippe, plant manager | Performance, investment decisions | OEE per day/week, top downtime causes, comparison between shifts | Desktop, e-mailed PDF |
| IT/OT administrator (integrator) | Runs the platform | Backups, users, updates, no surprises | Gateway web UI |

## 3. Conventions

- Requirement id: `MES-<area>-<nn>`. Ids never change. Deleted requirements stay as "withdrawn".
- **Priority**: **MVP** = must be in the first delivery; **Later** = planned, not in the MVP.
- Acceptance tests run against the simulated cell with its default settings (deterministic, see
  scenario.md section 6), unless stated otherwise. "PT1" = PartType 1.
- OEE terms follow the standard definitions (oee.com):
  - Availability = Run Time / Planned Production Time;
  - Performance = (Ideal Cycle Time × Total Count) / Run Time;
  - Quality = Good Count / Total Count;
  - OEE = A × P × Q.

## 4. Functional requirements

### 4.1 Production orders (ORD)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-ORD-01 | The MES keeps a list of production orders. Fields: order id (unique, ≤ 32 printable ASCII), product code, target good quantity, due date, sequence number, status, created by/at. | MVP | An order can be created, edited while Planned, and viewed. A duplicate order id is refused with a message. |
| MES-ORD-02 | Order statuses: Planned → Released → Dispatched → Running → Completed / ClosedShort; Planned or Released → Cancelled. Every status change is time-stamped with the user. | MVP | The order history shows every transition with user and UTC time. Illegal transitions (e.g. Completed → Running) are impossible from the UI. |
| MES-ORD-03 | The shift lead creates orders manually, or imports a CSV file (order id, product code, quantity, due date). | MVP | Importing a 10-line CSV creates 10 Planned orders; a line with an unknown product code is rejected and reported, the others are imported. |
| MES-ORD-04 | The shift lead releases orders and sets their sequence (drag or up/down). Only Released orders can be dispatched. | MVP | Reordering is saved and visible to the operator screen within 2 s. |
| MES-ORD-05 | Product master: product code, description, cell part type number, nominal bore, tolerance, ideal cycle time. MVP content: HSG-A20, HSG-B32, HSG-C45 as in scenario.md section 3. | MVP | The three products exist. Their part type, nominal, tolerance and ideal cycle time match the cell's recipe table. |
| MES-ORD-06 | ERP stub: an `erp_order_inbox` table that an external system (or a test script) fills. The MES imports new rows as Planned orders every 60 s. | Later | Inserting a row in the inbox creates the order within 60 s, and the row is marked imported. |
| MES-ORD-07 | Order completion report back to ERP (good/reject quantity, start/end) through an outbox table. | Later | A completed order produces one outbox row. |
| MES-ORD-08 | The shift lead can close a Dispatched or Running order short (ClosedShort) while the cell is not producing (`C01.Status.StateCurrent` not 6), with a mandatory comment. | MVP | A Running order with the cell Stopped at 300/500 can be closed short; its counts stay frozen at their value. |

### 4.2 Dispatch to the cell (DSP)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-DSP-01 | The operator dispatches the next Released order (first in sequence, or another one chosen by the operator) to Cell 01. The MES writes `C01.Order.Request.OrderId`, `C01.Order.Request.PartType` and `C01.Order.Request.TargetQuantity`, then `C01.Order.Request.LoadRequest`, and evaluates `C01.Order.Request.LoadResult`. | MVP | With the cell Idle, dispatching sets `C01.Order.Active.OrderId` within 1 s; the order goes to Dispatched. With the cell in Execute, the MES shows "cell busy" (LoadResult 2) and the order stays Released. |
| MES-DSP-02 | Only one order is Dispatched or Running on the cell at a time. Dispatching a new one while the previous one is not Completed requires closing the previous one short (MES-ORD-08) first. | MVP | The UI refuses to dispatch while another order is Dispatched/Running, and offers "close short". |
| MES-DSP-03 | After a load, the MES checks `C01.Order.Active.PartType`, `C01.Order.Active.LowerLimit`, `C01.Order.Active.UpperLimit` and `C01.Order.Active.IdealCycleTime` against the product master. On a mismatch it raises a warning event. | MVP | Altering the ideal cycle time in the product master and dispatching produces a warning event naming the field. |
| MES-DSP-04 | Order status follows the cell: Dispatched → Running when `C01.Order.Active.OrderStatus` becomes 2; Running → Completed when it becomes 3. | MVP | Start the cell: Running within 2 s. At target: Completed within 2 s of `C01.Status.StateCurrent` = 17. |
| MES-DSP-05 | The operator can send PackML commands (Reset, Start, Stop, Hold, Unhold, Abort, Clear) to `C01.Command.CntrlCmd` from the HMI. Only commands accepted in the current state are enabled, and the result (`C01.Command.CmdResult`) is shown. | MVP | Start is greyed out in Stopped. A refused Start (e.g. no order) shows "interlock" within 1 s. |
| MES-DSP-06 | Recipe parameter download (tolerances, speeds) instead of a part type number only. | Later | n/a in MVP (needs a registry extension). |

### 4.3 Production counting (CNT)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-CNT-01 | The MES counts good and non-good parts per order, per shift and per hour. The part result records (MES-TRC-01) are the authoritative source. | MVP | After 60 min of PT1, the MES good count equals the number of Good part_result rows for the order and equals `C01.Order.Active.GoodCount`. |
| MES-CNT-02 | Live progress of the running order: good / target, rejects, % complete, estimated end time based on `C01.Status.CurMachSpeed`. | MVP | The operator screen shows the progress and updates within 2 s of each part. The 500-part PT1 estimate is within ±2 min of the real end. |
| MES-CNT-03 | Reconciliation: the MES compares its counts with the PLC counters (`C01.Order.Active.GoodCount`, `C01.Order.Active.RejectCount`) at order completion and stores any difference with the order. A controller restart (change of `C01.Admin.StartUpTime`) must not corrupt the counts. | MVP | No difference after a normal order. After restarting the `plc` container mid-order, the MES counts still match the stored part records, and a "controller restart" event is logged. |
| MES-CNT-04 | Hourly production table (good, reject per hour of each shift) for the shift lead. | MVP | Values match a SQL count of part_result grouped by hour. |

### 4.4 OEE (OEE)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-OEE-01 | Planned Production Time = shift duration - planned breaks - time in Maintenance mode (`C01.Status.UnitModeCurrent` = 2). If the cell is in Execute during a planned break, that time is added back to Planned Production Time. | MVP | A shift with 30 min of break and 20 min of maintenance mode has 430 min of planned production time. |
| MES-OEE-02 | Run Time = time with `C01.Status.StateCurrent` = 6 (Execute) inside Planned Production Time. | MVP | Matches the sum of Execute intervals in the state history, ±1 s per interval. |
| MES-OEE-03 | Performance = Σ over part types (IdealCycleTime × parts processed) / Run Time. IdealCycleTime comes from the product master; parts processed = Good + Reject + Scrapped. The raw value is stored even when above 100 % (shorter reject cycles); displays may cap it at 100 %. | MVP | PT1 at default sim settings gives 96.0 % ± 1 %; PT2 and PT3 give 100.7 % ± 1 % (scenario.md section 6). |
| MES-OEE-04 | Quality = Good / parts processed. | MVP | PT1 default: 96.0 % ± 0.5 % over ≥ 500 parts. |
| MES-OEE-05 | OEE, A, P and Q are computed for the current shift (live, refreshed ≤ 60 s), each closed shift, each order, each day and each week. | MVP | Live OEE is visible on the cell screen; closed-shift values are stored and not recomputed differently later. A × P × Q equals (Good × IdealCycleTime) / Planned Production Time within 0.5 %. |
| MES-OEE-06 | OEE trend (per shift, last 30 days) and shift comparison A versus B. | Later | Chart available to Manager. |

### 4.5 Downtime (DT)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-DT-01 | Every interval inside Planned Production Time where the cell is not in Execute is a downtime event: start, end, duration, PackML states seen, `C01.Admin.StopReason` at the start. Consecutive non-Execute states form one event (e.g. Holding → Held → Unholding). | MVP | A reject-bin hold produces exactly one event, whose duration equals the time between leaving and re-entering Execute (±1 s). |
| MES-DT-02 | Each event gets an automatic reason from the StopReason (mapping table below), editable by the operator or shift lead until the end of the next shift. Edits are audited. | MVP | Bin-full holds are auto-classified "Reject bin full". An operator reclassifies one; the audit shows the old value, new value, user and time. |
| MES-DT-03 | Reason codes are kept in a two-level table (category, reason) editable by the shift lead; codes are never deleted, only deactivated. | MVP | A new reason added by the shift lead appears in the operator's list without a restart. |
| MES-DT-04 | Unclassified events longer than 2 min (automatic reason "Unknown" or "Stop command") are flagged on the operator screen until classified. | MVP | After a manual Stop of 3 min, the operator screen shows one event to classify. |
| MES-DT-05 | Pareto of downtime by reason (duration and count) per shift, day, week. | MVP | Pareto matches a SQL sum over downtime events. |
| MES-DT-06 | Downtime during which Ignition had no data (communication loss) is recorded as a separate "No data" reason, never silently merged. | Later | A 2-min `Sim.Faults.OpcUaOutage` produces a "No data" interval. |

Default StopReason → reason mapping (MVP content of the reason table):

| StopReason | Category / reason |
|---|---|
| 0, no order loaded | Organisational / No order |
| 1 Stop command, 2 Hold command, 5 Suspend command, 4 Abort command | Unclassified / Stop command (operator must refine) |
| 3 Order complete (time until the next Execute) | Planned / Changeover |
| 10 Starved | Organisational / No parts from upstream |
| 11 Blocked | Organisational / Downstream blocked |
| 20 Reject bin full | Process / Reject bin full |
| 101, 103 | Safety / Emergency stop, Guard door |
| 110, 111 | Technical / Robot gripper |
| 120, 121, 122, 140 | Technical / Conveyor |
| 130, 131 | Technical / Quality station |
| 150 | Utilities / Compressed air |
| 160 | Technical / Robot controller |
| Maintenance mode | Planned / Maintenance (excluded from planned time, MES-OEE-01) |

### 4.6 Traceability (TRC)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-TRC-01 | Every part finished by the cell is stored in the database: part id, order id, product code, result, defect code, measured diameter, timestamp, cell, shift, plus the controller start time and sequence, which make the record unique. Records are read with the handshake `C01.Traceability.DataReady` / `C01.Traceability.AckSequence`. The ack is written only after the database commit. | MVP | After 60 min of PT1, the row count equals the number of finished parts (`C01.Admin.ProdProcessedCount` delta), with no duplicates. |
| MES-TRC-02 | No record is lost for an MES or network outage up to 5 min. If `C01.Traceability.LostCount` increases, a High alarm is raised and the gap (time range, number of records) is logged. | MVP | `Sim.Faults.OpcUaOutage` = 300 s: all records arrive after reconnection and the backlog `C01.Traceability.BufferCount` returns to ≤ 1 within 2 min. |
| MES-TRC-03 | Search by part id, by order or by time range, with export to CSV. | MVP | Searching a part id returns its record in < 2 s with 1 million rows in the table. |
| MES-TRC-04 | Genealogy upstream (raw material batch, machining operation) and downstream (packing box id). | Later | n/a in MVP. |

### 4.7 Quality (QA)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-QA-01 | Rejects per order and per shift by defect code (undersize, oversize, scrapped ...). | MVP | Matches part_result counts by defect code. |
| MES-QA-02 | Trend of measured diameter for the running order, with nominal and limits drawn (from part_result, last 500 parts). | MVP | With `Sim.Faults.QualityDriftRate` set, the trend visibly drifts towards a limit. |
| MES-QA-03 | Quality hold: the quality engineer can hold the cell with reason "Quality hold". Only Quality (or Admin) can then allow Unhold. A `C01.Alarms.RejectRateHigh` alarm notifies Quality. | Later | The operator's Unhold is refused while a quality hold is active. |
| MES-QA-04 | SPC charts (X-bar/R, Cpk) on the measured diameter. | Later | n/a in MVP (Sepasoft SPC is the usual product). |

### 4.8 Alarms and events (ALM)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-ALM-01 | Alarms on the `C01.Alarms.*` bits and the status bits listed in fault-catalogue.md, with the priorities given there. They are shown on the cell screen (active, unacknowledged) and acknowledged by Operator or higher. | MVP | `C01.Alarms.RejectBinFull` appears within 1 s with priority Medium; acknowledging records the user. |
| MES-ALM-02 | Alarm journal kept in PostgreSQL with active, clear and ack events, searchable by time, equipment and priority. | MVP | An alarm 1 week old is retrievable with its ack user. |
| MES-ALM-03 | Event journal (database) for: PackML state changes (`C01.Status.StateCurrent`), mode changes, order loads (with LoadResult), operator commands (user, command, CmdResult), controller restarts. | MVP | A Start by the operator produces a command event with user, and a state event 3 → 6. |
| MES-ALM-04 | Communication health: an alarm when the OPC UA or Modbus data is stale for more than 5 s (heartbeats `C01.Status.Heartbeat`, `IO01.Status.Heartbeat`). | MVP | `Sim.Faults.ModbusOutage` = 30 s raises the alarm within 10 s and clears it after reconnection. |
| MES-ALM-05 | E-mail/SMS notification of High and Critical alarms to maintenance on call. | Later | Requires an SMTP server; out of MVP. |

### 4.9 Reports (RPT)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-RPT-01 | Shift report (PDF) generated automatically 10 min after each shift end. Content: orders worked with good/reject; OEE and A/P/Q; downtime Pareto (top 5); rejects by defect code; alarm count by priority; energy per good part (from `UT01.Status.EnergyTotal`); comments. Archived and downloadable. | MVP | The report exists for every shift of a test day; its figures equal the MES screens for that shift. |
| MES-RPT-02 | The shift lead can add a free-text comment to the shift before the report is generated. | MVP | The comment appears in the PDF. |
| MES-RPT-03 | Order report (PDF) on completion: quantities, start/end, duration, OEE, downtime, measurement summary (min/mean/max). | MVP | Generated for each Completed order. |
| MES-RPT-04 | Weekly management report e-mailed to the plant manager. | Later | |

### 4.10 Users and roles (USR)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-USR-01 | Roles: Operator, ShiftLead, Quality, Maintenance, Manager, Admin, with the permission matrix below. Every user logs in by name; the cell panel can switch user without closing the session. | MVP | Each role sees only its permitted actions; forbidden actions are hidden or disabled, and refused server-side. |
| MES-USR-02 | Every write to the cell (commands, order load, bin emptied, speed) and every data edit (reason, order) is audited with user, time, old value and new value. | MVP | The audit log shows all of the operator's writes during a test shift. |
| MES-USR-03 | Integration with the company directory (Active Directory / LDAP). | Later | |

| Action | Operator | ShiftLead | Quality | Maintenance | Manager | Admin |
|---|---|---|---|---|---|---|
| View all screens | yes | yes | yes | yes | yes | yes |
| PackML commands, bin emptied (`RJ01.Command.BinEmptied`) | yes | yes | no | yes | no | yes |
| Dispatch order | yes | yes | no | no | no | yes |
| Create / release / sequence / close orders | no | yes | no | no | no | yes |
| Classify downtime | yes | yes | no | yes | no | yes |
| Edit reason table | no | yes | no | no | no | yes |
| Maintenance mode, conveyor jog, speed (`C01.Command.MachSpeed`) | no | no | no | yes | no | yes |
| Quality hold (Later) | no | no | yes | no | no | yes |
| Users, configuration | no | no | no | no | no | yes |

### 4.11 HMI (HMI)

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-HMI-01 | Cell overview screen (Perspective, 1920×1080 touch). It shows: PackML state with colour, mode, active order and progress, live OEE, CurMachSpeed, StopReason text, active alarms, reject bin level (`RJ01.Status.Count` / `RJ01.Parameters.Capacity`), and status of robot, conveyors and camera. | MVP | All values update within 1 s of the PLC. Buttons can be used with gloves (≥ 15 mm targets). |
| MES-HMI-02 | Screens: order list, dispatch, downtime classification, traceability search, quality, reports, alarms. Navigation reachable in ≤ 2 touches from the overview. | MVP | Walk-through with each persona's main task. |
| MES-HMI-03 | Destructive commands (Stop, Abort, close order short) ask for confirmation. | MVP | |
| MES-HMI-04 | French translation of the UI. | Later | |
| MES-HMI-05 | Mobile layout for tablets (shift lead, maintenance). | Later | |

## 5. Non-functional requirements

| Id | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| MES-NF-01 | Platform: Ignition 8.3 with standard modules only (Perspective, SQL Bridge, Reporting, Alarm Notification/Journal, Historian, OPC UA, drivers) and PostgreSQL. No third-party module in the MVP. | MVP | Gateway module list contains no third-party module. |
| MES-NF-02 | Performance: screen data latency ≤ 1 s; command round trip (write → CmdResult shown) ≤ 1 s; page load ≤ 3 s; report generation ≤ 30 s. | MVP | Measured on the lab stack. |
| MES-NF-03 | Production never depends on the MES: if Ignition or the database is down, the cell keeps producing. Data gaps are bounded (MES-TRC-02) and visible (MES-ALM-04). | MVP | Stop the gateway for 3 min during production: the cell stays in Execute, and no record is lost after restart. |
| MES-NF-04 | Time: all data stored in UTC; displayed in Europe/Paris; shifts follow local time across daylight-saving changes (a shift crossing a change is 7 h or 9 h long, not 8). | MVP | Unit test of the shift calculation for the last Sunday of March and of October. |
| MES-NF-05 | Data retention: traceability 10 years; events, alarms and downtime 3 years; tag history (raw) 1 year. Volume basis: about 6 million part records per year per cell. | MVP | Database sizing note delivered; partitioning or pruning jobs configured. |
| MES-NF-06 | Backup: daily gateway backup and PostgreSQL dump, kept 30 days; a restore procedure tested once. | MVP | Restore test report. |
| MES-NF-07 | Maintainability: one UDT per equipment type, tag paths and names from the registry, Named Queries for all SQL, shared scripts in a project library, project and gateway configuration kept in git. | MVP | Adding a second cell needs no copy-paste of scripts, only new UDT instances and a new cell row. |
| MES-NF-08 | Security: role-based access (MES-USR-01); the simulation namespace (`Sim.*`) is not reachable from the production project; HTTPS and OPC UA security (Basic256Sha256, user/password) before go-live. | MVP (roles, Sim isolation); Later (HTTPS, OPC UA security) | Pen-test checklist for go-live. |
| MES-NF-09 | Scalability: the design supports 4 cells on one gateway without schema change (cell id in every table). | MVP | Schema review. |
| MES-NF-10 | Documentation: user guide per persona (2 pages each) and an administrator guide. | Later | |

## 6. MVP implementation map (core Ignition only)

| Feature | Core Ignition approach | Sepasoft module usually used (paid, not used here) |
|---|---|---|
| Orders, product master | PostgreSQL tables, Named Queries, Perspective tables/forms | MES Production / Work Orders |
| Dispatch, PackML commands | Perspective buttons → gateway message handler → `system.tag.writeBlocking` + CmdResult/LoadResult check | Settings & Changeover, MES Production |
| State history and downtime | Gateway tag-change event on `C01.Status.StateCurrent` → `state_event` table; SQL views building downtime events | OEE Downtime |
| OEE | SQL over `state_event`, `part_result`, shift calendar; gateway timer script every 60 s for the live shift; stored on shift close | OEE Downtime |
| Traceability | SQL Bridge transaction group triggered by `C01.Traceability.DataReady`, with handshake write of Sequence to `C01.Traceability.AckSequence` (or an equivalent gateway script) | Track & Trace |
| Alarms, journal | Tag alarms, Alarm Journal (database profile), Alarm Status Table | (core) |
| Trends | SQL Historian on PostgreSQL (or Core Historian) for status/analog tags | (core) |
| Reports | Reporting module, scheduled per shift, PDF archive | (core) |
| Users and audit | Ignition user source + security levels, audit profile | (core) |
| ERP link | Inbox/outbox tables (MVP stub) | Business Connector, Interface for SAP ERP |
| SPC | (Later) | SPC |

Suggested minimum schema (indicative; the integrator owns the final design):

| Table | Key columns |
|---|---|
| `cell` | cell_id, code, name |
| `product` | product_code, part_type, description, nominal_mm, tolerance_mm, ideal_cycle_s |
| `production_order` | order_id, product_code, target_qty, due_date, seq, status, created_by/at |
| `order_event` | order_id, ts, from_status, to_status, user, comment |
| `part_result` | cell_id, controller_start, sequence (unique together), part_id, order_id, product_code, result, defect_code, diameter_mm, ts, shift_id |
| `state_event` | cell_id, ts, state, mode, stop_reason |
| `downtime_event` | cell_id, start_ts, end_ts, auto_reason, reason_id, comment, edited_by/at |
| `reason_code` | reason_id, category, reason, active |
| `shift_calendar`, `shift` | pattern; shift_id, cell_id, start_ts, end_ts, planned_break_s, comment |
| `shift_kpi` | shift_id, planned_s, run_s, good, total, ideal_s, A, P, Q, OEE |

## 7. Out of scope for the MVP

Labour tracking, material/stock management, maintenance work orders (CMMS), recipes beyond part
type selection, multi-site roll-up, ERP real-time integration.

## 8. Sources

- OEE definitions and formulas: https://www.oee.com/calculating-oee/
- ISA-95 / IEC 62264 functional hierarchy (levels 0-4) and ISA-TR88 PackML (state model used for downtime): see scenario.md sources.
- Ignition 8.3 historian (Core Historian, SQL Historian): https://docs.inductiveautomation.com/docs/8.3/ignition-modules/tag-historian and https://docs.inductiveautomation.com/docs/8.3/getting-started/modules-overview/core-modules/sql-historian-module
