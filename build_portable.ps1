$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$distributionRoot = Join-Path $projectRoot "dist"
$legacyPackageRoot = Join-Path $distributionRoot "SteelDominion"
$workRoot = Join-Path $projectRoot "build\pyinstaller"
$stagingRoot = Join-Path $workRoot "dist"

& py -3.6 -m PyInstaller --noconfirm --clean --windowed --onefile `
    --name SteelDominion `
    --distpath $stagingRoot `
    --workpath $workRoot `
    --specpath $workRoot `
    (Join-Path $projectRoot "steel_dominion.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed. Install PyInstaller 4.10 for Python 3.6 first."
}

Move-Item -Path (Join-Path $stagingRoot "SteelDominion.exe") `
    -Destination (Join-Path $distributionRoot "SteelDominion.exe") -Force

$mapsDestination = Join-Path $distributionRoot "maps"
if (-not (Test-Path $mapsDestination)) {
    $mapsSource = Join-Path $legacyPackageRoot "maps"
    if (-not (Test-Path $mapsSource)) {
        $mapsSource = Join-Path $projectRoot "maps"
    }
    Copy-Item -Path $mapsSource -Destination $distributionRoot -Recurse -Force
}

$configDestination = Join-Path $distributionRoot "config.json"
if (-not (Test-Path $configDestination)) {
    $configSource = Join-Path $legacyPackageRoot "config.json"
    if (-not (Test-Path $configSource)) {
        $configSource = Join-Path $projectRoot "config.json"
    }
    Copy-Item -Path $configSource -Destination $configDestination -Force
}

$savesDestination = Join-Path $distributionRoot "saves"
if (-not (Test-Path $savesDestination)) {
    $savesSource = Join-Path $legacyPackageRoot "saves"
    if (-not (Test-Path $savesSource)) {
        $savesSource = Join-Path $projectRoot "saves"
    }
    Copy-Item -Path $savesSource -Destination $distributionRoot -Recurse -Force
}

if (Test-Path $legacyPackageRoot) {
    Remove-Item -Path $legacyPackageRoot -Recurse -Force
}

if (Test-Path $workRoot) {
    Remove-Item -Path $workRoot -Recurse -Force
}

$buildRoot = Join-Path $projectRoot "build"
if ((Test-Path $buildRoot) -and -not (Get-ChildItem -Path $buildRoot -Force)) {
    Remove-Item -Path $buildRoot -Force
}

Write-Host "Portable build created at $distributionRoot"
Write-Host "Keep SteelDominion.exe, maps, config.json, and saves together."
