"""Daily production export of the finishing area (docs/system/kpi.md).

For each production day it writes one folder, ready to ship:

    exports/daily/<YYYY-MM-DD>/
        FIN_<date>_report.pdf        daily report (KPIs, OEE per cell, production, charts, downtime, rejects, orders)
        FIN_<date>_production.xlsx   the same tables, one sheet each, plus the order list
        FIN_<date>_<table>.csv       one CSV per table, and the part records (traceability, MES-TRC-03)
        manifest.json                period, completeness, area KPIs, files with size, rows and SHA-256

The figures come from the KPI functions in schema mes (db/init/20-kpi.sql),
the same ones the HMI KPI page uses. A folder appears in one step (written
under a temporary name, then renamed): a folder with a manifest is complete.

Usage:
    daily_export.py serve                  scheduler (compose service "exporter"): exports every
                                           finished day not yet exported, EXPORT_DELAY_MIN after its end
    daily_export.py run [DAY] [--force]    one day: YYYY-MM-DD, "yesterday" (default) or "today"
                                           (today gives a partial export, marked complete: false)

Database: libpq environment (PGHOST, PGUSER, PGPASSWORD, PGDATABASE).
"""

from __future__ import annotations

import csv
import datetime as dt
import decimal
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import psycopg
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "/exports/daily"))
DELAY_MIN = int(os.environ.get("EXPORT_DELAY_MIN", "10"))       # wait after the end of the day
CATCHUP_DAYS = int(os.environ.get("EXPORT_CATCHUP_DAYS", "7"))  # how far back serve fills gaps
PARTS_CSV = os.environ.get("EXPORT_PARTS_CSV", "1") == "1"      # part records (largest file)
POLL_S = 300
AREA = "FIN"
GENERATOR = "exporter/daily_export.py 1.0"

BLUE, ORANGE = colors.HexColor("#2a78d6"), colors.HexColor("#eb6834")
INK, INK2, RULE, HEAD = colors.HexColor("#1F2933"), colors.HexColor("#52514e"), colors.HexColor("#C9CED4"), \
    colors.HexColor("#E6E8EB")


def log(msg: str) -> None:
    print(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}", flush=True)


# --------------------------------------------------------------------------- data

# name -> (title, SQL over %(f)s / %(t)s). Every figure comes from a mes.* KPI function.
TABLES = {
    "oee": ("OEE per cell", """
        SELECT cell, round((oee * 100)::numeric, 1) AS oee_pct,
               round((availability * 100)::numeric, 1) AS availability_pct,
               round((performance * 100)::numeric, 1) AS performance_pct,
               round((quality * 100)::numeric, 1) AS quality_pct,
               good, rejects, scrapped, total,
               round((planned_s / 3600)::numeric, 2) AS planned_h, round((run_s / 3600)::numeric, 2) AS run_h,
               round((down_s / 60)::numeric, 1) AS down_min
        FROM mes.oee(%(f)s, %(t)s)"""),
    "production": ("Production per cell and product", """
        SELECT cell, product_code, good, rejects, scrapped, total, round(reject_pct::numeric, 2) AS reject_pct,
               first_part, last_part
        FROM mes.production(%(f)s, %(t)s)"""),
    "hourly": ("Production per hour and cell", """
        SELECT hour, cell, good, not_good FROM mes.hourly(%(f)s, %(t)s)"""),
    "downtime": ("Downtime per cell and reason", """
        SELECT cell, category, reason, round((seconds / 60)::numeric, 1) AS minutes, stops
        FROM mes.downtime(%(f)s, %(t)s) ORDER BY cell, seconds DESC"""),
    "rejects": ("Rejects and scrap per cell and defect", """
        SELECT cell, defect_code, defect, result, parts FROM mes.rejects(%(f)s, %(t)s) ORDER BY cell, parts DESC"""),
    "orders": ("Orders worked", """
        SELECT order_id, product_code, cell, status, target_qty, good, rejects, good_in_period,
               rejects_in_period, plc_good, plc_rejects, started_at, ended_at,
               round(duration_min::numeric, 1) AS duration_min
        FROM mes.orders(%(f)s, %(t)s)"""),
}
PARTS_SQL = """
    SELECT produced_at, cell, part_id, order_id, product_code, part_type, measured_mm,
           CASE result WHEN 1 THEN 'Good' WHEN 2 THEN 'Reject' ELSE 'Scrapped' END AS result,
           defect_code, startup_time, sequence
    FROM mes.part_result WHERE produced_at >= %(f)s AND produced_at < %(t)s
    ORDER BY produced_at, cell"""


