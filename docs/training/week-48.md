# Training week 48 (Mon 2026-11-23 to Fri 2026-11-27): you at the controls

Goal: learn Ignition by changing this lab yourself, about 2 hours a day. You
make every Ignition change: gateway web UI and Designer, no scripts doing it
for you. Claude has prepared the simulator and reviews your work each day.

| Day | Theme | What you build |
|---|---|---|
| Mon | UI changes in existing screens | reject % on the cell tile, a theme switch, your first style class |
| Tue | A new view | an Orders page: named query, table, filters, order history popup |
| Wed | Commission a sixth cell | C06 by hand: OPC UA connection, Modbus device, MES master data, UDT instances |
| Thu | Bind a new device: tags | the andon station AN01 in the cell UDT (six cells at once), an alarm |
| Fri | Bind a new device: screens | a stack light view, an andon panel with acknowledge, then the wrap-up |

## How the week works

| Who | Does |
|---|---|
| You | every change in Ignition. Save in the Designer when a step works. |
| Claude (before Monday, done) | the simulator side: controller `plc-c06` running, andon station AN01 in all six controllers, smoke test passing. Nothing on the Ignition side. |
| Claude (each day, after you) | reviews your `git diff`: explains what the Designer wrote, flags problems, updates the system docs (`docs/system/*.md`), commits and pushes when you ask |

Rules for the week:

- Claude does not edit views, tags or gateway config while you work, so the
  Designer never fights with an outside edit.
- Stuck for more than 15 minutes: ask. Claude can read the gateway log
  (`rtk proxy docker compose logs gateway`), the controller logs and the files
  the Designer saved.
- The daily rhythm: 10 min reading the day's section, 90 min building, 20 min
  checking against "Done when", then ask for the review.
- The **core** steps fit in 2 hours. **Stretch** steps are for when you have time left.

### Before Monday: tools

1. Designer Launcher: http://127.0.0.1:8088 → *Get Designer*. Log in with the
   gateway admin user (`.env`), open project **plant**.
2. Know where things are in the Designer: *Project Browser* (views, named
   queries, scripts, styles), *Tag Browser*, *Property Editor*, *Perspective
   Component palette*, *OPC Browser*. Preview mode is the play button of the
   view workspace.
3. The HMI in a browser: http://127.0.0.1:8088/data/perspective/client/plant.
   Every Designer save shows there at once.
4. After a save, look at `git status`: views are
   `ignition/data/projects/plant/com.inductiveautomation.perspective/views/<path>/view.json`.
   Reading the JSON the Designer writes is a fast way to understand a view.

References: the Ignition 8.3 user manual (docs.inductiveautomation.com) and the
free Inductive University videos (Perspective, Tags, UDTs, Alarming), plus the
lab's own [hmi.md](../system/hmi.md), [mes.md](../system/mes.md) and
[panorama-e2-to-ignition.md](../system/panorama-e2-to-ignition.md).

---

## Monday: UI changes in existing screens

**Concepts:** component properties (`props`, `custom`, `meta`, `position`),
bindings (tag, property, expression), transforms (map, format), property
change scripts, session properties, style classes, Preview mode.
**Panorama E2:** animations on a mimic object, and the shared styles of the
application.

Open `Cell/Tile` (the tile of one cell on the overview). Look first at its
`custom` properties: each one is an indirect tag binding on
`[default]ANN/FIN/{cell}/...`, with `{cell}` taken from `view.params.cell`. The
labels then bind to expressions over these custom properties.

### Core

1. **Reject % on the tile** (30 min).
   - Add a Label `RejectPct` under `Counts` (drag from the component palette;
     order it in the Project Browser tree).
   - `props.text`: an expression binding that shows the reject share of the
     active order, for example
     `if({view.custom.good} + {view.custom.rejects} = 0, "", numberFormat(100.0 * {view.custom.rejects} / ({view.custom.good} + {view.custom.rejects}), "0.0") + " % rejects")`.
   - `props.style.color`: an expression binding that turns orange (`#eb6834`)
     above 4 % and stays the normal text colour otherwise.
   - Check in Preview mode, then on the overview in the browser: C04 (worn
     gauge, 1 in 15) should be orange, C02 (1 in 40) not.
