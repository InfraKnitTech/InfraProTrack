param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AgentDir

& $PythonExe -m pip install -r requirements.txt
& $PythonExe agent.py install
& $PythonExe agent.py start

Write-Host "InfraProTrack Agent service installed and started."
