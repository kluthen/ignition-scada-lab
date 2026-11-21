# OPC UA and Modbus signal registry: Cell 01

**Single source of truth: [`opcua-registry.csv`](opcua-registry.csv).** This document explains
the conventions and lists the same content in readable form. The tables in section 7 are
generated from the CSV. If the two ever differ, the CSV is right.

The registry covers every signal exchanged between the simulated cell and Ignition:

- 210 OPC UA nodes: 46 objects/folders and 164 variables, in three namespaces;
- 36 Modbus TCP points on device IO01.

The plant itself is described in [`scenario.md`](scenario.md).

## 1. Server and namespaces

| Item | Value |
|---|---|
| Endpoint (inside compose network) | `opc.tcp://plc-c0n:4840/ignition-lab/`, one server per cell (`plc-c01`..`plc-c06`) |
| Endpoint (from the host) | `opc.tcp://127.0.0.1:484n/ignition-lab/` (C03 → 4843, see [cells.csv](cells.csv)) |
| Application URI | `urn:ignition-lab:plc-sim:c0n` |
| Security, phase 1 | SecurityPolicy None, MessageSecurityMode None, anonymous user |
| Server implementation | Python `asyncua`, same process as the Modbus server and the cell program |

| Namespace URI | Expected index | Content |
|---|---|---|
| `urn:ignition-lab:cell` | 2 | `Machines` folder, cell `C01`, quality station `QS01`, andon station `AN01` |
| `urn:ignition-lab:robot` | 3 | Robot `RB01` (organised under `Machines`) |
| `urn:ignition-lab:sim` | 4 | `Sim`: simulation-only instructor interface |

The server registers the namespaces in this order, so asyncua gives them indexes 2, 3 and 4.
Clients must not hard-code the index: use the namespace URI.

This registry is the **type** of one PIC-200 cell, written for the instance C01.
The six cells of the area ([plant-layout.md](plant-layout.md)) serve the same
address space, with one substitution: the cell's own nodes (`C01` and `C01.*`)
carry the cell id in their NodeId and BrowsePath (`C03.Status.StateCurrent`
under `Machines/C03`). Equipment inside a cell (`QS01`, `RB01`, `CV01`…) and
`Sim.*` keep their names, which are local to each server. Identification values
and `Sim.Process.*` start values come from docs/cells.csv (`plc/instance.py`).

## 2. NodeId convention

- Every node has a **string** identifier equal to its signal name: the dotted path from the
  equipment object, without `Objects` or `Machines`. Example: `C01.Status.StateCurrent`.
- Full form, as stored in the CSV `node_id` column:
  `nsu=urn:ignition-lab:cell;s=C01.Status.StateCurrent`. The index form is `ns=2;s=C01.Status.StateCurrent`.
- The BrowseName is the last path segment, in the node's own namespace (`2:StateCurrent`). The DisplayName is the same text.
- The Description attribute holds the CSV `description` column.
- Identifiers are stable. Renaming a node is a breaking change for Ignition tags, the MES, and these documents.
- In Ignition, the OPC Item Path of a tag is the `node_id` column. If the OPC UA client refuses the `nsu=` form, use `ns=<index>;s=...` (see open questions in the README).

## 3. Address space layout

```
Objects
├── Machines                      (FolderType, OPC 40001-1 entry point)
│   ├── C01                       cell, PackML unit
│   │   ├── Identification        OPC 40001-1 nameplate (properties)
│   │   ├── Status                PackML Status + Machinery item state, heartbeat
│   │   ├── Command               PackTags-style commands (HMI/MES write)
│   │   ├── Admin                 counters, stop reason, times (PackML Admin)
│   │   ├── Order
│   │   │   ├── Request           MES -> cell order download + handshake
│   │   │   └── Active            order held by the cell, order counters, recipe values
│   │   ├── Traceability          one part record at a time + MES acknowledge
│   │   └── Alarms                Boolean alarm condition bits
│   ├── QS01                      quality station (Identification, Status)
│   ├── AN01                      andon station: stack light, operator calls (Status, Command)
│   └── RB01                      robot (ns robot), OPC 40010-1 structure
│       ├── Identification
│       ├── MotionDevices/Arm     MotionDeviceCategory, ParameterSet, Axes/J1..J4
│       ├── Controllers/RC01      ParameterSet, TaskControls/Main/ParameterSet
│       ├── SafetyStates/SS01     ParameterSet (OperationalMode, EmergencyStop, ProtectiveStop)
│       └── Status                integrator extension: cycle step, gripper, counters
└── Sim                           (ns sim) SIMULATION ONLY
    ├── Process                   feed interval, reject pattern, ...
    ├── Andon                     simulated operator at the andon station
    ├── Panel                     simulated hard-wired buttons (phase 2)
    └── Faults                    fault injection (phase 2)
```

All references are hierarchical: `Organizes` from `Objects` to `Machines` and `Sim`,
`HasComponent` for objects, folders and variables, `HasProperty` for properties. All
variables are scalars (ValueRank -1). No node is typed with a companion-spec ObjectType
(see section 6).

## 4. CSV columns

The CSV is UTF-8, comma-separated, with a header row and standard double-quote escaping. Column order is fixed. New columns may only be appended.

| Column | Content |
|---|---|
| `signal` | Canonical name, unique. Used in every document, and as the string NodeId for OPC UA rows |
| `protocol` | `opcua` or `modbus` |
| `namespace_uri` | OPC UA namespace URI (empty for Modbus) |
| `node_id` | `nsu=<uri>;s=<signal>` (empty for Modbus) |
| `browse_path` | `/Objects/Machines/...` or `/Objects/Sim/...` (empty for Modbus) |
| `node_class` | `Object` or `Variable` (empty for Modbus) |
| `type_definition` | `FolderType`, `BaseObjectType`, `BaseDataVariableType` or `PropertyType` |
| `data_type` | OPC UA built-in type: Boolean, Byte, UInt16, Int32, UInt32, Double, String, DateTime. For Modbus, the engineering-value type (Double when scaled) |
| `access` | `R` (CurrentRead) or `RW` (CurrentRead + CurrentWrite). Modbus: R for discrete inputs/input registers, RW for coils/holding registers |
| `writer` | Who writes the value in normal use: `PLC` (cell controller), `ROBOT` (robot controller), `IO` (field device via the I/O coupler), `HMI` (operator screen in Ignition), `MES` (Ignition MES logic), `HMI/MES`, `SIM` (instructor) |
| `eng_unit` | Engineering unit (s, mm, mm/s, kPa, bar, kW, kWh, %, parts/min, count, parts) |
| `min`, `max` | Valid range of the engineering value. The server does not validate writes: the PLC logic handles out-of-range values as the description says (clamp, or refuse through CmdResult / LoadResult) |
| `initial_value` | Value at controller start, in engineering units. Empty for a String = empty string. `@startup` = UTC time of controller start. `1601-01-01T00:00:00Z` = OPC UA null DateTime |
| `enum_ref` | Name of the enumeration in section 5 that gives the meaning of the values |
| `modbus_table` | `coil`, `discrete_input`, `holding`, `input` |
| `modbus_address` | Zero-based PDU address (what the Python server uses), `a-b` for 32-bit values |
| `ignition_modbus_address` | Address string for an Ignition Modbus tag (one-based, Ignition default), e.g. `C1`, `DI4`, `HRUS1`, `IRUI12` |
| `modbus_scale` | Engineering value = raw × scale |
| `ignition_tag_path` | Recommended Ignition tag path (rule in scenario.md 2.1) |
| `sim_only` | `Y` for the `Sim` namespace: never part of a real plant, keep it out of the production tag provider |
| `phase` | 1 = behaviour implemented in phase 1; 2 = node exists from phase 1 with its initial value, behaviour comes with faults |
| `companion_ref` | Companion spec element the node borrows its name/meaning from |
| `description` | Meaning, update rule, handshake |