def connect() -> psycopg.Connection:
    conn = psycopg.connect(autocommit=True)
    site = conn.execute("SELECT timezone FROM mes.site ORDER BY site LIMIT 1").fetchone()
    conn.execute(f"SET TIME ZONE '{site[0]}'")
    return conn


def fetch(conn, sql: str, params: dict) -> tuple[list[str], list[tuple]]:
    cur = conn.execute(sql, params)
    return [d.name for d in cur.description], cur.fetchall()


def day_info(conn, day: dt.date) -> dict:
    f, t = conn.execute("SELECT t_from, t_to FROM mes.day_bounds(%s)", (day,)).fetchone()
    now, site, name, tz = conn.execute(
        "SELECT now(), site, name, timezone FROM mes.site ORDER BY site LIMIT 1").fetchone()
    return {"day": day, "f": f, "t": t, "now": now, "complete": now >= t, "site": site, "site_name": name, "tz": tz}


# --------------------------------------------------------------------------- writers

def cell_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        return v.isoformat(timespec="milliseconds" if v.microsecond else "seconds")
    return str(v)


def write_csv(path: Path, cols: list[str], rows: list[tuple]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([cell_text(v) for v in r])


def xlsx_value(v):
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None)  # local time of the site; Excel has no time zones
    return v


