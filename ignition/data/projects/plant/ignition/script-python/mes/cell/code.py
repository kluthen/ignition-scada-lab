"""MES functions of one cell, gateway scope (docs/system/mes.md). Jython 2.7.

Called from tag event scripts of the cell UDT PIC200_Cell (generate_tags.py):
  MES/Tick                valueChanged, every second  -> tick(base)
  Traceability/DataReady  valueChanged                -> store_record(base)
  Status/StateCurrent     valueChanged                -> log_state(base, currentValue)
base is the UDT instance path, e.g. "[default]ANN/FIN/C03"; the instance name is the cell id.

Requirement ids refer to docs/mes-requirements.md. Everything here is idempotent,
so a tick and an event handling the same record at the same time do no harm.
"""

import time

DB = "mes"
log = system.util.getLogger("mes.cell")
BAD_LOG_PERIOD_S = 300
_bad_logged = {}        # cell -> time of the last "not good" log line

TICK = ["Status/StateCurrent", "Admin/StopReason", "Admin/StateCurrentTime",
        "Order/Active/OrderId", "Order/Active/OrderStatus", "Order/Active/GoodCount",
        "Order/Active/RejectCount", "Order/Active/RemainingQuantity",
        "Order/Request/LoadRequest", "Order/Request/LoadResult",
        "Traceability/DataReady", "MES/AutoRun"]
OPTIONAL = ["RJ01/Status/Full"]      # Modbus (IO01): bad while the driver is unlicensed (trial expired)
CELL_NODE = "nsu=urn:ignition-lab:cell;s=%s.%s"
STATE_QUALIFIERS = ["Status.StateCurrentName", "Admin.StopReason", "Admin.StopReasonText", "Order.Active.OrderId"]
TRACE = ["Traceability/DataReady", "Traceability/Sequence", "Traceability/PartId", "Traceability/OrderId",
         "Traceability/PartType", "Traceability/MeasuredDiameter", "Traceability/Result",
         "Traceability/DefectCode", "Traceability/Timestamp", "Admin/StartUpTime"]


def cell_of(base):
    return base.rsplit("/", 1)[-1]


def read(base, names):
    """Read base/name for every name. Returns (values by name, names whose quality is not good)."""
    qvs = system.tag.readBlocking([base + "/" + n for n in names])
    return (dict((n, qv.value) for n, qv in zip(names, qvs)),
            ["%s (%s)" % (n, qv.quality) for n, qv in zip(names, qvs) if not qv.quality.isGood()])


def tick(base):
    v, bad = read(base, TICK)
    cell = cell_of(base)
    optional, missing = read(base, OPTIONAL)
    v.update((k, None if any(m.startswith(k + " ") for m in missing) else x) for k, x in optional.items())
    if bad:                          # controller offline, or gateway in demo mode: nothing to do
        if time.time() - _bad_logged.get(cell, 0) > BAD_LOG_PERIOD_S:
            _bad_logged[cell] = time.time()
            log.warnf("%s: MES cycle skipped, not good: %s", cell, ", ".join(bad))
        return
    if v["Traceability/DataReady"]:  # fallback if a DataReady event was missed
        store_record(base)
    follow_order(cell, v)
    if v["MES/AutoRun"]:
        labsim.autopilot.step(base, cell, v)


# --- traceability (MES-TRC-01) -----------------------------------------------
def store_record(base):
    """Store the presented record, then acknowledge it (ack only after the commit)."""
    v, bad = read(base, TRACE)
    if bad or not v["Traceability/DataReady"]:
        return
    cell, seq = cell_of(base), v["Traceability/Sequence"]
    system.db.runPrepUpdate(
        "INSERT INTO mes.part_result (cell, startup_time, sequence, part_id, order_id, product_code, part_type,"
        " measured_mm, result, defect_code, produced_at)"
        " VALUES (?, ?, ?, ?, ?, (SELECT product_code FROM mes.product WHERE part_type = ?), ?, ?, ?, ?, ?)"
        " ON CONFLICT DO NOTHING",
        [cell, v["Admin/StartUpTime"], seq, v["Traceability/PartId"], v["Traceability/OrderId"],
         v["Traceability/PartType"], v["Traceability/PartType"], v["Traceability/MeasuredDiameter"],
         v["Traceability/Result"], v["Traceability/DefectCode"], v["Traceability/Timestamp"]], DB)
    system.tag.writeBlocking([base + "/Traceability/AckSequence"], [seq])


