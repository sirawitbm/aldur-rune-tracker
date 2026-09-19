# Builds dist\PoE2RuneTracker\PoE2RuneTracker.exe - a standalone folder you
# can copy anywhere and double-click to run (no Python install needed).
# Re-run this after any code change; config.json/data/ (session, capture
# history, the learned icon library) are created next to the exe on first
# run and are left alone by rebuilds.

$ErrorActionPreference = "Stop"
$distDir = Join-Path $PSScriptRoot "dist\PoE2RuneTracker"
$distExe = Join-Path $distDir "PoE2RuneTracker.exe"
$runtimeBackup = Join-Path ([System.IO.Path]::GetTempPath()) ("PoE2RuneTracker-build-" + [guid]::NewGuid())

$running = Get-Process -Name "PoE2RuneTracker" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $distExe }
if ($running) {
    throw "Quit PoE2RuneTracker before rebuilding."
}

New-Item -ItemType Directory -Path $runtimeBackup | Out-Null
if (Test-Path (Join-Path $distDir "config.json")) {
    Copy-Item (Join-Path $distDir "config.json") $runtimeBackup
}
if (Test-Path (Join-Path $distDir "data")) {
    Copy-Item (Join-Path $distDir "data") $runtimeBackup -Recurse
}

$buildSucceeded = $false
try {
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed with exit code $LASTEXITCODE." }

    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed with exit code $LASTEXITCODE." }

    python -m PyInstaller --noconfirm --onedir --windowed --name PoE2RuneTracker `
        --icon "data/RA.ico" `
        --version-file "version_info.txt" `
        --collect-all winrt `
        --collect-all winocr `
        --exclude-module cv2 `
        --exclude-module numpy `
        --add-data "data/RA.jpg;data" `
        --add-data "data/rune_icon_seed.json;data" `
        --add-data "data/seed_icons;data/seed_icons" `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
    $buildSucceeded = $true
}
finally {
    $backedUpConfig = Join-Path $runtimeBackup "config.json"
    $backedUpData = Join-Path $runtimeBackup "data"
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    if (Test-Path $backedUpConfig) {
        Copy-Item $backedUpConfig (Join-Path $distDir "config.json") -Force
    }
    if (Test-Path $backedUpData) {
        $runtimeData = Join-Path $distDir "data"
        if (Test-Path $runtimeData) { Remove-Item $runtimeData -Recurse -Force }
        Copy-Item $backedUpData $runtimeData -Recurse
    }
    if ((Test-Path $backedUpConfig) -and -not (Test-Path (Join-Path $distDir "config.json"))) {
        throw "Build completed but config.json restoration failed. Backup retained at $runtimeBackup"
    }
    if ((Test-Path $backedUpData) -and -not (Test-Path (Join-Path $distDir "data"))) {
        throw "Build completed but runtime data restoration failed. Backup retained at $runtimeBackup"
    }
    if ($buildSucceeded) {
        Remove-Item $runtimeBackup -Recurse -Force
    }
    else {
        Write-Warning "Build failed. Runtime backup retained at $runtimeBackup"
    }
}

Write-Host "Done: dist\PoE2RuneTracker\PoE2RuneTracker.exe"
