# From Panorama E2 to Ignition: concept map

A working glossary for an engineer coming from Codra Panorama E2. The Ignition
column is checked against 8.3. The Panorama column uses general terms: correct
it where your practice differs, it is meant to grow with the lab.

## Architecture

| Topic | Panorama E2 (typical) | Ignition 8.3 |
|---|---|---|
| Runtime server | Panorama E2 server station(s) running the application | **Gateway**: one Java service per server, hosting all modules. Configured from its web UI (`:8088`), and in 8.3 from files plus a REST API. |
| Engineering tool | Panorama Studio / application explorer, editing the application | **Designer**: Java client launched from the gateway (Designer Launcher). Edits *projects* (screens, scripts, queries) live on the gateway. Gateway-wide config (devices, DBs, users) is done in the gateway web UI or the REST API. |
| Application | one application, deployed to stations | **Projects** (screens, scripts, named queries, reports) on top of **gateway resources** (devices, tag providers, DB connections, security). Projects can inherit from a parent project. |
| Operator client | Panorama station client / web client | **Perspective** (HTML5, browser or mobile app; the current choice) or **Vision** (Java desktop client, older; not available in Maker Edition). Unlimited clients under the standard licence. |
| Licensing | per station, sized by variables / options | per **gateway** and **modules**; unlimited tags, clients and connections in the standard edition. Maker Edition is free for personal, non-commercial use. |
| Multi-server | client/server stations, redundancy | **Gateway Network** (gateway-to-gateway), remote tag providers, Enterprise Administration (EAM), redundancy (master/backup pair). |

## Data model

| Topic | Panorama E2 | Ignition |
|---|---|---|
| Variable / point | variable (bit, register/analog, text…) bound to an equipment address | **Tag**: atomic tag with a *value source*: OPC (device item), memory, expression, query, reference, derived. Data types Boolean, Int1…Int8, Float4/8, String, DateTime, Document… |
| Variable container | folders / hierarchy in the application tree | **Tag provider** (`[default]`, …) containing folders. Path syntax `[provider]Folder/Sub/Tag`. |
| Object model (classes, instances) | object-oriented modelling: classes, instantiated per equipment | **UDT** (User Defined Type): a typed tag structure with parameters (`{DeviceName}`, `{BaseAddress}`…), instantiated per equipment, with inheritance and overrides. This is the main reuse tool. In the lab: UDT `PIC200_Cell` (parameters `CellId`, `OpcServer`, `IoDevice`), instances `[default]ANN/FIN/C01`..`C05` (docs/plant-layout.md). |
| Behaviour attached to the class | class scripts / methods | **Tag event scripts on UDT members** (value changed, quality changed, alarm events) run for every instance in gateway scope; they call **project library** functions. The lab's MES runs this way (docs/system/mes.md). |
| Variable properties (scaling, units, limits) | properties of the variable | tag properties: `scaleMode`, `rawLow/High`, `scaledLow/High`, `engUnit`, `engLow/High`, `formatString`, `deadband`, `tagGroup` (scan class) |
| Scan rates | acquisition cycles per equipment | **Tag groups**: Direct, Driven, Leased, each with rates. OPC subscriptions are handled by the OPC UA client. |
| Quality | variable status / validity | **Quality code** on every value (`Good`, `Bad_NotConnected`, `Uncertain_…`), alongside value and timestamp |

## Communication

| Topic | Panorama E2 | Ignition |
|---|---|---|
| Field drivers | Panorama communication drivers (Modbus, S7, OPC UA client…) per equipment | **Device connections** of the built-in OPC UA module: Modbus TCP/RTU, Siemens S7, Allen-Bradley Logix, Omron, Mitsubishi, BACnet, DNP3, IEC 61850. Every device appears in Ignition's **own OPC UA server**, and tags read it from there. |
| Third-party OPC UA servers | OPC UA client driver | **OPC connections** (OPC UA client; legacy OPC DA through COM). Browse the remote server in the Designer and drag nodes in as tags. |
| Exposing data | OPC UA server option | Ignition OPC UA server: devices always, tag providers optionally ("exposed tags"). Also MQTT (Cirrus Link modules), REST (WebDev), Event Streams, Kafka. |

