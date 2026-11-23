# Training week 50 (Mon 2026-12-07 to Fri 2026-12-11): programming the PLC

Goal: learn to program a PLC, about 2 hours a day, starting from zero: Siemens
S7-1500 with TIA Portal on days 1 to 4, a Schneider M221 on day 5. No
hardware: the PLC is simulated (S7-PLCSIM / PLCSIM Advanced, Machine Expert –
Basic simulator) on your Windows 11 PC. On day 4 the lab's Ignition
gateway connects to your simulated PLC.

The machine is **LT01, a leak test station** ([../lt01-leak-test.md](../lt01-leak-test.md)).
Its program is delivered complete and runs with a built-in plant model; you
build it from sources on day 2, then extend it: a stack light (day 2), a
marking unit (day 3), an HMI in Ignition (day 4). Why these tools and not
others, with sources: [plc-options.md](plc-options.md).

| Day | Theme | What you build |
|---|---|---|
| Mon | First steps | TIA Portal tour, hardware configuration, your first Ladder rungs, PLCSIM, watch tables |
| Tue | The LT01 station | the project from sources, run it in simulation, read it; **new component: stack light** (Ladder) |
| Wed | Extend the sequence | **new component: marking unit MK01** in the sequence, the I/O and the plant model (SCL) |
| Thu | Ignition meets the PLC | PLCSIM Advanced on the network, OPC UA from Ignition, a station view with commands and recipe |
| Fri | Schneider for comparison | the clamp-and-test cycle in Grafcet on an M221 simulator, read by Ignition over Modbus; wrap-up |

## How the week works

| Who | Does |
|---|---|
| You | everything in TIA Portal, PLCSIM, Machine Expert and Ignition |
| Claude (before Monday, done) | the LT01 program sources and tag table (`plc-training/siemens/lt01/`, pushed to `C:\PLC-Training` on the PC), the network path from the gateway to the PC (port proxy script, tested, [../system/plc-engineering.md](../system/plc-engineering.md)), this plan, the station spec |
| Claude (each day, after you) | reviews the sources you export (below), explains compiler messages, checks the network path on day 4, updates the docs, commits when you ask |

Rules:

