param([Parameter(Mandatory=$true)][string]$Config)
$ErrorActionPreference = 'Stop'
try {
    $cfg = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
    $env:SERVICE_DATABASE_PATH = $cfg.database
    $env:SERVICE_ENVIRONMENT = $cfg.mode
    $env:SERVICE_MODE = 'local'
    Set-Location -LiteralPath $cfg.source
    # Bounded startup log retention; logs are private, never committed.
    if ((Test-Path $cfg.log) -and (Get-Item $cfg.log).Length -gt 10MB) { Move-Item -LiteralPath $cfg.log -Destination ($cfg.log + '.previous') -Force }
    $process = Start-Process -FilePath $cfg.python -ArgumentList ('"' + (Join-Path $cfg.source 'run_preview.py') + '"'),$cfg.port -WorkingDirectory $cfg.source -WindowStyle Hidden -RedirectStandardOutput $cfg.log -RedirectStandardError ($cfg.log + '.error') -PassThru -Wait
    # Any unexpected exit must activate the scheduler restart policy.
    exit 1
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
