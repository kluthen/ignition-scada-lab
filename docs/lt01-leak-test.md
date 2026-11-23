# LT01: leak test station (PLC training machine)

The machine of training week 50 ([training/week-50.md](training/week-50.md)).
Unlike the six cells, whose controllers are Python simulators, LT01 is
controlled by a real PLC program: a Siemens S7-1500 program in SCL, run on
S7-PLCSIM / PLCSIM Advanced on the lab's Windows PLC engineering station
([system/plc-engineering.md](system/plc-engineering.md)). The program is delivered complete
(`plc-training/siemens/lt01/`); the week's exercises extend it.

This document is the station's specification, the same role scenario.md
plays for a cell: the code cites its sections.

## 1. Context

Brevent's customer for the large housing HSG-C45 (tractor hydraulics) now
asks for a 100 % leak test. Brevent bought a semi-automatic leak test
station, **LT01**, placed next to the packing conveyor of the finishing area.
An operator puts a housing in the test nest; the station clamps it, fills it
with air, measures the pressure decay and releases it with an OK / NOK result.
The integrator delivered the station with a Siemens CPU 1511-1 PN and a
simulation mode for commissioning without the machine.

ISA-95: `BRV / ANN / FIN / LT01`.

## 2. Equipment

```
            supply 7 bar ──[B_AirOK]──┬──[Y_Fill]──┐
                                      │            ├── test volume ── PT01 (0..10 bar)
                                      │  [Y_Vent]──┘        │
                                      │     │          part in the nest
                                      │   atmosphere   [B_PartPresent]
                                      └──[Y_ClampClose]── clamp cylinder
                                                          [B_ClampOpen] [B_ClampClosed]
  panel: PB_Start  PB_Stop (NC)  PB_Reset  SW_Auto      safety relay: EStopOK
```

| Code | Device | Role |
|---|---|---|
| Nest | test fixture with a seal | the housing's ports are sealed when clamped |
| Clamp | pneumatic cylinder, monostable valve, two end switches | holds the part against the seal; stroke 0.6 s |
| Y_Fill / Y_Vent | 2/2 solenoid valves | connect the test volume to the supply / to atmosphere |
| PT01 | pressure transmitter 0..10 bar, 4..20 mA | test pressure, read as 0..27648 by the analog module |
| B_AirOK | pressure switch on the supply | supply ≥ 6.5 bar |
| Panel | start, stop (NC), reset push buttons, auto / manual selector | |
| Safety relay | e-stop circuit, feedback contact | safety is hard-wired; the PLC only reads its state |

## 3. I/O list and PLC tags (tag table "LT01")

Hardware: CPU 1511-1 PN; DI 16x24VDC (I0.0..I1.7); DQ 16x24VDC/0.5A
(Q0.0..Q1.7); AI 8xU/I (start address **64**, channel 0 = IW64, 4..20 mA).
`plc-training/siemens/lt01/LT01_tags.xlsx` holds the same table for import.

| Tag | Type | Address | Meaning |
|---|---|---|---|
| PB_Start | Bool | %I0.0 | start push button (NO) |
| PB_Stop | Bool | %I0.1 | stop push button (**NC**: TRUE = not pressed) |
| PB_Reset | Bool | %I0.2 | fault reset (NO) |
| EStopOK | Bool | %I0.3 | safety relay feedback, TRUE = healthy |
| SW_Auto | Bool | %I0.4 | TRUE = automatic |
| B_PartPresent | Bool | %I0.5 | part in the nest |
| B_ClampClosed | Bool | %I0.6 | clamp closed |
| B_ClampOpen | Bool | %I0.7 | clamp open |
| B_AirOK | Bool | %I1.0 | air supply OK |
| PT01_Raw | Int | %IW64 | test pressure, 0..27648 = 0..10 bar |
| Y_ClampClose | Bool | %Q0.0 | clamp valve, TRUE closes |
| Y_Fill | Bool | %Q0.1 | fill valve |
| Y_Vent | Bool | %Q0.2 | vent valve |
| (free) | | %Q0.3..Q1.7, %I1.1..I1.7 | for the extensions of the week (stack light, marker) |

NC stop button and "healthy = TRUE" safety feedback are deliberate: a broken
wire must stop the machine, not start it (wire-break safe).

