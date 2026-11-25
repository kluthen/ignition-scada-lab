# Ignition Core Certification: learning plan

Goal: pass the Inductive Automation **Ignition Core Certification** (Ignition
8.3), using this lab for what it already covers and a separate Standard
Edition gateway for the rest (Vision, the practice backup, the exam itself).

Facts gathered on 2026-11-25 from the official pages (sources at the end).
Check them again before buying the test: they change (the switch from 8.1 to
8.3 happened on 2026-10-26).

## 1. The exam

| Item | Official answer |
|---|---|
| Prerequisites | **None.** The test "requires knowledge of all of the fundamentals of designing with Ignition, as well as a basic understanding of databases, SQL, and Python scripting." The free Inductive University (IU) credential courses are recommended, not required. |
| Price | 350 USD, one attempt. Another attempt can be bought (price not published). Integrator Program members get a free test for completing IU. |
| Format | Online on Testinvite, autograded. 100 multiple-choice and short-answer questions in 9 sections. Webcam, ID photo and screen share. No hands-on deliverable (that is the Gold test). |
| Time | Finish within 30 days of purchase. Each section has its own timer (2 to 4 h, 25 h max in total, average under 10 h). The timer keeps running if the browser is closed. A started section must be finished; finished sections are locked. Any order. |
| Pass mark | **75 % in every section.** One failed section fails the test. Result by e-mail within 24 h. |
| Allowed | Open book: the User Manual, Inductive University, a running gateway and Designer. |
| Forbidden | Collaboration, and **any AI tool** (ChatGPT, Claude, Copilot, the manual's "Ask AI" widget...). Claude helps you prepare, never during the test. |
| Ignition | 8.3.6 or later. "A copy of Ignition that uses the default or typical modules and that you can restore a Gateway backup on." The free trial is enough (reset it every 2 hours). Maker Edition is not mentioned. |
| Validity | 3 years, no grace period. Renew by passing the test again, or by passing Gold. |

The 9 sections, with the IU credential course (titles from the IU course
list, Ignition 8.3) that teaches each:

| # | Section | IU courses |
|---|---|---|
| 1 | Ignition Platform / Gateway Basics | Ignition Overview, Ignition Editions, Ignition Gateway, OPC UA and Devices, Databases, Ignition Designer, Clients and Sessions |
| 2 | Vision | Vision Windows, Vision Components and Property Bindings |
| 3 | Perspective | Perspective Pages, Views, and Containers; Perspective Components and Bindings |
| 4 | Tags | Tags in Ignition |
| 5 | Security | Security in Ignition |
| 6 | Reporting | Reporting in Ignition |
| 7 | Tag History | Tag Historian in Ignition |
| 8 | Transaction Groups | Transaction Groups in Ignition |
| 9 | Alarming | Alarming in Ignition |

Also in the IU credential track and useful across sections: Scripting in
Ignition, SQL in Ignition. Not in the exam topics: Localization, Enterprise
Administration Module, Sequential Function Charts, Data Handling (skip them
for now).

## 2. Setup: a second gateway for the certification

The lab gateway runs **Maker Edition**: no Vision, and the practice backup
(`Core_Certification.gwbk`) is meant to be restored "on a fresh Ignition 8.3
Standard Edition install". So the exam work has its own gateway,
**`gateway-cert`** (built 2026-11-25, details in
[operations.md](../system/operations.md#certification-gateway-gateway-cert)):

- Standard Edition in trial mode, 8.3.10 like the lab, empty, with the
  default modules (Vision, Perspective, Reporting, SQL Bridge, alarm
  notification, historian, drivers, Programmable Device Simulator).
- `docker compose --profile cert up -d gateway-cert`, then
  http://127.0.0.1:8089. Data in a Docker volume, not in git: a sandbox to
  break and restore. "Fresh install" = drop the volume.
- An empty PostgreSQL database `cert` for transaction groups, recipes and
  report data sources (`jdbc:postgresql://db:5432/cert`).
- You reset its 2-hour trial by hand (gateway web page). Never by script.

The lab stays on Maker. Exercises that improve the plant (alarms on the cell
UDT, the daily report in the Reporting module, recipes) are done on the lab
gateway if Maker has the module, else on the cert gateway.

### Where your work goes

`main` stays the clean starting point: it never receives exercise results.
Before the first session:

```bash
git switch main && git pull
git switch -c training/core-cert
```

Commit on that branch whatever the exercises change in the lab (views, tags,
named queries, gateway config) and what you export from the cert gateway that
is yours (project exports, tag exports as JSON) under `certification/work/`.
Never commit `Core_Certification.gwbk` or anything restored from it.
Claude reviews on that branch too, and updates the system docs there when an
exercise changes the lab.

## 3. What the exam checks, and where you stand

Status: **done** = you have built it in this lab; **partly** = seen, not
practised in every form the exam asks; **gap** = not covered yet. The skill
lines are the official ones (study guide, "Topics Covered").

### 1. Ignition Platform / Gateway Basics

| Skill | Status | Where in the lab / what to do |
|---|---|---|
| Backup and restore a gateway or a project; what each contains | gap | Take a `.gwbk` and a project export on the cert gateway, restore both |
| Connect to a database | done | connections `mes`, `historian` |
| Configure device connections; OPC UA; **Programmable Device Simulator** | partly | OPC UA connections and Modbus devices done (week 48 day 3); simulator device never used |
| Activate a licence; licensing model basics | partly | Maker activation done; learn the standard model (modules, trial, leased vs perpetual) |
| Designer Launcher; create projects; **project inheritance**; module areas in the Designer | partly | `plant` project done; inheritance not used |
| Install and upgrade Ignition | partly | Docker only; read the native install and the upgrade procedure |
| Gateway Network: redundancy basics; which subsystems use it | gap | Manual reading (no second gateway in the lab) |

### 2. Vision (all new)

| Skill | Status |
|---|---|
| Components, properties, drawing tools | gap |
| Bindings: tag, indirect tag, property, expression | gap (same idea as Perspective) |
| **Client tags** | gap |
| Basic navigation; types of windows (main, docked, popup) | gap |
| Templates, template/instance relation, template indirection | gap |
| Layout: size, shape, grouping (relative / anchored) | gap |
| `system.gui` scripting library | gap |
| Client permissions and security on a project, window, component | gap |

### 3. Perspective

| Skill | Status | Where in the lab |
|---|---|---|
| Bindings (tag, indirect, property, expression) and transforms | done | `Cell/Tile`, `Cell/Detail` |
| Session, component, custom properties, view parameters | done | `cell` param, `session-props` (week 48) |
| Views: design, embed | done | flex repeater of `Cell/Tile` |
| Page URLs and docked views | done | `/cell/:cell`, `Shared/Header` |
| Containers and layout | done | coordinate, flex |
| Style properties and style classes | done | week 48 day 1 |
| `system.perspective` library | partly | navigate used; review popups, messages, session functions |
| Security levels on views and scripts | gap | |

### 4. Tags

| Skill | Status | Where in the lab |
|---|---|---|
| Tag types; Tag Browser and Tag Editor | done | |
| Tag paths, dynamic access to several tags | done | indirect bindings, `base + ...` in scripts |
| System and client tag providers vs standard | partly | client tags are Vision only |
| Import and export tags | done | `gateway-config/tags/default.json` |
| Tag groups and execution modes (direct, driven, leased) | partly | `Fast`, `Default`, `Modbus` are all direct; try driven and leased |
| UDTs: definition/instances, **inheritance, nesting, multi-instance wizard** | partly | `PIC200_Cell` uses nesting; inheritance and the wizard not used |
| Read/write: Tag Browser, bindings, scripts with the qualified value | done | |
| Tag read/write permissions; security outside the tag (history, alarm ack) | gap | |

### 5. Security (mostly new)

| Skill | Status |
|---|---|
| User sources of various types; users and roles | partly (internal source only) |
| Identity providers and authentication strategies (and when one cannot be used) | gap |
| Security levels hierarchy | gap |
| Security zones and how they relate to security levels | gap |
| SSL: which connections can be encrypted and where | gap |
| Service security vs project properties vs component security | gap |
| Security through system functions and expression functions | gap |

### 6. Reporting (new)

| Skill | Status |
|---|---|
| Data source types, report parameters | gap |
| Report design with dynamic data | gap |
| Schedules; `system.report` | gap |
| Show a report in Vision and Perspective, with parameters | gap |

Good lab exercise: rebuild the daily export report with the Reporting module
(already planned in status.md, item 5), on the `mes.*` KPI functions.

### 7. Tag History

| Skill | Status | Where in the lab |
|---|---|---|
| Configure history; how tag properties affect sampling | done | 22 members of `PIC200_Cell`, deadbands |
| Tag Historian vs Transaction Groups | gap | see section 8 |
| Display with tag history bindings, tables, charts (Vision and Perspective) | partly | `Cell/Detail` uses a script; try the binding and the Power Chart |

### 8. Transaction Groups (new)

| Skill | Status |
|---|---|
| Group types (standard, block, historical, stored procedure) and how they behave | gap |
| Transaction groups vs tag history | gap |
| Use cases: historical logging, **recipes**, triggered or timed execution | gap |
| Query the stored data and show it in Vision and Perspective | partly (named queries done) |

Good lab exercise: a recipe table per product in `mes` written to a cell by a
group, and a block group logging `Admin/*` counters every shift.

### 9. Alarming

| Skill | Status |
|---|---|
| Alarms on tags; dynamic alarms on UDTs; alarm properties | partly (week 48 day 4: one alarm on AN01) |
| Alarm journal: configure, read the stored history | gap |
| Alarm Status Table and Alarm Journal components with filters | partly (andon panel, week 48 day 5) |
| Notification profiles, on-call rosters, pipelines | gap |

Good lab exercise: status.md item 1 (alarms on `Alarms/*`, `RJ01`, `SF01`,
journal in schema `alarms`, alarm table on the HMI).

## 4. Plan: 14 sessions of about 2 hours

Same rhythm as the training weeks: you do every change, Claude prepares and
reviews. For each session: watch the IU lessons first (on the cert gateway
or the lab, following along), then build, then 10 practice questions of the
section if the practice test has them.

| # | Theme | IU courses | Build |
|---|---|---|---|
| 1 | Setup and platform | Overview, Editions, Gateway | Branch `training/core-cert`; cert gateway: commissioning, trial, gateway backup and restore, project export/import, project inheritance (a parent `base` project) |
| 2 | Devices and databases | OPC UA and Devices, Databases | Programmable Device Simulator device; read the Gateway Network and redundancy pages; licensing model |
| 3 | Tags, part 1 | Tags in Ignition | Tag group modes (driven, leased) on the lab, UDT inheritance (a `PIC200_CellFast` child), multi-instance wizard on the cert gateway |
| 4 | Tags, part 2, and scripting | Tags, Scripting | Reads and writes from scripts with qualified values; tag permissions; export/import |
| 5 | Vision, part 1 | Vision Windows | On the cert gateway: main window, docked header, popup, navigation |
| 6 | Vision, part 2 | Vision Components and Bindings | A cell window: bindings of the four types, a template with indirection, client tags, `system.gui` |
| 7 | Perspective review | Perspective courses | Security levels on a view, `system.perspective` popups and messages; review what you built in week 48 |
| 8 | Security | Security in Ignition | User source with roles, security levels, a security zone, SSL settings; restrict the instructor page and the command buttons |
| 9 | Tag History | Tag Historian | Tag history binding and Power Chart on the cell page; compare with the script version |
| 10 | Transaction Groups | Transaction Groups, SQL | A historical group, a block group, a recipe group with a trigger, all in `mes` |
| 11 | Alarming | Alarming | Alarms on the cell UDT, the alarm journal, a notification pipeline with a roster |
| 12 | Reporting | Reporting | The daily report rebuilt in the Reporting module, a schedule, the report in Perspective with parameters |
| 13 | Practice test | | `Core_Certification.gwbk` restored on a fresh cert gateway, the 41 official practice questions, timed |
| 14 | Weak spots | | Redo the sections below 75 %, then the Testinvite sample test |

Then buy the test and take it within 30 days, one or two sections a day.

## 5. Exam technique (from the official strategies page)

- Read each question closely: "select all that apply" means several answers;
  fill-in answers want exactly what is asked.
- Read every option: component and property names are close to each other.
- Check in the gateway and the Designer when unsure; the questions test
  exact locations, property names and default behaviours.
- Use the Designer hover help and the manual's search box (not its AI).
- Keep the provided backup untouched; if you change it, restore it on a fresh
  install.
- Budget the time per question before starting a section.

Style of the practice questions: multiple choice (single and multiple),
true/false, fill-in, "write one line of script or an expression", paste an
exported tag as JSON, troubleshooting (for example an alarm that does not
fire exactly at its setpoint: the setpoint is "not inclusive").

## Sources

- [Core Certification](https://training.inductiveautomation.com/core-certification/)
- [Test FAQs](https://training.inductiveautomation.com/core-certification/test-FAQs)
- [Study guide](https://training.inductiveautomation.com/core-certification/study-guide/): topics covered (one page per section), recommended resources, test-taking strategies, practice test questions
- [Certification tests](https://inductiveautomation.com/training/certification-tests)
- [Inductive University courses](https://inductiveuniversity.com/courses) (lesson lists are only visible in a browser)
