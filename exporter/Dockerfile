# Runtime for the daily production export (docs/system/kpi.md). The code is
# mounted from ./exporter (read-only), so edits only need a restart.
FROM python:3.13-slim
RUN pip install --no-cache-dir --root-user-action=ignore \
        "psycopg[binary]==3.3.9" openpyxl==3.1.5 reportlab==5.1.0
WORKDIR /app
CMD ["python", "-u", "daily_export.py", "serve"]
