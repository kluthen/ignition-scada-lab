# plc-training: material for training week 50

Copied to the Windows PLC PC as `C:\PLC-Training` by `scripts/plc-pc push`
(and back from its `work/` folders by `scripts/plc-pc pull`). Plan:
[../docs/training/week-50.md](../docs/training/week-50.md), station:
[../docs/system/plc-engineering.md](../docs/system/plc-engineering.md).

| Path | Content |
|---|---|
| `siemens/lt01/01..06_*` | the LT01 station program as TIA Portal external sources: UDTs, FB `LT01_ProcessSim` (plant model), FB `LT01_Seq` (sequence), DBs, FCs `LT01_IoRead/IoWrite`, OB1 `Main`. Generate in file order. Spec: [../docs/lt01-leak-test.md](../docs/lt01-leak-test.md) |
| `siemens/lt01/LT01_tags.xlsx` | PLC tag table `LT01` for *PLC tags > Import*, made by `make_tags_xlsx.py` |
| `siemens/work/dayN/` | your exported sources at the end of each day (*Generate source from blocks*), versioned and reviewed |
| `schneider/work/` | your Machine Expert – Basic exports (day 5) |
| `windows/plcsim-portproxy.ps1` | forwards S7 / OPC UA / Modbus ports of the Windows machine to the PLCSIM Advanced instance (or the M221 simulator), with firewall rules limited to the lab host; `-Remove` undoes it |


The delivered sources are the reference: keep them unchanged and put your
own versions under `siemens/work/`.
