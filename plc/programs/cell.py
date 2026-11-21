"""Cell 01 program: pick-and-inspect cell, phase 1 (deterministic, no faults).

Implements docs/scenario.md sections 4 to 7. Signal names are those of
docs/opcua-registry.csv; section numbers in comments refer to scenario.md.
"""

from __future__ import annotations

import collections
import datetime as dt
import logging
import math

from registry import NULL_DATETIME
from tags import Tags

log = logging.getLogger("cell")
UTC = dt.timezone.utc

# --- enumerations (opcua-registry.md section 5) ------------------------------
STATES = ["Undefined", "Clearing", "Stopped", "Starting", "Idle", "Suspended", "Execute", "Stopping",
          "Aborting", "Aborted", "Holding", "Held", "Unholding", "Suspending", "Unsuspending",
          "Resetting", "Completing", "Complete"]
(CLEARING, STOPPED, STARTING, IDLE, SUSPENDED, EXECUTE, STOPPING, ABORTING, ABORTED, HOLDING, HELD,
 UNHOLDING, SUSPENDING, UNSUSPENDING, RESETTING, COMPLETING, COMPLETE) = range(1, 18)
MODES = {1: "Production", 2: "Maintenance", 3: "Manual"}
STOP_TEXT = {0: "None", 1: "Stop command", 2: "Hold command", 3: "Order complete", 4: "Abort command",
             5: "Suspend command", 10: "Starved", 11: "Blocked", 20: "Reject bin full",
             101: "Emergency stop", 103: "Guard door open", 110: "Vacuum loss", 111: "Pick failed",
             120: "Infeed jam", 121: "Infeed drive fault", 122: "Outfeed drive fault",
             130: "Quality station no result", 131: "Part ID unreadable", 140: "Part sensor stuck",
             150: "Air pressure low", 160: "Robot communication fault"}
STEP_NAMES = ["NotReady", "Homing", "WaitPart", "MoveToPick", "Grip", "Lift", "MoveToPlace",
              "WaitPlaceClear", "Release", "ReturnToWait", "Halted"]
(NOT_READY, HOMING, WAIT_PART, MOVE_TO_PICK, GRIP, LIFT, MOVE_TO_PLACE, WAIT_PLACE_CLEAR, RELEASE,
 RETURN_TO_WAIT, HALTED) = range(11)
WAIT_STEPS = (WAIT_PART, WAIT_PLACE_CLEAR)
ON_PATH_STEPS = (HOMING, MOVE_TO_PICK, LIFT, MOVE_TO_PLACE, RETURN_TO_WAIT)
GOOD, REJECT, SCRAPPED = 1, 2, 3                     # PartResult
UNDERSIZE, OVERSIZE, PURGED = 1, 2, 6                # DefectCode

# --- recipes (section 3) -----------------------------------------------------
RECIPES = {
    1: dict(code="HSG-A20", nominal=20.000, tol=0.050, factor=1.0, ideal=2.4, program="PNP_HSG_A20"),
    2: dict(code="HSG-B32", nominal=32.000, tol=0.080, factor=1.1, ideal=2.6, program="PNP_HSG_B32"),
    3: dict(code="HSG-C45", nominal=45.000, tol=0.100, factor=1.2, ideal=2.8, program="PNP_HSG_C45"),
}

# --- constants ---------------------------------------------------------------
CV01_LEN, CV02_LEN, PITCH = 2000.0, 1500.0, 100.0
SETTLE_S, INSPECT_S = 0.2, 0.4
TRACE_FIFO = 200
SERIAL_EPOCH = dt.datetime(2026, 1, 1, tzinfo=UTC)
ACTING_TIMEOUTS = {CLEARING: (1.0, STOPPED), STARTING: (1.0, EXECUTE), ABORTING: (0.5, ABORTED),
                   UNHOLDING: (1.0, EXECUTE), UNSUSPENDING: (1.0, EXECUTE)}
CONVEYORS_ON = {STARTING, SUSPENDED, EXECUTE, STOPPING, HOLDING, UNHOLDING, SUSPENDING, UNSUSPENDING,
                COMPLETING}
