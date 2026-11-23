"""Write LT01_tags.xlsx: the PLC tag table "LT01" in the layout TIA Portal
exports and imports (PLC tags > Import). The same table is in
docs/lt01-leak-test.md section 3 for typing by hand if the import refuses it.
Run (from the repo root, with the exporter image, which has openpyxl):
  docker run --rm -v "$PWD/plc-training/siemens/lt01:/src" -u "$(id -u):$(id -g)" \
    --entrypoint python ignition-lab-exporter /src/make_tags_xlsx.py
"""
import os, sys
from openpyxl import Workbook

TAGS = [  # name, type, address, comment
    ("PB_Start", "Bool", "%I0.0", "Start push button (NO)"),
    ("PB_Stop", "Bool", "%I0.1", "Stop push button (NC, TRUE = not pressed)"),
    ("PB_Reset", "Bool", "%I0.2", "Fault reset push button (NO)"),
    ("EStopOK", "Bool", "%I0.3", "Safety relay feedback, TRUE = e-stop circuit healthy"),
    ("SW_Auto", "Bool", "%I0.4", "Mode selector, TRUE = automatic"),
    ("B_PartPresent", "Bool", "%I0.5", "Part present in the test nest"),
    ("B_ClampClosed", "Bool", "%I0.6", "Clamp cylinder closed"),
    ("B_ClampOpen", "Bool", "%I0.7", "Clamp cylinder open"),
    ("B_AirOK", "Bool", "%I1.0", "Compressed air supply OK"),
    ("PT01_Raw", "Int", "%IW64", "Test pressure transmitter, 0..27648 = 0..10 bar"),
    ("Y_ClampClose", "Bool", "%Q0.0", "Clamp valve, TRUE closes"),
    ("Y_Fill", "Bool", "%Q0.1", "Fill valve"),
    ("Y_Vent", "Bool", "%Q0.2", "Vent valve"),
]

wb = Workbook()
ws = wb.active
ws.title = "PLC Tags"
ws.append(["Name", "Path", "Data Type", "Logical Address", "Comment",
           "Hmi Visible", "Hmi Accessible", "Hmi Writeable", "Typeobject ID", "Version ID"])
for name, typ, addr, comment in TAGS:
    ws.append([name, "LT01", typ, addr, comment, "True", "True", "True", "", ""])
out = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "LT01_tags.xlsx")
wb.save(out)
print("wrote", out, len(TAGS), "tags")
