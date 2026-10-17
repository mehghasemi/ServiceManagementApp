# Run once in PowerShell as Administrator on the application host.
# Restrict inbound access to the company subnet and Domain profile.
$ErrorActionPreference = 'Stop'
$ruleName = 'ServiceManagementApp LAN 8766'
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8766 -LocalAddress 172.16.5.18 -RemoteAddress 172.16.5.0/24 -Profile Domain -Enabled True
}