Generation rules for the server:

- Create **every** row, whatever its phase.
- Folders: `add_folder`. Objects: `add_object`. Properties: `add_property`. Variables: `add_variable` with the explicit VariantType.
- Call `set_writable()` on RW variables only. Write the Description attribute.
- Values written by Ignition are read by the PLC at the next scan.
- Handshake resets (`CntrlCmd`, `UnitModeRequest`, `LoadRequest`) are written by the server itself.

## 5. Enumerations

All enumerations are plain Int32 (or UInt16 on Modbus) values, not OPC UA Enumeration DataTypes (simpler for Ignition, see section 6).

**PackMLState** (`C01.Status.StateCurrent`): 0 Undefined, 1 Clearing, 2 Stopped, 3 Starting, 4 Idle, 5 Suspended,
6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 10 Holding, 11 Held, 12 Unholding, 13 Suspending,
14 Unsuspending, 15 Resetting, 16 Completing, 17 Complete. `C01.Status.StateCurrentName` uses exactly these names.

**CntrlCmd** (`C01.Command.CntrlCmd`): 0 None/Undefined, 1 Reset, 2 Start, 3 Stop, 4 Hold, 5 Unhold, 6 Suspend, 7 Unsuspend, 8 Abort, 9 Clear.

**CmdResult** (`C01.Command.CmdResult`): 0 None, 1 Accepted, 2 RejectedInvalidState, 3 RejectedInterlock, 4 RejectedInvalidValue.

**UnitMode** (`C01.Status.UnitModeCurrent`, `C01.Command.UnitModeRequest`): 0 None (request only: no request), 1 Production, 2 Maintenance, 3 Manual (reserved, refused).

**StopReason** (`C01.Admin.StopReason`). The text is the value of `C01.Admin.StopReasonText`. Codes 100 and above are faults (phase 2).

| Code | Text | Code | Text |
|---|---|---|---|
| 0 | None | 101 | Emergency stop |
| 1 | Stop command | 103 | Guard door open |
| 2 | Hold command | 110 | Vacuum loss |
| 3 | Order complete | 111 | Pick failed |
| 4 | Abort command | 120 | Infeed jam |
| 5 | Suspend command | 121 | Infeed drive fault |
| 10 | Starved | 122 | Outfeed drive fault |
| 11 | Blocked | 130 | Quality station no result |
| 20 | Reject bin full | 131 | Part ID unreadable |
|  |  | 140 | Part sensor stuck |
|  |  | 150 | Air pressure low |
|  |  | 160 | Robot communication fault |

Alarm codes 21 (reject bin near full) and 170 (reject rate high) are warnings: they appear in alarm descriptions but are never a StopReason.

**LoadResult** (`C01.Order.Request.LoadResult`): 0 None, 1 Accepted, 2 RejectedBusy, 3 RejectedInvalidOrderId, 4 RejectedInvalidPartType, 5 RejectedInvalidQuantity.

**OrderStatus** (`C01.Order.Active.OrderStatus`): 0 None, 1 Loaded, 2 InProgress, 3 Complete.

**PartType**: 0 None, 1 HSG-A20, 2 HSG-B32, 3 HSG-C45 (recipe table in scenario.md section 3).

**PartResult** (`C01.Traceability.Result`): 0 None, 1 Good, 2 Reject, 3 Scrapped.

**DefectCode** (`C01.Traceability.DefectCode`): 0 None, 1 Undersize, 2 Oversize, 3 NoMeasurement, 4 IdUnreadable, 5 Dropped, 6 Purged.

**InspectionResult** (`QS01.Status.LastResult`): 0 None, 1 OK, 2 NOK, 3 NoResult.

**AndonCall** (`AN01.Status.CallType`, `Sim.Andon.CallButton`): 0 None, 1 Material, 2 Quality, 3 Maintenance.

**MachineryItemState** (OPC 40001-1): 0 NotAvailable, 1 OutOfService, 2 NotExecuting, 3 Executing.

**MachineryOperationMode** (OPC 40001-1): 0 None, 1 Maintenance, 2 Setup, 3 Processing.

**MotionDeviceCategory** (OPC 40010-1): 0 OTHER, 1 ARTICULATED_ROBOT, 2 SCARA_ROBOT, 3 CARTESIAN_ROBOT, 4 SPHERICAL_ROBOT, 5 PARALLEL_ROBOT, 6 CYLINDRICAL_ROBOT.

**ExecutionMode** (OPC 40010-1): 0 CYCLE, 1 CONTINUOUS, 2 STEP.

**OperationalMode** (OPC 40010-1): 0 OTHER, 1 MANUAL_REDUCED_SPEED, 2 MANUAL_HIGH_SPEED, 3 AUTOMATIC, 4 AUTOMATIC_EXTERNAL.

**RobotCycleStep** (`RB01.Status.CycleStep`, names in `RB01.Status.CycleStepName`): 0 NotReady, 1 Homing, 2 WaitPart, 3 MoveToPick, 4 Grip, 5 Lift, 6 MoveToPlace, 7 WaitPlaceClear, 8 Release, 9 ReturnToWait, 10 Halted.

**Destination** (`RB01.Status.Destination`): 0 None, 1 Outfeed, 2 RejectBin.

**DriveFaultCode** (Modbus): 0 None, 1 Overcurrent, 2 Overtemperature, 3 PhaseLoss.

## 6. Alignment with companion specifications, and where it diverges

| Spec | What is borrowed | Divergence |
|---|---|---|
| OPC 40001-1 Machinery | `Machines` entry folder; `Identification` with the standard property names (Manufacturer, SerialNumber, ProductInstanceUri, YearOfConstruction, ...); MachineryItemState and MachineryOperationMode values | Item state and operation mode are Int32 variables, not state machine objects with `CurrentState`. Identification properties are String, not LocalizedText. No ObjectType instances, so a generic Machinery client will not recognise the machine |
| OPC 40010-1 Robotics | `MotionDevices` / `Controllers` / `SafetyStates` structure, `ParameterSet` variables (SpeedOverride, OnPath, InControl, ActualPosition, StartUpTime, TaskProgramName, TaskProgramLoaded, ExecutionMode, OperationalMode, EmergencyStop, ProtectiveStop), enumeration values | Folders and objects are not typed (no MotionDeviceSystemType ...). Mandatory items such as PowerTrains, Software and EmergencyStopFunctions are omitted. Axis positions are Double without AnalogUnitType/EURange. `RB01.Status` is an integrator extension that the spec does not have |
| OPC 30050 PackML | Status/Admin folder names and variable names (StateCurrent, UnitModeCurrent, MachSpeed, CurMachSpeed, EquipmentStarved/Blocked, ProdProcessedCount, ProdDefectiveCount, ProdConsumedCount, StopReason, StateCurrentTime, AccTimeSinceReset, MachDesignSpeed); state numbers 1-17 | Commands are PackTags-style variables (`C01.Command.CntrlCmd`) instead of the OPC 30050 methods. Counters and StopReason are scalars instead of structured types. No BaseStateMachine object. `PacDateTime` comes from PackTags; it is not in OPC 30050 |

Why simplify: Ignition maps variables to tags directly. Custom structures (ExtensionObjects) and
methods take extra work in Ignition, and a hand-built asyncua address space with typed
companion-spec instances would require importing the official NodeSet2 files. Importing the
real Machinery/Robotics nodesets is a good later exercise (open question in the README).

