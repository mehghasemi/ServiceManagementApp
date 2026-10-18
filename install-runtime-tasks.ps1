param([switch]$Start)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$releaseName = (Get-Content (Join-Path $root 'private\release-next.txt') -Raw).Trim()
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $root 'private\releases'))
$release = [IO.Path]::GetFullPath((Join-Path $releaseRoot $releaseName))
if ((Split-Path $release -Parent) -ne $releaseRoot -or !(Test-Path "$release\run_preview.py")) { throw 'Invalid release path' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$operations = Join-Path $root ('private\operations\' + (Get-Date -Format yyyyMMddTHHmmssfff))
New-Item $operations -ItemType Directory -Force | Out-Null
foreach ($mode in @('stable', 'development')) {
    $name = "ServiceManagementApp-$mode"
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw "Task already exists: $name. Review before replacing an active release." }
    $source = if ($mode -eq 'stable') { $release } else { $root }
    $db = if ($mode -eq 'stable') { 'preview.sqlite3' } else { 'development.sqlite3' }
    $port = if ($mode -eq 'stable') { 8769 } else { 8768 }
    $config = @{ python=$python; source=$source; database=(Join-Path $root "private\$db"); mode=$mode; port=$port; log=(Join-Path $root "private\$mode-task.log") }
    $config | ConvertTo-Json | Set-Content "$operations\$mode.json" -Encoding UTF8
    Copy-Item "$root\managed_runtime.py" "$operations\managed_runtime.py" -Force
    $action = New-ScheduledTaskAction -Execute (Join-Path $root '.venv\Scripts\pythonw.exe') -Argument "`"$operations\managed_runtime.py`" `"$operations\$mode.json`"" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Independent $mode application runtime; current Windows identity for read-only CRM." | Out-Null
    if ($Start) { Start-ScheduledTask -TaskName $name }
    Write-Output "$name configured on port $port"
}