## Alarms, history, events

| Topic | Panorama E2 | Ignition |
|---|---|---|
| Alarms | alarm definitions on variables, alarm manager, acknowledgement | **Alarm configuration on the tag**: one or more alarms per tag, each with mode (above/below setpoint, equality, bit state…), priority (Diagnostic, Low, Medium, High, Critical), setpoints, deadband, delays, shelving, ack modes, bindings (expressions). |
| Alarm log | event/alarm history | **Alarm journal** (stored in a DB connection, here `mes`) plus an alarm status/journal table component in Perspective |
| Alarm notification | e-mail / SMS options | **Alarm Notification module**: pipelines (logic blocks: delay, escalation, rosters), e-mail, SMS, voice |
| Historian | Panorama Historian / archive to DB | **Tag history** per tag (`historyEnabled`), stored by a historian provider. In 8.3: **SQL Historian** (any DB connection, here PostgreSQL) or the internal **Core Historian**. Deadband, max time between samples, aggregation on query. |
| SQL logging of process data | export to DB | **SQL Bridge transaction groups** (tag ↔ table, triggered, handshakes) and **named queries** / scripting |
| Audit | user action log | **Audit profile** (DB) logging logins, writes and config changes |

## Screens

| Topic | Panorama E2 | Ignition Perspective |
|---|---|---|
| Mimic / synoptic | mimic with animated graphic objects | **View** (`view.json`) built from components in containers (coordinate, flex, column, breakpoint). Responsive by design. |
| Graphic object libraries, symbols | symbol libraries | **Symbol Factory** module (ISA/industrial SVG symbols), custom SVG, Perspective "embedded views" as reusable symbols with parameters. Lab: `Cell/Tile` with a `cell` parameter, repeated by a **flex repeater** over the rows of `mes.cell` (docs/system/hmi.md) |
| Mimic bound to an instance | mimic template opened on an object instance | a view with a parameter and **indirect tag bindings** (`[default]ANN/FIN/{cell}/…`); the page URL can carry the parameter (`/cell/:cell`) |
| Animation | animations bound to variables | **Property bindings**: tag, indirect tag, expression, query, property, with **transforms** (map, script, format) |
| Navigation | mimic calls / popups | **Page configuration** (URL routes → views), docks, popups, `system.perspective.navigate()` |
| Trends | trend objects | **Power Chart** / **Time Series Chart** components reading tag history |

## Scripting

| Topic | Panorama E2 | Ignition |
|---|---|---|
| Language | VBA / scripts attached to objects and events | **Python 2.7 (Jython)** everywhere, with the `system.*` API (`system.tag.readBlocking`, `system.db.runNamedQuery`, `system.alarm.queryStatus`…) and access to Java classes. Plus a separate **expression language** for bindings and expression tags. |
| Where scripts run | client-side and server-side events | **Gateway scope**: tag change scripts, gateway timer/startup events, alarm pipelines, message handlers. **Session scope**: Perspective event handlers, run on the gateway for each session. **Designer/Vision client scope**. Shared code goes in **project script library** modules. |
| Recipes | recipe manager option | no core recipe module: SQL tables + scripts, or Sepasoft Batch/Recipe modules (third party) |
| Sequences | sequences / automata | **SFC module** (Sequential Function Charts) running on the gateway |

## Security

| Topic | Panorama E2 | Ignition |
|---|---|---|
| Users and profiles | users, groups, access rights per object | **User sources** (internal, DB, AD/LDAP), **identity providers** (internal, OIDC, SAML) for login, **roles** and **security levels**. Permissions are set per project, per view or component, and per tag (read/write permissions). |
| Gateway admin | administrator profile | gateway `readPermissions` / `writePermissions` (security levels, e.g. `Authenticated/Roles/Administrator`), API tokens for automation |

## MES

Panorama E2 has MES-oriented options in the Codra suite. Ignition's core
modules give the building blocks (SQL, transaction groups, scripting,
Perspective, reporting). Packaged MES functions (OEE/downtime, track & trace,
batch, SPC) usually come from **Sepasoft** modules, which are paid and
third-party. This lab builds a small MES on the core modules only. See
`docs/mes-requirements.md`.