- PLC code lives in a binary TIA project on the PC. So that it can be
  reviewed and versioned, end each day with **Generate source from blocks**
  (select the blocks, right-click) into `C:\PLC-Training\siemens\work\dayN\`;
  Claude fetches it with `scripts/plc-pc pull` into `plc-training/siemens/work/`.
  Also archive the project (*Project > Archive*) to `C:\PLC-Training\archives\`
  (stays on the PC).
- Stuck for more than 15 minutes: ask. Paste the compiler message, or export
  the block.
- Daily rhythm: 10 min reading the day's section, 90 min building, 20 min
  "Done when" checks.
- **Core** steps fit in 2 hours; **Stretch** steps are for spare time.
- The PC does the heavy work (TIA Portal, PLCSIM: 16 GB, as Siemens asks).
  The lab stack on the Linux host only matters on days 4 and 5 (`gateway`,
  `db`).

### Before Monday: accounts, downloads, installation (your part, about 3 hours)

These need your own accounts and licence acceptance, so Claude has not done them.

1. **Today or tomorrow: create a Siemens ID** on [SiePortal](https://sieportal.siemens.com/en-ww/home).
   Trial downloads are "for registered customers" and can wait for an approval:
   start early. If it is refused, switch to the CODESYS fallback (plc-options.md
   section 6) and tell Claude.
2. Check the PC has about 60 GB free on `C:` (it had 93 GB on 2026-11-23)
   and that Windows Update is done (TIA asks for recent security updates).
3. On the PC, download into `C:\Install`:
   - **SIMATIC STEP 7 (TIA Portal) V21 incl. Safety and S7-PLCSIM V21, TRIAL**
     (SIOS entry 109989774, or the V21.1 trial if offered: entry 110004178).
   - **SIMATIC S7-PLCSIM Advanced V8.0 TRIAL** (SIOS entry 109990051).
4. Install TIA Portal (products: STEP 7 Professional, S7-PLCSIM; WinCC is not
   needed), then PLCSIM Advanced. Accept the restarts. 1 to 2 hours.
5. Do **not** start TIA Portal yet: the 21-day trial licences (one-time
   activation each) start on Monday at the first start. 21 days from Monday
   covers this week and two more.
6. By Thursday: an se.com account and **EcoStruxure Machine Expert – Basic V1.4**
   (free) from the [Schneider download page](https://www.se.com/au/en/download/document/MachineExpertBasicV1_4/),
   installed on the same PC (20 min).

References for the week: Siemens' [Programming Guideline S7-1200/1500](https://support.industry.siemens.com/cs/ww/en/view/81318674),
the SCE modules for S7-1500 ([siemens.com/sce/documents](https://www.siemens.com/sce/documents)),
the TIA Portal help (F1 on any instruction), and for a fast video start the
free [TIA FAST Track](https://contentpath.siemens.com/tia-fast-track/part-one-tia-portal).

### Panorama E2 and Ignition, seen from the PLC

| You know (SCADA) | In the PLC |
|---|---|
| Polling: the SCADA reads every n ms | The **scan cycle**: read all inputs into the process image, run the program top to bottom, write all outputs, repeat (a few ms) |
| Variable / tag with an address | **PLC tag** (symbol table entry) with an absolute address `%I0.0`, `%QW2`, `%MW10`; data in **DBs** (data blocks) |
| S7 driver address `DB10.DBW2` (Panorama), `DB10,INT2` (Ignition) | the same byte offset in a **non-optimized** DB. Optimized DBs have no fixed offsets: reach them by name (OPC UA) |
| Script on value change | edge detection in the program (`R_TRIG`), every scan |
| Equipment template / UDT | **PLC data type** (UDT) for data, **function block** + instance DB for behaviour |
| Grafcet in the specification | Grafcet (SFC) on Schneider and S7-GRAPH on Siemens, or a step number with `CASE` in SCL (used here) |

---

## Monday: first steps (TIA Portal, Ladder, PLCSIM)

**Concepts:** scan cycle and process image; inputs `%I`, outputs `%Q`, memory
`%M`, data blocks; bit / byte / word addresses (`%I0.3`, `%IB0`, `%IW64`);
normally open and normally closed contacts, coils, set / reset; the seal-in
(latch) rung; TON / TP timers, CTU counter; online monitoring.
Read first: [TIA FAST Track part one](https://contentpath.siemens.com/tia-fast-track/part-one-tia-portal),
or SCE module 012-101 (S7-1500 hardware configuration).

### Core

1. **Start TIA Portal and activate the trial** (10 min). Accept the trial licence
   offered by the Automation License Manager. Portal view → *Create new
   project* `Basics` in `C:\Users\lab\Documents\Automation`.
2. **Hardware configuration** (20 min). *Configure a device* → *Controllers* →
   SIMATIC S7-1500 → CPU 1511-1 PN (newest order number and firmware offered).
   In the device view, drag from the hardware catalogue a DI 16x24VDC module
   to slot 2 and a DQ 16x24VDC/0.5A module to slot 3. Look at *Device
   overview*: the DI module got `I0.0..I1.7`, the DQ `Q0.0..Q1.7`. In the CPU
   properties, *System and clock memory*: enable the clock memory byte at
   `MB100` (`M100.5` is a 1 Hz blinker).
3. **PLC tags** (10 min). *PLC tags > Show all tags*: `Start` `%I0.0`,
   `Stop` `%I0.1` (an NC push button: TRUE when not pressed), `Motor`
   `%Q0.0`, `Lamp` `%Q0.1`, `Starts` (Int) `%MW10`.
4. **Ladder in OB1 "Main"** (30 min). Three networks:
   - Network 1, the seal-in: `Start` (NO) in parallel with `Motor` (NO), in
     series with `Stop` (NO contact on an NC button), coil `Motor`.
     Explain to yourself why the stop is wired NC.
   - Network 2: `Lamp` blinks while the motor runs: `Motor` AND `M100.5`.
   - Network 3: count the starts with a `CTU` on `Start` (counter instance as
     a single-instance DB when TIA asks), output `CV` to `Starts`.
5. **Simulate** (30 min). Select the PLC → *Start simulation* (S7-PLCSIM
   opens, a simulated CPU is created) → *Load*. In PLCSIM create a SIM table
   with `Start`, `Stop`, `Motor`, `Lamp`; set `Stop` TRUE (button not
   pressed), pulse `Start`. In TIA, *Monitoring on* (glasses icon) in OB1:
   watch the power flow. Then a *Watch table* with the same tags.
6. **Change while running** (10 min). Add a TON in network 2 so the lamp only
   blinks after the motor has run 5 s. Download (TIA downloads only the changed
   block; the CPU stays in RUN).

### Done when

- The motor latches on Start, stops on Stop, and stops if the Stop wire
  "breaks" (`Stop` FALSE).
- You can say where the counter's data lives (its instance DB) and what
  happens to `Starts` on a PLC STOP → RUN.

### Stretch

- The same logic in SCL: a new FC `Motor_SCL` (*Add new block* → FC, SCL),
  called from OB1. Compare with the LAD.
- Use `R_TRIG` to count only rising edges of `Start`; why is the CTU already
  edge-triggered?
- Add a second motor with interlock: never both on.

---

## Tuesday: the LT01 station from sources, and a stack light

**Concepts:** project structure (OB, FC, FB, DB, UDT), instance vs global DB,
optimized vs non-optimized DBs, external source files, SCL, a sequence as a
step number, cyclic interrupt OB, simulation mode. Read first:
[../lt01-leak-test.md](../lt01-leak-test.md) sections 2 to 5 and 8.

### Core

1. **New project `LT01`** (20 min). CPU 1511-1 PN; DI 16 (slot 2), DQ 16
   (slot 3), AI 8xU/I (slot 4: set its I/O start address to **64**, channel 0
   to 4..20 mA). CPU properties:
   - *System and clock memory*: clock byte `MB100`.
   - *Protection & Security*: **Full access (no protection)**, and under
     *Connection mechanisms* **Permit access with PUT/GET** (for Thursday).
   - *OPC UA > Server*: **Activate OPC UA server**; *Security*: allow the
     policy "No security" and **guest authentication** (lab only); *Runtime
     licenses > OPC UA*: select "SIMATIC OPC UA S7-1500 small" (for
     Thursday).
   - Project properties (*right-click project > Properties > Protection*):
     **Support simulation during block compilation**.
2. **Tag table** (5 min). *PLC tags > Add new tag table* `LT01`, open it,
   *Import* `C:\PLC-Training\siemens\lt01\LT01_tags.xlsx`. If TIA refuses the
   file, type the 13 tags of [../lt01-leak-test.md](../lt01-leak-test.md)
   section 3.
3. **Blocks from sources** (15 min). *External source files > Add new external
   file*: the six files of `C:\PLC-Training\siemens\lt01\`. Then, **in this
   order**, right-click → *Generate blocks from source*: 01 (types), 02, 03,
   04 (DBs), 05 (I/O FCs), 06 (Main: answer *Yes* to overwrite OB1).
   Give DB `LT01_HMI` the number **10** (*Properties > General*, number
   "manual").
4. **OB30 by hand** (5 min). *Add new block* → Organization block → *Cyclic
   interrupt*, name `LT01_SimCyclic`, language SCL, cycle time 100 ms. Paste
   the call written in the header comment of `06_LT01_Main.scl`.
5. **Compile** (10 min). Select the PLC → *Compile > Software (rebuild all
   blocks)*. Errors are expected to be rare but possible: the sources were
   written on Linux without TIA. Send Claude the message if one stays unclear.
6. **Run it** (20 min). *Start simulation*, load, RUN. Watch table
   `Watch_LT01`: `"LT01_Sim".Panel.Start`, `"LT01_HMI".Status.State`,
   `.Fault`, `.Result`, `.Pressure`, `.Decay`, `.CountTotal`, `.CountOk`,
   `.CountNok`, `"LT01_IO".Outputs`. Write `"LT01_Sim".Panel.Start` TRUE
   (*Modify > Modify to 1*): the cycle starts. Open `LT01_Seq` with
   monitoring on and follow the `CASE`. Inject `"LT01_Sim".Process.ClampStuck`
   and `"LT01_Sim".Panel.EStopPressed`; reset with `Panel.Reset`.
7. **Read the code** (15 min), with these questions: why does `LT01_Seq`
   never use a global DB? Where is `Y_Fill` written, and why only there?
   What would you change to run the station on the real machine? Why is
   `LT01_HMI` not optimized?
8. **New component: stack light** (30 min, in **Ladder**). The station gets a
   four-way stack light: red `H_Red` %Q0.4, amber `H_Amber` %Q0.5, green
   `H_Green` %Q0.6, buzzer `H_Buzzer` %Q0.7 (add the tags to table `LT01`).
   New FC `LT01_StackLight` (LAD), called in `Main` after `LT01_Seq`:
   - green steady when `Status.Running` and no stop pending; green flashing
     1 Hz (`M100.5`) when `Status.StopPending`;
   - amber steady when `Status.State = 0` (stopped, ready to start);
   - red steady while `Status.Fault <> 0`;
   - buzzer for the first 3 s of a fault (`TP` on the rising edge of
     "fault active").
   Use compare boxes (`CMP ==`, `CMP <>`) on `"LT01_HMI".Status.*`.

### Done when

- 10 parts tested, part 12 NOK on decay (`Result` 3, `Decay` ≈ 75 mbar),
  tight parts `Decay` ≈ 9 mbar, `CycleTime` ≈ 8.3 s
  (reference values: [../lt01-leak-test.md](../lt01-leak-test.md) section 10).
- Clamp stuck → fault 10 or 11, state 90; reset brings it back to 0.
- The stack light shows the right colour in Stopped, Running, stop pending
  (`Panel.StopPressed` during a test) and Faulted.
- Sources exported to `plc-training/siemens/work/day2/`.

### Stretch

- `"LT01_Sim".Enable` FALSE: the station now reads the real `%I`. Drive it
  by hand from the PLCSIM SIM table (part present, clamp switches, pressure
  as an integer). You are the plant: see why a plant model pays off.
- Set `Process.GrossEvery` to 5 and watch gross leaks.

---

## Wednesday: a new component in the sequence: marking unit MK01

**Concepts:** changing a UDT and what it does to DBs and downloads (instance
DBs re-initialised), adding a step to a sequence, supervision timeouts,
extending the plant model, `Download without reinitialization` (stretch).
Read first: the `CASE` of `LT01_Seq` again, and the SCE module on global DBs
(032-600) if DBs are still unclear.

The new requirement: every part that tests OK is marked with a pin marker
before it is released, so packing can see it was tested. MK01 is a
pneumatic pin: valve `Y_Mark` %Q1.0 (TRUE pushes the pin out), sensor
`B_MarkerUp` %I1.1 (TRUE when the pin is retracted).

### Core

1. **Interface** (20 min). Edit the UDTs in TIA (they are regular blocks now):
   - `LT01_typeIn` + `B_MarkerUp : Bool`; `LT01_typeOut` + `Y_Mark : Bool`;
   - `LT01_typeRecipe` + `MarkEnable : Bool := TRUE`, `MarkTime : Time := T#300MS`;
   - `LT01_typeStatus` + `CountMarked : DInt` **at the end**.
   - Tags `Y_Mark` %Q1.0 and `B_MarkerUp` %I1.1; extend `LT01_IoRead` and
     `LT01_IoWrite`.
