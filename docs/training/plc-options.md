# Programming PLCs without hardware: options and choice (research 2026-11-23)

Research behind training week 50 ([week-50.md](week-50.md)): which vendor
tools a learner can use for free or on trial, which of them can simulate a PLC
without hardware, and which simulated PLC the lab's Ignition gateway (Docker,
Maker Edition) can actually reach. Every fact carries its source. **Tested
here** marks what was checked on this lab host; everything else comes from
the vendor's documents as of 2026-11-23 and may change.

Constraints of the lab: Linux host (Debian 13, 12 cores, 11 GB RAM, KVM),
Ignition 8.3.10 Maker Edition in Docker, personal non-commercial use, no PLC
hardware, about 10 hours of practice. A Windows 11 Pro PC (16 GB RAM) is
available on the same LAN.

## 1. Conclusion first

| | Choice |
|---|---|
| Main track (days 1 to 4) | **Siemens TIA Portal V21 trial (STEP 7 Professional + S7-PLCSIM) and S7-PLCSIM Advanced V8.0 trial**, 21 days each, on the Windows PC |
| Comparison day (day 5) | **Schneider EcoStruxure Machine Expert – Basic V1.4** (free, M221 controller and simulator) |
| Fallback if the Siemens download is not granted | **CODESYS V3.5 SP22** (free IDE) with **CODESYS Control Win SL** in demo mode (2 h runs, restartable). The same week works with the ST sources, see section 6 |
| Windows | the **Windows 11 Pro PC** on the LAN (16 GB RAM, meets Siemens' figures), [../system/plc-engineering.md](../system/plc-engineering.md). A VM on the Linux host was tried and dropped (section 5) |
| Ignition to the simulated PLC | **OPC UA** to the S7-1500's own server (main), **legacy Siemens driver** with absolute addresses (second). The symbolic driver is not available on Maker |

Why Siemens for the main track: S7-1500 / TIA Portal is the most common PLC
platform in French and European manufacturing. Its simulator, PLCSIM
Advanced, gives the simulated CPU a real TCP/IP interface (S7, OPC UA,
Modbus TCP), so the week can end with Ignition talking to the PLC program
you wrote. Its program text (SCL, DB, UDT) can be imported from source files,
so the finished station program could be prepared on Linux.

Why Schneider for one day only: the only Schneider tool that is both free and
simulates without hardware is Machine Expert – Basic. It is good for Ladder
and Grafcet on the small M221, but it has no Structured Text and no function
blocks. The CODESYS-based Machine Expert cannot simulate under its free
licence, and its simulation mode has no network services.

## 2. Siemens

### 2.1 TIA Portal trial

| Fact | Source |
|---|---|
| TIA Portal V21 released 2025-11-11. V21.1 announced 2026-11-19, download from end of November 2026, feature-based licensing | [Siemens press V21](https://press.siemens.com/global/en/pressrelease/tia-portal-v21-combines-engineering-efficiency-higher-plant-availability), [press V21.1](https://press.siemens.com/global/en/node/7501) |
| siemens.com offers "Try TIA Portal V21.1 free for 21 days" (SIOS entry 110004178) | [TIA Portal product page](https://www.siemens.com/en-us/products/tia-portal/) |
| V21 trial package: STEP 7 Basic/Professional V21, STEP 7 Safety, WinCC V21 and **S7-PLCSIM V21**, "for registered customers", 21 days, main ISO about 8.1 GB | SIOS entry [109989774](https://www.industry-mobile-support.siemens-info.com/en/article/detail/109989774) (read through a search extract: SIOS refuses automated fetches); overview of trials V17..V21: [109798506](https://www.industry-mobile-support.siemens-info.com/en/article/detail/109798506) |
| "You have the one-time option of activating a Trial License … expires after 21 days." After expiry TIA Portal "only runs with restrictions" | [STEP 7 / WinCC V20 installation notes, 11/2024](https://cache.industry.siemens.com/dl/files/850/109963850/att_1304955/v1/Install_STEP7_WinCC_V20_enUS.pdf) |
| Download needs a Siemens ID (SiePortal). Some packages go through an export-control check, which can delay access | [SiePortal](https://sieportal.siemens.com/en-ww/home); export check reported by [a third party](https://www.automation-fair.com/tia-portal-v21-trial-download-install/) (not confirmed by Siemens) |
| V21 OS: Windows 10 Enterprise 2021 LTSC, Windows 11 Pro/Enterprise 24H2, **Enterprise 24H2 LTSC**, Enterprise 23H2, Server 2022/2025 | [TIA Portal V21 system requirements](https://docs.tia.siemens.cloud/r/en-us/v21/installation/system-requirements-for-installation/general-software-and-hardware-requirements) |
| V21 hardware: minimum 8 GB RAM, 20 GB free disk; recommended 16 GB RAM, 50 GB SSD, 1920 × 1080 | same page |
| Supported hypervisors: VMware ESXi / Workstation / Player, Hyper-V. **QEMU/KVM is not listed** (not supported, not forbidden) | same page |
| Browser option: TIA Portal Cloud (paid per hour or subscription; a 21-day free test is advertised), and the "Machine automation engineering" cloud trial with TIA Portal and PLCSIM Advanced, 21 days, no installation | [TIA Portal V21 technical slides](https://cache.industry.siemens.com/dl/files/772/109989772/att_1348791/v5/TIA_Portal_V21_technical_slides_EN.pdf), [Siemens cloud trial](https://trials.sw.siemens.com/en-US/trials/machine-automation-engineering) (eligibility not confirmed; the page renders only in a browser) |

Consequence: start the trial on the first day of the training week, not
before (it runs 21 days from activation and can be activated once). Register
the Siemens ID several days ahead: the download may wait for an approval.
Like the Ignition trial in this lab, never reset a trial by tricks (clock,
snapshots, reinstall).

### 2.2 S7-PLCSIM and S7-PLCSIM Advanced

| | S7-PLCSIM V21 (in the STEP 7 trial) | S7-PLCSIM Advanced V8.0 (own trial) |
|---|---|---|
| CPUs | S7-1500, S7-1200, S7-1200 G2, ET 200SP… (classic S7-1200 only as a "Standard" instance) | S7-1500 (standard, F, T, R/H), ET 200SP CPU, Software Controller, S7-1200 G2; not the classic S7-1200 |
| Communication | Softbus only (TIA Portal and WinCC on the same PC) | Softbus or **TCP/IP** through the "Siemens PLCSIM Virtual Ethernet Adapter" |
| Reachable from another program / machine | **no** | **yes**: S7 PUT/GET, **OPC UA server**, Modbus TCP (MB_SERVER), web server, open user communication |
| OPC UA | no | yes, TCP/IP mode only; the PLCSIM Advanced licence includes the OPC UA authorization |
| Licence | STEP 7 trial | own **21-day trial**, offered by the Automation License Manager when an instance starts; after it, instances no longer start |
| Requirements | as TIA Portal | 16 GB RAM minimum, one core per instance + OS |

Sources: [S7-PLCSIM V21 manual (11/2025)](https://cache.industry.siemens.com/dl/files/161/109997161/att_1348284/v1/S7-PLCSIM_Help_en-US.pdf)
("Only S7-PLCSIM Advanced simulation instances can use [TCP/IP]");
[S7-PLCSIM V21 readme](https://cache.industry.siemens.com/dl/files/163/109997163/att_1348297/v1/Readme_enUS_en-US.pdf);
[PLCSIM Advanced V8.0 function manual](https://support.industry.siemens.com/dl/files/788/109997788/att_1350855/v1/s7-plcsim_advanced_function_manual_en-US_en-US.pdf)
(communication services table 6-2, OPC UA, licences);
[PLCSIM Advanced V6.0 function manual](https://cache.industry.siemens.com/dl/files/578/109955578/att_1267815/v1/s7-plcsim_advanced_function_manual_en-US.pdf)
(section 2.2 product comparison, 3.1.4 trial licence "available for the limited period of 21 days",
4.2 TCP/IP single / multiple adapter modes, 4.3 distributed communication through the
"S7-PLCSIM Advanced Virtual Switch"); PLCSIM Advanced V8.0 trial download: SIOS entry
[109990051](https://www.industry-mobile-support.siemens-info.com/en/article/detail/109990051) (search extract).

Consequence: plain PLCSIM is enough for days 1 to 3; Ignition (day 4) needs a
PLCSIM Advanced instance in TCP/IP mode with an S7-1500 CPU. The lab uses
the "local" TCP/IP mode (instance on the virtual adapter inside Windows) plus a
Windows port proxy, so no promiscuous mode or bridged network is needed
(design in [../system/plc-engineering.md](../system/plc-engineering.md); the
path up to the proxy is tested, the PLCSIM end is not yet, see section 7).
The S7-1500 OPC UA server advertises its own (virtual adapter) address in its
endpoints: the Ignition connection needs a host override.

### 2.3 Program text from files

| Fact | Source |
|---|---|
| External source files `*.scl`, `*.awl` (STL), `*.db`, `*.udt` go into "External source files"; right-click → "Generate blocks from source". Existing blocks with the same name are overwritten. LAD/FBD cannot be external sources | [TIA Portal Openness manual V16](https://cache.industry.siemens.com/dl/files/802/109773802/att_1007204/v1/TIAPortalOpenness_en-US.pdf) (sections on external sources) |
| LAD/FBD as text: Openness XML (SimaticML) import, and new in V21 "SIMATIC Source Documents" (`.s7dcl`, readable LAD as `RUNG … END_RUNG`) through Openness / Version Control Interface | same manual; [V21 technical slides](https://cache.industry.siemens.com/dl/files/772/109989772/att_1348791/v5/TIA_Portal_V21_technical_slides_EN.pdf) |
| PLC tag tables import from / export to Excel (PLC tags editor → Import) | TIA Portal help (PLC tags); layout used here = TIA's own export layout |
| Recommended reading for a software developer: Programming Guideline for S7-1200/S7-1500 | SIOS [81318674](https://support.industry.siemens.com/cs/ww/en/view/81318674) |

The station program of week 50 is therefore delivered as SCL / DB / UDT
sources (`plc-training/siemens/lt01/`), with a tag table in Excel. The
hardware configuration and the LAD exercises are done by hand.

### 2.4 SIMATIC AX

VS Code-style IDE for object-oriented ST, git, unit tests, package manager.
Local IDE on Windows 11 only, web IDE in a browser; simulation through
PLCSIM Advanced on Windows. Named-user subscription through an organisation
account, "initial 3-month trial"; a free "AX Academy" learning path after
registration. Not suited to this week (organisation account, no Linux
simulation), worth knowing as Siemens' "software developer" path.
Sources: [SIMATIC AX Logic Control Engineering documentation, 06/2026](https://assets.ctfassets.net/17si5cpawjzf/ABgWY9wp3r7VpyFW1Eb7G/b9cba4890252942fe18cb595f68568c7/Product_Documentation_SIMATIC_AX_Logic_Control_Engineering_final.pdf),
[product page](https://www.siemens.com/en-us/products/simatic-ax/logic-control-engineering/),
[AX training](https://www.siemens.com/en-us/training/simatic-ax/).

### 2.5 Ignition 8.3 to S7-1200/1500

| Fact | Source |
|---|---|
| Legacy "Siemens Driver" (S7-300/400/1200/1500): absolute addressing only, global DBs only. On the CPU: **optimized block access off**, **Full access (no protection)**, **Permit access with PUT/GET** | [Ignition 8.3 docs: Siemens](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/siemens) |
| Address syntax `DB10,REAL10`, `DB500,DI8`, `IX20.3`, `IW0`; port 102; rack 0, slot 2 by default | [Ignition 8.3 docs: Siemens drivers](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/siemens/siemens-drivers) |
| "Siemens Enhanced Driver" (symbolic, optimized DBs, browsing) "is not included on a Platform license" | [Siemens Enhanced Driver](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/siemens/siemens-enhanced-driver) |
| Maker Edition lists the Siemens Driver (legacy) and "Siemens S7 Symbolic", but IA staff wrote (2026-09-23) that the Enhanced driver is "not available for Maker" (third-party native library); it faults with "Not eligible for use with Ignition Maker Edition" | [Maker Edition docs](https://docs.inductiveautomation.com/docs/8.3/other-editions/ignition-maker-edition), [forum thread](https://forum.inductiveautomation.com/t/siemens-enhanced-driver-not-working-with-ignition-maker-8-3-9/117166) |
| IA's advice for S7-1500: "Direct OPC UA connection or Siemens Enhanced are the best options"; the legacy driver needs insecure PLC settings | [forum, 2026-07](https://forum.inductiveautomation.com/t/siemens-s7-1500-which-driver/116306) |
| PLCSIM Advanced OPC UA: enable the server in the hardware configuration, TCP/IP mode; users report only security policy None working | [forum](https://forum.inductiveautomation.com/t/cant-connect-to-siemens-s7-plcsim-advanced/89993) |
| Clock skew between the gateway and the simulated PLC made Designer drop values as stale | [forum](https://forum.inductiveautomation.com/t/opc-tag-updates-in-quick-client-but-not-in-designer-virtual-s7-1500sp-via-plcsim-advanced/109724) |

For a Panorama E2 user: the legacy driver with `DBn,TYPEoffset` addresses is
the S7 driver you know (absolute addresses, non-optimized DBs). The OPC UA
route is the modern one (symbols, browsing, optimized DBs).

### 2.6 Free learning material

- SCE learn / training documents (free with a Siemens ID): S7-1500 modules
  032-xxx (function blocks, IEC timers and counters, global DBs, analog
  values, diagnostics), updated for V21 in 2026.
  [siemens.com/sce/documents](https://www.siemens.com/sce/documents),
  [S7-1500 set](https://www.siemens.com/sce/S7-1500),
  [SCE quick links](https://assets.new.siemens.com/siemens/assets/api/uuid:16a99191-2445-4d3a-b608-0de9ecacf019/sce-quick-links-en.pdf).
- TIA Portal Tutorial Center: [SIOS 106656707](https://support.industry.siemens.com/cs/ww/en/view/106656707);
  TIA Portal videos: [SIOS 109767570](https://support.industry.siemens.com/cs/ww/en/view/109767570).
- Siemens TIA University: free "TIA FAST Track" videos
  ([part one](https://contentpath.siemens.com/tia-fast-track/part-one-tia-portal)).
- SITRAIN access "Freemium": free selected trainings
  ([how-to](https://assets.new.siemens.com/siemens/assets/api/uuid:24c05c7f-513d-4bf8-b5f5-6708c96e0e9a/How-to-steps-Freemium.pdf)).

## 3. Schneider Electric

| Tool | Licence | Simulation without hardware | Reachable by Ignition | Sources |
|---|---|---|---|---|
| **Machine Expert – Basic V1.4** (2025-11-24), M221 / M100 / M200 | **free** ("free licence", free download; an se.com account is likely needed for the download) | built-in simulator, I/O manager, simulated clock | Modbus TCP on port 502, **one data connection** (+ one for the IDE). Documented for an HMI at 127.0.0.1 | [download V1.4](https://www.se.com/au/en/download/document/MachineExpertBasicV1_4/), [catalogue ESEBASXZZPA10](https://www.se.com/us/en/product/ESEBASXZZPA10/ecostruxuremachine-expert-basic-free-licence-programing-software-for-m221-controllers), [Operating Guide EIO0000003281](https://www.se.com/au/en/download/document/EIO0000003281) chapter 7, [FAQ port 502](https://www.se.com/uk/en/faqs/FA328632/), [FAQ HMI to simulator](https://www.se.com/br/pt/faqs/FA284461) |
| Machine Expert V2.x (CODESYS 3.5 based), M241/M251/M262 | Free licence (no simulation), **Trial 42 days**, Standard / Professional, University | CODESYS "Online > Simulation": "Fieldbus stacks are not evaluated", no network services | no (an Ignition user could not connect to a simulated M262) | [licences V2.2](https://product-help.se.com/docs/Machine%20Expert/V2.2/en/Installer/Installer/D-SE-0075111.html), [simulation V2.2](https://product-help.se.com/docs/Machine%20Expert/V2.2/en/SoMMenu/SoMMenu/D-SE-0084008.html), [forum](https://forum.inductiveautomation.com/t/schneider-machine-expert-simulation/73385), [V2.3 = CODESYS 3.5 SP20](https://www.se.com/us/en/faqs/FAQ000278101/) |
| Control Expert V16.2 (ex Unity Pro), M340 / M580 | **trial 30 days**, full XL feature set | PLC simulator | Modbus TCP 127.0.0.1:502; Ignition users connected to it | [V16.2 download](https://www.se.com/be/en/download/document/EcoStruxureControlExpert_V162), [FAQ trial](https://www.se.com/us/en/faqs/FAQ000282562/), [FAQ HMI to simulator](https://www.se.com/au/en/faqs/FA248397/), [Ignition forum](https://forum.inductiveautomation.com/t/control-expert-schneider-and-ignition/41868) |
| Automation Expert V25 (IEC 61499) | 42-day demo "except the application deployment"; Soft dPAC runtime licensed | no deployable runtime in the trial | n/a | [catalogue 04/2025](https://media.distributordatasolutions.com/228/schneider_synd_json/4a52baea0c5a4d00587882b5b1c528b4cabd7cb6.pdf) |

Machine Expert – Basic specifics that shape day 5:

- Languages: Ladder, Instruction List, Grafcet (List) and Grafcet (SFC); no
  ST, no FBD (Operating Guide, sections 5.12 to 5.15; [FAQ FA360163](https://www.se.com/be/en/faqs/FA360163)).
- The M221 Modbus TCP server accepts function codes 3, 4, 6, 16 and 23 only
  ([FAQ FA273024](https://www.se.com/uk/en/faqs/FA273024/)): no coils, no mask
  write. FC 02 returns %M bits ([FAQ FA295250](https://www.se.com/uk/en/faqs/FA295250/)).
  So Ignition exchanges **whole %MW words only** (no `HRn.b` writes, which
  need FC 22: [Ignition Modbus addressing](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/modbus/modbus-addressing)).
- %MW0 should be holding register 0 (Ignition `HR1` one-based, `HR0`
  zero-based): verify with HR0/HR1 test tags as the Ignition docs advise
  ([Modbus driver](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers/modbus)).
- A Control Expert trial licence breaks if the VM's host id changes
  ([FAQ FA383202](https://www.se.com/ca/en/faqs/FA383202/)): do not clone or move the VM during a trial.

Free Schneider learning material is thin: the Operating Guide and the
[M221 Programming Guide EIO0000003297](https://www.se.com/uk/en/download/document/EIO0000003297),
how-to videos inside se.com FAQs, and the
[Schneider community board](https://community.se.com/t5/c-krefy84679/EcoStruxure%E2%84%A2+Machine+Expert+-+Basic/pd-p/ecostruxure-machine-expert---basic).

## 4. Vendor-neutral options

| Tool | Facts | Sources |
|---|---|---|
| **CODESYS Development System V3.5 SP22** | free, no licence; Windows 10/11 64-bit only, 8 GB RAM recommended; setup includes a demo CODESYS Control Win SL. Store account needed to download | [CODESYS store](https://us.store.codesys.com/codesys.html), [SP22 release](https://www.codesys.com/company/news-center/latest-news/codesys-v35-sp22-release/) |
| CODESYS Control Win SL | "Without a license, the software runs in demo mode for two hours. After that, a manual restart is required." Includes OPC UA server and Modbus TCP master/slave. "Not released for use in containers or virtual machines" (unsupported, not blocked) | [datasheet 2026-09](https://store.codesys.com/media/n98_media_assets/files/2302000003-SW/4/CODESYS%20Control%20Win%20SL_en.pdf) |
| CODESYS IDE simulation mode | runs inside the IDE, "I/O channels are not updated", no fieldbus; no network services | [CODESYS help](https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_cmd_simulation.html) |
| CODESYS Virtual Control for Linux SL 4.23 | official runtime as a container image (Docker/Podman, kernel ≥ 6.1), 2-hour demo, deployed and programmed from the Windows IDE | [store page](https://store.codesys.com/en/codesys-virtual-control.html), [datasheet](https://api-de.codesys.com/fileadmin/user_upload/CODESYS_Group/Ecosystem/Up-to-Date/Releases-Lifecycle/Release-Updates/Datasheets/CODESYS-Virtual-Control-SL_en.pdf) |
| Beckhoff TwinCAT 3 | XAE free; 7-day trial licences, repeatable; real-time runtime cannot start under Hyper-V, Usermode Runtime in VMs | [licensing](https://www.beckhoff.com/en-en/products/automation/twincat/twincat-3-licensing/), [infosys](https://infosys.beckhoff.com/content/1033/tf6250_tc3_modbus_tcp/262609675.html), [Usermode Runtime](https://infosys.beckhoff.com/content/1033/tc170x_tc3_usermode_runtime/11319883275.html) |
| OpenPLC | v3 archived 2026-04-04 (end of life). Runtime v4.3.2 (headless, REST API, official Docker image) + Editor v4.3.5 (Linux AppImage): ST, LD, FBD, IL; Modbus, OPC UA, S7comm plugins. Runs fully on Linux, young and fast-moving | [OpenPLC v3](https://github.com/thiagoralves/OpenPLC_v3), [runtime v4](https://github.com/Autonomy-Logic/openplc-runtime), [editor](https://github.com/Autonomy-Logic/openplc-editor/releases) |
| Factory I/O (3D plant) | Windows only, GPU needed; 30-day trial of Ultimate; Siemens Edition 158 €/year; drivers for PLCSIM (V13 to 21) and PLCSIM Advanced (3.0 to 8.0), Modbus, OPC UA | [buy](https://factoryio.com/buy), [trial](https://factoryio.com/start-trial), [S7-PLCSIM driver](https://docs.factoryio.com/manual/drivers/s7-plcsim/) |

Schneider Machine Expert, WAGO e!COCKPIT and several others are built on
CODESYS ([Schneider](https://se.com/dk/da/faqs/FAQ000255449),
[WAGO](https://techdocs.wago.com/Software/eCOCKPIT_Migration/en-US/2023913739.html)):
CODESYS skills carry over to Schneider's M241/M251/M262.

No 3D simulator is used this week. The station's plant model is a function
block inside the PLC (simulation mode), a common practice that runs on plain
PLCSIM and needs no GPU.

## 5. Windows on this Linux host

| Fact | Source |
|---|---|
| Windows 11 Enterprise evaluation: 90 days, free, offered as Enterprise 25H2 and **Enterprise LTSC 2024** (24H2). LTSC 2024 matches TIA V21's "Enterprise 24H2 LTSC"; 25H2 is not on Siemens' list | [Microsoft Evaluation Center](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise), [TIA V21 requirements](https://docs.tia.siemens.cloud/r/en-us/v21/installation/system-requirements-for-installation/general-software-and-hardware-requirements) |
| dockur/windows: QEMU/KVM in a container, downloads the ISO from Microsoft, unattended install, web viewer :8006, RDP :3389, `/shared` → `\\host.lan\Data`, `/oem/install.bat` runs after setup. In NAT mode the container forwards its ports to the VM | [github.com/dockur/windows](https://github.com/dockur/windows), [qemus/qemu network.sh](https://github.com/qemus/qemu/blob/master/src/network.sh). **Tried here 2026-11-23** (LTSC 2024 eval installed, SSH and firewall by OEM script), then **removed completely** |
| RAM: TIA V21 minimum 8 GB, PLCSIM Advanced 16 GB minimum. This host has 11 GB in total | sections 2.1, 2.2 |

**RAM decided it.** The Linux host (11 GB) can give a VM 6 GB at most,
below TIA's 8 GB minimum and far from PLCSIM Advanced's 16 GB, and Siemens
does not list QEMU/KVM. The Windows 11 Pro PC (i5-12400F, 16 GB) meets both,
so it is the PLC station and the VM was removed. The PC runs 26H2, newer
than V21's tested 24H2: unsupported on paper, expected to work.

## 6. If the Siemens trial cannot be downloaded

Same station, same week, with CODESYS: the logic in
`plc-training/siemens/lt01/*.scl` is IEC 61131-3 Structured Text apart from
the TIA syntax (`#` before local names, `"..."` around global names,
`{ S7_Optimized_Access }`, `REGION`, `TON_TIME` instead of `TON`, `.db`
blocks instead of global variable lists). Converting the two FBs takes about
30 minutes and is itself a good exercise. CODESYS Control Win SL gives the OPC
UA server for day 4 (restart the soft PLC every 2 hours).

## 7. What was tested here, what was not

| Item | Status |
|---|---|
| Windows VM on the Linux host (dockur/windows, LTSC 2024 eval, OEM script) | installed and checked, then removed (RAM, see section 5) |
| Compose network → Windows PC (LAN and Tailscale) → `plcsim-portproxy.ps1` (port proxy + firewall limited to the lab host) → stand-in listener | tested, then removed |
| TIA Portal / PLCSIM Advanced install and licences | **not tested** (needs your Siemens ID and the licence acceptance) |
| SCL sources compile in TIA Portal | **not tested** (no TIA on Linux). Written to TIA's source syntax; logic checked with a Python mirror of the two FBs (expected results in [../lt01-leak-test.md](../lt01-leak-test.md) section 10) |
| PLCSIM Advanced instance reached from Ignition | **not tested** (day 4 is where you prove it) |
| Machine Expert – Basic simulator reached from Ignition | **not tested** (day 5) |
