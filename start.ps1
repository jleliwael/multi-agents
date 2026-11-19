# Démarrage du système multi-agents local (Phase 8)
# Usage : clic droit > « Exécuter avec PowerShell », ou dans un terminal :  .\start.ps1
# Arrêt : fermer les deux fenêtres « API » et « Interface ».

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== Système multi-agents local ===" -ForegroundColor Cyan

# 1. Environnement Python
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Création de l'environnement Python (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
}

# 2. Fichier de configuration
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Fichier .env créé à partir de .env.example." -ForegroundColor Yellow
}

# 3. Ollama
try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3
    $names = ($tags.models | ForEach-Object { $_.name }) -join ", "
    Write-Host "Ollama actif. Modèles : $names" -ForegroundColor Green
} catch {
    Write-Host "Ollama ne répond pas : lancement..." -ForegroundColor Yellow
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Host "Ollama n'est pas installé : https://ollama.com/download" -ForegroundColor Red
        exit 1
    }
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

# 4. API FastAPI et interface Streamlit, chacune dans sa fenêtre
$apiPort = 8000
$uiPort = 8501
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='API multi-agents'; & '$python' -m uvicorn api.app:app --host 127.0.0.1 --port $apiPort" -WorkingDirectory $PSScriptRoot
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='Interface multi-agents'; & '$python' -m streamlit run ui/app.py --server.port $uiPort --server.headless true" -WorkingDirectory $PSScriptRoot

# 5. Attente puis ouverture du navigateur
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://localhost:$uiPort" -UseBasicParsing -TimeoutSec 2 | Out-Null
        break
    } catch { Start-Sleep -Seconds 1 }
}
Start-Process "http://localhost:$uiPort"
Write-Host "Interface : http://localhost:$uiPort" -ForegroundColor Green
Write-Host "API (documentation) : http://127.0.0.1:$apiPort/docs" -ForegroundColor Green