2. **Sequence** (40 min), in `LT01_Seq`: a new step **55 Marking**, entered
   from step 50 when the result is OK and `Recipe.MarkEnable`, else straight
   to 60 as before:
   - `Y_Mark` on until `B_MarkerUp` is FALSE, then held `MarkTime`, then off;
   - wait for `B_MarkerUp` TRUE, count `Status.CountMarked`, go to 60;
   - pin not down or not back within 1 s: **fault 13 "marker stuck"**.
   `Y_Mark` is written in the *Outputs* region like the others (from the
   step and a sub-state), and the clamp must stay closed during step 55.
3. **Plant model** (20 min), in `LT01_ProcessSim`: a pin position with a
   0.15 s stroke driven by `Cmd.Y_Mark`, `Field.B_MarkerUp` TRUE when
   retracted; a new `LT01_typeSimProcess.MarkerStuck : Bool` that blocks it.
4. **Download** (10 min). TIA warns that the changed UDTs re-initialise the
   DBs that use them: the PLC goes to STOP and the counters restart from 0.
   Accept (this is a test bench).
5. **Test** (20 min), then export the sources to `work/day3/`.

### Done when

- `CountMarked` = `CountOk` after 15 parts; NOK parts are not marked.
- With `MarkEnable` FALSE, no marking and the cycle is 0.6 s shorter.
- `MarkerStuck` TRUE → fault 13 in step 55, the part is vented and released
  after reset.