2. **Theme switch in the header** (30 min).
   - Open `Shared/Header`, add a Toggle Switch with the text "Dark".
   - Add a property change script on its `props.selected`: right-click the
     property → *Add Change Script*:
     `self.session.props.theme = "dark" if currentValue.value else "light"`.
   - Try it in the browser. Several parts of the HMI keep their light grey:
     their colours are hard-coded in the views. That is what style classes
     and theme variables are for (next step).
3. **Your first style class** (40 min).
   - Project Browser → *Perspective → Styles* → New Style `Card`: background
     `var(--neutral-10)`, border 1 px `var(--neutral-30)`, radius 6 px, a light
     shadow. The `var(--…)` values are theme variables, so they change with the theme.
   - Apply it to the root of `Cell/Tile`: `props.style.classes` = `Card`, and
     remove the hard-coded `backgroundColor`, `borderColor` and `borderRadius`
     from its `props.style`, or they win over the class.
   - Apply it to the KPI tiles of `Kpi/Area` as well. One change in the style
     class now changes every tile.

### Stretch

- The tile's `State` label colour is a map transform (state number → colour).
  Read it, then make the Held colour (11) match the orange of the cell page.
- Add a tooltip to the tile (`meta.tooltip`) with the cell's notes.

**Done when:** the tile shows the reject %, coloured above 4 %; the theme
switch works; tiles use the `Card` class. `git status` shows `Cell/Tile`,
`Shared/Header`, `Kpi/Area` and a new style resource.

---

## Tuesday: a new view, the Orders page

**Concepts:** named queries (parameters, testing), query bindings, the Table
component (data, columns, selection, events), dropdowns, page configuration
(URL routes), popups with parameters (`system.perspective.openPopup`).
**Panorama E2:** a new mimic with a list fed from a database, and a pop-up
window opened with a parameter.

Data: table `mes.work_order` (order_id, cell, product_code, target_qty,
good_qty, reject_qty, status, created_at, started_at, ended_at; statuses
Planned, Released, Dispatched, Running, Completed, ClosedShort, Cancelled) and
`mes.order_event` (the status history of each order: status, cell, by_user,
at, comment).

### Core

1. **Named query `Orders/List`** (20 min). Project Browser → *Named Queries* →
   New, database `mes`, parameters `status` and `cell` (String, `''` = all):

   ```sql
   SELECT order_id, cell, product_code, target_qty, good_qty, reject_qty, status,
          created_at, started_at, ended_at
   FROM mes.work_order
   WHERE (:status = '' OR status = :status) AND (:cell = '' OR cell = :cell)
   ORDER BY seq DESC
   LIMIT 200
   ```

   Run it in the query's *Testing* tab with both parameters empty, then with
   `Running`.
2. **View `Orders/List`** (50 min). New view, Flex container, column direction.
   - A filter row: a Dropdown for the status (static options: All = `''`,
     then the statuses), and a Dropdown for the cell (options from the named
     query `Area/Cells`, as on the KPI page: look at how `Kpi/Area` does it).
   - A Table: `props.data` is a query binding on `Orders/List`, with its
     parameters bound to the two dropdowns' `props.value`, polling every 10 s.
   - Table columns (`props.columns`): titles, widths, a date format for the
     three timestamps, and the status column rendered with a colour per status
     (the same green / blue-grey as the tiles).
3. **Route and navigation** (15 min). Project Browser → *Perspective → Page
   Configuration*: add the page `/orders` → view `Orders/List`. In
   `Shared/Header`, copy the KPI button and make it navigate to `/orders`.
4. **Order history popup** (35 min).
   - Named query `Orders/Events` (parameter `orderId`): the `mes.order_event`
     rows of that order, oldest first.
   - View `Orders/Detail` with a parameter `orderId`: a title and a table on
     `Orders/Events`.
   - On the Orders table, configure the event `onRowClick`: a script action
     `system.perspective.openPopup("orderDetail", "Orders/Detail", params={"orderId": event.value["order_id"]}, title="Order history", modal=True)`.

### Stretch

- An "Export CSV" button: `system.dataset.toCSV` on the table data, then
  `system.perspective.download("orders.csv", csv)`.
