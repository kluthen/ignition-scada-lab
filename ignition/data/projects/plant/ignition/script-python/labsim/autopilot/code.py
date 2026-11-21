"""Lab autopilot, gateway scope (docs/system/mes.md). Jython 2.7.

Stands in for the people of the plant so that the five cells keep producing
and the lab collects data without anyone at the screens:
  - planner:  keeps MIN_RELEASED Released orders per product (a shift lead's job, MES-ORD-01..04);
  - operator: dispatches the next order a cell is qualified for (MES-DSP-01), starts the cell,
              resets it after a changeover, clears an abort, empties the reject bin.
Not a customer requirement. Called by mes.cell.tick() only while the cell's
MES/AutoRun tag is true; set it false to drive a cell by hand (HMI, smoke test).
"""

import random
import time

DB = "mes"
log = system.util.getLogger("labsim.autopilot")
USER = "labsim.autopilot"

MIN_RELEASED = 2                        # per product
ORDER_SIZES = [50, 80, 100, 150, 200, 300]
CHANGEOVER_S = (20.0, 90.0)             # Complete -> Reset
BIN_RESPONSE_S = (60.0, 240.0)          # Held on reject bin full -> operator empties the bin
START_DELAY_S = (3.0, 15.0)             # order loaded -> Start
RESET_DELAY_S = (3.0, 10.0)             # Stopped -> Reset
COMMAND_HOLDOFF_S = 5.0                 # do not repeat a command sooner

# PackML (opcua-registry.md section 5)
STOPPED, IDLE, ABORTED, HELD, COMPLETE = 2, 4, 9, 11, 17
RESET, START, UNHOLD, CLEAR = 1, 2, 5, 9

_waits = {}         # (cell, kind) -> (seconds in state at last look, drawn delay)
_last_cmd = {}      # cell -> (code, time)
_loading = {}       # cell -> order id written to Order/Request, waiting for LoadResult


def waited(cell, kind, in_state, bounds):
    """True once the cell has been in its state for a random delay drawn on state entry."""
    last, delay = _waits.get((cell, kind), (None, None))
    if last is None or in_state < last:          # new occurrence of the state
        delay = random.uniform(*bounds)
    _waits[(cell, kind)] = (in_state, delay)
    return in_state >= delay


def command(base, cell, code):
    code_t = _last_cmd.get(cell)
    if code_t and code_t[0] == code and time.time() - code_t[1] < COMMAND_HOLDOFF_S:
        return
    _last_cmd[cell] = (code, time.time())
    system.tag.writeBlocking([base + "/Command/CntrlCmd"], [code])


def step(base, cell, v):
    state, in_state = v["Status/StateCurrent"], v["Admin/StateCurrentTime"]
    if state == ABORTED:
        command(base, cell, CLEAR)
    elif state == STOPPED and waited(cell, "reset", in_state, RESET_DELAY_S):
        command(base, cell, RESET)
    elif state == COMPLETE and waited(cell, "changeover", in_state, CHANGEOVER_S):
        command(base, cell, RESET)
    elif state == HELD and v["Admin/StopReason"] == 20 and waited(cell, "bin", in_state, BIN_RESPONSE_S):
        if v["RJ01/Status/Full"] is False:
            command(base, cell, UNHOLD)
        else:                                       # full, or unknown (Modbus down): empty it first
            system.tag.writeBlocking([base + "/RJ01/Command/BinEmptied"], [True])
            command(base, cell, UNHOLD)             # refused (3) while the PLC still sees it full
    elif state == IDLE:
        if v["Order/Active/OrderStatus"] in (1, 2) and v["Order/Active/RemainingQuantity"] > 0:
            if waited(cell, "start", in_state, START_DELAY_S):
                command(base, cell, START)
        else:
            dispatch(base, cell, v)


# --- planner -----------------------------------------------------------------
def plan():
    rows = system.db.runQuery(
        "SELECT p.product_code, count(w.order_id) FROM mes.product p"
        " LEFT JOIN mes.work_order w ON w.product_code = p.product_code AND w.status = 'Released'"
        " GROUP BY p.product_code", DB)
    for row in rows:
        for _ in range(MIN_RELEASED - row[1]):
            order_id = system.db.runScalarPrepQuery(
                "INSERT INTO mes.work_order (order_id, product_code, target_qty, status, created_by)"
                " VALUES ('OF-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('mes.order_no_seq')::text, 5, '0'),"
                " ?, ?, 'Released', ?) RETURNING order_id",
                [row[0], random.choice(ORDER_SIZES), USER], DB)
            system.db.runPrepUpdate(
                "INSERT INTO mes.order_event (order_id, status, by_user, comment) VALUES (?, 'Released', ?, 'planned')",
                [order_id, USER], DB)


# --- operator: dispatch (MES-DSP-01/02) --------------------------------------
NEXT_ORDER = """
WITH next AS (
    SELECT w.order_id FROM mes.work_order w
    JOIN mes.product p USING (product_code)
    JOIN mes.cell c ON c.cell = ?
    WHERE w.status = 'Released' AND p.part_type = ANY (c.qualified_part_types)
    ORDER BY w.seq LIMIT 1
    FOR UPDATE OF w SKIP LOCKED)
UPDATE mes.work_order w SET status = 'Dispatched', cell = ?, dispatched_at = now()
FROM next, mes.product p
WHERE w.order_id = next.order_id AND p.product_code = w.product_code
RETURNING w.order_id, p.part_type, w.target_qty
"""


def dispatch(base, cell, v):
    if v["Order/Request/LoadRequest"]:
        return                                      # the PLC has not answered yet
    pending = _loading.pop(cell, None)
    if pending and v["Order/Request/LoadResult"] not in (0, 1):
        result = v["Order/Request/LoadResult"]
        mes.cell.set_order_status(pending, "Released" if result == 2 else "Cancelled", cell, USER,
                                  comment="LoadResult %d" % result, sets=", cell = NULL")
        return
    rows = system.db.runPrepQuery(
        "SELECT w.order_id, p.part_type, w.target_qty FROM mes.work_order w JOIN mes.product p USING (product_code)"
        " WHERE w.cell = ? AND w.status = 'Dispatched' ORDER BY w.seq LIMIT 1", [cell], DB)
    if not len(rows):
        plan()
        rows = system.db.runPrepQuery(NEXT_ORDER, [cell, cell], DB)
        if not len(rows):
            return
        system.db.runPrepUpdate(
            "INSERT INTO mes.order_event (order_id, status, cell, by_user) VALUES (?, 'Dispatched', ?, ?)",
            [rows[0][0], cell, USER], DB)
        log.infof("%s: dispatching %s (part type %d, %d parts)", cell, rows[0][0], rows[0][1], rows[0][2])
    order_id, part_type, qty = rows[0][0], rows[0][1], rows[0][2]
    if v["Order/Active/OrderId"] == order_id:
        return                                      # loaded; Start follows in step()
    system.tag.writeBlocking([base + "/Order/Request/OrderId", base + "/Order/Request/PartType",
                              base + "/Order/Request/TargetQuantity"], [order_id, part_type, qty])
    system.tag.writeBlocking([base + "/Order/Request/LoadRequest"], [True])
    _loading[cell] = order_id