## 7. Registry tables

Columns as in the CSV. "Ph" = phase; "prop" = PropertyType. Ranges are in engineering units.

### Cell C01 (`urn:ignition-lab:cell`)

| Signal (NodeId `s=`) | Class / type | Acc | Writer | Unit | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|
| `C01` | Object |  |  |  |  |  | 1 | Cell 01: pick-and-inspect cell, PackML unit. Owns the state machine, order and counters. |
| `C01.Identification` | Object |  |  |  |  |  | 1 | Nameplate of the cell. |
| `C01.Identification.Manufacturer` | String (prop) | R | PLC |  |  | Ignition Lab Integration (fictional) | 1 | Cell builder (integrator). |
| `C01.Identification.ManufacturerUri` | String (prop) | R | PLC |  |  | urn:ignition-lab | 1 | URI of the manufacturer. |
| `C01.Identification.Model` | String (prop) | R | PLC |  |  | PIC-200 Pick and Inspect Cell | 1 | Model name. |
| `C01.Identification.ProductCode` | String (prop) | R | PLC |  |  | PIC-200 | 1 | Manufacturer product code. |
| `C01.Identification.SerialNumber` | String (prop) | R | PLC |  |  | PIC200-26-0001 | 1 | Serial number of the cell. |
| `C01.Identification.ProductInstanceUri` | String (prop) | R | PLC |  |  | urn:ignition-lab:machine:PIC200-26-0001 | 1 | Globally unique instance URI. |
| `C01.Identification.HardwareRevision` | String (prop) | R | PLC |  |  | A | 1 | Hardware revision. |
| `C01.Identification.SoftwareRevision` | String (prop) | R | PLC |  |  | 1.0.0 | 1 | Cell controller program revision (bump when the simulation logic changes). |
| `C01.Identification.YearOfConstruction` | UInt16 (prop) | R | PLC |  |  | 2026 | 1 | Year of construction. |
| `C01.Identification.MonthOfConstruction` | Byte (prop) | R | PLC |  |  | 3 | 1 | Month of construction (1-12). |
| `C01.Identification.AssetId` | String (prop) | R | PLC |  |  | ANN-FIN-C01 | 1 | Customer asset id (ISA-95 site-area-cell). |
| `C01.Identification.ComponentName` | String (prop) | R | PLC |  |  | Cell 01 - housing inspection and sorting | 1 | Customer-facing name. |
| `C01.Identification.Location` | String (prop) | R | PLC |  |  | ANN/FIN/BAY3 | 1 | Site/area/bay. |
| `C01.Status` | Folder |  |  |  |  |  | 1 | Live state of the cell. |
| `C01.Status.StateCurrent` | Int32 | R | PLC |  | 0..17 | 2 | 1 | Current PackML state number. Enum: PackMLState. |
| `C01.Status.StateCurrentName` | String | R | PLC |  |  | Stopped | 1 | Name of the current PackML state (English, as in the PackMLState table). Enum: PackMLState. |
| `C01.Status.UnitModeCurrent` | Int32 | R | PLC |  | 1..3 | 1 | 1 | Current unit mode. Enum: UnitMode. |
| `C01.Status.UnitModeCurrentName` | String | R | PLC |  |  | Production | 1 | Name of the current unit mode. Enum: UnitMode. |
| `C01.Status.MachSpeed` | Double | R | PLC | parts/min | 0..25 | 25.0 | 1 | Effective speed setpoint: C01.Command.MachSpeed clamped to [0.1, 1.0] x C01.Admin.MachDesignSpeed. |
| `C01.Status.CurMachSpeed` | Double | R | PLC | parts/min | 0..30 | 0.0 | 1 | Actual rate: 60 / mean interval of the last 5 robot placements; 0 outside Execute or if no placement for 15 s. |
| `C01.Status.EquipmentStarved` | Boolean | R | PLC |  |  | false | 1 | True when the robot has waited for a part > 3.0 s, CV01 is empty and the order still needs parts. |
| `C01.Status.EquipmentBlocked` | Boolean | R | PLC |  |  | false | 1 | True when the robot has waited for a free place position on CV02 > 3.0 s. |
| `C01.Status.MachineryItemState` | Int32 | R | PLC |  | 0..3 | 2 | 1 | OPC 40001-1 item state derived from the PackML state (mapping in scenario.md). Enum: MachineryItemState. |
| `C01.Status.MachineryOperationMode` | Int32 | R | PLC |  | 0..3 | 3 | 1 | OPC 40001-1 operation mode derived from the unit mode. Enum: MachineryOperationMode. |
| `C01.Status.Heartbeat` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Increments by 1 every second (wraps at 2^32). Used by Ignition to detect a frozen controller. |
| `C01.Status.PacDateTime` | DateTime | R | PLC |  |  | @startup | 1 | Controller clock (UTC), updated every second. |
| `C01.Command` | Folder |  |  |  |  |  | 1 | Commands written by SCADA/MES. The PLC consumes them on the next scan. |
| `C01.Command.CntrlCmd` | Int32 | RW | HMI/MES |  | 0..9 | 0 | 1 | PackML state command. Write a non-zero value; the PLC executes or refuses it within one scan (100 ms), writes C01.Command.CmdResult, increments C01.Command.CmdCounter, then writes 0 back. Enum: CntrlCmd. |
| `C01.Command.UnitModeRequest` | Int32 | RW | HMI |  | 0..3 | 0 | 1 | Unit mode request (1 Production, 2 Maintenance). Same handshake as CntrlCmd. Accepted only in Stopped, Idle, Complete or Aborted. Enum: UnitMode. |
| `C01.Command.MachSpeed` | Double | RW | HMI | parts/min | 0..30 | 25.0 | 1 | Requested speed. The PLC clamps it (see C01.Status.MachSpeed) and maps it to RB01 speed override. |
| `C01.Command.CmdResult` | Int32 | R | PLC |  | 0..4 | 0 | 1 | Result of the last command (CntrlCmd or UnitModeRequest) processed. Enum: CmdResult. |
| `C01.Command.CmdCounter` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Incremented each time a command is processed (accepted or refused). Lets the HMI match a result to its write. |
| `C01.Admin` | Folder |  |  |  |  |  | 1 | Counters and administrative data. |
| `C01.Admin.ProdProcessedCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Parts finished by the cell since controller start: one per C01.Traceability record (good, reject or scrapped). Restarts at 0 when the controller restarts. |
| `C01.Admin.ProdDefectiveCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Records with Result Reject or Scrapped since controller start. |
| `C01.Admin.ProdConsumedCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Parts released by upstream onto CV01 since controller start. |
| `C01.Admin.StopReason` | Int32 | R | PLC |  | 0..999 | 0 | 1 | First-out cause of the last transition into Stopping, Holding, Suspending, Aborting or Completing. Kept until the next such transition; reset to 0 when Execute is re-entered. Enum: StopReason. |
| `C01.Admin.StopReasonText` | String | R | PLC |  |  | None | 1 | English text of C01.Admin.StopReason. Enum: StopReason. |
| `C01.Admin.StateCurrentTime` | Double | R | PLC | s | 0..1e9 | 0.0 | 1 | Time spent in the current state. |
| `C01.Admin.AccTimeSinceReset` | Double | R | PLC | s | 0..1e9 | 0.0 | 1 | Time since controller start. |
| `C01.Admin.MachDesignSpeed` | Double | R | PLC | parts/min | 0..30 | 25.0 | 1 | Design rate of the active part type = 60 / C01.Order.Active.IdealCycleTime; 25.0 when no order. |
| `C01.Admin.StartUpTime` | DateTime | R | PLC |  |  | @startup | 1 | UTC time the controller (simulation) started. A change tells the MES that counters restarted. |
| `C01.Order` | Folder |  |  |  |  |  | 1 | Production order interface (MES <-> cell). |
| `C01.Order.Request` | Folder |  |  |  |  |  | 1 | Order download area written by the MES. |
| `C01.Order.Request.OrderId` | String | RW | MES |  |  |  | 1 | Order id to load (1-32 printable ASCII characters). |
| `C01.Order.Request.PartType` | Int32 | RW | MES |  | 0..3 | 0 | 1 | Part type to produce (recipe number). Enum: PartType. |
| `C01.Order.Request.TargetQuantity` | UInt32 | RW | MES | count | 0..100000 | 0 | 1 | Number of GOOD parts to produce. |
| `C01.Order.Request.LoadRequest` | Boolean | RW | MES |  |  | false | 1 | Set true after writing the three fields above. The PLC evaluates on the rising edge, writes C01.Order.Request.LoadResult and resets this to false. |
| `C01.Order.Request.LoadResult` | Int32 | R | PLC |  | 0..5 | 0 | 1 | Result of the last load request. Enum: LoadResult. |
| `C01.Order.Active` | Folder |  |  |  |  |  | 1 | Order currently held by the cell. |
| `C01.Order.Active.OrderId` | String | R | PLC |  |  |  | 1 | Active order id (empty = no order). |
| `C01.Order.Active.PartType` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Active part type. Enum: PartType. |
| `C01.Order.Active.ProductCode` | String | R | PLC |  |  |  | 1 | Product code of the active part type (from the cell recipe table). Enum: PartType. |
| `C01.Order.Active.TargetQuantity` | UInt32 | R | PLC | count | 0..100000 | 0 | 1 | Target good quantity. |
| `C01.Order.Active.GoodCount` | UInt32 | R | PLC | count | 0..100000 | 0 | 1 | Good parts of the active order. |
| `C01.Order.Active.RejectCount` | UInt32 | R | PLC | count | 0..100000 | 0 | 1 | Reject + scrapped parts of the active order. |
| `C01.Order.Active.RemainingQuantity` | UInt32 | R | PLC | count | 0..100000 | 0 | 1 | max(0, TargetQuantity - GoodCount). |
| `C01.Order.Active.OrderStatus` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Status of the active order inside the cell. Enum: OrderStatus. |
| `C01.Order.Active.NominalDiameter` | Double | R | PLC | mm | 0..100 | 0.0 | 1 | Nominal bore diameter of the active part type. |
| `C01.Order.Active.LowerLimit` | Double | R | PLC | mm | 0..100 | 0.0 | 1 | Lower acceptance limit = nominal - tolerance. |
| `C01.Order.Active.UpperLimit` | Double | R | PLC | mm | 0..100 | 0.0 | 1 | Upper acceptance limit = nominal + tolerance. |
| `C01.Order.Active.IdealCycleTime` | Double | R | PLC | s | 0..10 | 0.0 | 1 | Ideal cycle time of the active part type at 100 % speed (used for OEE performance). |
| `C01.Order.Active.StartTime` | DateTime | R | PLC |  |  | 1601-01-01T00:00:00Z | 1 | UTC time Execute was first entered for this order. |
| `C01.Order.Active.EndTime` | DateTime | R | PLC |  |  | 1601-01-01T00:00:00Z | 1 | UTC time the order reached Complete. |
| `C01.Traceability` | Folder |  |  |  |  |  | 1 | Part result FIFO with MES handshake (one record per finished part). |
| `C01.Traceability.Sequence` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Record number, +1 per record from 1 at controller start. 0 = no record presented yet. |
| `C01.Traceability.PartId` | String | R | PLC |  |  |  | 1 | Part serial read from the part DataMatrix, format P + 9 digits (e.g. P027345601); NOREAD when unreadable (phase 2). |
| `C01.Traceability.OrderId` | String | R | PLC |  |  |  | 1 | Order the part was produced for. |
| `C01.Traceability.PartType` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Part type. Enum: PartType. |
| `C01.Traceability.MeasuredDiameter` | Double | R | PLC | mm | 0..100 | 0.0 | 1 | Measured bore diameter (0.0 when not measured). |
| `C01.Traceability.Result` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Part result. Enum: PartResult. |
| `C01.Traceability.DefectCode` | Int32 | R | PLC |  | 0..6 | 0 | 1 | Defect code (0 when good). Enum: DefectCode. |
| `C01.Traceability.Timestamp` | DateTime | R | PLC |  |  | 1601-01-01T00:00:00Z | 1 | UTC time the part was finished (placed, dropped or purged). |
| `C01.Traceability.DataReady` | Boolean | R | PLC |  |  | false | 1 | True when the record fields above hold an unacknowledged record. Fields are written one scan before DataReady goes true. |
| `C01.Traceability.AckSequence` | UInt32 | RW | MES | count | 0..4294967295 | 0 | 1 | MES writes the Sequence it has stored. When equal to Sequence the PLC drops DataReady and presents the next record one scan later. |
| `C01.Traceability.BufferCount` | UInt16 | R | PLC | count | 0..200 | 0 | 1 | Records waiting, including the presented one. |
| `C01.Traceability.LostCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Records discarded because the 200-record buffer was full (oldest dropped first). |
| `C01.Alarms` | Folder |  |  |  |  |  | 1 | Alarm condition bits for Ignition tag alarms. Fault bits latch until the state machine leaves the fault state (see fault-catalogue.md). |
| `C01.Alarms.EStopActive` | Boolean | R | PLC |  |  | false | 2 | Emergency stop circuit open (SF01.Status.EStopOk false). Alarm code 101. |
| `C01.Alarms.GuardDoorOpen` | Boolean | R | PLC |  |  | false | 2 | Guard door opened while the robot was in automatic. Alarm code 103. |
| `C01.Alarms.VacuumLoss` | Boolean | R | PLC |  |  | false | 2 | Vacuum lost while transferring a part (part dropped). Alarm code 110. |
| `C01.Alarms.PickFailed` | Boolean | R | PLC |  |  | false | 2 | Two consecutive pick attempts failed to build vacuum. Alarm code 111. |
| `C01.Alarms.InfeedJam` | Boolean | R | PLC |  |  | false | 2 | CV01 runs but no part reached the pick position within the jam timeout. Alarm code 120. |
| `C01.Alarms.InfeedDriveFault` | Boolean | R | PLC |  |  | false | 2 | CV01 drive tripped (CV01.Status.DriveFault). Alarm code 121. |
| `C01.Alarms.OutfeedDriveFault` | Boolean | R | PLC |  |  | false | 2 | CV02 drive tripped (CV02.Status.DriveFault). Alarm code 122. |
| `C01.Alarms.QualityNoResult` | Boolean | R | PLC |  |  | false | 2 | QS01 returned no result within 2.0 s of the trigger. Alarm code 130. |
| `C01.Alarms.PartIdUnreadable` | Boolean | R | PLC |  |  | false | 2 | Three consecutive parts with an unreadable DataMatrix. Alarm code 131. |
| `C01.Alarms.PartSensorStuck` | Boolean | R | PLC |  |  | false | 2 | CV01.Sensors.PartAtPick still on 1.0 s after a successful pick. Alarm code 140. |
| `C01.Alarms.AirPressureLow` | Boolean | R | PLC |  |  | false | 2 | Compressed air below 5.5 bar (UT01.Status.AirPressureOk false). Alarm code 150. |
| `C01.Alarms.RobotCommFault` | Boolean | R | PLC |  |  | false | 2 | RB01.Status.Heartbeat unchanged for more than 2.5 s. Alarm code 160. |
| `C01.Alarms.RejectRateHigh` | Boolean | R | PLC |  |  | false | 2 | Warning: 5 or more non-good parts among the last 50 (no state change). Alarm code 170. |
| `C01.Alarms.RejectBinNearFull` | Boolean | R | PLC |  |  | false | 1 | Warning: RJ01.Status.NearFull. Alarm code 21. |
| `C01.Alarms.RejectBinFull` | Boolean | R | PLC |  |  | false | 1 | RJ01.Status.Full: the cell holds until the bin is emptied. Alarm code 20. |