# --- PackML state log (basis for downtime and OEE) ---------------------------
def log_state(base, qv):
    if not qv.quality.isGood():
        return
    cell, state = cell_of(base), qv.value
    last = system.db.runScalarPrepQuery(
        "SELECT state FROM mes.cell_state WHERE cell = ? ORDER BY started_at DESC LIMIT 1", [cell], DB)
    if last == state:                # gateway restart, reconnection: same state, no new row
        return
    # Admin/* members sit in the 1 s tag group and lag behind the 250 ms state: read the
    # qualifiers from the controller itself, through the cell's OPC connection (named like the cell).
    qvs = system.opc.readValues(cell, [CELL_NODE % (cell, n) for n in STATE_QUALIFIERS])
    name, reason, text, order_id = [q.value if q.quality.isGood() else None for q in qvs]
    system.db.runPrepUpdate(
        "INSERT INTO mes.cell_state (cell, started_at, state, state_name, stop_reason, stop_text, order_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
        [cell, qv.timestamp, state, name or str(state), reason or 0, text or "", order_id or ""], DB)


# --- orders (MES-ORD-02, MES-DSP-04) -----------------------------------------
def set_order_status(order_id, status, cell, by_user, comment="", sets="", args=None):
    """Change an order's status and log the transition. sets: extra "col = ?" assignments."""
    system.db.runPrepUpdate("UPDATE mes.work_order SET status = ?" + sets + " WHERE order_id = ?",
                            [status] + (args or []) + [order_id], DB)
    system.db.runPrepUpdate(
        "INSERT INTO mes.order_event (order_id, status, cell, by_user, comment) VALUES (?, ?, ?, ?, ?)",
        [order_id, status, cell, by_user, comment], DB)
    log.infof("%s: order %s -> %s (%s)", cell, order_id, status, by_user)


def follow_order(cell, v):
    order_id, plc_status = v["Order/Active/OrderId"], v["Order/Active/OrderStatus"]
    if not order_id:
        return
    # A Running order that is no longer the cell's active order was replaced by hand
    # (HMI, smoke test): close it short with the counts recorded so far (MES-ORD-08).
    replaced = system.db.runPrepQuery(
        "SELECT order_id FROM mes.work_order WHERE cell = ? AND status = 'Running' AND order_id <> ?",
        [cell, order_id], DB)
    for row in replaced:
        set_order_status(row[0], "ClosedShort", cell, "mes", comment="replaced on the cell by " + order_id,
                         sets=", ended_at = now(), good_qty = (SELECT count(*) FROM mes.part_result r"
                              " WHERE r.order_id = ? AND r.result = 1), reject_qty = (SELECT count(*)"
                              " FROM mes.part_result r WHERE r.order_id = ? AND r.result <> 1)",
                         args=[row[0], row[0]])
    if plc_status not in (2, 3):
        return
    status = system.db.runScalarPrepQuery(
        "SELECT status FROM mes.work_order WHERE order_id = ? AND cell = ?", [order_id, cell], DB)
    if status is None:               # not an MES order (e.g. the smoke test's TEST-xxxxx)
        return
    if status == "Dispatched":
        set_order_status(order_id, "Running", cell, "mes", sets=", started_at = now()")
        status = "Running"
    if status == "Running" and plc_status == 3:
        set_order_status(order_id, "Completed", cell, "mes",
                         sets=", ended_at = now(), good_qty = ?, reject_qty = ?",
                         args=[v["Order/Active/GoodCount"], v["Order/Active/RejectCount"]])
