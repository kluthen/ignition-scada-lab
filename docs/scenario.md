# Cell 01: pick-and-inspect cell (simulated plant)

This document describes the plant the lab simulates. It is written so that the
PLC simulation (`plc/`) can be coded from it without guessing. Every signal named
here exists with the same name in [`opcua-registry.csv`](opcua-registry.csv);
the registry is the reference for types, ranges and addresses.

The finishing area runs five identical cells C01..C05 ([`plant-layout.md`](plant-layout.md));
this document describes one, with the names of C01.

Phase 1 is deterministic and has no faults. Fault behaviour is reserved in
[`fault-catalogue.md`](fault-catalogue.md); its signals already exist in the registry.

## 1. Context

**Brevent Hydraulics SAS** (fictional) is an 85-person subcontractor that
machines aluminium hydraulic valve housings for agricultural machinery makers. In
its finishing area at the Annecy site, **Cell 01** takes machined housings from
the deburring line, reads each part's DataMatrix, gauges its main bore diameter,
and sorts it: good parts go on to packing, out-of-tolerance parts go to a reject bin.

ISA-95 equipment hierarchy:

| Level | Code | Name |
|---|---|---|
| Enterprise | BRV | Brevent Hydraulics |
| Site | ANN | Annecy plant |
| Area | FIN | Finishing |
| Work cell | C01 | Cell 01, housing inspection and sorting |
| Equipment | CV01, QS01, RB01, CV02, RJ01, SF01, UT01, IO01 | see section 2 |

## 2. Equipment list

```
 upstream (deburring)                                         packing
   |  parts released every Sim.Process.FeedInterval              ^
   v                                                             |
 [CV01 infeed conveyor 2000 mm]--> end stop / pick position      |
                                   QS01 camera above it          |
                                        |                        |
                                   RB01 SCARA + vacuum gripper   |
                                    /                  \         |
                        RJ01 reject bin      [CV02 outfeed conveyor 1500 mm]
   SF01 e-stop + guard door around the robot      UT01 air + energy meter
   IO01 remote I/O coupler (Modbus TCP) wires CV01, CV02, RJ01, SF01, UT01
```

| Code | Equipment | Function | Interface to SCADA |
|---|---|---|---|
| C01 | Cell controller (PLC) | PackML state machine, order handling, counters, traceability, alarms | OPC UA, namespace `urn:ignition-lab:cell` |
| QS01 | Smart camera | Reads the part DataMatrix and gauges the bore diameter at the pick position | OPC UA, `urn:ignition-lab:cell` (published by the cell controller) |
| RB01 | 4-axis SCARA robot, vacuum gripper, own controller RC01 | Picks each inspected part and places it on CV02 (good) or in RJ01 (reject) | OPC UA, namespace `urn:ignition-lab:robot` |
| CV01 | Infeed accumulation conveyor, 2000 mm, VFD-driven | Brings parts from upstream to a hard end stop (pick position) | Modbus TCP, device IO01 |
| CV02 | Outfeed conveyor, 1500 mm, VFD-driven | Carries good parts to packing | Modbus TCP, device IO01 |
| RJ01 | Reject bin with level counting | Collects rejects, capacity 50 parts | Modbus TCP, device IO01 |
| SF01 | Safety circuit (e-stop, guard door, safety relay) | Status only; safety is hard-wired | Modbus TCP, device IO01 |
| UT01 | Utilities: compressed air (vacuum ejector supply), cell energy meter | Supply monitoring, energy | Modbus TCP, device IO01 |
| IO01 | Remote I/O coupler | Modbus TCP adapter for the field devices above | Modbus TCP, unit id 1 |

### 2.1 Naming convention

- Equipment code: 2 letters + 2 digits (`RB01`), unique within the cell. The cell itself is `C01`.
- Signal name: `<EquipmentCode>.<Folder>[.<Sub>].<Name>`, PascalCase, ASCII only, for example
  `C01.Status.StateCurrent`, `CV01.Sensors.PartAtPick`. Folders group by role:
  `Identification`, `Status`, `Command`, `Parameters`, `Admin` (counters), `Order`,
  `Traceability`, `Alarms`, `Sensors`. Robot nodes keep the OPC 40010 structure
  (`RB01.SafetyStates.SS01.ParameterSet.EmergencyStop`).