- The stack light still works (you did not touch it: why?).

### Stretch

- Look at `LT01_HMI` in the DB editor: `Status` grew by 4 bytes, so every
  `Recipe` offset moved by 4. What does that do to an S7-driver tag
  `DB10,REAL38`? (Thursday's answer: use OPC UA, or keep offsets stable with a
  reserve.)
- *Download without reinitialization*: give `LT01_HMI` a memory reserve
  (block properties) and add a member without losing the counters.
- Rewrite the sequence of step 55 as a small FB `LT01_Marker` with its own
  steps, called from `LT01_Seq` (multi-instance).

---

## Thursday: Ignition meets the PLC

**Concepts:** PLCSIM Advanced instance in TCP/IP mode, the CPU's OPC UA
server, NodeIds of an S7-1500, the network path PC → Docker
([../system/plc-engineering.md](../system/plc-engineering.md)); in Ignition: OPC UA connection,
UDT over OPC items, a station view, writing pulse commands. The Ignition part
uses what you learned in week 48.

### Core

1. **PLCSIM Advanced instance** (20 min). Start *S7-PLCSIM Advanced V8.0
   Control Panel* (or the Advanced instance from the PLCSIM V21 UI): online
   access **PLCSIM Virtual Eth. Adapter**, TCP/IP communication `<Local>`,
   instance name `LT01`, IP **192.168.0.1** / 255.255.255.0, PLC type
   "Unspecified CPU 1500", *Start*. Accept the 21-day trial licence. In TIA,
   set the CPU's PROFINET interface to 192.168.0.1 and load into the instance
   through the *Siemens PLCSIM Virtual Ethernet Adapter*. RUN.