def write_xlsx(path: Path, info: dict, data: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "About"
    for row in (("Report", f"Daily production, finishing area {AREA}"), ("Site", info["site_name"]),
                ("Production day", info["day"].isoformat()),
                ("Period", f"{cell_text(info['f'])} to {cell_text(info['t'])} ({info['tz']}, local times in sheets)"),
                ("Complete", "yes" if info["complete"] else f"no, data up to {cell_text(info['now'])}"),
                ("Generated", cell_text(dt.datetime.now().astimezone())), ("Source", "mes.* KPI functions, "
                 "same figures as the HMI KPI page"),
                ("Definitions", "OEE = Availability x Performance x Quality. Planned time = time covered by the "
                 "state log (24/7, no shift calendar yet).")):
        ws.append(row)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 16, 100
    bold, fill = Font(bold=True), PatternFill("solid", fgColor="E6E8EB")
    for name, (title, _) in TABLES.items():
        cols, rows = data[name]
        ws = wb.create_sheet(name)
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = bold, fill
        for r in rows:
            ws.append([xlsx_value(v) for v in r])
        for i, col in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(10, len(col) + 2,
                                                                   19 if col.endswith(("_at", "_part", "hour")) else 0)
            if col.endswith(("_at", "_part", "hour")):
                for c in ws.iter_cols(min_col=i, max_col=i, min_row=2):
                    for x in c:
                        x.number_format = "yyyy-mm-dd hh:mm:ss"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def fmt(v, pattern="{:,.0f}") -> str:
    if v is None:
        return "-"
    if isinstance(v, dt.datetime):
        return v.strftime("%H:%M")
    if isinstance(v, (int, float, decimal.Decimal)):
        return pattern.format(float(v)).replace(",", " ")
    return str(v)


def pdf_table(header: list[str], rows: list[list[str]], widths: list[float], total_row=False, text_cols=1) -> Table:
    t = Table([header] + rows, colWidths=[w * mm for w in widths], repeatRows=1)
    style = [("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
             ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("BACKGROUND", (0, 0), (-1, 0), HEAD),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE), ("ALIGN", (text_cols, 0), (-1, -1), "RIGHT"),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if total_row:
        style.append(("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8))
    t.setStyle(TableStyle(style))
    return t


def hourly_chart(hourly_area: list[tuple]) -> Drawing:
    d = Drawing(180 * mm, 62 * mm)
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 14 * mm, 14 * mm, 160 * mm, 44 * mm
    c.data = [[float(r[1]) for r in hourly_area], [float(r[2]) for r in hourly_area]]
    c.categoryAxis.categoryNames = [r[0].strftime("%H") for r in hourly_area]
    c.categoryAxis.labels.fontSize = 6
    c.categoryAxis.style = "stacked"
    c.valueAxis.valueMin = 0
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.visibleGrid, c.valueAxis.gridStrokeColor, c.valueAxis.gridStrokeWidth = True, RULE, 0.25
    c.bars.strokeColor, c.bars.strokeWidth = colors.white, 0.5
    c.bars[0].fillColor, c.bars[1].fillColor = BLUE, ORANGE
    c.barSpacing, c.groupSpacing = 0, 2
    d.add(c)
    lg = Legend()
    lg.x, lg.y, lg.fontSize, lg.columnMaximum, lg.alignment = 120 * mm, 60 * mm, 7, 1, "right"
    lg.colorNamePairs = [(BLUE, "Good"), (ORANGE, "Not good")]
    lg.dx, lg.dy, lg.deltax = 6, 6, 50
    d.add(lg)
    d.add(String(14 * mm, 3 * mm, "hour of the day (local time), parts per hour, all cells", fontSize=7,
                 fillColor=INK2))
    return d


def write_pdf(path: Path, info: dict, data: dict, area: dict, hourly_area: list[tuple]) -> None:
    ss = getSampleStyleSheet()
    h1, h2, body = ss["Title"], ss["Heading3"], ss["BodyText"]
    h1.alignment, h1.fontSize, h1.textColor = 0, 16, INK
    h2.textColor, h2.spaceBefore, h2.spaceAfter = INK, 8, 3
    small = ss["BodyText"].clone("small", fontSize=7.5, textColor=INK2, leading=9)
    day = info["day"]
    status = "complete day" if info["complete"] else \
        f"<font color='#D9480F'>PARTIAL: data up to {info['now'].strftime('%H:%M')}</font>"
    story = [
        Paragraph(f"Daily production report &middot; finishing area {AREA}", h1),
        Paragraph(f"{info['site_name']} &middot; production day <b>{day.strftime('%A %d %B %Y')}</b> "
                  f"({info['f'].strftime('%d/%m %H:%M')} to {info['t'].strftime('%d/%m %H:%M')}, {info['tz']}) "
                  f"&middot; {status}", body),
        Spacer(1, 4 * mm),
    ]
    # Headline figures (area row of mes.oee).
    tiles = [("OEE", area.get("oee_pct"), "{:.1f} %"), ("Availability", area.get("availability_pct"), "{:.1f} %"),
             ("Performance", area.get("performance_pct"), "{:.1f} %"),
             ("Quality", area.get("quality_pct"), "{:.1f} %"),
             ("Good parts", area.get("good"), "{:,.0f}"),
             ("Not good", (area.get("rejects") or 0) + (area.get("scrapped") or 0), "{:,.0f}"),
             ("Downtime min", area.get("down_min"), "{:,.0f}")]
    t = Table([[x[0] for x in tiles], [fmt(x[1], x[2]) for x in tiles]], colWidths=[25.5 * mm] * 7)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica", 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), INK2),
                           ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 14), ("TEXTCOLOR", (0, 1), (-1, 1), INK),
                           ("BOX", (0, 0), (-1, -1), 0.5, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
                           ("TOPPADDING", (0, 1), (-1, 1), 4), ("BOTTOMPADDING", (0, 1), (-1, 1), 6)]))
    story += [t]

    cols, rows = data["oee"]
    i = {c: n for n, c in enumerate(cols)}
    def section(title, flowable):
        story.append(KeepTogether([Paragraph(title, h2), flowable]))

    section("OEE per cell", pdf_table(
        ["Cell", "OEE %", "A %", "P %", "Q %", "Good", "Rejects", "Scrap", "Planned h", "Run h", "Down min"],
        [[r[i["cell"]] if r[i["cell"]] != AREA else f"{AREA} (area)", fmt(r[i["oee_pct"]], "{:.1f}"),
          fmt(r[i["availability_pct"]], "{:.1f}"), fmt(r[i["performance_pct"]], "{:.1f}"),
          fmt(r[i["quality_pct"]], "{:.1f}"), fmt(r[i["good"]]), fmt(r[i["rejects"]]), fmt(r[i["scrapped"]]),
          fmt(r[i["planned_h"]], "{:.2f}"), fmt(r[i["run_h"]], "{:.2f}"), fmt(r[i["down_min"]], "{:.1f}")]
         for r in rows], [24, 14, 14, 14, 14, 17, 15, 13, 17, 15, 17], total_row=True))

    cols, rows = data["production"]
    section("Production per cell and product", pdf_table(
        ["Cell", "Product", "Good", "Rejects", "Scrap", "Total", "Reject %", "First part", "Last part"],
        [[r[0], r[1], fmt(r[2]), fmt(r[3]), fmt(r[4]), fmt(r[5]), fmt(r[6], "{:.2f}"), fmt(r[7]), fmt(r[8])]
         for r in rows], [16, 22, 18, 16, 14, 18, 16, 20, 20], text_cols=2))

    section("Production per hour", hourly_chart(hourly_area))

    cols, rows = data["downtime"]
    by_reason: dict[tuple, list] = {}
    for cell, cat, reason, minutes, stops in rows:
        acc = by_reason.setdefault((reason, cat), [0.0, 0])
        acc[0] += float(minutes)
        acc[1] += int(stops)
    total_down = sum(v[0] for v in by_reason.values()) or 1.0
    cum, pareto = 0.0, []
    for (reason, cat), (minutes, stops) in sorted(by_reason.items(), key=lambda kv: -kv[1][0])[:5]:
        cum += minutes
        pareto.append([reason, cat, fmt(minutes, "{:.1f}"), fmt(stops), fmt(100 * minutes / total_down, "{:.1f}"),
                       fmt(100 * cum / total_down, "{:.1f}")])
    section("Downtime Pareto, top 5 (all cells)", pdf_table(
        ["Reason", "Category", "Minutes", "Stops", "% of downtime", "Cumulative %"], pareto,
        [40, 30, 20, 18, 26, 26], text_cols=2))

    cols, rows = data["rejects"]
    by_defect: dict[tuple, int] = {}
    for cell, code, defect, result, parts in rows:
        by_defect[(defect, result)] = by_defect.get((defect, result), 0) + int(parts)
    section("Rejects and scrap by defect (all cells)", pdf_table(
        ["Defect", "Result", "Parts"], [[d, r, fmt(n)] for (d, r), n in sorted(by_defect.items(),
                                                                               key=lambda kv: -kv[1])],
        [40, 30, 20], text_cols=2))

    cols, rows = data["orders"]
    i = {c: n for n, c in enumerate(cols)}
    summary: dict[tuple, dict] = {}
    for r in rows:
        s = summary.setdefault((r[i["cell"]], r[i["product_code"]]),
                               {"Completed": 0, "ClosedShort": 0, "open": 0, "dur": [], "good": 0})
        st = r[i["status"]]
        s[st if st in ("Completed", "ClosedShort") else "open"] += 1
        if st == "Completed" and r[i["duration_min"]] is not None:
            s["dur"].append(float(r[i["duration_min"]]))
        s["good"] += int(r[i["good_in_period"]])
    section("Orders worked (full list in the XLSX and orders CSV)", pdf_table(
        ["Cell", "Product", "Completed", "Closed short", "Open at day end", "Mean duration min", "Good in day"],
        [[c, p, fmt(s["Completed"]), fmt(s["ClosedShort"]), fmt(s["open"]),
          fmt(sum(s["dur"]) / len(s["dur"]) if s["dur"] else None, "{:.1f}"), fmt(s["good"])]
         for (c, p), s in sorted(summary.items())], [16, 22, 20, 22, 26, 30, 22], text_cols=2))

    story += [Spacer(1, 4 * mm), Paragraph(
        "OEE = Availability &times; Performance &times; Quality (oee.com definitions, MES-OEE-01..04). Planned "
        "production time = time covered by the PackML state log (the lab runs 24/7, no shift calendar or planned "
        "breaks yet). Performance uses the ideal cycle time of each product and is not capped. Changeover "
        "(Order complete until the next Execute) counts as downtime. Figures come from the mes.* KPI functions, "
        "the same as the HMI KPI page. Not included yet: alarms (none configured), energy per good part, "
        "shift-lead comments (MES-RPT-01).", small)]

    generated = dt.datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(INK2)
        canvas.drawString(15 * mm, 10 * mm, f"Brevent Hydraulics (fictional) - {AREA} daily report {day.isoformat()}"
                                            f" - generated {generated} - lab system, not for customer use")
        canvas.drawRightString(195 * mm, 10 * mm, f"page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=16 * mm, title=f"{AREA} daily production report {day.isoformat()}",
                            author="ignition-lab exporter")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


# --------------------------------------------------------------------------- export

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_of(day: dt.date) -> dict | None:
    p = EXPORT_DIR / day.isoformat() / "manifest.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def export_day(conn, day: dt.date) -> Path:
    info = day_info(conn, day)
    p = {"f": info["f"], "t": info["t"]}
    data = {name: fetch(conn, sql, p) for name, (_, sql) in TABLES.items()}
    cols, rows = data["oee"]
    area = dict(zip(cols, next((r for r in rows if r[0] == AREA), [None] * len(cols))))
    _, hourly_area = fetch(conn, "SELECT hour, good, not_good FROM mes.hourly_area(%(f)s, %(t)s)", p)

    final = EXPORT_DIR / day.isoformat()
    tmp = EXPORT_DIR / f".{day.isoformat()}.tmp-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    stem = f"{AREA}_{day.isoformat()}"
    files = []  # (name, rows, content)
    write_pdf(tmp / f"{stem}_report.pdf", info, data, area, hourly_area)
    files.append((f"{stem}_report.pdf", None, "daily report"))
    write_xlsx(tmp / f"{stem}_production.xlsx", info, data)
    files.append((f"{stem}_production.xlsx", None, "all tables, one sheet each"))
    for name, (title, _) in TABLES.items():
        cols, rows = data[name]
        write_csv(tmp / f"{stem}_{name}.csv", cols, rows)
        files.append((f"{stem}_{name}.csv", len(rows), title))
    if PARTS_CSV:
        cols, rows = fetch(conn, PARTS_SQL, p)
        write_csv(tmp / f"{stem}_parts.csv", cols, rows)
        files.append((f"{stem}_parts.csv", len(rows), "part records (traceability)"))

    manifest = {
        "format": "fin-daily-export/1",
        "site": info["site"], "area": AREA, "production_day": day.isoformat(),
        "period": {"from": cell_text(info["f"]), "to": cell_text(info["t"]), "timezone": info["tz"]},
        "complete": info["complete"],
        "data_until": cell_text(min(info["now"], info["t"])),
        "generated_at": cell_text(dt.datetime.now().astimezone()),
        "generator": GENERATOR,
        "kpi": {k: (float(v) if isinstance(v, decimal.Decimal) else v) for k, v in area.items() if k != "cell"},
        "files": [{"name": n, "content": c, "bytes": (tmp / n).stat().st_size, "rows": r,
                   "sha256": sha256(tmp / n)} for n, r, c in files],
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    old = None
    if final.exists():
        old = EXPORT_DIR / f".{day.isoformat()}.old-{os.getpid()}"
        final.rename(old)
    tmp.rename(final)
    if old:
        shutil.rmtree(old, ignore_errors=True)
    log(f"exported {day} ({'complete' if info['complete'] else 'partial'}) to {final}")
    return final


def catch_up(conn) -> None:
    today, first = conn.execute(
        "SELECT mes.production_day(now()), mes.production_day(min(started_at)) FROM mes.cell_state").fetchone()
    if first is None:
        return
    day = max(first, today - dt.timedelta(days=CATCHUP_DAYS))
    while day < today:
        info = day_info(conn, day)
        due = info["now"] >= info["t"] + dt.timedelta(minutes=DELAY_MIN)
        m = manifest_of(day)
        if due and not (m and m.get("complete")):
            export_day(conn, day)
        day += dt.timedelta(days=1)


def serve() -> None:
    log(f"exporter started: {EXPORT_DIR}, delay {DELAY_MIN} min, catch-up {CATCHUP_DAYS} days")
    while True:
        try:
            with connect() as conn:
                catch_up(conn)
        except Exception:  # keep the scheduler alive; the next poll retries
            log("export failed:\n" + traceback.format_exc())
        time.sleep(POLL_S)


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "serve":
        serve()
    elif argv[0] == "run":
        args = [a for a in argv[1:] if not a.startswith("--")]
        with connect() as conn:
            today = conn.execute("SELECT mes.production_day(now())").fetchone()[0]
            arg = args[0] if args else "yesterday"
            day = {"today": today, "yesterday": today - dt.timedelta(days=1)}.get(arg) or dt.date.fromisoformat(arg)
            m = manifest_of(day)
            if m and m.get("complete") and "--force" not in argv:
                print(f"{day} already exported (complete); use --force to rewrite")
                return
            export_day(conn, day)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