## 4. Modes and commands

- **Automatic** (`SW_Auto` TRUE): Start (push button or HMI `Cmd.Start`)
  starts the cycle loop from step 0.
- **Stop** (push button, HMI `Cmd.Stop`, or selector to manual): in step 10
  the station stops at once; during a test it finishes the part
  (`StopPending`) then stops.
- **Manual** (`SW_Auto` FALSE): no automatic start. Manual jog of the valves
  is not implemented (an exercise).
- HMI commands live in `"LT01_HMI".Cmd` and are **pulses**: the HMI writes
  TRUE, the PLC clears the bit once read.

## 5. Sequence (FB "LT01_Seq", `Status.State`)

| Step | Name | Outputs | Leaves when | To |
|---|---|---|---|---|
| 0 | Stopped | vent | start edge, auto, stop not pressed | 10 |
| 10 | WaitPart | vent | part present and clamp open / stop | 20 / 0 |
| 20 | Clamping | clamp, vent | clamp closed / 3 s | 30 / fault 10 |
| 30 | Filling | clamp, fill | pressure ≥ `Recipe.TestPressure` / `FillTimeout` | 40 / 60 with result 2 (gross leak) |
| 40 | Stabilising | clamp | `StabTime` elapsed, store p_start | 50 |
| 50 | Measuring | clamp | `MeasTime` elapsed: decay = (p_start − p) × 1000 mbar, OK if ≤ `MaxDecay` | 60 |
| 60 | Venting | clamp, vent | pressure < `VentPressure` / 3 s | 70 / fault 12 |
| 70 | Unclamping | vent | clamp open: count the part, publish result and cycle time / 3 s | 80 / fault 11 |
| 80 | Unload | vent | part removed | 10, or 0 if a stop is pending |
| 90 | Faulted | vent | reset edge and no active cause | 0 |

Outputs are written in one place each, from the step number (section
"Outputs" of the FB), never inside the CASE: one line tells why a valve is on.
The vent is open in every step that does not hold pressure, which is also the
safe state.

## 6. Faults (`Status.Fault`)

| Code | Fault | Detected | Reset |
|---|---|---|---|
| 1 | emergency stop | `EStopOK` FALSE, any step | e-stop released, then reset |
| 2 | air supply lost | `B_AirOK` FALSE, any step | air back, then reset |
| 10 | clamp close timeout | step 20, 3 s | reset |
| 11 | clamp open timeout | step 70, 3 s | reset |
| 12 | vent timeout | step 60, 3 s | reset |

A gross leak (pressure not reached) is a **part result**, not a fault: the
station vents and goes on.

## 7. Recipe (`"LT01_HMI".Recipe`)

| Parameter | Default | Unit |
|---|---|---|
| TestPressure | 6.0 | bar |
| MaxDecay | 20.0 | mbar over MeasTime |
| VentPressure | 0.2 | bar |
| FillTimeout | 5 s | |
| StabTime | 2 s | |
| MeasTime | 3 s | |

## 8. Simulation mode (FB "LT01_ProcessSim", DB "LT01_Sim")

`"LT01_Sim".Enable` TRUE (default) makes FC `LT01_IoRead` take the inputs
from `"LT01_Sim".Field` instead of `%I`. The plant model runs in OB30
(cyclic interrupt, 100 ms) and reads the valve commands `"LT01_IO".Outputs`.
The station logic does not know it is simulated.

| Model | Behaviour |
|---|---|
| Operator | places a part `Process.PartInterval` (4 s) after the nest is empty and the clamp open; removes a tested part 1.5 s after the clamp opens (`Process.AutoUnload`) |
| Part pattern | part n is a small leak if n mod `LeakEvery` (12) = 0, a gross leak if n mod `GrossEvery` (40) = 0, tight otherwise; reproducible |
| Clamp | 0.6 s stroke; does not move without air or with `Process.ClampStuck` |
| Pressure | filling: dp/dt = 1.5 (7 − p); leak: dp/dt = −k p with k = 0.0005 /s (tight), 0.004 /s (small), 2 /s (gross), 50 /s without seal; vent adds 4 /s |
| Transmitter | `PT01_Raw` = p / 10 × 27648 |
| Panel | `Panel.Start` / `Panel.Reset`: write TRUE, held 0.5 s, then released by the model; `Panel.StopPressed`, `Panel.EStopPressed` stay until you clear them; `Panel.Auto` = selector |
| Faults to inject | `Process.AirFail`, `Process.ClampStuck`, `Panel.EStopPressed` |