2. **Open the path** (5 min). In an administrator PowerShell on the PC:
   `C:\PLC-Training\windows\plcsim-portproxy.ps1 -AllowFrom <lab host LAN IP>,<lab host Tailscale IP>`
   (or ask Claude to run it over SSH; it knows the addresses). It forwards
   102, 4840 and 502 of the PC to 192.168.0.1 and lets only the lab host in.
   Then ask Claude to check from the gateway's network that
   `opc.tcp://<PLC_PC_HOST>:4840` answers (`PLC_PC_HOST` in `.env`).
3. **OPC UA connection in Ignition** (15 min). Gateway web UI → *Connections >
   OPC > Connections* → new OPC UA connection `LT01`, endpoint
   `opc.tcp://<PLC_PC_HOST>:4840`, security policy None, anonymous. The
   discovery returns the PLC's own endpoint `opc.tcp://192.168.0.1:4840`,
   which the gateway cannot reach: in the connection's advanced settings set
   **Host Override** to `<PLC_PC_HOST>`. Status Connected. If the gateway
   rejects the PLC's certificate, trust it under *OPC UA > Security > Server*
   (week 48, C06).
4. **Tags** (25 min). In the Designer's OPC browser, find `LT01_HMI` under
   the PLC (expect NodeIds like `ns=3;s="LT01_HMI"."Status"."State"`). Build a
   UDT `LT01_Station` (parameter `OpcServer`) with `Status/*`, `Cmd/*`,
   `Recipe/*` members, one instance `[default]ANN/FIN/LT01`. Check values
   change while the station runs.
5. **View `Station/LT01`** (40 min): state as text (map transform: 10
   WaitPart, 30 Filling, ...), fault as text, pressure with a bar or gauge
   (0..7 bar), last result OK / NOK coloured, decay, cycle time, counters;
   buttons Start, Stop, Reset, Reset counters (each writes TRUE: the PLC clears
   it); recipe `TestPressure` and `MaxDecay` as numeric entries; the stack
   light as four indicators bound to the `H_*` outputs (OPC: `%Q` area, or
   copy them into `Status` first). Add a link from the area overview.

### Done when

- The view follows the cycle live; Start / Stop / Reset work from the HMI.
- `MaxDecay` set to 5 mbar from the HMI → tight parts (9 mbar) turn NOK. Set
  it back to 20.
- A fault injected in TIA (`Panel.EStopPressed`) shows in the HMI; Reset
  from the HMI clears it once the e-stop is released.

### Stretch

- **Legacy Siemens driver**: device `LT01_S7` (*Siemens S7-1500*, host
  `<PLC_PC_HOST>`, port 102), tags with absolute addresses from
  [../lt01-leak-test.md](../lt01-leak-test.md) section 9 **after correcting
  them for Wednesday's 4-byte shift**. Compare with OPC UA: browsing, names,
  what breaks when the DB changes.
