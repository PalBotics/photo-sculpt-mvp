<# 
Photo Sculpt MVP — Windows Prereqs Setup
Run this from the repo root: C:\Users\Paul\Box\Apps\photo-sculpt-mvp

What it does:
  1) Installs Node.js LTS and Python 3.11 via winget (per-user scope).
  2) Creates a Python virtual env in backend\.venv and installs backend deps.
  3) Creates backend\.env with DATA_ROOT=./data
  4) Runs npm install in frontend/

Notes:
  - You may be prompted by Windows to allow app installation.
  - If winget asks for admin rights, you can re-run this script in an elevated PowerShell or remove --scope machine if present.
  - COLMAP is optional for the MVP. See the end of this script for install guidance.
#>

$ErrorActionPreference = "Stop"

function Write-Title($msg) {
  Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

function Run($cmd, $cwd = $null) {
  if ($cwd) { Push-Location $cwd }
  Write-Host "`n> $cmd" -ForegroundColor DarkGray
  cmd.exe /c $cmd
  $code = $LASTEXITCODE
  if ($cwd) { Pop-Location }
  if ($code -ne 0) { throw "Command failed with exit code ${code}: $cmd" }
}

# 0) Ensure we're in repo root (has frontend and backend)
if (!(Test-Path ".\frontend") -or !(Test-Path ".\backend")) {
  throw "Run this from the repo root (should contain 'frontend' and 'backend' folders)."
}

# 1) Install Node.js LTS (OpenJS.NodeJS.LTS) and Python 3.11
Write-Title "Installing Node.js LTS and Python 3.11 via winget"
try {
  Run 'winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements'
} catch {
  Write-Warning "Node.js install skipped or failed. If it's already installed, that's fine."
}
try {
  Run 'winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements'
} catch {
  Write-Warning "Python 3.11 install skipped or failed. If it's already installed, that's fine."
}

# 2) Verify versions
Write-Title "Verifying versions"
try { Run 'node -v' } catch { Write-Warning "Node not found in PATH yet (open a new terminal after install)"; }
try { Run 'npm -v' } catch { Write-Warning "npm not found in PATH yet (open a new terminal after install)"; }
try { Run 'py -3.11 -V' } catch { Write-Warning "Python launcher not found; try ''python --version'' manually."; }

# 3) Create virtual environment and install backend deps
Write-Title "Setting up Python virtual environment (backend\.venv)"
if (!(Test-Path '.\backend\.venv')) {
  Run 'py -3.11 -m venv .venv' '.\backend'
}
Run '.\.venv\Scripts\python.exe -m pip install -U pip' '.\backend'
Run '.\.venv\Scripts\pip.exe install -r requirements.txt' '.\backend'

# 4) Create backend\.env
Write-Title "Creating backend\.env"
$envPath = Join-Path (Resolve-Path '.\backend') '.env'
'DATA_ROOT=./data' | Out-File -FilePath $envPath -Encoding utf8

# 5) Frontend npm install
Write-Title "Installing frontend dependencies (npm install)"
Run 'npm install' '.\frontend'

Write-Host "`nAll set. Next steps:" -ForegroundColor Green
Write-Host "  Backend:  cd backend; .\.venv\Scripts\activate; python main.py"
Write-Host "  Frontend: cd frontend; npm run dev"
Write-Host "Then open the URL that Vite prints (e.g., http://localhost:5173)."

Write-Host "`nOptional: Install COLMAP for real reconstructions:" -ForegroundColor Yellow
Write-Host "  1) Download the Windows prebuilt binaries from the official releases."
Write-Host "  2) Extract e.g. to C:\Tools\colmap and add that folder to your PATH."
Write-Host "  3) Test with:  colmap -h   or   run COLMAP.bat for the GUI."
Write-Host "Details: https://colmap.github.io/install.html and https://github.com/colmap/colmap/releases"