### Quality station QS01 (`urn:ignition-lab:cell`)

| Signal (NodeId `s=`) | Class / type | Acc | Writer | Unit | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|
| `QS01` | Object |  |  |  |  |  | 1 | Quality station: fixed camera at the CV01 pick position (DataMatrix read + bore diameter gauge). |
| `QS01.Identification` | Object |  |  |  |  |  | 1 | Nameplate of the camera. |
| `QS01.Identification.Manufacturer` | String (prop) | R | PLC |  |  | SimVision (fictional) | 1 | Manufacturer of the camera. |
| `QS01.Identification.Model` | String (prop) | R | PLC |  |  | VC-200 smart camera | 1 | Model of the camera. |
| `QS01.Identification.SerialNumber` | String (prop) | R | PLC |  |  | VC200-26-1187 | 1 | SerialNumber of the camera. |
| `QS01.Status` | Folder |  |  |  |  |  | 1 | Camera status and last result. |
| `QS01.Status.Ready` | Boolean | R | PLC |  |  | true | 1 | Camera healthy and not busy. |
| `QS01.Status.Busy` | Boolean | R | PLC |  |  | false | 1 | Inspection in progress (0.4 s per part). |
| `QS01.Status.CameraOk` | Boolean | R | PLC |  |  | true | 2 | False while Sim.Faults.CameraNoResult is active. |
| `QS01.Status.InspectionCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Inspections since controller start. |
| `QS01.Status.LastPartId` | String | R | PLC |  |  |  | 1 | Part id read at the last inspection (empty if unreadable). |
| `QS01.Status.LastMeasurement` | Double | R | PLC | mm | 0..100 | 0.0 | 1 | Last measured bore diameter. |
| `QS01.Status.LastResult` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Last inspection result. Enum: InspectionResult. |

### Andon station AN01 (`urn:ignition-lab:cell`)

Not bound in Ignition yet: the CSV column `ignition_tag_path` is empty, so
`scripts/generate_tags.py` leaves these nodes out. They are bound by hand in
the training week ([training/week-48.md](training/week-48.md)); suggested paths
`[default]ANN/FIN/<cell>/AN01/...` and `[sim]<cell>/Andon/...`.

| Signal (NodeId `s=`) | Class / type | Acc | Writer | Unit | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|
| `AN01` | Object |  |  |  |  |  | 1 | Andon station: four-lamp stack light with buzzer, and three operator call buttons (material, quality, maintenance) at the cell. No Ignition tags yet: bound by hand in the training week (docs/training/week-48.md). |
| `AN01.Status` | Folder |  |  |  |  |  | 1 | Stack light outputs and the active operator call. |
| `AN01.Status.LampRed` | Boolean | R | PLC |  |  | false | 1 | Red lamp: the cell needs intervention: Aborting, Aborted or Clearing, Holding or Held on a fault (StopReason 100 and above), or safety not OK. |
| `AN01.Status.LampAmber` | Boolean | R | PLC |  |  | false | 1 | Amber lamp: the cell waits: Suspending, Suspended or Unsuspending (starved or blocked), or Holding, Held or Unholding without a fault (e.g. reject bin full). Off when the red lamp is on. |
| `AN01.Status.LampGreen` | Boolean | R | PLC |  |  | false | 1 | Green lamp: the cell is producing (state Execute). |
| `AN01.Status.LampBlue` | Boolean | R | PLC |  |  | false | 1 | Blue lamp: an operator call is active (steady; the HMI may blink it while AN01.Status.Buzzer is on). |
| `AN01.Status.Buzzer` | Boolean | R | PLC |  |  | false | 1 | Buzzer: an operator call is active and not acknowledged yet. |
| `AN01.Status.CallType` | Int32 | R | PLC |  | 0..3 | 0 | 1 | Type of the active call, 0 when none. Enum: AndonCall. |
| `AN01.Status.CallAcknowledged` | Boolean | R | PLC |  |  | false | 1 | The active call has been acknowledged (AN01.Command.Acknowledge). False when no call is active. |
| `AN01.Status.CallStartTime` | DateTime | R | PLC |  |  |  | 1 | Time the active call was raised (controller clock, UTC). OPC UA null DateTime (1601-01-01) when no call is active. |
| `AN01.Status.CallCount` | UInt32 | R | PLC | count | 0..4294967295 | 0 | 1 | Calls raised since controller start. |
| `AN01.Command` | Folder |  |  |  |  |  | 1 | Andon commands (HMI write). |
| `AN01.Command.Acknowledge` | Boolean | RW | HMI |  |  | false | 1 | Write true to acknowledge the active call: the buzzer stops, the blue lamp stays on until the operator clears the call at the cell. The PLC writes false back within one scan, also when there is nothing to acknowledge. |

### Robot RB01 (`urn:ignition-lab:robot`)

| Signal (NodeId `s=`) | Class / type | Acc | Writer | Unit | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|
| `RB01` | Object |  |  |  |  |  | 1 | SCARA robot with vacuum gripper (simulated robot controller). |
| `RB01.Identification` | Object |  |  |  |  |  | 1 | Nameplate of the robot. |
| `RB01.Identification.Manufacturer` | String (prop) | R | ROBOT |  |  | SimRobotics (fictional) | 1 | Manufacturer of the robot. |
| `RB01.Identification.Model` | String (prop) | R | ROBOT |  |  | SR-S400 SCARA | 1 | Model of the robot. |
| `RB01.Identification.ProductCode` | String (prop) | R | ROBOT |  |  | SR-S400-4 | 1 | ProductCode of the robot. |
| `RB01.Identification.SerialNumber` | String (prop) | R | ROBOT |  |  | SRS400-26-0417 | 1 | SerialNumber of the robot. |
| `RB01.Identification.SoftwareRevision` | String (prop) | R | ROBOT |  |  | 4.2.1 | 1 | SoftwareRevision of the robot. |
| `RB01.Identification.YearOfConstruction` | UInt16 (prop) | R | ROBOT |  |  | 2026 | 1 | YearOfConstruction of the robot. |
| `RB01.MotionDevices` | Folder |  |  |  |  |  | 1 | Motion devices of the system. |
| `RB01.MotionDevices.Arm` | Object |  |  |  |  |  | 1 | The 4-axis SCARA arm. |
| `RB01.MotionDevices.Arm.MotionDeviceCategory` | Int32 (prop) | R | ROBOT |  |  | 2 | 1 | Robot kinematics category. Enum: MotionDeviceCategory. |
| `RB01.MotionDevices.Arm.ParameterSet` | Object |  |  |  |  |  | 1 | Arm parameters. |
| `RB01.MotionDevices.Arm.ParameterSet.SpeedOverride` | Double | R | ROBOT | % | 10..100 | 100.0 | 1 | Speed override applied to motion steps = clamp(100 x C01.Status.MachSpeed / C01.Admin.MachDesignSpeed, 10, 100). |
| `RB01.MotionDevices.Arm.ParameterSet.OnPath` | Boolean | R | ROBOT |  |  | false | 1 | True while the arm is executing a motion step. |
| `RB01.MotionDevices.Arm.ParameterSet.InControl` | Boolean | R | ROBOT |  |  | false | 1 | Servos on and controlled (see robot state table in scenario.md). |
| `RB01.MotionDevices.Arm.Axes` | Folder |  |  |  |  |  | 2 | Axes of the arm (phase 2: position animation). |
| `RB01.MotionDevices.Arm.Axes.J1` | Object |  |  |  |  |  | 2 | Axis J1: Shoulder rotation. |
| `RB01.MotionDevices.Arm.Axes.J1.ParameterSet` | Object |  |  |  |  |  | 2 | Axis J1 parameters. |
| `RB01.MotionDevices.Arm.Axes.J1.ParameterSet.ActualPosition` | Double | R | ROBOT | deg | -130..130 | 0.0 | 2 | Shoulder rotation. Linear interpolation between taught points (scenario.md). |
| `RB01.MotionDevices.Arm.Axes.J2` | Object |  |  |  |  |  | 2 | Axis J2: Elbow rotation. |
| `RB01.MotionDevices.Arm.Axes.J2.ParameterSet` | Object |  |  |  |  |  | 2 | Axis J2 parameters. |
| `RB01.MotionDevices.Arm.Axes.J2.ParameterSet.ActualPosition` | Double | R | ROBOT | deg | -145..145 | 30.0 | 2 | Elbow rotation. Linear interpolation between taught points (scenario.md). |
| `RB01.MotionDevices.Arm.Axes.J3` | Object |  |  |  |  |  | 2 | Axis J3: Quill stroke, 0 = top, positive downwards. |
| `RB01.MotionDevices.Arm.Axes.J3.ParameterSet` | Object |  |  |  |  |  | 2 | Axis J3 parameters. |
| `RB01.MotionDevices.Arm.Axes.J3.ParameterSet.ActualPosition` | Double | R | ROBOT | mm | 0..150 | 20.0 | 2 | Quill stroke, 0 = top, positive downwards. Linear interpolation between taught points (scenario.md). |
| `RB01.MotionDevices.Arm.Axes.J4` | Object |  |  |  |  |  | 2 | Axis J4: Tool rotation. |
| `RB01.MotionDevices.Arm.Axes.J4.ParameterSet` | Object |  |  |  |  |  | 2 | Axis J4 parameters. |
| `RB01.MotionDevices.Arm.Axes.J4.ParameterSet.ActualPosition` | Double | R | ROBOT | deg | -360..360 | 0.0 | 2 | Tool rotation. Linear interpolation between taught points (scenario.md). |
| `RB01.Controllers` | Folder |  |  |  |  |  | 1 | Controllers of the system. |
| `RB01.Controllers.RC01` | Object |  |  |  |  |  | 1 | Robot controller. |
| `RB01.Controllers.RC01.ParameterSet` | Object |  |  |  |  |  | 1 | Controller parameters. |
| `RB01.Controllers.RC01.ParameterSet.StartUpTime` | DateTime | R | ROBOT |  |  | @startup | 1 | UTC time the robot controller started. |
| `RB01.Controllers.RC01.TaskControls` | Folder |  |  |  |  |  | 1 | Task controls. |
| `RB01.Controllers.RC01.TaskControls.Main` | Object |  |  |  |  |  | 1 | Main robot task. |
| `RB01.Controllers.RC01.TaskControls.Main.ParameterSet` | Object |  |  |  |  |  | 1 | Task parameters. |
| `RB01.Controllers.RC01.TaskControls.Main.ParameterSet.TaskProgramName` | String | R | ROBOT |  |  |  | 1 | Loaded robot program (per part type, see PartType table); empty when none. |
| `RB01.Controllers.RC01.TaskControls.Main.ParameterSet.TaskProgramLoaded` | Boolean | R | ROBOT |  |  | false | 1 | True once an order has been loaded into the cell. |
| `RB01.Controllers.RC01.TaskControls.Main.ParameterSet.ExecutionMode` | Int32 | R | ROBOT |  | 0..2 | 1 | 1 | Program execution mode (always CONTINUOUS in this cell). Enum: ExecutionMode. |
| `RB01.SafetyStates` | Folder |  |  |  |  |  | 1 | Safety states. |
| `RB01.SafetyStates.SS01` | Object |  |  |  |  |  | 1 | Safety state of the robot. |
| `RB01.SafetyStates.SS01.ParameterSet` | Object |  |  |  |  |  | 1 | Safety parameters. |
| `RB01.SafetyStates.SS01.ParameterSet.OperationalMode` | Int32 | R | ROBOT |  | 0..4 | 4 | 1 | Robot operational mode (AUTOMATIC_EXTERNAL: program driven by the cell controller). Enum: OperationalMode. |
| `RB01.SafetyStates.SS01.ParameterSet.EmergencyStop` | Boolean | R | ROBOT |  |  | false | 2 | True while the e-stop chain is open. |
| `RB01.SafetyStates.SS01.ParameterSet.ProtectiveStop` | Boolean | R | ROBOT |  |  | false | 2 | True while a protective stop is active (guard door open in automatic). |
| `RB01.Status` | Folder |  |  |  |  |  | 1 | Integrator extension: cycle status of the pick-and-place program (not in OPC 40010). |
| `RB01.Status.Heartbeat` | UInt32 | R | ROBOT | count | 0..4294967295 | 0 | 1 | Increments by 1 every second; watched by the cell (RobotCommFault). |
| `RB01.Status.Homed` | Boolean | R | ROBOT |  |  | false | 1 | True after homing in Resetting; false after Aborting. |
| `RB01.Status.CycleStep` | Int32 | R | ROBOT |  | 0..10 | 0 | 1 | Current step of the pick-and-place cycle. Enum: RobotCycleStep. |
| `RB01.Status.CycleStepName` | String | R | ROBOT |  |  | NotReady | 1 | Name of the current step. Enum: RobotCycleStep. |
| `RB01.Status.AtHome` | Boolean | R | ROBOT |  |  | false | 1 | Arm at the WaitAbovePick taught point. |
| `RB01.Status.PartInGripper` | Boolean | R | ROBOT |  |  | false | 1 | A part is held by the gripper. |
| `RB01.Status.Destination` | Int32 | R | ROBOT |  | 0..2 | 0 | 1 | Where the held part goes. Enum: Destination. |
| `RB01.Status.VacuumOn` | Boolean | R | ROBOT |  |  | false | 1 | Vacuum valve commanded on. |
| `RB01.Status.VacuumOk` | Boolean | R | ROBOT |  |  | false | 1 | Vacuum switch: RB01.Status.VacuumLevel <= -60 kPa. |
| `RB01.Status.VacuumLevel` | Double | R | ROBOT | kPa | -90..0 | 0.0 | 1 | Gripper vacuum (gauge, negative = vacuum). |
| `RB01.Status.CycleCount` | UInt32 | R | ROBOT | count | 0..4294967295 | 0 | 1 | Completed pick-and-place cycles since controller start. |
| `RB01.Status.LastCycleTime` | Double | R | ROBOT | s | 0..600 | 0.0 | 1 | Duration of the last cycle, MoveToPick start to ReturnToWait end, waits included. |

### Simulation interface (`urn:ignition-lab:sim`, simulation only)

| Signal (NodeId `s=`) | Class / type | Acc | Writer | Unit | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|
| `Sim` | Object |  |  |  |  |  | 1 | SIMULATION ONLY. Instructor interface: process parameters, operator panel, fault injection. Never part of a real plant. |
| `Sim.Process` | Folder |  |  |  |  |  | 1 | Process parameters of the simulated environment. |
| `Sim.Process.FeedInterval` | Double | RW | SIM | s | 1.0..60.0 | 2.5 | 1 | Minimum time between two parts released by upstream onto CV01. |
| `Sim.Process.UpstreamFeedEnable` | Boolean | RW | SIM |  |  | true | 1 | False = upstream stops releasing parts (starvation). |
| `Sim.Process.RejectEveryN` | UInt16 | RW | SIM | count | 0..1000 | 25 | 1 | Every Nth part serial is out of tolerance (0 = no rejects). |
| `Sim.Process.AutoEmptyRejectBin` | Boolean | RW | SIM |  |  | false | 1 | True = the bin empties itself when it reaches RJ01.Parameters.NearFullLevel (no holds). |
| `Sim.Panel` | Folder |  |  |  |  |  | 2 | Simulated hard-wired operator panel (in a real plant these are physical buttons, never SCADA writes). |
| `Sim.Panel.EStopPressed` | Boolean | RW | SIM |  |  | false | 2 | Mushroom e-stop pressed (latched while true). |
| `Sim.Panel.SafetyResetButton` | Boolean | RW | SIM |  |  | false | 2 | Blue safety reset button (pulse: the sim resets it to false after one scan). |
| `Sim.Panel.GuardDoorOpen` | Boolean | RW | SIM |  |  | false | 2 | Guard door open while true. |
| `Sim.Faults` | Folder |  |  |  |  |  | 2 | Fault injection (see fault-catalogue.md). |
| `Sim.Faults.VacuumLossNext` | Boolean | RW | SIM |  |  | false | 2 | One-shot: vacuum is lost halfway through the next MoveToPlace. Self-clears when triggered. |
| `Sim.Faults.PickFailCount` | UInt16 | RW | SIM | count | 0..100 | 0 | 2 | The next N grip attempts fail to build vacuum. Decrements per failed attempt. |
| `Sim.Faults.InfeedJam` | Boolean | RW | SIM |  |  | false | 2 | While true parts on CV01 stop moving although the belt runs. |
| `Sim.Faults.InfeedDriveTrip` | Boolean | RW | SIM |  |  | false | 2 | One-shot: CV01 drive trips (fault code 1 overcurrent). Self-clears when triggered. |
| `Sim.Faults.OutfeedDriveTrip` | Boolean | RW | SIM |  |  | false | 2 | One-shot: CV02 drive trips (fault code 1 overcurrent). Self-clears when triggered. |
| `Sim.Faults.PartSensorStuckOn` | Boolean | RW | SIM |  |  | false | 2 | While true CV01.Sensors.PartAtPick reads true. |
| `Sim.Faults.CameraNoResult` | Boolean | RW | SIM |  |  | false | 2 | While true QS01 never returns a result. |
| `Sim.Faults.IdUnreadableCount` | UInt16 | RW | SIM | count | 0..100 | 0 | 2 | The next N inspections cannot read the DataMatrix. Decrements per inspection. |
| `Sim.Faults.QualityDriftRate` | Double | RW | SIM | mm/100 parts | -0.5..0.5 | 0.0 | 2 | Drift added to Sim.Faults.QualityOffset for every inspected part. |
| `Sim.Faults.QualityOffset` | Double | RW | SIM | mm | -5.0..5.0 | 0.0 | 2 | Current bias added to every measurement. Write 0 to remove the drift. |
| `Sim.Faults.AirPressureLow` | Boolean | RW | SIM |  |  | false | 2 | While true air pressure ramps down to 4.8 bar in 30 s; when false it recovers to 6.2 bar in 10 s. |
| `Sim.Faults.RobotHeartbeatFreeze` | Boolean | RW | SIM |  |  | false | 2 | While true RB01.Status.Heartbeat stops incrementing. |
| `Sim.Faults.DownstreamBlocked` | Boolean | RW | SIM |  |  | false | 2 | While true parts cannot leave CV02 at the exit. |
| `Sim.Faults.ModbusOutage` | UInt16 | RW | SIM | s | 0..600 | 0 | 2 | Write N: the Modbus server closes all connections and refuses new ones for N s. Counts down to 0. |
| `Sim.Faults.OpcUaOutage` | UInt16 | RW | SIM | s | 0..600 | 0 | 2 | Write N: 1 s later the OPC UA server stops; it restarts after N s and this node reads 0 again. |
| `Sim.Faults.ClearAll` | Boolean | RW | SIM |  |  | false | 2 | Pulse: reset every Sim.Faults and Sim.Panel node to its initial value. |
| `Sim.Andon` | Folder |  |  |  |  |  | 1 | Simulated operator at the andon station (AN01). |
| `Sim.Andon.CallButton` | Int32 | RW | SIM |  | 0..3 | 0 | 1 | Press a call button at the cell: 1 Material, 2 Quality, 3 Maintenance. With no call active it raises that call; the button of the active call clears it (problem solved); anything else is ignored. The PLC writes 0 back after one scan. |
| `Sim.Andon.ResolveTime` | Double | RW | SIM | s | 0..3600 | 90 | 1 | The simulated operator clears an acknowledged call this long after the acknowledge (0 = never: clear it with Sim.Andon.CallButton). |
| `Sim.Andon.AutoCallInterval` | Double | RW | SIM | min | 0..1440 | 0 | 1 | Mean time between random calls raised by the simulated operator, type drawn among 1..3 (0 = off). A call is raised only when none is active. |

### Modbus TCP device IO01 (unit id 1)

| Signal | Ignition addr | PDU table / addr | Type | Acc | Writer | Unit | Scale | Range | Initial | Ph | Description |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CV01.Command.JogForward` | `C1` | coil 0 | Boolean | RW | HMI |  | 1 |  | false | 1 | Maintenance mode only (and state Stopped or Idle): CV01 runs at its setpoint while true. |
| `CV02.Command.JogForward` | `C2` | coil 1 | Boolean | RW | HMI |  | 1 |  | false | 1 | Maintenance mode only (and state Stopped or Idle): CV02 runs at its setpoint while true. |
| `CV01.Command.DriveReset` | `C3` | coil 2 | Boolean | RW | HMI |  | 1 |  | false | 2 | Pulse: reset a CV01 drive fault. The PLC writes it back to false after one scan. |
| `CV02.Command.DriveReset` | `C4` | coil 3 | Boolean | RW | HMI |  | 1 |  | false | 2 | Pulse: reset a CV02 drive fault. The PLC writes it back to false after one scan. |
| `RJ01.Command.BinEmptied` | `C5` | coil 4 | Boolean | RW | HMI |  | 1 |  | false | 1 | Pulse: operator confirms the reject bin was emptied; RJ01.Status.Count is set to 0. PLC writes it back to false. |
| `CV01.Status.Running` | `DI1` | discrete_input 0 | Boolean | R | IO |  | 1 |  | false | 1 | CV01 belt running. |
| `CV01.Status.DriveFault` | `DI2` | discrete_input 1 | Boolean | R | IO |  | 1 |  | false | 2 | CV01 drive tripped (see CV01.Status.DriveFaultCode). |
| `CV01.Sensors.EntryOccupied` | `DI3` | discrete_input 2 | Boolean | R | IO |  | 1 |  | false | 1 | Photo-eye at CV01 entry: a part occupies the first 100 mm. |
| `CV01.Sensors.PartAtPick` | `DI4` | discrete_input 3 | Boolean | R | IO |  | 1 |  | false | 1 | Photo-eye at the CV01 end stop: a part is at the pick position. |
| `CV02.Status.Running` | `DI5` | discrete_input 4 | Boolean | R | IO |  | 1 |  | false | 1 | CV02 belt running. |
| `CV02.Status.DriveFault` | `DI6` | discrete_input 5 | Boolean | R | IO |  | 1 |  | false | 2 | CV02 drive tripped (see CV02.Status.DriveFaultCode). |
| `CV02.Sensors.EntryOccupied` | `DI7` | discrete_input 6 | Boolean | R | IO |  | 1 |  | false | 1 | Photo-eye at the CV02 place zone: a part rear edge is within the first 150 mm. |
| `CV02.Sensors.ExitPE` | `DI8` | discrete_input 7 | Boolean | R | IO |  | 1 |  | false | 1 | Photo-eye at the CV02 exit: a part front is within the last 100 mm. |
| `RJ01.Status.NearFull` | `DI9` | discrete_input 8 | Boolean | R | IO |  | 1 |  | false | 1 | RJ01.Status.Count >= RJ01.Parameters.NearFullLevel. |
| `RJ01.Status.Full` | `DI10` | discrete_input 9 | Boolean | R | IO |  | 1 |  | false | 1 | RJ01.Status.Count >= RJ01.Parameters.Capacity. |
| `SF01.Status.EStopOk` | `DI11` | discrete_input 10 | Boolean | R | IO |  | 1 |  | true | 1 | E-stop chain closed (fail-safe: true = healthy). |
| `SF01.Status.GuardDoorClosed` | `DI12` | discrete_input 11 | Boolean | R | IO |  | 1 |  | true | 1 | Guard door closed. |
| `SF01.Status.SafetyOk` | `DI13` | discrete_input 12 | Boolean | R | IO |  | 1 |  | true | 1 | Safety relay output: e-stop OK, door closed and safety reset done. |
| `UT01.Status.AirPressureOk` | `DI14` | discrete_input 13 | Boolean | R | IO |  | 1 |  | true | 1 | UT01.Status.AirPressure >= 5.5 bar. |
| `CV01.Parameters.SpeedSetpoint` | `HRUS1` | holding 0 | UInt16 | RW | HMI | mm/s | 1 | 100..400 | 250 | 1 | CV01 belt speed setpoint. Out-of-range writes are clamped. |
| `CV02.Parameters.SpeedSetpoint` | `HRUS2` | holding 1 | UInt16 | RW | HMI | mm/s | 1 | 100..400 | 250 | 1 | CV02 belt speed setpoint. Out-of-range writes are clamped. |
| `RJ01.Parameters.Capacity` | `HRUS3` | holding 2 | UInt16 | RW | HMI | parts | 1 | 10..100 | 50 | 1 | Reject bin capacity (Full threshold). |
| `RJ01.Parameters.NearFullLevel` | `HRUS4` | holding 3 | UInt16 | RW | HMI | parts | 1 | 5..99 | 40 | 1 | NearFull threshold; clamped to Capacity - 1. |
| `CV01.Status.ActualSpeed` | `IRUS1` | input 0 | UInt16 | R | IO | mm/s | 1 | 0..400 | 0 | 1 | Belt speed: setpoint when running, 0 when stopped (no ramp). |
| `CV01.Status.MotorCurrent` | `IRUS2` | input 1 | Double | R | IO | A | 0.01 | 0..5 | 0 | 1 | Motor current: 1.20 A running, 2.60 A when jammed, 0 stopped. |
| `CV01.Status.DriveFaultCode` | `IRUS3` | input 2 | UInt16 | R | IO |  | 1 | 0..3 | 0 | 2 | Drive fault code. Enum: DriveFaultCode. |
| `CV01.Status.PartsOnConveyor` | `IRUS4` | input 3 | UInt16 | R | IO | count | 1 | 0..20 | 0 | 1 | Parts on CV01 including the one at the pick position. |
| `CV02.Status.ActualSpeed` | `IRUS5` | input 4 | UInt16 | R | IO | mm/s | 1 | 0..400 | 0 | 1 | Belt speed: setpoint when running, 0 when stopped (no ramp). |
| `CV02.Status.MotorCurrent` | `IRUS6` | input 5 | Double | R | IO | A | 0.01 | 0..5 | 0 | 1 | Motor current: 1.10 A running, 0 stopped. |
| `CV02.Status.DriveFaultCode` | `IRUS7` | input 6 | UInt16 | R | IO |  | 1 | 0..3 | 0 | 2 | Drive fault code. Enum: DriveFaultCode. |
| `CV02.Status.PartsOnConveyor` | `IRUS8` | input 7 | UInt16 | R | IO | count | 1 | 0..15 | 0 | 1 | Parts on CV02. |
| `RJ01.Status.Count` | `IRUS9` | input 8 | UInt16 | R | IO | parts | 1 | 0..101 | 0 | 1 | Parts in the reject bin (may exceed Capacity by 1, see scenario.md). |
| `UT01.Status.AirPressure` | `IRUS10` | input 9 | Double | R | IO | bar | 0.01 | 0..10 | 6.20 | 1 | Compressed air supply pressure (6.20 bar nominal). |
| `UT01.Status.ActivePower` | `IRUS11` | input 10 | Double | R | IO | kW | 0.01 | 0..10 | 0.60 | 1 | Cell active power from the energy meter (model in scenario.md). |
| `UT01.Status.EnergyTotal` | `IRUI12` | input 11-12 | Double | R | IO | kWh | 0.001 | 0..4294967.295 | 0 | 1 | Energy counter since controller start, UInt32 in Wh, high word first (Ignition default word order). |
| `IO01.Status.Heartbeat` | `IRUS14` | input 13 | UInt16 | R | IO | count | 1 | 0..65535 | 0 | 1 | I/O coupler heartbeat: +1 every 100 ms scan, wraps at 65535. |