- **MES record**: a tag change script on `Status/CountTotal` that inserts the
  last result (time, result, decay, cycle time) into a table `mes.leak_test`
  (named query; ask Claude to add the table to `db/init`).
- Watch the gateway's and the PC's clocks: stale values in the Designer can
  come from clock skew (plc-options.md section 2.5).

---

## Friday: Schneider for comparison, and wrap-up

**Concepts:** another vendor's view of the same ideas: Machine Expert – Basic,
M221 memory (`%I0.x`, `%Q0.x`, `%M`, `%MW`), Grafcet (SFC) steps and
transitions, the simulator's I/O manager, Modbus TCP server of the M221.
Read first: Machine Expert – Basic Operating Guide (EIO0000003281),
chapters on Grafcet (SFC) and on the simulator.

The plant is now **LT02**, a second leak tester built by another integrator
on a Schneider M221. No plant model: in the simulator, you are the machine.

### Core

1. **Project** (15 min). Machine Expert – Basic → *Create new project* →
   controller **TM221CE16T** (Ethernet, 9 DI, 7 DQ, 2 analog inputs).
   I/O: `%I0.0` start, `%I0.1` stop (NC), `%I0.2` part present, `%I0.3`
   clamp closed, `%I0.4` clamp open; `%Q0.0` clamp, `%Q0.1` fill, `%Q0.2`
   vent; analog `%IW0.0` pressure (0..1000 = 0..10 bar). Give them symbols.
2. **Grafcet (SFC) POU** (45 min). The LT01 cycle without stabilise/measure
   details: step 1 wait part → 2 clamp → 3 fill (until `%IW0.0 >= 600`) →
   4 hold 5 s (timer) → 5 vent (until `%IW0.0 < 20`) → 6 unclamp → 1.
   Actions in Ladder or as step actions; outputs set from the active steps
   (`%X2`, `%X3` ...). A rung counts finished parts into `%MW10`.
3. **Simulate** (20 min). *Commissioning > Launch simulator*, download, RUN.
   In the I/O manager, play the machine: part present, clamp switches,
   pressure slider. Watch the active step move.
4. **Modbus to Ignition** (25 min). Copy the active step number to `%MW0`,
   the part counter to `%MW10`, the pressure to `%MW2` (rungs with
   operation blocks). On the PC (administrator):
   `C:\PLC-Training\windows\plcsim-portproxy.ps1 -Ports @() -Map "5502=127.0.0.1:502" -AllowFrom <lab host addresses>`
   (or ask Claude). Ignition: Modbus TCP device `LT02_M221`, host
   `<PLC_PC_HOST>`, port 5502. Test tags `HR0`, `HR1` to
   find the offset (zero-based or not), then `%MW0`, `%MW2`, `%MW10`. Read
   only words: the M221 server has no coils and no mask write
   (plc-options.md section 3).
5. **Wrap-up** (15 min): fill the comparison table below with your own words,
   and the "next steps" list. Claude reviews, updates the docs and commits.

| | Siemens S7-1500 / TIA Portal | Schneider M221 / Machine Expert – Basic |
|---|---|---|
| Languages used | | |
| Data organisation | | |
| Sequence | | |
| Simulation | | |
| Path to Ignition | | |
| What you liked / disliked | | |

### Done when

- The Grafcet runs a full cycle driven by hand in the simulator.
- Ignition shows the step number, pressure and part count of the M221.

### Stretch

- Write the same cycle in Ladder only (step bits with set / reset) and
  compare readability with the Grafcet.
- Machine Expert's simulator accepts one data client: connect a second
  Modbus client and see what happens.

---

## After the week

- Trials: TIA Portal and PLCSIM Advanced run until about 2026-12-27 (21 days
  from activation on Monday 2026-12-07, one-time). Machine Expert – Basic is
  free. Do not reset trials.
- Possible follow-ups: LT01 in Ignition for good (the UDT and view kept in the
  `plant` project, MES table for test results); fault handling with the
  ProDiag / Program_Alarm instructions and Ignition alarms; a second LT
  station from the same FB (multi-instance, instance DB per station); the
  CODESYS port of `LT01_Seq` (plc-options.md section 6); S7-GRAPH for the
  sequence instead of `CASE`.
