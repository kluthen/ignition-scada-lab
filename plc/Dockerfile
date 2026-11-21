# Runtime for the simulated cell controller. The code itself is mounted from ./plc
# (read-only) so edits only need `docker compose restart plc`.
FROM python:3.13-slim
RUN pip install --no-cache-dir --root-user-action=ignore asyncua==2.1.0
WORKDIR /app
CMD ["python", "-u", "main.py"]
