# Fault catalogue: Cell 01

Faults are **not implemented in phase 1**. Their nodes exist from phase 1 (registry
`phase` = 2), so Ignition tags, alarms and screens can be built before the behaviour exists.
Every signal named here is in [`opcua-registry.csv`](opcua-registry.csv). The state model is in
[`scenario.md`](scenario.md) section 5.

## 1. General rules

**Injection interface.** All injections go through the simulation-only OPC UA namespace
`urn:ignition-lab:sim`:

- `Sim.Panel.*`: simulated hard-wired operator panel (e-stop, safety reset, guard door). In a real plant these are physical devices, never SCADA writes.
- `Sim.Faults.*`: fault injection. Three kinds of node:
  - *latched* Booleans: active while true;
  - *one-shot* Booleans: the sim writes them back to false once triggered;
  - *count* UInt16: the next N events fail, decremented by the sim.
- `Sim.Faults.ClearAll`: pulse that returns every `Sim.Faults` and `Sim.Panel` node to its initial value. It does not reset the cell; the operator procedure still applies.
- Communication outages are timed (`Sim.Faults.ModbusOutage`, `Sim.Faults.OpcUaOutage`, in seconds), so they end without needing the channel they cut.

The Sim namespace must be kept out of the production tag provider: use a separate `[sim]` provider and an instructor screen.

**Reactions.** Each fault is handled one of three ways:

- *Abort* (safety, loss of control): any state except Aborting/Aborted -> Aborting. Conveyors and robot stop immediately; a part may stay in the gripper.
- *Hold* (process fault needing an operator): Execute -> Holding. The robot finishes its cycle up to a wait step, then the cell is Held. A process fault detected in any state other than Execute only sets its alarm bit; it does not change the state.
- *Warning*: alarm only, no state change.

**Alarm bits** (`C01.Alarms.*`):

- Hold-fault bits latch until Unhold is accepted, or until Resetting.
- Abort-fault bits latch until Clear is accepted.
- Warning bits follow their condition.

`C01.Admin.StopReason` is set as listed below (first-out: a second fault while already Holding/Aborting does not overwrite it).

**Unhold / Clear interlocks.** If the cause is measurable (drive fault, air pressure, safety, heartbeat), Unhold or Clear is refused with CmdResult 3 while the cause is present. If the cause is an event (dropped part, failed pick, jam, stuck sensor, camera), Unhold is accepted and the detection re-arms. If the cause was not really removed, the fault trips again.

**Ignition alarm priorities.** Ignition offers Diagnostic, Low, Medium, High, Critical. They are used as follows:

- Critical: personnel safety.
- High: loss of control or loss of supervision.
- Medium: production stopped, operator action needed.
- Low: production degraded or a warning.
- Diagnostic: information.

Acknowledgement is manual (operator, in the alarm status table). Acknowledging never resets the machine; the PackML command does.

**MES impact.** Every Hold/Abort/Suspend opens a downtime event. Its automatic reason is the StopReason, which the MES maps to a reason code (mes-requirements.md, MES-DT-02).

## 2. Summary

