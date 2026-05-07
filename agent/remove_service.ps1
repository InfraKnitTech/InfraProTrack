param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AgentDir

try {
  & $PythonExe agent.py stop
} catch {
  Write-Host "Service was not running."
}

& $PythonExe agent.py remove
Write-Host "InfraProTrack Agent service removed."
