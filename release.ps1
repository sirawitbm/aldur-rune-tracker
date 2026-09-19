param(
    [string]$Version = "0.1.1",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use semantic version format, for example 0.1.0."
}

$distDir = Join-Path $PSScriptRoot "dist\PoE2RuneTracker"
$releaseDir = Join-Path $PSScriptRoot "dist\release"
$artifactName = "PoE2RuneTracker-v$Version-windows-x64"
$zipPath = Join-Path $releaseDir "$artifactName.zip"
$checksumPath = "$zipPath.sha256"
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("PoE2RuneTracker-release-" + [guid]::NewGuid())
$stageApp = Join-Path $stageRoot $artifactName

if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot "build.ps1")
}
if (-not (Test-Path (Join-Path $distDir "PoE2RuneTracker.exe"))) {
    throw "Packaged app not found. Run .\build.ps1 first or omit -SkipBuild."
}

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
New-Item -ItemType Directory -Path $stageRoot | Out-Null

try {
    Copy-Item $distDir $stageApp -Recurse

    # Local builds deliberately retain these. Public releases must never do so.
    Remove-Item (Join-Path $stageApp "config.json") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $stageApp "data") -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item (Join-Path $PSScriptRoot "README.md") $stageApp
    Copy-Item (Join-Path $PSScriptRoot "TECHNICAL.md") $stageApp
    Copy-Item (Join-Path $PSScriptRoot "LICENSE") $stageApp

    Remove-Item $zipPath, $checksumPath -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path $stageApp -DestinationPath $zipPath -CompressionLevel Optimal

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $relativePaths = @($archive.Entries | ForEach-Object {
            $_.FullName -replace '^[^/\\]+[/\\]', ''
        })
        $missingRequired = @(
            'PoE2RuneTracker.exe',
            'README.md',
            'TECHNICAL.md',
            'LICENSE',
            '_internal\data\RA.jpg'
        ) |
            Where-Object {
                $expected = $_
                -not ($relativePaths | Where-Object { ($_ -replace '/', '\') -eq $expected })
            }
        if ($missingRequired) {
            throw "Release is missing required files: $($missingRequired -join ', ')"
        }

        $forbiddenEntries = $archive.Entries | Where-Object {
            $relativePath = $_.FullName -replace '^[^/\\]+[/\\]', ''
            $relativePath -eq 'config.json' -or $relativePath -match '^data[/\\]'
        }
        if ($forbiddenEntries) {
            $names = ($forbiddenEntries.FullName -join ', ')
            throw "Release contains private runtime paths: $names"
        }
    }
    finally {
        $archive.Dispose()
    }

    $hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -Path $checksumPath -Value "$hash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ascii
}
finally {
    Remove-Item $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Release: $zipPath"
Write-Host "SHA-256: $checksumPath"