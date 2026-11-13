$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$distributionRoot = Join-Path $projectRoot "dist"
$packageRoot = Join-Path $distributionRoot "SteelDominion"
$workRoot = Join-Path $projectRoot "build\pyinstaller"

& py -3.6 -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name SteelDominion `
    --distpath $distributionRoot `
    --workpath $workRoot `
    --specpath $workRoot `
    (Join-Path $projectRoot "steel_dominion.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed. Install PyInstaller 4.10 for Python 3.6 first."
}

Copy-Item -Path (Join-Path $projectRoot "maps") -Destination $packageRoot -Recurse -Force
Copy-Item -Path (Join-Path $projectRoot "config.json") -Destination $packageRoot -Force

Write-Host "Portable build created at $packageRoot"
Write-Host "Keep SteelDominion.exe, maps, config.json, and all bundled runtime files together."