- Show the reject % per order as a computed column (in the SQL, or a script
  transform on the binding: compare the two).

**Done when:** `/orders` lists the orders, both filters work, clicking an order
opens its history. A ClosedShort order shows the "closed short" event with its
comment.

---

## Wednesday: commission the sixth cell C06

**Concepts:** OPC UA client connections, device drivers (Modbus TCP), the OPC
Browser, tag quality, UDT instances and parameters, MES master data, and
everything that follows by itself from a UDT instance (history, MES scripts,
autopilot, HMI, KPIs, export).
**Panorama E2:** declaring a new equipment's communication, then an instance of
an existing class.

C06 (bay 6, serial PIC200-26-0006, qualified for part types 2 and 3) was
delivered last week. Its controller already runs: `docker compose ps plc-c06`
shows it, and its log says the program is running, state Stopped. Ignition
does not know it yet. C01..C05 are your references: open their settings side
by side with what you create.

### Core

1. **OPC UA connection `C06`** (25 min). Gateway web UI → *Connections → OPC
   connections* → create an OPC UA connection.
   - Endpoint `opc.tcp://plc-c06:4840/ignition-lab/`, security policy None,
     mode None, anonymous.
   - **Host override `plc-c06`.** The simulated server advertises `0.0.0.0` in
     its endpoints; without the override the gateway tries to connect to
     itself.
   - If the connection faults with *"Unable to retrieve KeyPair for alias
     'client'"*, set the keystore alias password to `password`, Ignition's
     default.
   - Done when the status is Connected.
