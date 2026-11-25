# Build the Windows version of Cornerplay: dist\Cornerplay\ (the app folder) and
# dist\cornerplay-<version>-windows-setup.exe (the installer).
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Needs Python 3.10+ and Inno Setup 6 (winget install JRSoftware.InnoSetup). -SkipInstaller
# builds only the app folder.
param([switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "..\..")
Set-Location $Root

$Version = (Select-String -Path "cornerplay\__init__.py" -Pattern '^__version__ = "(.*)"').Matches[0].Groups[1].Value
Write-Host "==> Cornerplay $Version for Windows"

python -m pip install --upgrade pip | Out-Null
python -m pip install "PySide6-Essentials>=6.6" "PySide6-Addons>=6.6" requests pyyaml "pyinstaller>=6.10"
if ($LASTEXITCODE) { throw "pip failed" }

Write-Host "==> legendary, gogdl, nile and SDL2.dll (checked against their SHA-256)"
python packaging\windows\fetch_extras.py
if ($LASTEXITCODE) { throw "fetching the backends failed" }

Write-Host "==> Cornerplay.exe"
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\windows\cornerplay.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }
New-Item -ItemType Directory -Force -Path "dist\Cornerplay\backends" | Out-Null
Copy-Item "packaging\windows\extra\backends\*" "dist\Cornerplay\backends\" -Force

if (-not $SkipInstaller) {
    $iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
    if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
    if (-not (Test-Path $iscc)) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
    Write-Host "==> installer"
    & $iscc "/DAppVersion=$Version" "packaging\windows\cornerplay.iss"
    if ($LASTEXITCODE) { throw "Inno Setup failed" }
}
Write-Host "==> done: dist\Cornerplay\Cornerplay.exe"
