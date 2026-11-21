FROM python:3.13-slim

ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl jq less procps iputils-ping netcat-openbsd postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# Clients for poking the PLC (Modbus) and Ignition's OPC UA server from scripts/tests.
RUN pip install --no-cache-dir --root-user-action=ignore pymodbus==3.16.2 asyncua==2.1.0

RUN groupadd -g ${USER_GID} dev && useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash dev
USER dev
WORKDIR /workspace