| Id | Fault | Equipment | Injection | Detection (registry signals) | Reaction | StopReason | Alarm (priority) |
|---|---|---|---|---|---|---|---|
| F01 | Emergency stop | SF01, all | `Sim.Panel.EStopPressed` | `SF01.Status.EStopOk` false | Abort | 101 | `C01.Alarms.EStopActive` (Critical) |
| F02 | Guard door opened | SF01, RB01 | `Sim.Panel.GuardDoorOpen` | `SF01.Status.GuardDoorClosed` false, `RB01.SafetyStates.SS01.ParameterSet.ProtectiveStop` | Abort | 103 | `C01.Alarms.GuardDoorOpen` (High) |
| F03 | Vacuum loss in transfer (part dropped) | RB01 | `Sim.Faults.VacuumLossNext` | `RB01.Status.VacuumOk` false in step 6/7 | Hold | 110 | `C01.Alarms.VacuumLoss` (Medium) |
| F04 | Pick failed (part missing / not gripped) | RB01, CV01 | `Sim.Faults.PickFailCount` | `RB01.Status.VacuumOk` false at end of Grip, twice | Hold | 111 | `C01.Alarms.PickFailed` (Medium) |
| F05 | Infeed jam | CV01 | `Sim.Faults.InfeedJam` | `CV01.Sensors.PartAtPick` not reached in time, `CV01.Status.MotorCurrent` 2.60 A | Hold | 120 | `C01.Alarms.InfeedJam` (Medium) |
| F06 | Conveyor drive trip | CV01 / CV02 | `Sim.Faults.InfeedDriveTrip`, `Sim.Faults.OutfeedDriveTrip` | `CV01.Status.DriveFault` / `CV02.Status.DriveFault`, `CV01.Status.DriveFaultCode` / `CV02.Status.DriveFaultCode` | Hold | 121 / 122 | `C01.Alarms.InfeedDriveFault` / `C01.Alarms.OutfeedDriveFault` (Medium) |
| F07 | Part-at-pick sensor stuck on | CV01 | `Sim.Faults.PartSensorStuckOn` | `CV01.Sensors.PartAtPick` never drops after a pick | Hold | 140 | `C01.Alarms.PartSensorStuck` (Medium) |
| F08 | Camera gives no result | QS01 | `Sim.Faults.CameraNoResult` | `QS01.Status.CameraOk` false, `QS01.Status.LastResult` = 3 | Hold | 130 | `C01.Alarms.QualityNoResult` (Medium) |
| F09 | DataMatrix unreadable | QS01 | `Sim.Faults.IdUnreadableCount` | `QS01.Status.LastPartId` empty, `C01.Traceability.DefectCode` = 4 | Reject part; Hold after 3 in a row | 131 | `C01.Alarms.PartIdUnreadable` (Medium) |
| F10 | Quality drift | QS01 (upstream process) | `Sim.Faults.QualityDriftRate`, `Sim.Faults.QualityOffset` | `QS01.Status.LastMeasurement` trend, `C01.Alarms.RejectRateHigh` | Warning | - | `C01.Alarms.RejectRateHigh` (Low) |
| F11 | Low compressed air | UT01, RB01 | `Sim.Faults.AirPressureLow` | `UT01.Status.AirPressure` < 5.5 bar, `UT01.Status.AirPressureOk` false | Hold | 150 | `C01.Alarms.AirPressureLow` (High) |
| F12 | Robot communication fault | RB01 | `Sim.Faults.RobotHeartbeatFreeze` | `RB01.Status.Heartbeat` unchanged > 2.5 s | Abort | 160 | `C01.Alarms.RobotCommFault` (High) |
| F13 | Downstream blocked | CV02 | `Sim.Faults.DownstreamBlocked` | `CV02.Sensors.ExitPE` stays on, `CV02.Status.PartsOnConveyor` = 15, `C01.Status.EquipmentBlocked` | Suspend (automatic resume) | 11 | Ignition alarm on `C01.Status.EquipmentBlocked` (Low) |
| F14 | SCADA communication loss | IO01 / OPC UA server | `Sim.Faults.ModbusOutage`, `Sim.Faults.OpcUaOutage` | Ignition tag quality bad, `C01.Status.Heartbeat` / `IO01.Status.Heartbeat` stale | None in the cell | - | Ignition expression-tag alarm (High) |

Phase-1 operational alarms, for completeness (not faults):

- `C01.Alarms.RejectBinNearFull`: Low.
- `C01.Alarms.RejectBinFull`: Medium (Hold, StopReason 20).
- `C01.Status.EquipmentStarved`: Diagnostic. Suspend after 10 s, StopReason 10.

## 3. Fault details

### F01 Emergency stop