- For OPC UA signals the signal name is the string NodeId identifier (see the registry).
- Simulation-only signals live under `Sim.*` in their own namespace.
- Ignition tag path (recommendation, given per row in the CSV): `[default]ANN/FIN/C01/` + the signal
  name with `.` replaced by `/`, dropping the leading `C01.` for the cell's own nodes
  (`C01.Status.StateCurrent` -> `[default]ANN/FIN/C01/Status/StateCurrent`,
  `RB01.Status.Heartbeat` -> `[default]ANN/FIN/C01/RB01/Status/Heartbeat`). `Sim.*` goes to a
  separate `[sim]` tag provider.

### 2.2 Protocol split

| Side | What | Why |
|---|---|---|
| OPC UA (one server per cell, endpoint `opc.tcp://plc-c01:4840/ignition-lab/` for C01) | C01 cell controller, QS01 results, RB01 robot, Sim interface | Structured, self-describing data with strings and timestamps (order ids, part ids, result records), browsable hierarchy that mirrors the equipment, and the place where companion specifications (Machinery, Robotics, PackML) apply. In a real cell, the PLC (e.g. an S7-1500) and the robot controller would each expose an OPC UA server. |
| Modbus TCP (device IO01, existing server on port 502) | Conveyor drives and photo-eyes, reject bin, safety status, air pressure, energy meter | Plain bits and 16-bit words from field devices that only speak Modbus (VFDs, I/O couplers, energy meters). Keeps the brownfield reality the user will meet at customers, and exercises Ignition's Modbus driver (addressing, scaling, 32-bit word order). |

Both sides are served by the same Python process, so the cell logic reads the Modbus
I/O image directly. Ignition sees two devices: an OPC UA connection and a Modbus TCP device.

## 3. Part types (recipes)

An order names a part type; the cell holds the recipe table below (PackML "Product").
The MES downloads only the part type number.

| PartType | ProductCode | Description | Nominal bore (mm) | Tolerance (mm) | Motion factor | IdealCycleTime (s) | Design speed (parts/min) | Robot program |
|---|---|---|---|---|---|---|---|---|
| 1 | HSG-A20 | Valve housing, 20 mm bore | 20.000 | ±0.050 | 1.0 | 2.4 | 25.00 | PNP_HSG_A20 |
| 2 | HSG-B32 | Valve housing, 32 mm bore | 32.000 | ±0.080 | 1.1 | 2.6 | 23.08 | PNP_HSG_B32 |
| 3 | HSG-C45 | Valve housing, 45 mm bore | 45.000 | ±0.100 | 1.2 | 2.8 | 21.43 | PNP_HSG_C45 |

- `C01.Order.Active.LowerLimit` = nominal - tolerance, `C01.Order.Active.UpperLimit` = nominal + tolerance.
- IdealCycleTime is the robot good-part cycle at 100 % speed override (section 6), so
  `C01.Admin.MachDesignSpeed` = 60 / IdealCycleTime.
- PartType 0 means "none" (no order loaded).

## 4. Process description

### 4.1 Upstream feed (simulated)

Upstream releases one part onto CV01 at the start of a scan when **all** of these hold:

1. `C01.Status.StateCurrent` is Execute (6), Suspending (13), Suspended (5) or Unsuspending (14);
2. `Sim.Process.UpstreamFeedEnable` is true;
3. at least `Sim.Process.FeedInterval` seconds since the previous release (the first release after
   entering Execute is immediate);
4. `CV01.Sensors.EntryOccupied` is false;
5. `C01.Order.Active.GoodCount` + parts in process < `C01.Order.Active.TargetQuantity`, where
   parts in process = `CV01.Status.PartsOnConveyor` + 1 if the robot holds a part going to CV02.
   This rule makes the order finish with exactly TargetQuantity good parts and empty conveyors.

Each released part gets the next serial number *n* and `PartId` = `P` + *n* on 9 digits.
At controller start, *n* is initialised to *k* × 100 000 000 plus the number of seconds
elapsed since 2026-01-01T00:00:00Z, where *k* is the cell number (C03 → 3,
[plant-layout.md](plant-layout.md)). Since a cell finishes fewer than one part per second,
part ids stay unique across restarts and across the five cells without any persistent
storage (until 2029-03, when the seconds reach 10⁸).
Each release increments `C01.Admin.ProdConsumedCount`.

### 4.2 CV01 infeed conveyor

- Length 2000 mm. Parts ride on 100 mm pucks: the pitch between accumulated parts is 100 mm and
  the capacity is 20 parts.
