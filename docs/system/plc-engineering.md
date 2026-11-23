# PLC engineering station (Windows)

The PLC tools of training week 50 (TIA Portal, S7-PLCSIM, PLCSIM Advanced,
Machine Expert – Basic; CODESYS as a fallback) are Windows-only, and so are
the simulated PLCs the Ignition gateway connects to. They run on a Windows 11
Pro PC on the LAN (i5-12400F, 16 GB RAM), outside Docker. Choice and sources:
[../training/plc-options.md](../training/plc-options.md).

A Windows VM on the lab host (QEMU/KVM in Docker, dockur/windows) was set up
and tested on 2026-11-23, then removed: the 11 GB host can give it 6 GB at
most, below TIA Portal's 8 GB minimum and PLCSIM Advanced's 16 GB.

The PC's name and addresses stay in `.env` (git-ignored): the repository is
public.

## The Windows PC

| Item | State (2026-11-23) |
|---|---|
| OS | Windows 11 Pro 26H2 (build 26300). TIA Portal V21 lists Windows 11 Pro **24H2**: 26H2 is newer than the tested list (unsupported on paper, expected to work; V21.1 may extend the list) |
| Hyper-V | enabled on the PC. Siemens' Hyper-V notes concern TIA running *inside* a Hyper-V VM talking to the outside; local TCP/IP mode on the host is not affected (PLCSIM Advanced V6.0 function manual, 7.15) |
| Account | administrator, OpenSSH server running |
| Network | Ethernet on the lab host's LAN, Tailscale; both reach the PC from the compose network (tested) |
| Siemens / Schneider software | none installed yet (your part before the week, [../training/week-50.md](../training/week-50.md)) |
| Training folder | `C:\PLC-Training` (sources pushed 2026-11-23) |

### Files: `scripts/plc-pc`

```bash
scripts/plc-pc push          # plc-training/{README.md,siemens,schneider,windows/*.ps1} -> C:\PLC-Training
scripts/plc-pc pull          # C:\PLC-Training\{siemens,schneider}\work -> plc-training/.../work (for review and git)
scripts/plc-pc ps -c 'Get-Date'           # one PowerShell command on the PC
scripts/plc-pc ps < something.ps1         # a script
```

Settings in `.env`: `PLC_PC_SSH` (ssh alias), `PLC_PC_HOST` (address the
gateway uses: prefer a stable one, the Tailscale address or a fixed LAN IP),
`PLC_PC_DIR`.

### Network path to a simulated PLC

```
 gateway container ──► PLC_PC_HOST:4840 / :102 / :502   (Docker NAT → LAN or Tailscale)
   └─ Windows firewall: rule "lab-plc-proxy <port>", only from the lab host's addresses
        └─ netsh portproxy 0.0.0.0:<port> → 192.168.0.1:<port>
             └─ "Siemens PLCSIM Virtual Ethernet Adapter" (local TCP/IP mode)
                  └─ PLCSIM Advanced instance LT01, 192.168.0.1: S7 102, OPC UA 4840, Modbus 502
```

- PLCSIM Advanced runs the instance in **local** TCP/IP mode on its virtual
  adapter: the instance IP exists only inside the PC, no promiscuous mode,
  no virtual switch on the real NIC, no clash with the LAN. The port proxy
  publishes it on the PC's own addresses.
- `C:\PLC-Training\windows\plcsim-portproxy.ps1` (elevated) does both the
  proxies and the firewall rules:
  `.\plcsim-portproxy.ps1 -AllowFrom <lab host LAN IP>,<lab host Tailscale IP>`;
  `-Map "5502=127.0.0.1:502"` for the Machine Expert – Basic simulator,
  which listens on 127.0.0.1:502 (5502 so it does not clash with the PLCSIM
  proxy on 502); `-Remove` deletes only what the script created.
  Containers reach the LAN and Tailscale through the host's NAT, so the
  source address the PC sees is the lab host's.
- **OPC UA endpoint URLs**: the S7-1500 server advertises its own address
  (`opc.tcp://192.168.0.1:4840`) in GetEndpoints, which the gateway cannot
  reach. Set **Host Override** to `PLC_PC_HOST` in the Ignition OPC UA
  connection (advanced settings), so the client keeps using the address it
  discovered the server with.

### Verified (2026-11-23)

| Check | Result |
|---|---|
| Compose network → PC, LAN and Tailscale addresses (TCP 22) | reachable |
| Compose network → PC port proxy (0.0.0.0:14840 → 127.0.0.1:14841) → test listener, through `plcsim-portproxy.ps1` with a firewall rule limited to the lab host | data received, over LAN and over Tailscale; proxies and rules removed afterwards |
| PLCSIM Advanced instance behind the proxy, OPC UA from Ignition | not yet: needs TIA / PLCSIM installed (week 50, Thursday) |