- **Injection:** `Sim.Panel.EStopPressed` = true (latched mushroom button).
- **Sim effect:** `SF01.Status.EStopOk` and `SF01.Status.SafetyOk` false; `RB01.SafetyStates.SS01.ParameterSet.EmergencyStop` true.
- **Detection:** falling edge of `SF01.Status.EStopOk`, in any state.
- **State machine:** Aborting (StopReason 101) -> Aborted. Conveyors stop at once. The robot halts (step 10) and `RB01.Status.Homed` goes false. A part in the gripper stays there.
- **Reset:**
  1. Release the button: `Sim.Panel.EStopPressed` = false.
  2. Press `Sim.Panel.SafetyResetButton`: `SF01.Status.SafetyOk` true, EmergencyStop false.
  3. Clear (CntrlCmd 9; refused while SafetyOk is false), then Stopped.
  4. Reset: homing, plus purge of the gripper part to RJ01 (Scrapped, DefectCode 6), then Idle. Then Start.
- **Alarm:** `C01.Alarms.EStopActive`, Critical, latched until Clear.

### F02 Guard door opened

- **Injection:** `Sim.Panel.GuardDoorOpen` = true.
- **Sim effect:** `SF01.Status.GuardDoorClosed` and `SF01.Status.SafetyOk` false; `RB01.SafetyStates.SS01.ParameterSet.ProtectiveStop` true.
- **Detection:** door opens while `RB01.MotionDevices.Arm.ParameterSet.InControl` is true -> abort. If the robot is not in control (Stopped not homed, Aborted), there is no state change, but Reset/Clear are refused while the door is open.
- **State machine:** Aborting (103) -> Aborted.
- **Reset:**
  1. Close the door: `Sim.Panel.GuardDoorOpen` = false.
  2. Press `Sim.Panel.SafetyResetButton`.
  3. Clear, then Reset, then Start (same as F01).
- **Alarm:** `C01.Alarms.GuardDoorOpen`, High, latched until Clear.

### F03 Vacuum loss in transfer

- **Injection:** `Sim.Faults.VacuumLossNext` = true (one-shot).
- **Sim effect:** halfway through the next MoveToPlace, `RB01.Status.VacuumLevel` returns to 0 within 0.1 s. `RB01.Status.VacuumOk` and `RB01.Status.PartInGripper` go false: the part is dropped inside the guarding.
- **Detection:** VacuumOk false while the robot is in step 6 or 7 with a part.
- **State machine:**
  - The part is recorded Result 3 Scrapped, DefectCode 5 Dropped. It counts in ProdDefectiveCount and the order RejectCount, and upstream releases a replacement.
  - The robot finishes the move, skips Release and returns to step 2.
  - Execute -> Holding (110) -> Held.
- **Reset:** the operator removes the dropped part (implicit), then Unhold.
- **Alarm:** `C01.Alarms.VacuumLoss`, Medium.

### F04 Pick failed

- **Injection:** `Sim.Faults.PickFailCount` = N (N attempts fail).
- **Sim effect:** during Grip, the vacuum only reaches -20 kPa, so `RB01.Status.VacuumOk` stays false. PickFailCount - 1.
- **Detection:** VacuumOk false at the end of step 4.
- **State machine:**
  - First failure: automatic retry. Lift (no part), MoveToPick, Grip again. This adds 0.8 s.
  - Second consecutive failure: the robot lifts and returns to step 2 with the part still on CV01. Execute -> Holding (111) -> Held.
- **Reset:** Unhold. The robot tries again; with PickFailCount still > 0 it fails again.
- **Alarm:** `C01.Alarms.PickFailed`, Medium.

### F05 Infeed jam

- **Injection:** `Sim.Faults.InfeedJam` = true (latched).
- **Sim effect:** CV01 parts stop moving although `CV01.Status.Running` is true. `CV01.Status.MotorCurrent` = 2.60 A.
- **Detection:** CV01 running, `CV01.Status.PartsOnConveyor` > 0 and `CV01.Sensors.PartAtPick` false, all continuously for 1900 / `CV01.Status.ActualSpeed` + 5.0 s (12.6 s at 250 mm/s). The timer restarts whenever any condition drops.
- **State machine:** Execute -> Holding (120) -> Held.
- **Reset:** clear the jam (`Sim.Faults.InfeedJam` = false), then Unhold. If still jammed, it trips again 12.6 s later.
- **Alarm:** `C01.Alarms.InfeedJam`, Medium. Ignition can also show the motor current trend.