- Position of a part = its front edge *x* in mm from the entry. A released part enters at *x* = 100.
- Each scan, while CV01 runs, parts are processed front to back:
  *x* = min(*x* + *v*·dt, limit). The limit is 2000 (the end stop) for the first part and
  (front of the part ahead - 100) for the others. *v* = `CV01.Status.ActualSpeed`.
- `CV01.Status.ActualSpeed` = `CV01.Parameters.SpeedSetpoint` (default 250 mm/s) when running, else 0. No ramp.
- `CV01.Sensors.PartAtPick` = a part has *x* >= 1999.5. `CV01.Sensors.EntryOccupied` = a part has *x* - 100 < 100.
- `CV01.Status.MotorCurrent` = 1.20 A when running, 0 when stopped.
- Transport time entry to pick: (2000 - 100) / 250 = 7.6 s.
- A part leaves CV01 when the robot finishes the Lift step. The queue then advances 100 mm (0.4 s at 250 mm/s).

### 4.3 QS01 quality station

- On the rising edge of `CV01.Sensors.PartAtPick` the cell waits 0.2 s (settling), then QS01 inspects for 0.4 s
  (`QS01.Status.Busy` true, `QS01.Status.Ready` false). Each part is inspected exactly once.
- At the end of the inspection: `QS01.Status.LastPartId` = PartId, `QS01.Status.LastMeasurement`
  = measured diameter *m*, `QS01.Status.LastResult` = 1 (OK) or 2 (NOK),
  `QS01.Status.InspectionCount` + 1.
- Measured diameter, deterministic, for serial *n* with N = `Sim.Process.RejectEveryN`, nominal and tolerance from the active part type:
  - if N > 0 and *n* mod N = 0: let *k* = *n* div N; *m* = nominal + 1.6 × tolerance if *k* is odd,
    otherwise nominal - 1.6 × tolerance;
  - otherwise *m* = nominal + 0.5 × tolerance × sin(2π·*n*/17);
  - *m* += `Sim.Faults.QualityOffset` (0.0 in phase 1), then round to 0.001 mm.
- The part is good if `C01.Order.Active.LowerLimit` <= *m* <= `C01.Order.Active.UpperLimit`.
  Otherwise it is a reject: DefectCode 1 (undersize) if *m* < LowerLimit, 2 (oversize) if *m* > UpperLimit.
- With N = 25 the reject rate is exactly 4 % of released parts.

### 4.4 RB01 robot

SCARA with a vacuum gripper. The cell controller runs the robot program. In the real cell it
would use the robot's external-automatic interface (`RB01.SafetyStates.SS01.ParameterSet.OperationalMode` = 4, AUTOMATIC_EXTERNAL).

Cycle steps (`RB01.Status.CycleStep`):

| Code | Step | Base duration | Scaled by speed? | Actions / end condition |
|---|---|---|---|---|
| 0 | NotReady | - | - | Servos off (`RB01.MotionDevices.Arm.ParameterSet.InControl` false) |
| 1 | Homing | 2.0 s | no | Resetting only. Ends with `RB01.Status.Homed` and `RB01.Status.AtHome` true |
| 2 | WaitPart | - | - | At the WaitAbovePick point. Leaves only when the cell is in Execute **and** the part at pick has its inspection result |
| 3 | MoveToPick | 0.3 s | yes | Descend onto the part |
| 4 | Grip | 0.2 s | no | `RB01.Status.VacuumOn` true. `RB01.Status.VacuumLevel` ramps linearly 0 -> -75 kPa in 0.15 s. `RB01.Status.VacuumOk` = level <= -60 kPa. At the end, `RB01.Status.PartInGripper` is true and `RB01.Status.Destination` = 1 (good) or 2 (reject) |
| 5 | Lift | 0.3 s | yes | At the end the part leaves CV01 |
| 6 | MoveToPlace | good 0.7 s, reject 0.5 s | yes | Move above CV02 place zone or RJ01 |
| 7 | WaitPlaceClear | - | - | Good parts only: wait while `CV02.Sensors.EntryOccupied` is true (0 s when the zone is free) |
| 8 | Release | 0.2 s | no | `RB01.Status.VacuumOn` false; level returns to 0 in 0.1 s. At the end the part is placed: counting and traceability record (section 4.7) |
| 9 | ReturnToWait | good 0.7 s, reject 0.5 s | yes | Back to WaitAbovePick. At the end, `RB01.Status.CycleCount` + 1 and `RB01.Status.LastCycleTime` is updated, then step 2 |
| 10 | Halted | - | - | Frozen in place (Aborting, Aborted, Clearing); a held part stays in the gripper |

