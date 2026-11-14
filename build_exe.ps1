# Builds the standalone desktop tool: dist\CDC MTL Tool.exe
# Needs the project venv (.venv, with requirements.txt installed) and Node.js for the UI build.
# (Exit codes are checked explicitly: PyInstaller logs to stderr, which "Stop" would treat as a failure.)
Set-Location $PSScriptRoot

npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw "UI build failed" }

.venv\Scripts\python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\cdc_mtl_tool.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "Built: $PSScriptRoot\dist\CDC MTL Tool.exe"