### F06 Conveyor drive trip

- **Injection:** `Sim.Faults.InfeedDriveTrip` or `Sim.Faults.OutfeedDriveTrip` = true (one-shot).
- **Sim effect:**
  - `CV01.Status.DriveFault` (or `CV02.Status.DriveFault`) true and `CV01.Status.DriveFaultCode` (or `CV02.Status.DriveFaultCode`) = 1 Overcurrent.
  - The belt stops: Running false, ActualSpeed and MotorCurrent 0.
- **Detection:** rising edge of the DriveFault bit.
- **State machine:** Execute -> Holding (121 or 122) -> Held. With CV02 stopped, the robot may finish in step 7 (WaitPlaceClear), which counts as a wait step.
- **Reset:**
  1. Pulse `CV01.Command.DriveReset` or `CV02.Command.DriveReset` from the HMI (a Modbus coil). The fault bit and code clear.
  2. Unhold, which is refused while a DriveFault is present.
- **Alarm:** `C01.Alarms.InfeedDriveFault` / `C01.Alarms.OutfeedDriveFault`, Medium.

### F07 Part-at-pick sensor stuck on

- **Injection:** `Sim.Faults.PartSensorStuckOn` = true (latched).
- **Sim effect:** `CV01.Sensors.PartAtPick` reads true whatever is physically there. No rising edge means no new inspection.
- **Detection:** after the end of Lift, PartAtPick does not go false for at least one scan within 1.0 s. Normally the gap lasts at least 0.25 s at the maximum belt speed.
- **State machine:** Execute -> Holding (140) -> Held.
- **Reset:** fix the sensor (`Sim.Faults.PartSensorStuckOn` = false), then Unhold. The PLC treats the next rising edge normally.
- **Alarm:** `C01.Alarms.PartSensorStuck`, Medium.

### F08 Camera gives no result

- **Injection:** `Sim.Faults.CameraNoResult` = true (latched).
- **Sim effect:** `QS01.Status.CameraOk` and `QS01.Status.Ready` false. An inspection never completes (`QS01.Status.Busy` stays true).
- **Detection:** no result 2.0 s after the trigger. `QS01.Status.LastResult` = 3 NoResult.
- **State machine:** Execute -> Holding (130) -> Held. The part stays at the pick position, not inspected.
- **Reset:** `Sim.Faults.CameraNoResult` = false, then Unhold. The cell re-triggers the inspection of the waiting part.
- **Alarm:** `C01.Alarms.QualityNoResult`, Medium.

### F09 DataMatrix unreadable

- **Injection:** `Sim.Faults.IdUnreadableCount` = N.
- **Sim effect:** the next N inspections return an empty `QS01.Status.LastPartId`. The measurement is still made.
- **Detection and reaction:**
  - Each unreadable part is rejected: Result 2, DefectCode 4, `C01.Traceability.PartId` = `NOREAD`. The MES keys such records on (`C01.Admin.StartUpTime`, `C01.Traceability.Sequence`).
  - Three consecutive unreadable parts: Execute -> Holding (131) -> Held, and the alarm is raised.
- **Reset:** clean the camera window (implicit), then Unhold. The consecutive counter resets on Unhold.
- **Alarm:** `C01.Alarms.PartIdUnreadable`, Medium.

### F10 Quality drift

- **Injection:** `Sim.Faults.QualityDriftRate` in mm per 100 parts. Example: 0.02 drifts PartType 1 out of tolerance after a few hundred parts.
- **Sim effect:** each inspection adds rate / 100 to `Sim.Faults.QualityOffset`, which biases every measurement (scenario.md 4.3).
- **Detection:**
  - Trend of `QS01.Status.LastMeasurement` in the historian; the measured values also sit in the traceability table.
  - `C01.Alarms.RejectRateHigh`: 5 or more non-good parts among the last 50 records. The baseline is 2 per 50.
- **State machine:** none. Stopping the cell is a quality decision (MES requirement MES-QA-03).
- **Reset:** `Sim.Faults.QualityDriftRate` = 0 and `Sim.Faults.QualityOffset` = 0 (tool change or recalibration upstream). The alarm clears by itself when the rate falls below 5 in 50.
- **Alarm:** `C01.Alarms.RejectRateHigh`, Low, not latched.