- Motion step duration = base × motion factor (part type) × 100 / `RB01.MotionDevices.Arm.ParameterSet.SpeedOverride`.
- Speed override = clamp(100 × `C01.Status.MachSpeed` / `C01.Admin.MachDesignSpeed`, 10, 100). Gripper times do not scale,
  so the real rate at reduced speed is a little higher than MachSpeed (accepted simplification).
- Good-part cycle at 100 %: 0.3 + 0.2 + 0.3 + 0.7 + 0.2 + 0.7 = **2.4 s** (factor 1.0). Reject cycle: 2.0 s.
- `RB01.MotionDevices.Arm.ParameterSet.OnPath` is true during steps 1, 3, 5, 6 and 9.
- `RB01.Status.AtHome` is true in step 2 only. `RB01.Status.Heartbeat` increments every second.
- Step timers carry their overshoot into the next step (a step ending 40 ms into a scan gives
  those 40 ms to the next step), so mean cycle times match this table within 1 % despite the 100 ms scan.
- Steps 3 to 9 always run to the end once started, except on Abort (step 10). The robot reaches a
  *wait step* when it is in step 2 or step 7. Holding, Stopping, Suspending and Completing wait for it.

Robot state against cell state:

| Cell state | `RB01.MotionDevices.Arm.ParameterSet.InControl` | Robot behaviour |
|---|---|---|
| Stopped | = `RB01.Status.Homed` (false at controller start and after an abort, true after a normal stop) | No motion. Step 0 if not homed, else its wait step |
| Clearing | false | Step 10, then step 0 on reaching Stopped |
| Resetting | true | Homing (step 1). If a part is in the gripper, it is first put in RJ01 (extra 1.0 s) and recorded as Scrapped / Purged |
| Idle, Complete, Held, Suspended | true | Stays in its wait step |
| Starting, Unholding, Unsuspending | true | Stays in its wait step |
| Execute | true | Cycles |
| Holding, Stopping, Suspending, Completing | true | Finishes the current cycle up to a wait step, starts no new pick |
| Aborting, Aborted | false | Step 10. `RB01.Status.Homed` false |

Taught points, used for axis animation in phase 2 (`RB01.MotionDevices.Arm.Axes.J1.ParameterSet.ActualPosition` to J4; linear interpolation over the motion step):

| Point | J1 (deg) | J2 (deg) | J3 (mm) | J4 (deg) |
|---|---|---|---|---|
| WaitAbovePick (home) | 0 | 30 | 20 | 0 |
| Pick | 0 | 30 | 120 | 0 |
| AbovePlaceGood / PlaceGood | 75 / 75 | -40 / -40 | 20 / 110 | 90 / 90 |
| AbovePlaceReject / PlaceReject | -60 / -60 | 50 / 50 | 20 / 80 | 0 / 0 |

MoveToPick goes WaitAbovePick -> Pick, Lift goes Pick -> WaitAbovePick, MoveToPlace goes to the
place point through its "above" point, and ReturnToWait goes to WaitAbovePick. During Release the
arm sits at the place point.

### 4.5 CV02 outfeed conveyor

- Length 1500 mm, 100 mm pitch, capacity 15. A placed part has its rear at 0 (front *x* = 100).
- Same motion rule as CV01, with limit 1500 for the first part. When a part's front reaches 1500 it
  leaves to packing, unless `Sim.Faults.DownstreamBlocked` is true (phase 2), in which case it stays and the others accumulate behind it.
- `CV02.Sensors.EntryOccupied` = a part has rear edge < 150 mm (front < 250). It clears 0.6 s after placing at 250 mm/s.
- `CV02.Sensors.ExitPE` = a part has front in [1400, 1500]. `CV02.Status.MotorCurrent` = 1.10 A running.
- Travel to exit: (1500 - 100) / 250 = 5.6 s.

### 4.6 RJ01 reject bin

- Every Release into the bin (reject cycle, or purge during Resetting) increments `RJ01.Status.Count`.
- `RJ01.Status.NearFull` = Count >= `RJ01.Parameters.NearFullLevel` (40). `RJ01.Status.Full` = Count >= `RJ01.Parameters.Capacity` (50).
- When `RJ01.Status.Full` becomes true in Execute, the cell holds (StopReason 20). The current
  cycle still finishes, so Count can reach Capacity + 1 (the bin has room for it).
- The operator empties the bin and confirms with `RJ01.Command.BinEmptied` (HMI pulse): Count = 0.
  Unhold is then accepted.