## 8. Ignition connection notes

- OPC UA: one connection per cell, named like the cell (**`C03`**, from `gateway-config/opc-connection.template.json`,
  endpoint `opc.tcp://plc-c03:4840/ignition-lab/`, security None, host override `plc-c03`). The `nsu=` item paths in the
  `node_id` column work as-is in Ignition 8.3.10 (verified). `scripts/generate_tags.py` turns this CSV into the
  UDT `PIC200_Cell`, with `s=C01.` replaced by the parameter `s={CellId}.` (UInt32 becomes Int8, UInt16 becomes Int4).
  The `ignition_tag_path` column gives the member path relative to the instance (`[default]ANN/FIN/C01/` = the instance).
- Modbus TCP: one device per cell (`C03_IO01`, host `plc-c03`), port 502, unit id 1, default settings: one-based addressing (`HR1` = PDU 0) and high word first for 32-bit values.
  If `UT01.Status.EnergyTotal` looks wrong, toggle "Reverse Word Order": that is a deliberate learning point.
  Apply `modbus_scale` with tag scaling (linear, raw × scale).
- Keep `Sim.*` in a separate tag provider (`[sim]`), visible only to an instructor screen.
- Alarms are configured as Ignition tag alarms on the `C01.Alarms.*` bits and selected status bits (see fault-catalogue.md). The server does not implement OPC UA Alarms & Conditions.

## 9. Sources

- OPC 40001-1 Machinery: https://reference.opcfoundation.org/specs/OPC-40001-1/full
- OPC 40010-1 Robotics: https://reference.opcfoundation.org/specs/OPC-40010-1/full
- OPC 30050 PackML: https://reference.opcfoundation.org/specs/OPC-30050/full
- PackTags CntrlCmd codes: https://download.sew-eurodrive.com/download/html/26884623/en-EN/35730789387.html
- Ignition 8.3 Modbus addressing (prefixes C, DI, HRUS, IRUS, IRUI ...): https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/modbus/modbus-addressing
- Ignition 8.3 Modbus device settings (Zero-Based Addressing, Reverse Word Order): https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/modbus/connecting-to-modbus-device