## 9. Program structure and data

| Block | Type | Role | Source file |
|---|---|---|---|
| `LT01_typeIn`, `LT01_typeOut`, `LT01_typeCmd`, `LT01_typeStatus`, `LT01_typeRecipe`, `LT01_typeSim*` | PLC data types (UDT) | interfaces | 01_LT01_types.udt |
| `LT01_ProcessSim` | FB | plant model | 02_LT01_ProcessSim.scl |
| `LT01_Seq` | FB | sequence, modes, faults, counters (no global access) | 03_LT01_Seq.scl |
| `LT01_IO` | global DB, optimized | station I/O image | 04_LT01_data.db |
| `LT01_HMI` | global DB, **not optimized, number 10, retentive** | SCADA interface: Cmd, Status, Recipe | 04_LT01_data.db |
| `LT01_Sim` | global DB | simulation switch, panel, settings, simulated field | 04_LT01_data.db |
| `LT01_Seq_DB`, `LT01_ProcessSim_DB` | instance DBs | FB memory | 04_LT01_data.db |
| `LT01_IoRead`, `LT01_IoWrite` | FC | the only blocks that touch %I / %Q | 05_LT01_IO.scl |
| `Main` | OB1, program cycle | IoRead → Seq → IoWrite | 06_LT01_Main.scl |
| `LT01_SimCyclic` | OB30, cyclic interrupt 100 ms | calls the plant model | created by hand (one line, in 06_LT01_Main.scl) |

`"LT01_HMI"` layout (non-optimized; check against the "Offset" column of
the DB editor after compiling). Ignition legacy Siemens driver addresses
with the DB as number 10:

| Member | Offset | Ignition S7 address |
|---|---|---|
| Cmd.Start / Stop / Reset / ResetCounters | 0.0 / 0.1 / 0.2 / 0.3 | `DB10,X0.0` … `DB10,X0.3` |
| Status.State | 2 | `DB10,INT2` |
| Status.Fault | 4 | `DB10,INT4` |
| Status.Result | 6 | `DB10,INT6` |
| Status.Running / StopPending | 8.0 / 8.1 | `DB10,X8.0` / `DB10,X8.1` |
| Status.Pressure | 10 | `DB10,REAL10` |
| Status.Decay | 14 | `DB10,REAL14` |
| Status.CycleTime | 18 | `DB10,REAL18` |
| Status.StepTime | 22 | `DB10,REAL22` |
| Status.CountTotal / CountOk / CountNok | 26 / 30 / 34 | `DB10,DINT26` … |
| Recipe.TestPressure / MaxDecay / VentPressure | 38 / 42 / 46 | `DB10,REAL38` … |
| Recipe.FillTimeout / StabTime / MeasTime | 50 / 54 / 58 (Time = DInt ms) | `DB10,DINT50` … |

With OPC UA, the same data is browsable by name under the CPU's server
(`ServerInterfaces` / `DataBlocksGlobal` › `LT01_HMI`), optimized or not.

## 10. Expected behaviour in simulation (reference values)

From a Python mirror of the two FBs (dt 0.1 s), default settings, 10 minutes
from Start:

| Check | Expected |
|---|---|
| Throughput | about 4.3 parts/min (cycle 8.3 s + 4 s part interval + 1.5 s unload) |
| Tight part | Result 1, Decay ≈ 9 mbar, CycleTime ≈ 8.3 s |
| Small leak (parts 12, 24, 36) | Result 3, Decay ≈ 75 mbar |
| Gross leak (part 40) | Result 2, pressure stalls near 3 bar, CycleTime ≈ 6.7 s |
| 10 min | 43 parts: 39 OK, 3 NOK decay, 1 NOK gross |
| `Process.ClampStuck` during a cycle | fault 10 or 11 depending on the step, State 90; reset after clearing it → State 0 |
| `Panel.EStopPressed` | fault 1 at once, vent open, clamp opens |