- If `Sim.Process.AutoEmptyRejectBin` is true, Count is reset to 0 as soon as it reaches NearFullLevel (no holds).
- Alarm bits: `C01.Alarms.RejectBinNearFull` = `RJ01.Status.NearFull`, `C01.Alarms.RejectBinFull` = `RJ01.Status.Full`.

### 4.7 Counting and traceability

When a part is finished (Release done, or purged), the cell:

1. increments `C01.Admin.ProdProcessedCount`; also `C01.Admin.ProdDefectiveCount` if not good;
2. increments `C01.Order.Active.GoodCount` or `C01.Order.Active.RejectCount` if the part belongs to the active order,
   and updates `C01.Order.Active.RemainingQuantity`;
3. appends a record {Sequence, PartId, OrderId, PartType, MeasuredDiameter, Result, DefectCode, Timestamp}
   to a FIFO of 200 records. If the FIFO is full, the oldest record is dropped and `C01.Traceability.LostCount` + 1.

Results: 1 Good (placed on CV02), 2 Reject (inspected NOK, placed in RJ01), 3 Scrapped (never
placed: purged, or dropped in phase 2; MeasuredDiameter 0.0 if it was not inspected yet).

Handshake with the MES (the classic PLC/MES data handshake, made for an Ignition transaction group):

1. If `C01.Traceability.DataReady` is false and the FIFO is not empty, the PLC writes the oldest
   record into `C01.Traceability.Sequence` ... `C01.Traceability.Timestamp`, and sets
   `C01.Traceability.DataReady` true one scan later.
2. The MES stores the record and writes its Sequence into `C01.Traceability.AckSequence`.
3. When `C01.Traceability.AckSequence` = `C01.Traceability.Sequence`, the PLC removes the record,
   sets DataReady false, and goes back to step 1 on the next scan.

At 24 parts/min the 200-record buffer covers about 8 minutes of MES or network outage.
`C01.Traceability.BufferCount` shows the backlog. Production never waits for the MES.

### 4.8 Utilities and energy

- `UT01.Status.AirPressure` = 6.20 bar constant in phase 1. `UT01.Status.AirPressureOk` = pressure >= 5.5 bar.
- `UT01.Status.ActivePower` (kW) = 0.60 (controller, camera, I/O)
  + 0.30 if `RB01.MotionDevices.Arm.ParameterSet.InControl`
  + 0.90 if `RB01.MotionDevices.Arm.ParameterSet.OnPath`
  + 0.18 if `CV01.Status.Running` + 0.18 if `CV02.Status.Running`.
- `UT01.Status.EnergyTotal` integrates ActivePower every scan (UInt32 in Wh, two registers, high word first). Expect about 2.0 kW in Execute.

### 4.9 Safety (status only)

`SF01.Status.EStopOk`, `SF01.Status.GuardDoorClosed` and `SF01.Status.SafetyOk` are true in phase 1.
Their behaviour (driven by `Sim.Panel.*`) is phase 2, see the fault catalogue. Safety functions are
hard-wired in a real cell. SCADA only reads them, and no SCADA write can reset safety.

## 5. Cell state model (PackML)

The cell implements the ISA-TR88.00.02 / PackML base state model (17 states). State numbers
follow PackTags `StateCurrent`, which match the OPC 30050 state numbers 1-17. Commands use the
PackTags `CntrlCmd` codes. They are written to a variable, not called as OPC UA methods (section 5.6).

### 5.1 States

| # | State | Type | Duration / completion condition (SC) | Conveyors | Robot |
|---|---|---|---|---|---|
| 0 | Undefined | - | Never used (reserved) | - | - |
| 1 | Clearing | acting | 1.0 s -> Stopped | off | halted |
| 2 | Stopped | wait | Initial state at controller start | off | no motion |
| 3 | Starting | acting | 1.0 s -> Execute | on | waits |
| 4 | Idle | wait | | off | waits |
| 5 | Suspended | wait | Auto Unsuspend, see 5.3 | on | waits |
| 6 | Execute | dual | Production; internal transitions in 5.3 | on | cycles |
| 7 | Stopping | acting | Robot at a wait step -> Stopped | on | finishes cycle |
| 8 | Aborting | acting | 0.5 s -> Aborted | off immediately | halted immediately |
| 9 | Aborted | wait | | off | halted |
| 10 | Holding | acting | Robot at a wait step -> Held | on | finishes cycle |
| 11 | Held | wait | | off | waits |
| 12 | Unholding | acting | 1.0 s -> Execute | on | waits |
| 13 | Suspending | acting | 0.5 s and robot at a wait step -> Suspended | on | finishes cycle |
| 14 | Unsuspending | acting | 1.0 s -> Execute | on | waits |
| 15 | Resetting | acting | Robot homed (2.0 s, +1.0 s purge) -> Idle | off | homing |
| 16 | Completing | acting | Robot at step 2 **and** `CV02.Status.PartsOnConveyor` = 0 -> Complete | on | finishes cycle |
| 17 | Complete | wait | | off | waits |

