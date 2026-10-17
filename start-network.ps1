param(
    [string]$ServerAddress = '172.16.5.18',
    [string]$AllowedSubnet = '172.16.5.0/24',
    [int]$Port = 8766
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' 'run_lan.py' '--host' $ServerAddress '--subnet' $AllowedSubnet '--port' $Port
