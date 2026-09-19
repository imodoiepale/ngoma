param(
  [string]$HostName,
  [int]$Port,
  [string]$KeyPath = "$PSScriptRoot\..\epalle_runpod_ed25519"
)
# Ship the repo's workflows/ tree to the pod.
#
#   workflows/**/*.json           -> /workspace/epalle/workflows/           (the reviewed library;
#                                    setup-pod.sh and the remote step below copy the workflow
#                                    graphs into ComfyUI/user/default/workflows/EPALLE)
#   workflows/icekiub/nodes/<pack> -> /workspace/epalle/node-packs/<pack>   (staging; installed into
#                                    ComfyUI/custom_nodes by setup-pod.sh, or right away below when
#                                    the pod already has a ComfyUI)
#
# Which Icekiub packs go up, and why:
#   icynodes                       merged pack (2026-09-16). It registers the SAME node class names as
#                                  the four standalone folders it replaces, so those four must never be
#                                  installed next to it: ComfyUI loads both, the second registration
#                                  wins or fails, and every Icekiub graph breaks. The standalone folders
#                                  stay in the repo only as the record of what each lesson shipped
#                                  (see SUPERSEDED_BY_ICYNODES in packages/library/tools/import_skool_pack.py).
#   ComfyUI-IcyQwen3               not merged into icynodes; shipped as-is.
#   ComfyUI-icyTikTokDownloader    not merged into icynodes; shipped as-is.
#   comfyui-unsafe-torch           NEVER. It patches torch.load so any model file can run code
#                                  (NEVER_IMPORT in import_skool_pack.py). Excluded here and in setup-pod.sh.
$ErrorActionPreference = 'Stop'
if (-not $HostName -or -not $Port) { throw 'Pass the current RunPod public IP as -HostName and mapped SSH port as -Port.' }
$workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$source = Join-Path $workspace 'workflows'
if (-not (Test-Path $source)) { throw "No workflows/ tree at $source" }

$ShipPacks = @('icynodes', 'ComfyUI-IcyQwen3', 'ComfyUI-icyTikTokDownloader')
$SupersededByIcynodes = @('betterimage_loader', 'ICYLM', 'icymegapixelresize', 'ComfyUI-IcyHider-icekiub')
$NeverInstall = @('comfyui-unsafe-torch')

$remoteRoot = '/workspace/epalle'
$comfy = "$remoteRoot/ComfyUI"
$venvPy = "$remoteRoot/venv/bin/python"

# scp has no --exclude, so build the exact tree to ship in a temp folder and scp that.
$staging = Join-Path ([IO.Path]::GetTempPath()) ("epalle-sync-" + [guid]::NewGuid().ToString('N'))
$stageWf = Join-Path $staging 'workflows'
$stagePacks = Join-Path $staging 'node-packs'
New-Item -ItemType Directory -Path $stageWf, $stagePacks | Out-Null
try {
  # 1. The workflow library: every file under workflows/ except the node packs (shipped separately
  #    below) and the Skool import records, which are not workflows.
  Get-ChildItem -Path $source -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($source.Length + 1)
    if ($rel -like 'icekiub\nodes\*') { return }
    if ($rel -like 'icekiub\skool\*') { return }
    if ($rel -match '\\__pycache__\\' -or $_.Extension -eq '.pyc') { return }
    $dest = Join-Path $stageWf $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $dest
  }

  # 2. The node packs listed in $ShipPacks, minus caches and any nested .git.
  $nodes = Join-Path $source 'icekiub\nodes'
  foreach ($pack in $ShipPacks) {
    if ($NeverInstall -contains $pack -or $SupersededByIcynodes -contains $pack) { throw "$pack must not be shipped" }
    $packSrc = Join-Path $nodes $pack
    if (-not (Test-Path $packSrc)) { Write-Warning "node pack $pack is not in $nodes; skipping"; continue }
    Copy-Item -Recurse -LiteralPath $packSrc -Destination (Join-Path $stagePacks $pack)
  }
  Get-ChildItem -Path $stagePacks -Recurse -Force -Directory | Where-Object { $_.Name -in @('__pycache__', '.git', '.zcode') } |
    Remove-Item -Recurse -Force
  Get-ChildItem -Path $stagePacks -Recurse -Force -File -Filter '*.pyc' | Remove-Item -Force

  $wfCount = (Get-ChildItem -Path $stageWf -Recurse -File -Filter '*.json' | Where-Object { $_.Name -notlike '*.ports.json' -and $_.Name -ne 'manifest.json' }).Count
  Write-Host "shipping $wfCount workflow graphs and $($ShipPacks.Count) node pack(s) to root@${HostName}:$remoteRoot"

  ssh -i $KeyPath -p $Port "root@$HostName" "mkdir -p $remoteRoot/workflows $remoteRoot/node-packs"
  scp -r -i $KeyPath -P $Port "$stageWf\*" "root@${HostName}:$remoteRoot/workflows/"
  scp -r -i $KeyPath -P $Port "$stagePacks\*" "root@${HostName}:$remoteRoot/node-packs/"

  # 3. On the pod: expose the graphs to the ComfyUI UI (port maps and the manifest are studio
  #    files, not graphs, so they stay out of the UI folder) and, if ComfyUI is already set up,
  #    install the shipped packs now. setup-pod.sh does the same for a fresh volume.
  $stalePacks = ($SupersededByIcynodes + $NeverInstall | ForEach-Object { "$comfy/custom_nodes/$_" }) -join ' '
  $remote = @(
    "mkdir -p $comfy/user/default/workflows/EPALLE",
    "find $remoteRoot/workflows -type f -name '*.json' ! -name '*.ports.json' ! -name manifest.json -exec cp -n '{}' $comfy/user/default/workflows/EPALLE/ ';'",
    ("if [ -d $comfy/custom_nodes ]; then rm -rf $stalePacks; " +
     "for p in $($ShipPacks -join ' '); do rm -rf $comfy/custom_nodes/`$p && cp -r $remoteRoot/node-packs/`$p $comfy/custom_nodes/`$p; " +
     "if [ -x $venvPy ] && [ -f $comfy/custom_nodes/`$p/requirements.txt ]; then $venvPy -m pip install -q -r $comfy/custom_nodes/`$p/requirements.txt; fi; done; " +
     "echo 'node packs installed; restart ComfyUI (bash $remoteRoot/start-comfy.sh) to load them'; " +
     "else echo 'no ComfyUI yet: run bash $remoteRoot/setup-pod.sh to install the staged packs'; fi")
  ) -join ' && '
  ssh -i $KeyPath -p $Port "root@$HostName" $remote
}
finally {
  Remove-Item -Recurse -Force -LiteralPath $staging -ErrorAction SilentlyContinue
}