"Conveyors on" means `CV01.Status.Running` and `CV02.Status.Running` true. In Maintenance mode, in
Stopped or Idle, a conveyor also runs while its jog coil (`CV01.Command.JogForward`,
`CV02.Command.JogForward`) is true. `C01.Status.StateCurrentName` holds the state name exactly as written in this table.

### 5.2 Commands (`C01.Command.CntrlCmd`)

| Code | Command | Accepted in | Target | Interlocks (else CmdResult 3) |
|---|---|---|---|---|
| 1 | Reset | Stopped, Complete | Resetting | `SF01.Status.SafetyOk` |
| 2 | Start | Idle | Starting | mode Production; OrderStatus 1 or 2; RemainingQuantity > 0; `SF01.Status.SafetyOk`; `RB01.Status.Homed`; not `RJ01.Status.Full` |
| 3 | Stop | all except Stopped, Stopping, Aborting, Aborted, Clearing | Stopping | - |
| 4 | Hold | Execute | Holding | - |
| 5 | Unhold | Held | Unholding | hold cause cleared (StopReason 20: not `RJ01.Status.Full`; fault causes: phase 2) |
| 6 | Suspend | Execute | Suspending | - |
| 7 | Unsuspend | Suspended | Unsuspending | only if StopReason is 5 (operator suspend); automatic suspensions resume by themselves |
| 8 | Abort | all except Aborting, Aborted | Aborting | - |
| 9 | Clear | Aborted | Clearing | `SF01.Status.SafetyOk` (phase 2 adds: robot heartbeat alive) |

Command handshake, evaluated at the start of each scan:

1. HMI/MES writes a non-zero value to `C01.Command.CntrlCmd`.
2. The PLC sets `C01.Command.CmdResult`: 1 Accepted, 2 RejectedInvalidState (not accepted in the
   current state), 3 RejectedInterlock, 4 RejectedInvalidValue (code outside 1-9). It then
   increments `C01.Command.CmdCounter` and writes `C01.Command.CntrlCmd` back to 0. All of this happens within one scan.
3. `C01.Command.UnitModeRequest` follows the same rules: 1 Production or 2 Maintenance, accepted in
   Stopped, Idle, Complete or Aborted (else 2); value 3 (Manual) or anything else gives 4. The state does not change on a mode change.

### 5.3 Internal transitions (no command)

| From | Trigger | To | `C01.Admin.StopReason` |
|---|---|---|---|
| Execute | Release of a good part makes `C01.Order.Active.GoodCount` >= TargetQuantity | Completing | 3 Order complete |
| Execute | `RJ01.Status.Full` | Holding | 20 Reject bin full |
| Execute | `C01.Status.EquipmentStarved` true for 10.0 s without interruption | Suspending | 10 Starved |
| Execute | `C01.Status.EquipmentBlocked` true for 10.0 s without interruption | Suspending | 11 Blocked |
| Suspended | StopReason 10 and `CV01.Status.PartsOnConveyor` > 0 | Unsuspending | (kept) |
| Suspended | StopReason 11 and `CV02.Sensors.EntryOccupied` false | Unsuspending | (kept) |
| any but Aborting/Aborted | safety or robot fault (phase 2, fault catalogue) | Aborting | 101 / 103 / 160 |
| Execute | process fault (phase 2, fault catalogue) | Holding | 110-150 |

- `C01.Status.EquipmentStarved` = robot in step 2 for > 3.0 s **and** `CV01.Status.PartsOnConveyor` = 0
  **and** the order still needs parts (rule 5 of 4.1). It is only evaluated in Execute, else false.
- `C01.Status.EquipmentBlocked` = robot in step 7 for > 3.0 s. Only evaluated in Execute, else false.
- When a command triggers Stopping, Holding, Suspending or Aborting, StopReason is set to 1, 2, 5
  or 4. StopReason is set on entering one of these states or Completing, keeps its value after that,
  and returns to 0 when Execute is entered. `C01.Admin.StopReasonText` holds the English text from the enumeration table in the registry.