### F11 Low compressed air

- **Injection:** `Sim.Faults.AirPressureLow` = true (latched).
- **Sim effect:**
  - `UT01.Status.AirPressure` ramps from 6.20 to 4.80 bar in 30 s; when the fault is removed it recovers to 6.20 bar in 10 s.
  - Vacuum capability: the maximum vacuum is -75 kPa at p >= 5.5 bar, otherwise -75 × (p - 4.0) / 1.5 kPa. Below about 5.2 bar, picks fail (F04 behaviour).
- **Detection:** `UT01.Status.AirPressureOk` false (p < 5.5 bar, about 15 s after injection).
- **State machine:** Execute -> Holding (150) -> Held.
- **Reset:** `Sim.Faults.AirPressureLow` = false, wait for AirPressureOk, then Unhold (refused while the pressure is low).
- **Alarm:** `C01.Alarms.AirPressureLow`, High (it affects the whole area).

### F12 Robot communication fault

- **Injection:** `Sim.Faults.RobotHeartbeatFreeze` = true (latched).
- **Sim effect:** the robot controller freezes. `RB01.Status.Heartbeat` stops and the robot executes no more steps.
- **Detection:** heartbeat unchanged for more than 2.5 s (it normally changes every 1.0 s).
- **State machine:** Aborting (160) -> Aborted.
- **Reset:**
  1. `Sim.Faults.RobotHeartbeatFreeze` = false: the heartbeat resumes.
  2. Clear, which is refused until the heartbeat has changed in the last 2.5 s. Then Stopped.
  3. Reset, then Start.
- **Alarm:** `C01.Alarms.RobotCommFault`, High.

### F13 Downstream blocked

- **Injection:** `Sim.Faults.DownstreamBlocked` = true (latched).
- **Sim effect:** parts cannot leave CV02. After 15 parts (about 37 s at 24 parts/min) the place zone stays occupied (`CV02.Sensors.EntryOccupied`).
- **Detection:**
  - Robot waits in step 7 for more than 3 s: `C01.Status.EquipmentBlocked`.
  - After 10 s more: Execute -> Suspending (11) -> Suspended.
- **Reset:** `Sim.Faults.DownstreamBlocked` = false. Parts leave, EntryOccupied clears, and the cell unsuspends by itself.
- **Alarm:** Ignition tag alarm on `C01.Status.EquipmentBlocked`, Low. The MES books the time as an external (downstream) loss.

### F14 SCADA communication loss

- **Injection:**
  - `Sim.Faults.ModbusOutage` = N s: the Modbus server closes its connections and refuses new ones.
  - `Sim.Faults.OpcUaOutage` = N s: the OPC UA server stops 1 s after the write and restarts after N s.
  - The simulation model keeps running during both: values are current when the server comes back, and counters do not reset.
- **Detection (Ignition side only):**
  - Tag quality goes bad on the device.
  - An Ignition expression tag per channel (for example "seconds since `C01.Status.Heartbeat` / `IO01.Status.Heartbeat` last changed" > 5 s).
- **State machine:** none. The cell is autonomous and keeps producing.
  - Traceability records accumulate (`C01.Traceability.BufferCount`) up to 200, about 8 min. Beyond that, `C01.Traceability.LostCount` increases.
  - Counters are cumulative, so the MES catches up on good/reject counts when the link returns.
- **Reset:** automatic on reconnection. The MES drains the backlog through the normal handshake.
- **Alarm:** Ignition alarm on the comm-health expression tags, High. Downtime of the cell is not affected, but OEE and traceability coverage are (MES-NF-03).

## 4. Implementation order suggested for phase 2

1. Sim namespace behaviour plus F06 and F05: Modbus write, Hold/Unhold.
2. F01 and F02: the Abort/Clear path and safety status.
3. F03, F04 and F07: robot-side faults.
4. F08, F09 and F10: quality.
5. F11, F12, F13 and F14.
