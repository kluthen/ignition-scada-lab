# Make a simulated PLC on this Windows machine reachable from the lab's
# Ignition gateway (Docker on the Linux host). docs/system/plc-engineering.md.
#
# PLCSIM Advanced runs the instance in local TCP/IP mode on the "Siemens PLCSIM
# Virtual Ethernet Adapter" (e.g. 192.168.0.1): that address exists only inside
# this PC. A Windows port proxy listens on this PC's own addresses and forwards
# to it; a firewall rule lets only the lab host in.
#
#   .\plcsim-portproxy.ps1 -AllowFrom 192.0.2.32,100.64.0.1               # S7 102, OPC UA 4840, Modbus 502 -> 192.168.0.1
#   .\plcsim-portproxy.ps1 -Map "5502=127.0.0.1:502" -AllowFrom ...     # Machine Expert - Basic simulator (Friday)
#   .\plcsim-portproxy.ps1 -Remove                                      # delete every proxy and rule made by this script
#
# Run as administrator (an elevated PowerShell, or over SSH as an admin user). Idempotent.
param(
    [string]$PlcIp = "192.168.0.1",
    [int[]]$Ports = @(102, 4840, 502),
    [string[]]$Map = @(),                  # extra "listenport=address:port" entries
    [string[]]$AllowFrom = @(),            # source addresses allowed in (the lab host); required unless -Remove
    [switch]$Remove
)
$tag = "lab-plc-proxy"
if ($Remove) {
    # only the ports this script opened (one firewall rule "lab-plc-proxy <port>" each)
    foreach ($r in @(Get-NetFirewallRule -DisplayName "$tag *" -ErrorAction SilentlyContinue)) {
        $lp = ($r.DisplayName -split ' ')[-1]
        netsh interface portproxy delete v4tov4 listenport=$lp listenaddress=0.0.0.0 | Out-Null
        $r | Remove-NetFirewallRule
    }
    "removed"; netsh interface portproxy show v4tov4; return
}
if ($AllowFrom.Count -eq 0) { throw "give -AllowFrom with the lab host's address(es)" }
$entries = @()
foreach ($p in $Ports) { $entries += ,@($p, $PlcIp, $p) }
foreach ($m in $Map) { $l, $t = $m -split '='; $a, $tp = $t -split ':'; $entries += ,@([int]$l, $a, [int]$tp) }
foreach ($e in $entries) {
    $lp, $ca, $cp = $e
    netsh interface portproxy delete v4tov4 listenport=$lp listenaddress=0.0.0.0 2>$null | Out-Null
    netsh interface portproxy add v4tov4 listenport=$lp listenaddress=0.0.0.0 connectport=$cp connectaddress=$ca
    Get-NetFirewallRule -DisplayName "$tag $lp" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName "$tag $lp" -Direction Inbound -Protocol TCP -LocalPort $lp -RemoteAddress $AllowFrom -Action Allow | Out-Null
}
Set-Service iphlpsvc -StartupType Automatic
Start-Service iphlpsvc
netsh interface portproxy show v4tov4
Get-NetFirewallRule -DisplayName "$tag *" | Select-Object DisplayName, Enabled | Format-Table -AutoSize