- Phase 1 can reach every state except the fault-driven paths. Aborted is reachable only with the Abort command.

### 5.4 Unit modes and Machinery state

| `C01.Status.UnitModeCurrent` | Meaning | `C01.Status.MachineryOperationMode` |
|---|---|---|
| 1 Production | Normal running | 3 Processing |
| 2 Maintenance | Start refused, conveyor jog allowed in Stopped/Idle. The MES counts this time as planned maintenance | 1 Maintenance |
| 3 Manual | Reserved, refused in phase 1 | (2 Setup) |

`C01.Status.MachineryItemState` (OPC 40001-1):

| Value | When |
|---|---|
| 3 Executing | Starting, Execute, Unholding, Unsuspending, Completing |
| 1 OutOfService | Aborting, Aborted, Clearing; Holding or Held with StopReason >= 100; any state in Maintenance mode |
| 2 NotExecuting | every other case (Stopped, Resetting, Idle, Stopping, Holding/Held with StopReason < 100, Suspending, Suspended, Complete) |
| 0 NotAvailable | never written by the server; Ignition derives it from a bad connection |

### 5.5 Orders: how work enters the cell

The MES (Ignition) holds the order list. Dispatching an order to C01 works as follows:

1. The MES writes `C01.Order.Request.OrderId`, `C01.Order.Request.PartType` and `C01.Order.Request.TargetQuantity`, then sets `C01.Order.Request.LoadRequest` true.
2. On the rising edge the PLC checks, in this order, and writes `C01.Order.Request.LoadResult`:
   - state not Stopped, Idle or Complete -> 2 RejectedBusy;
   - OrderId empty, longer than 32 characters or not printable ASCII -> 3 RejectedInvalidOrderId;
   - PartType not 1-3 -> 4 RejectedInvalidPartType;
   - TargetQuantity 0 or > 100000 -> 5 RejectedInvalidQuantity;
   - otherwise 1 Accepted.
3. The PLC resets `C01.Order.Request.LoadRequest` to false in the same scan.
4. On acceptance:
   - parts still on CV01 or in the gripper are purged: each produces a Scrapped / DefectCode 6
     record for the previous order, and CV01 is emptied;
   - `C01.Order.Active.*` is filled from the request and the recipe table;
   - GoodCount = RejectCount = 0, `C01.Order.Active.OrderStatus` = 1 Loaded, StartTime and EndTime are cleared;
   - `RB01.Controllers.RC01.TaskControls.Main.ParameterSet.TaskProgramName` is set and `RB01.Controllers.RC01.TaskControls.Main.ParameterSet.TaskProgramLoaded` becomes true;
   - `C01.Admin.MachDesignSpeed` is updated.
   A load never changes the PackML state.
5. On the first entry into Execute: OrderStatus = 2 InProgress, `C01.Order.Active.StartTime` = now.
   On entering Complete: OrderStatus = 3 Complete, `C01.Order.Active.EndTime` = now.
6. A Stopped or Held order stays loaded and resumes with Reset/Start or Unhold. Closing an order
   short (before its target) is an MES decision: the MES simply loads the next order.

### 5.6 Divergences from PackML (deliberate)

- Commands are variables (`CntrlCmd` and a PLC-side reset, as in PackTags) instead of the OPC 30050
  methods (Start, Stop, ...). Ignition tags bind naturally to variables; methods can be added later as an exercise.
- No `CmdChangeRequest` bit: writing a non-zero `CntrlCmd` is the request.
- StopReason, counters and Product are scalars instead of the PackML structured data types
  (PackMLAlarmDataType, PackMLCountDataType arrays).
- Unit modes are limited to 1-3, and Manual is not implemented.

## 6. Normal operating sequence (phase 1)

1. Controller start: state Stopped, mode Production, no order, robot not homed, conveyors empty,
   all counters 0, `C01.Admin.StartUpTime` = now.
2. Operator: Reset (CntrlCmd 1). Resetting lasts 2.0 s (homing), then Idle.
3. MES: load order, for example `OF-2026-0042`, PartType 1, 500 parts. LoadResult 1, OrderStatus 1.
4. Operator: Start (CntrlCmd 2). Starting lasts 1.0 s (conveyors start), then Execute. Upstream releases the first part immediately.
5. The first part reaches the pick position after 7.6 s and its result is ready 0.6 s later (8.2 s). The first placement (end of Release) happens 1.7 s after that, about 9.9 s after entering Execute.
6. Steady state, PartType 1, FeedInterval 2.5 s: one part every 2.5 s (24.0 parts/min, feed-limited;
   the robot could do 25.0). `C01.Status.CurMachSpeed` reads 24.0. One part in 25 is rejected.