2. **Modbus device `C06_IO01`** (15 min). *Connections → Devices* → create a
   Modbus TCP device, host `plc-c06`, port 502. Keep the default one-based
   addressing (the registry's `C1`, `DI4`, `HRUS3` addresses assume it).
   Status Connected.
3. **Look before you bind** (15 min). Designer → OPC Browser: open `C06` →
   `Machines/C06/Status/StateCurrent`, and *Ignition OPC UA Server → Devices →
   C06_IO01*. Compare the node ids with the item paths of a member of the UDT
   `PIC200_Cell` (Tag Browser → *UDT Definitions*).
4. **MES master data** (15 min). Designer → *Tools → Database Query Browser*,
   connection `mes`:

   ```sql
   INSERT INTO mes.cell (cell, bay, qualified_part_types, notes)
   VALUES ('C06', 'BAY6', '{2,3}', 'Newest cell (delivered 2026-11); medium and large housings.');
   ```

   The overview now shows a sixth tile, with bad-quality overlays: the views
   repeat over `mes.cell`, but the tags don't exist yet. Do this step before
   the next one: the MES and the autopilot look the cell up in `mes.cell`.
5. **Tags** (20 min). Tag Browser:
   - `[default]ANN/FIN` → *New Tag → UDT Instance*, type `PIC200_Cell`, name
     `C06`, parameters `CellId` = C06, `OpcServer` = C06, `IoDevice` = C06_IO01.
   - Provider `sim` → UDT instance of `PIC200_Sim`, name `C06`, `OpcServer` = C06.
   - Watch the qualities turn Good. `MES/AutoRun` is true by default, so the
     lab autopilot resets the cell, dispatches an order and starts it within
     seconds. The tile turns green.
6. **Check what followed by itself** (20 min): `/cell/C06` (mimic, commands,
   trends after a few minutes of history), the KPI page's cell selector, the
   instructor page row, `docker compose logs plc-c06` (order loads, state
   changes), and in the Database Query Browser
   `SELECT count(*) FROM mes.part_result WHERE cell = 'C06'`. Nothing in the
   views, the MES scripts or the export had to change.

### Stretch

- Six tiles on the overview: check the layout at your screen width and adjust
  the flex repeater (`elementPosition.basis`, `wrap`) if a tile ends up alone
  on a second row.
- Disconnect test: `docker compose stop plc-c06`, watch the tags go Bad and
  what the tile shows, then `docker compose start plc-c06`.

**Done when:** C06 produces under the autopilot, appears everywhere C01..C05
appear, and its part records land in `mes.part_result`.

Review note: your connections and tags are saved as JSON under
`ignition/data/config/resources/core/` (`git diff` shows them). In the review,
Claude compares them with what `scripts/apply_gateway_config.py` and
`scripts/generate_tags.py` would produce from `docs/cells.csv`, then the
scripts can take over again. Until that review, nobody runs the scripts.

---

## Thursday: bind the andon station AN01, tags

**Concepts:** editing a UDT definition (one edit, six instances), parameterised
OPC item paths, data types, tag groups, read-only tags, expression members with
relative paths, tag history, alarms on a tag.
**Panorama E2:** adding properties to a class, so every instance gets them.

Every cell now has an andon station AN01 on its controller: a four-lamp stack
light (red, amber, green, blue), a buzzer, three call buttons at the cell
(material, quality, maintenance), and an acknowledge command for the
supervisor. Its behaviour is in [scenario.md 4.10](../scenario.md) and its
signals are in the [registry](../opcua-registry.md) (section *Andon station
AN01*):

| Signal | Type | Access | Meaning |
|---|---|---|---|
| `AN01.Status.LampRed`, `LampAmber`, `LampGreen`, `LampBlue` | Boolean | R | stack light: intervention needed, waiting, producing, call active |
| `AN01.Status.Buzzer` | Boolean | R | call active and not acknowledged |
| `AN01.Status.CallType` | Int32 | R | 0 none, 1 Material, 2 Quality, 3 Maintenance |
| `AN01.Status.CallAcknowledged` | Boolean | R | the active call was acknowledged |
| `AN01.Status.CallStartTime` | DateTime | R | when the call was raised |
| `AN01.Status.CallCount` | UInt32 | R | calls since controller start |
| `AN01.Command.Acknowledge` | Boolean | RW | write true; the controller writes false back within 100 ms |
| `Sim.Andon.CallButton` | Int32 | RW | the operator presses button 1..3 (the same button again clears the call) |
| `Sim.Andon.ResolveTime` | Double, s | RW | the simulated operator clears an acknowledged call after this time (default 90 s) |
| `Sim.Andon.AutoCallInterval` | Double, min | RW | mean time between random calls (default 0 = off) |

AN01 is equipment inside the cell, like QS01: its NodeIds carry no cell id
(`nsu=urn:ignition-lab:cell;s=AN01.Status.LampRed`). Only the OPC connection
differs from cell to cell.

### Core

1. **Browse it** (10 min): OPC Browser → `C06` → `Machines/AN01`. Write 2 to
   `Sim/Andon/CallButton` from the OPC Browser or Quick Client and watch
   `LampBlue` and `Buzzer` turn on.
2. **UDT members** (50 min). Tag Browser → *UDT Definitions* →
   `PIC200_Cell` → edit.
   - Add folders `AN01/Status` and `AN01/Command`.
   - Add the ten OPC tags. The quickest way: copy an existing member such as
     `QS01/Status/Ready`, paste it into `AN01/Status`, rename it, change its
     item path. Look at how the OPC server is bound to the parameter `{OpcServer}`.
   - Data types: Boolean; `CallType` Integer (Int4); `CallStartTime`
     DateTime; `CallCount` Long (Int8, since Ignition has no unsigned 32-bit
     type). Status tags read-only, `Acknowledge` writable. Tag group `Fast`
     for lamps and buzzer, `Default` for the rest.
   - Save: all six instances get the members. Check C01 and C06 in the Tag
     Browser.
3. **An expression member** (20 min): `AN01/Status/CallDuration` (seconds),
   `if({[.]CallType} > 0, secondsBetween({[.]CallStartTime}, now(1000)), 0)`.
   `{[.]…}` is a path relative to the member's own folder, so the same
   expression works in every instance.
4. **Sim members** (15 min): UDT `PIC200_Sim`, folder `Andon` (next to
   `Process`) with the three `Sim.Andon.*` nodes (namespace
   `urn:ignition-lab:sim`), writable. They appear as `[sim]C0n/Andon/...`.
5. **History and an alarm** (25 min).
   - History on `CallType` (on change, provider `Historian`), so calls can be
     counted and charted later.
   - An alarm on `AN01/Status/Buzzer`: mode *Equal*, setpoint true, priority
     Medium, display path bound to the cell (`{CellId} andon`), label
     *Andon call*. Raise a call from `[sim]C03/Andon/CallButton` and find
     the active alarm on the gateway's alarm status page; write true to
     `AN01/Command/Acknowledge` and watch it clear.

### Stretch

- Make the alarm label say the call type: bind the label to an expression on
  `{[.]CallType}`.
- Set `[sim]C04/Andon/AutoCallInterval` to 20 (minutes) so calls come on
  their own for tomorrow's screens.

**Done when:** `[default]ANN/FIN/C0n/AN01/...` exists in all six cells with
Good quality, a call raised from `[sim]` lights `LampBlue` and `Buzzer` on the
right cell, writing `Acknowledge` stops the buzzer, and the alarm comes and goes.

---

## Friday: bind the andon station AN01, screens, then wrap-up

**Concepts:** a reusable view with a parameter, embedded views, style classes
with animation, indirect tag bindings, a button writing a tag
(`system.tag.writeBlocking`), enabling a button from a binding, the Alarm
Status Table.
**Panorama E2:** a reusable symbol with parameters, placed on several mimics.

### Core

1. **View `Cell/StackLight`** (40 min), parameter `cell`.
   - Four round lamps stacked vertically (Labels or Flex containers with
     `borderRadius: 50%`), each with an indirect tag binding on
     `[default]ANN/FIN/{cell}/AN01/Status/Lamp…`: full colour when on, dark grey
     when off.
   - A style class `Andon/Blink` with an animation (Perspective styles accept
     CSS animations: opacity 1 → 0.2, 1 s, infinite). Bind the blue lamp's
     `props.style.classes` to `Andon/Blink` while `Buzzer` is true.
2. **Embed it** (20 min): an Embedded View (`ia.display.view`) of
   `Cell/StackLight` in the `Cell/Tile` header, and a larger one in the mimic of
   `Cell/Detail`, with `params.cell` bound to `view.params.cell`.
3. **Andon panel on the cell page** (40 min), on `Cell/Detail`:
   - text "Quality call since 12:41 (3 min)" from `CallType`, `CallStartTime`
     and `CallDuration`, empty when no call;
   - an *Acknowledge* button, enabled only while `Buzzer` is true, whose
     onActionPerformed script is
     `system.tag.writeBlocking(["[default]ANN/FIN/%s/AN01/Command/Acknowledge" % self.view.params.cell], [True])`.
4. **Try it** (10 min): raise calls from the Tag Browser (`[sim]C0n/Andon/CallButton`),
   acknowledge from the cell page, see the blue lamp blink, then hold steady,
   then go out after 90 s.

### Stretch

- An Alarm Status Table on the overview (or a new `/andon` page) that shows
  only the andon alarms of all cells.
- A call selector on the instructor row (`Sim/CellRow`) that writes
  `[sim]{cell}/Andon/CallButton`, and a field for `AutoCallInterval`.
- MES: log each call (tag change script on `CallType` → a new table
  `mes.andon_call`) and a response-time KPI (raised → acknowledged). This is
  MES-EVT territory of the URS: a good next week.

### Wrap-up (last 20 min, with Claude)

- Walk through the week's `git diff` together: views, style classes, named
  queries, page config, connections, devices, tags.
- Claude then fills `ignition_tag_path` for the AN01 rows of
  `docs/opcua-registry.csv`, so that `scripts/generate_tags.py` reproduces your
  UDT members, updates `hmi.md`, `plant-layout.md`, `architecture.md` and
  `status.md` for six cells and AN01, and commits on your request.

---

## Prepared before the week (2026-11-21)

| Item | State |
|---|---|
| `docs/cells.csv` row C06 | added (BAY6, `plc-c06`, ports 4846 / 5026, device `C06_IO01`, part types 2 3) |
| compose service `plc-c06` | running; also in the devcontainer `runServices` |
| AN01 + `Sim.Andon` in the registry and `plc/programs/cell.py` | 17 nodes (13 AN01, 4 Sim) in all six controllers; `ignition_tag_path` left empty on purpose |
| scenario.md 4.10, opcua-registry.md | written |
| `scripts/cell_smoke_test.py` | now also checks the andon (lamps, call, acknowledge, clear); PASS on C06 and C02 |
| Ignition (connections, tags, `mes.cell`, views) | untouched: that is your week |
