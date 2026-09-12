param(
  [string]$HostName,
  [int]$Port,
  [string]$KeyPath = "$PSScriptRoot\..\epalle_runpod_ed25519"
)
$ErrorActionPreference = 'Stop'
if (-not $HostName -or -not $Port) { throw 'Pass the current RunPod public IP as -HostName and mapped SSH port as -Port.' }
$workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$source = Join-Path $workspace 'outputs\libraries\workflows'
scp -r -i $KeyPath -P $Port "$source\*" "root@${HostName}:/workspace/epalle/workflows/"
ssh -i $KeyPath -p $Port "root@$HostName" "mkdir -p /workspace/epalle/ComfyUI/user/default/workflows/EPALLE && find /workspace/epalle/workflows -type f -name '*.json' -exec cp -n '{}' /workspace/epalle/ComfyUI/user/default/workflows/EPALLE/ ';'"