7. Every 1250 parts (about 52 min) RJ01 is full: the cell holds (StopReason 20). The operator empties the
   bin, confirms (`RJ01.Command.BinEmptied`), and sends Unhold (CntrlCmd 5).
8. When GoodCount reaches 500: Completing, which waits for CV02 to empty (≤ 5.6 s), then Complete.
   OrderStatus 3, EndTime set.
9. Operator: Reset, then Idle. The MES loads the next order.

Expected rates (FeedInterval 2.5 s, RejectEveryN 25, CV01/CV02 at 250 mm/s, override 100 %):

| PartType | Robot cycle | Bottleneck | Actual rate (parts/min) | Performance vs ideal | Good parts/hour |
|---|---|---|---|---|---|
| 1 | 2.4 s | feed (2.5 s) | 24.00 | 96.0 % | 1382 |
| 2 | 2.6 s (reject 2.16 s) | robot | 23.24 | 100.7 % | 1339 |
| 3 | 2.8 s (reject 2.32 s) | robot | 21.57 | 100.7 % | 1243 |

When the robot is the bottleneck, the 4 % of reject cycles are shorter than the ideal (good) cycle,
so performance computed with IdealCycleTime comes out slightly above 100 %. This is expected; the
MES must not clamp it silently (it may display it capped at 100 % with the raw value stored).

With PartTypes 2 and 3 the infeed slowly fills up (20 parts after about 26 min for PartType 2, 8 min
for PartType 3). The upstream release then waits for `CV01.Sensors.EntryOccupied` to clear. That is normal. A 500-part order of PartType 1
takes about 22 min including the start and completion tails. A shift of 450 planned minutes of
PartType 1, with 8 bin holds of 3 min each, gives roughly A 94.7 % × P 96 % × Q 96 % ≈ OEE 87 %.

## 7. Timing, scan and restart rules

- PLC scan: 100 ms (`PLC_SCAN_MS`). The model advances by the measured dt. Commands and handshakes are processed at the start of the scan.
- 1 Hz values: `C01.Status.Heartbeat`, `RB01.Status.Heartbeat`, `C01.Status.PacDateTime`.
  `IO01.Status.Heartbeat` counts scans (+1 every 100 ms).
- All timestamps are UTC. The HMI converts them to local time (Europe/Paris).
- Recommended Ignition subscription: 250 ms sampling for C01/RB01/QS01, 1000 ms for Identification and Admin; Modbus poll 500 ms.
- Restart: nothing is persisted. The controller comes back in Stopped with all counters at 0 and a new
  `C01.Admin.StartUpTime`. The MES must treat a change of StartUpTime as a counter reset.
  Part serials stay unique (section 4.1).

## 8. Sources

- OPC 30050 PackML (OPC UA companion for ISA-TR88): PackMLBaseObjectType, Status/Admin components, state numbers (Annex B). https://reference.opcfoundation.org/specs/OPC-30050/full
- ISA-TR88.00.02 PackTags `CntrlCmd` codes (0 Undefined, 1 Reset ... 9 Clear) as implemented by vendors:
  SEW-EURODRIVE https://download.sew-eurodrive.com/download/html/26884623/en-EN/35730789387.html,
  Schneider Electric PackMLLb https://product-help.schneider-electric.com/Machine%20Expert/V1.1/en/PackMLli/PackMLli/PackMLLb_Enumerations/PackMLLb_Enumerations-2.htm,
  Beckhoff Tc3_PackML https://infosys.beckhoff.com/content/1033/tcplclib_tc3_packml/1075806475.html
- OPC 40001-1 Machinery: Identification, MachineryItemState (0 NotAvailable, 1 OutOfService, 2 NotExecuting, 3 Executing), MachineryOperationMode (0 None, 1 Maintenance, 2 Setup, 3 Processing). https://reference.opcfoundation.org/specs/OPC-40001-1/full
- OPC 40010-1 Robotics: MotionDeviceSystemType, ParameterSet (SpeedOverride, OnPath, InControl), SafetyStateType, TaskControlType, OperationalModeEnumeration. https://reference.opcfoundation.org/specs/OPC-40010-1/full