FEED_STATES = {EXECUTE, SUSPENDING, SUSPENDED, UNSUSPENDING}
ROBOT_FINISHING = {EXECUTE, HOLDING, STOPPING, SUSPENDING, COMPLETING}   # may finish steps 3..9


class Part:
    __slots__ = ("serial", "part_id", "order_id", "part_type", "x", "insp_t", "inspected",
                 "measured", "good", "defect")

    def __init__(self, serial: int, order_id: str, part_type: int):
        self.serial = serial
        self.part_id = f"P{serial:09d}"
        self.order_id = order_id
        self.part_type = part_type
        self.x = PITCH                 # front edge, mm from the entry
        self.insp_t = 0.0
        self.inspected = False
        self.measured = 0.0
        self.good = False
        self.defect = 0


class Program:
    def __init__(self, tags: Tags):
        self.t = tags
        self.now = dt.datetime.now(UTC)
        self.startup = self.now
        self.serial = int((self.now - SERIAL_EPOCH).total_seconds())
        self.state, self.state_time, self.uptime = STOPPED, 0.0, 0.0
        self.cv01: list[Part] = []          # front (closest to the end stop) first
        self.cv02: list[float] = []         # front positions, front first
        self.robot_step, self.step_t, self.step_dur = NOT_READY, 0.0, 0.0
        self.robot_part: Part | None = None
        self.purging = False
        self.cycle_start: float | None = None
        self.vacuum = 0.0
        self.feed_t: float | None = None    # time since last release; None = release immediately
        self.starved_t = self.blocked_t = 0.0
        self.placements: collections.deque[float] = collections.deque(maxlen=5)
        self.fifo: collections.deque[dict] = collections.deque()
        self.trace_seq = 0
        self.trace_pending = False          # record written, DataReady goes true next scan
        self.trace_acked = False            # record removed this scan, present the next one next scan
        self.energy_wh = 0.0
        self.sec_acc = 0.0
        self.order_seen_execute = False
        for name in ("C01.Admin.StartUpTime", "C01.Status.PacDateTime",
                     "RB01.Controllers.RC01.ParameterSet.StartUpTime"):
            tags[name] = self.startup
        self._publish_state()
        log.info("cell program ready: state Stopped, part serials start at %d", self.serial)

    # =========================================================================
    def scan(self, dt_s: float) -> None:
        t = self.t
        self.now = dt.datetime.now(UTC)
        self.uptime += dt_s
        self.state_time += dt_s
        self._clamp_parameters()
        self._commands()
        self._order_load()
        self._bin_and_trace_inputs()
        self._speed()
        self._acting_transitions()
        running = self._conveyors_running()
        self._feed(dt_s)
        self._move_cv01(dt_s if running[0] else 0.0)
        self._move_cv02(dt_s if running[1] else 0.0)
        self._inspect(dt_s)
        self._robot(dt_s)
        self._acting_transitions()
        self._internal_transitions(dt_s)
        self._outputs(dt_s, running)
        self._traceability_present()
        t["IO01.Status.Heartbeat"] = (t["IO01.Status.Heartbeat"] + 1) & 0xFFFF

    # --- state machine -------------------------------------------------------
    def _set_state(self, state: int, stop_reason: int | None = None) -> None:
        t = self.t
        prev = self.state
        self.state, self.state_time = state, 0.0
        if stop_reason is not None:
            t["C01.Admin.StopReason"] = stop_reason
        if state == EXECUTE:
            t["C01.Admin.StopReason"] = 0
            self.feed_t = None                          # first release is immediate (4.1)
            self.starved_t = self.blocked_t = 0.0
            if t["C01.Order.Active.OrderStatus"] == 1:
                t["C01.Order.Active.OrderStatus"] = 2
                t["C01.Order.Active.StartTime"] = self.now
        if state == COMPLETE:
            t["C01.Order.Active.OrderStatus"] = 3
            t["C01.Order.Active.EndTime"] = self.now
        if state == ABORTING:
            self.robot_step, self.step_t = HALTED, 0.0
            t["RB01.Status.Homed"] = False
        if state == CLEARING:
            self.robot_step = HALTED
        if state == STOPPED and prev == CLEARING:
            self.robot_step = NOT_READY
        if state == RESETTING:
            self.purging = self.robot_part is not None
            self._start_step(HOMING, (1.0 if self.purging else 0.0) + 2.0)
        self._publish_state()
        log.info("state %s -> %s (StopReason %d)", STATES[prev], STATES[state], t["C01.Admin.StopReason"])

    def _publish_state(self) -> None:
        t = self.t
        t["C01.Status.StateCurrent"] = self.state
        t["C01.Status.StateCurrentName"] = STATES[self.state]
        t["C01.Admin.StopReasonText"] = STOP_TEXT.get(t["C01.Admin.StopReason"], "Unknown")

    def _commands(self) -> None:
        t = self.t
        mode_req = t["C01.Command.UnitModeRequest"]
        if mode_req:
            if mode_req not in (1, 2):
                result = 4
            elif self.state not in (STOPPED, IDLE, COMPLETE, ABORTED):
                result = 2
            else:
                result = 1
                t["C01.Status.UnitModeCurrent"] = mode_req
                t["C01.Status.UnitModeCurrentName"] = MODES[mode_req]
                log.info("unit mode -> %s", MODES[mode_req])
            self._cmd_done("C01.Command.UnitModeRequest", result)

        cmd = t["C01.Command.CntrlCmd"]
        if not cmd:
            return
        s, safety = self.state, t["SF01.Status.SafetyOk"]
        target, reason, accepted_in, interlock = None, None, (), True
        if cmd == 1:
            accepted_in, target, interlock = (STOPPED, COMPLETE), RESETTING, safety
        elif cmd == 2:
            accepted_in, target = (IDLE,), STARTING
            interlock = (t["C01.Status.UnitModeCurrent"] == 1
                         and t["C01.Order.Active.OrderStatus"] in (1, 2)
                         and t["C01.Order.Active.RemainingQuantity"] > 0
                         and safety and t["RB01.Status.Homed"] and not t["RJ01.Status.Full"])
        elif cmd == 3:
            accepted_in = tuple(x for x in range(1, 18) if x not in (STOPPED, STOPPING, ABORTING, ABORTED, CLEARING))
            target, reason = STOPPING, 1
        elif cmd == 4:
            accepted_in, target, reason = (EXECUTE,), HOLDING, 2
        elif cmd == 5:
            accepted_in, target = (HELD,), UNHOLDING
            interlock = not (t["C01.Admin.StopReason"] == 20 and t["RJ01.Status.Full"])
        elif cmd == 6:
            accepted_in, target, reason = (EXECUTE,), SUSPENDING, 5
        elif cmd == 7:
            accepted_in, target = (SUSPENDED,), UNSUSPENDING
            interlock = t["C01.Admin.StopReason"] == 5
        elif cmd == 8:
            accepted_in = tuple(x for x in range(1, 18) if x not in (ABORTING, ABORTED))
            target, reason = ABORTING, 4
        elif cmd == 9:
            accepted_in, target, interlock = (ABORTED,), CLEARING, safety
        if target is None:
            result = 4
        elif s not in accepted_in:
            result = 2
        elif not interlock:
            result = 3
        else:
            result = 1
            self._set_state(target, reason)
        log.info("CntrlCmd %d in %s -> CmdResult %d", cmd, STATES[s], result)
        self._cmd_done("C01.Command.CntrlCmd", result)

    def _cmd_done(self, name: str, result: int) -> None:
        t = self.t
        t["C01.Command.CmdResult"] = result
        t.inc("C01.Command.CmdCounter")
        t[name] = 0

    def _acting_transitions(self) -> None:
        s, robot_waits = self.state, self.robot_step in WAIT_STEPS
        if s in ACTING_TIMEOUTS:
            limit, target = ACTING_TIMEOUTS[s]
            if self.state_time >= limit:
                self._set_state(target)
        elif s == STOPPING and robot_waits:
            self._set_state(STOPPED)
        elif s == HOLDING and robot_waits:
            self._set_state(HELD)
        elif s == SUSPENDING and robot_waits and self.state_time >= 0.5:
            self._set_state(SUSPENDED)
        elif s == RESETTING and self.robot_step == WAIT_PART and self.t["RB01.Status.Homed"]:
            self._set_state(IDLE)
        elif s == COMPLETING and self.robot_step == WAIT_PART and not self.cv02:
            self._set_state(COMPLETE)

    def _internal_transitions(self, dt_s: float) -> None:
        t = self.t
        if self.state == EXECUTE:
            if t["RJ01.Status.Full"]:
                self._set_state(HOLDING, 20)
            elif self.starved_t >= 10.0:
                self._set_state(SUSPENDING, 10)
            elif self.blocked_t >= 10.0:
                self._set_state(SUSPENDING, 11)
        elif self.state == SUSPENDED:
            reason = t["C01.Admin.StopReason"]
            if reason == 10 and self.cv01:
                self._set_state(UNSUSPENDING)
            elif reason == 11 and not self._cv02_entry_occupied():
                self._set_state(UNSUSPENDING)

    # --- order handling (5.5) --------------------------------------------------
    def _order_load(self) -> None:
        t = self.t
        if not t["C01.Order.Request.LoadRequest"]:
            return
        order_id = t["C01.Order.Request.OrderId"]
        part_type = t["C01.Order.Request.PartType"]
        qty = t["C01.Order.Request.TargetQuantity"]
        if self.state not in (STOPPED, IDLE, COMPLETE):
            result = 2
        elif not order_id or len(order_id) > 32 or not all(32 <= ord(c) < 127 for c in order_id):
            result = 3
        elif part_type not in RECIPES:
            result = 4
        elif qty == 0 or qty > 100000:
            result = 5
        else:
            result = 1
        t["C01.Order.Request.LoadResult"] = result
        t["C01.Order.Request.LoadRequest"] = False
        log.info("order load %r type %s qty %s -> LoadResult %d", order_id, part_type, qty, result)
        if result != 1:
            return
        for part in list(self.cv01) + ([self.robot_part] if self.robot_part else []):
            self._finish(part, SCRAPPED, PURGED)
        self.cv01.clear()
        if self.robot_part:
            self.robot_part = None
            if self.robot_step == WAIT_PLACE_CLEAR:
                self.robot_step = WAIT_PART
        r = RECIPES[part_type]
        for name, value in (("OrderId", order_id), ("PartType", part_type), ("ProductCode", r["code"]),
                            ("TargetQuantity", qty), ("GoodCount", 0), ("RejectCount", 0),
                            ("RemainingQuantity", qty), ("OrderStatus", 1), ("NominalDiameter", r["nominal"]),
                            ("LowerLimit", r["nominal"] - r["tol"]), ("UpperLimit", r["nominal"] + r["tol"]),
                            ("IdealCycleTime", r["ideal"]), ("StartTime", NULL_DATETIME), ("EndTime", NULL_DATETIME)):
            t[f"C01.Order.Active.{name}"] = value
        prog = "RB01.Controllers.RC01.TaskControls.Main.ParameterSet."
        t[prog + "TaskProgramName"] = r["program"]
        t[prog + "TaskProgramLoaded"] = True

    # --- reject bin, traceability acknowledge -------------------------------------
    def _bin_and_trace_inputs(self) -> None:
        t = self.t
        if t["RJ01.Command.BinEmptied"]:
            log.info("reject bin emptied (count was %d)", t["RJ01.Status.Count"])
            t["RJ01.Status.Count"] = 0
            t["RJ01.Command.BinEmptied"] = False
        if (t["C01.Traceability.DataReady"] and self.fifo
                and t["C01.Traceability.AckSequence"] == t["C01.Traceability.Sequence"]):
            self.fifo.popleft()
            t["C01.Traceability.DataReady"] = False
            self.trace_acked = True

    def _clamp_parameters(self) -> None:
        t = self.t
        for name, lo, hi in (("CV01.Parameters.SpeedSetpoint", 100, 400), ("CV02.Parameters.SpeedSetpoint", 100, 400),
                             ("RJ01.Parameters.Capacity", 10, 100)):
            if not lo <= t[name] <= hi:
                t[name] = max(lo, min(hi, t[name]))
        near_hi = min(99, t["RJ01.Parameters.Capacity"] - 1)
        if not 5 <= t["RJ01.Parameters.NearFullLevel"] <= near_hi:
            t["RJ01.Parameters.NearFullLevel"] = max(5, min(near_hi, t["RJ01.Parameters.NearFullLevel"]))

    def _speed(self) -> None:
        t = self.t
        part_type = t["C01.Order.Active.PartType"]
        design = 60.0 / RECIPES[part_type]["ideal"] if part_type in RECIPES else 25.0
        t["C01.Admin.MachDesignSpeed"] = design
        mach = max(0.1 * design, min(design, t["C01.Command.MachSpeed"]))
        t["C01.Status.MachSpeed"] = mach
        t["RB01.MotionDevices.Arm.ParameterSet.SpeedOverride"] = max(10.0, min(100.0, 100.0 * mach / design))

    # --- conveyors and feed (4.1, 4.2, 4.5) ---------------------------------------
    def _conveyors_running(self) -> tuple[bool, bool]:
        t = self.t
        on = self.state in CONVEYORS_ON
        jog = t["C01.Status.UnitModeCurrent"] == 2 and self.state in (STOPPED, IDLE)
        return (on or (jog and t["CV01.Command.JogForward"]),
                on or (jog and t["CV02.Command.JogForward"]))

    def _parts_in_process(self) -> int:
        holding_good = self.robot_part is not None and self.robot_part.good
        return len(self.cv01) + (1 if holding_good else 0)

    def _order_needs_parts(self) -> bool:
        t = self.t
        return t["C01.Order.Active.GoodCount"] + self._parts_in_process() < t["C01.Order.Active.TargetQuantity"]

    def _feed(self, dt_s: float) -> None:
        t = self.t
        if self.feed_t is not None:
            self.feed_t += dt_s
        if (self.state in FEED_STATES and t["Sim.Process.UpstreamFeedEnable"]
                and (self.feed_t is None or self.feed_t >= t["Sim.Process.FeedInterval"])
                and not self._cv01_entry_occupied() and self._order_needs_parts()):
            self.serial += 1
            self.cv01.append(Part(self.serial, t["C01.Order.Active.OrderId"], t["C01.Order.Active.PartType"]))
            self.feed_t = 0.0
            t.inc("C01.Admin.ProdConsumedCount")

    def _move_cv01(self, dt_s: float) -> None:
        v = self.t["CV01.Parameters.SpeedSetpoint"]
        limit = CV01_LEN
        for p in self.cv01:
            p.x = min(p.x + v * dt_s, limit)
            limit = p.x - PITCH

    def _move_cv02(self, dt_s: float) -> None:
        v = self.t["CV02.Parameters.SpeedSetpoint"]
        blocked = False             # phase 2: Sim.Faults.DownstreamBlocked holds parts at the exit
        limit, moved = CV02_LEN, []
        for x in self.cv02:
            x = min(x + v * dt_s, limit)
            if x >= CV02_LEN and not blocked:
                continue                         # leaves to packing
            moved.append(x)
            limit = x - PITCH
        self.cv02 = moved

    def _cv01_entry_occupied(self) -> bool:
        return any(p.x - PITCH < PITCH for p in self.cv01)

    def _cv02_entry_occupied(self) -> bool:
        return any(x < 250.0 for x in self.cv02)

    def _part_at_pick(self) -> Part | None:
        return self.cv01[0] if self.cv01 and self.cv01[0].x >= CV01_LEN - 0.5 else None

    # --- QS01 (4.3) ----------------------------------------------------------
    def _inspect(self, dt_s: float) -> None:
        t = self.t
        p = self._part_at_pick()
        busy = False
        if p is not None and not p.inspected:
            p.insp_t += dt_s
            busy = p.insp_t >= SETTLE_S
            if p.insp_t >= SETTLE_S + INSPECT_S:
                busy = False
                self._measure(p)
        t["QS01.Status.Busy"] = busy
        t["QS01.Status.Ready"] = not busy

    def _measure(self, p: Part) -> None:
        t = self.t
        r = RECIPES[p.part_type]
        n, every = p.serial, t["Sim.Process.RejectEveryN"]
        if every > 0 and n % every == 0:
            k = n // every
            m = r["nominal"] + (1.6 if k % 2 else -1.6) * r["tol"]
        else:
            m = r["nominal"] + 0.5 * r["tol"] * math.sin(2 * math.pi * n / 17)
        m = round(m, 3)             # phase 2 adds Sim.Faults.QualityOffset here
        lo, hi = t["C01.Order.Active.LowerLimit"], t["C01.Order.Active.UpperLimit"]
        p.measured, p.inspected = m, True
        p.good = lo <= m <= hi
        p.defect = 0 if p.good else (UNDERSIZE if m < lo else OVERSIZE)
        t["QS01.Status.LastPartId"] = p.part_id
        t["QS01.Status.LastMeasurement"] = m
        t["QS01.Status.LastResult"] = 1 if p.good else 2
        t.inc("QS01.Status.InspectionCount")

    # --- RB01 (4.4) ------------------------------------------------------------
    def _motion(self, base: float) -> float:
        t = self.t
        factor = RECIPES.get(t["C01.Order.Active.PartType"], RECIPES[1])["factor"]
        return base * factor * 100.0 / t["RB01.MotionDevices.Arm.ParameterSet.SpeedOverride"]

    def _start_step(self, step: int, duration: float = 0.0, carry: float = 0.0) -> None:
        self.robot_step, self.step_dur, self.step_t = step, duration, carry

    def _robot(self, dt_s: float) -> None:
        t = self.t
        step = self.robot_step
        if step in (NOT_READY, HALTED):
            return
        if step in WAIT_STEPS:
            self.step_t += dt_s                      # dwell time, for starved/blocked
        if step == WAIT_PART:
            p = self._part_at_pick()
            if self.state == EXECUTE and p is not None and p.inspected:
                self.cycle_start = self.uptime
                self._start_step(MOVE_TO_PICK, self._motion(0.3))
            return
        if step == WAIT_PLACE_CLEAR:
            if self.state == EXECUTE and not self._cv02_entry_occupied():
                self._start_step(RELEASE, 0.2)
            return
        if step != HOMING and self.state not in ROBOT_FINISHING:
            return                                   # frozen outside finishing states
        self.step_t += dt_s
        if step == GRIP:
            self.vacuum = max(-75.0, -75.0 * self.step_t / 0.15)
        elif step == RELEASE:
            self.vacuum = min(0.0, -75.0 + 75.0 * self.step_t / 0.1)
        while self.robot_step not in WAIT_STEPS and self.step_t >= self.step_dur:
            carry = self.step_t - self.step_dur
            if not self._end_step(carry):
                break

    def _end_step(self, carry: float) -> bool:
        """Finish the current timed step. Returns False when the next step is not timed."""
        t = self.t
        step = self.robot_step
        good = self.robot_part.good if self.robot_part else False
        if step == HOMING:
            if self.purging and self.robot_part:
                self._finish(self.robot_part, SCRAPPED, PURGED, to_bin=True)
                self.robot_part = None
            self.purging = False
            t["RB01.Status.Homed"] = True
            self._start_step(WAIT_PART)
            return False
        if step == MOVE_TO_PICK:
            self.vacuum = 0.0
            self._start_step(GRIP, 0.2, carry)
        elif step == GRIP:
            self.vacuum = -75.0
            self.robot_part = self.cv01[0]
            self._start_step(LIFT, self._motion(0.3), carry)
        elif step == LIFT:
            self.cv01.pop(0)                         # the part leaves CV01
            self._start_step(MOVE_TO_PLACE, self._motion(0.7 if good else 0.5), carry)
        elif step == MOVE_TO_PLACE:
            if good:
                self._start_step(WAIT_PLACE_CLEAR)
                if self.state == EXECUTE and not self._cv02_entry_occupied():
                    self._start_step(RELEASE, 0.2, carry)
                    return True
                return False
            self._start_step(RELEASE, 0.2, carry)
        elif step == RELEASE:
            self.vacuum = 0.0
            part, self.robot_part = self.robot_part, None
            if part.good:
                self.cv02.append(PITCH)
                self._finish(part, GOOD, 0)
            else:
                self._finish(part, REJECT, part.defect, to_bin=True)
            self.placements.append(self.uptime - carry)
            self._start_step(RETURN_TO_WAIT, self._motion(0.7 if part.good else 0.5), carry)
        elif step == RETURN_TO_WAIT:
            t.inc("RB01.Status.CycleCount")
            if self.cycle_start is not None:
                t["RB01.Status.LastCycleTime"] = round(self.uptime - carry - self.cycle_start, 3)
            self._start_step(WAIT_PART)
            p = self._part_at_pick()
            if self.state == EXECUTE and p is not None and p.inspected:
                self.cycle_start = self.uptime - carry
                self._start_step(MOVE_TO_PICK, self._motion(0.3), carry)
                return True
            return False
        return True

    # --- counting and traceability (4.7) --------------------------------------------
    def _finish(self, part: Part, result: int, defect: int, to_bin: bool = False) -> None:
        t = self.t
        t.inc("C01.Admin.ProdProcessedCount")
        if result != GOOD:
            t.inc("C01.Admin.ProdDefectiveCount")
        if to_bin:
            t.inc("RJ01.Status.Count")
        if part.order_id == t["C01.Order.Active.OrderId"]:
            t.inc("C01.Order.Active.GoodCount" if result == GOOD else "C01.Order.Active.RejectCount")
            t["C01.Order.Active.RemainingQuantity"] = max(
                0, t["C01.Order.Active.TargetQuantity"] - t["C01.Order.Active.GoodCount"])
        self.trace_seq += 1
        self.fifo.append(dict(Sequence=self.trace_seq, PartId=part.part_id, OrderId=part.order_id,
                              PartType=part.part_type, MeasuredDiameter=part.measured if part.inspected else 0.0,
                              Result=result, DefectCode=defect, Timestamp=self.now))
        if len(self.fifo) > TRACE_FIFO:
            dropped = self.fifo.popleft()
            t.inc("C01.Traceability.LostCount")
            if dropped["Sequence"] == t["C01.Traceability.Sequence"]:
                t["C01.Traceability.DataReady"] = False
                self.trace_pending = False
        if (result == GOOD and self.state == EXECUTE
                and t["C01.Order.Active.GoodCount"] >= t["C01.Order.Active.TargetQuantity"]):
            self._set_state(COMPLETING, 3)

    def _traceability_present(self) -> None:
        t = self.t
        if self.trace_pending:
            t["C01.Traceability.DataReady"] = True
            self.trace_pending = False
        elif self.trace_acked:
            self.trace_acked = False
        elif not t["C01.Traceability.DataReady"] and self.fifo:
            for key, value in self.fifo[0].items():
                t[f"C01.Traceability.{key}"] = value
            self.trace_pending = True
        t["C01.Traceability.BufferCount"] = min(len(self.fifo), TRACE_FIFO)

    # --- outputs ---------------------------------------------------------------
    def _outputs(self, dt_s: float, running: tuple[bool, bool]) -> None:
        t = self.t
        s, step = self.state, self.robot_step
        # conveyors (4.2, 4.5)
        for cv, on, current in (("CV01", running[0], 1.20), ("CV02", running[1], 1.10)):
            t[f"{cv}.Status.Running"] = on
            t[f"{cv}.Status.ActualSpeed"] = t[f"{cv}.Parameters.SpeedSetpoint"] if on else 0
            t[f"{cv}.Status.MotorCurrent"] = current if on else 0.0
        t["CV01.Status.PartsOnConveyor"] = len(self.cv01)
        t["CV02.Status.PartsOnConveyor"] = len(self.cv02)
        t["CV01.Sensors.EntryOccupied"] = self._cv01_entry_occupied()
        t["CV01.Sensors.PartAtPick"] = self._part_at_pick() is not None
        t["CV02.Sensors.EntryOccupied"] = self._cv02_entry_occupied()
        t["CV02.Sensors.ExitPE"] = any(1400.0 <= x <= CV02_LEN for x in self.cv02)
        # reject bin (4.6)
        if t["Sim.Process.AutoEmptyRejectBin"] and t["RJ01.Status.Count"] >= t["RJ01.Parameters.NearFullLevel"]:
            t["RJ01.Status.Count"] = 0
        t["RJ01.Status.NearFull"] = t["RJ01.Status.Count"] >= t["RJ01.Parameters.NearFullLevel"]
        t["RJ01.Status.Full"] = t["RJ01.Status.Count"] >= t["RJ01.Parameters.Capacity"]
        t["C01.Alarms.RejectBinNearFull"] = t["RJ01.Status.NearFull"]
        t["C01.Alarms.RejectBinFull"] = t["RJ01.Status.Full"]
        # robot (4.4)
        if s in (CLEARING, ABORTING, ABORTED):
            in_control = False
        elif s == STOPPED:
            in_control = t["RB01.Status.Homed"] and step != NOT_READY
        else:
            in_control = True
        on_path = step in ON_PATH_STEPS and in_control
        t["RB01.MotionDevices.Arm.ParameterSet.InControl"] = in_control
        t["RB01.MotionDevices.Arm.ParameterSet.OnPath"] = on_path
        t["RB01.Status.CycleStep"] = step
        t["RB01.Status.CycleStepName"] = STEP_NAMES[step]
        t["RB01.Status.AtHome"] = step == WAIT_PART
        t["RB01.Status.PartInGripper"] = self.robot_part is not None
        t["RB01.Status.Destination"] = 0 if self.robot_part is None else (1 if self.robot_part.good else 2)
        t["RB01.Status.VacuumOn"] = step in (GRIP, LIFT, MOVE_TO_PLACE, WAIT_PLACE_CLEAR)
        t["RB01.Status.VacuumLevel"] = round(self.vacuum, 2)
        t["RB01.Status.VacuumOk"] = self.vacuum <= -60.0
        # starved / blocked (5.3)
        if s == EXECUTE:
            starved = (step == WAIT_PART and self._wait_time() > 3.0
                       and not self.cv01 and self._order_needs_parts())
            blocked = step == WAIT_PLACE_CLEAR and self._wait_time() > 3.0
        else:
            starved = blocked = False
        self.starved_t = self.starved_t + dt_s if starved else 0.0
        self.blocked_t = self.blocked_t + dt_s if blocked else 0.0
        t["C01.Status.EquipmentStarved"] = starved
        t["C01.Status.EquipmentBlocked"] = blocked
        # rate (CurMachSpeed)
        recent = self.placements and self.uptime - self.placements[-1] <= 15.0
        if s == EXECUTE and recent and len(self.placements) >= 2:
            interval = (self.placements[-1] - self.placements[0]) / (len(self.placements) - 1)
            t["C01.Status.CurMachSpeed"] = round(60.0 / interval, 2) if interval > 0 else 0.0
        else:
            t["C01.Status.CurMachSpeed"] = 0.0
        # machinery state and mode (5.4)
        mode = t["C01.Status.UnitModeCurrent"]
        reason = t["C01.Admin.StopReason"]
        if s in (STARTING, EXECUTE, UNHOLDING, UNSUSPENDING, COMPLETING):
            item = 3
        else:
            item = 2
        if s in (ABORTING, ABORTED, CLEARING) or (s in (HOLDING, HELD) and reason >= 100) or mode == 2:
            item = 1
        t["C01.Status.MachineryItemState"] = item
        t["C01.Status.MachineryOperationMode"] = {1: 3, 2: 1, 3: 2}[mode]
        self._publish_state()
        # times, heartbeats (7)
        t["C01.Admin.StateCurrentTime"] = round(self.state_time, 1)
        t["C01.Admin.AccTimeSinceReset"] = round(self.uptime, 1)
        self.sec_acc += dt_s
        while self.sec_acc >= 1.0:
            self.sec_acc -= 1.0
            t.inc("C01.Status.Heartbeat")
            t.inc("RB01.Status.Heartbeat")
            t["C01.Status.PacDateTime"] = self.now.replace(microsecond=0)
        # utilities and energy (4.8)
        power = (0.60 + (0.30 if in_control else 0.0) + (0.90 if on_path else 0.0)
                 + (0.18 if running[0] else 0.0) + (0.18 if running[1] else 0.0))
        t["UT01.Status.ActivePower"] = power
        self.energy_wh += power * 1000.0 * dt_s / 3600.0
        t["UT01.Status.EnergyTotal"] = int(self.energy_wh) / 1000.0
        t["UT01.Status.AirPressure"] = 6.20
        t["UT01.Status.AirPressureOk"] = t["UT01.Status.AirPressure"] >= 5.5

    def _wait_time(self) -> float:
        """Time the robot has spent in its current wait step."""
        return self.step_t if self.robot_step in WAIT_STEPS else 0.0
