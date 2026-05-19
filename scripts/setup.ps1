# Virtus Job — Setup Script (Windows PowerShell)
Write-Host ""
Write-Host "  Virtus Job — Setup" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker not found. Install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Copy .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env created from .env.example" -ForegroundColor Green
    Write-Host "     Edit .env and set SECRET_KEY and AI API keys." -ForegroundColor Yellow
} else {
    Write-Host "[OK] .env already exists" -ForegroundColor Green
}

# Build containers
Write-Host ""
Write-Host "Building Docker containers..." -ForegroundColor Cyan
docker compose build

Write-Host ""
Write-Host "Starting database and Redis..." -ForegroundColor Cyan
docker compose up -d postgres redis

Write-Host "Waiting for services to be healthy..." -ForegroundColor DarkGray
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "Running database migrations..." -ForegroundColor Cyan
docker compose run --rm api alembic upgrade head

Write-Host ""
Write-Host "Seeding database with sample data..." -ForegroundColor Cyan
docker compose run --rm api python -m app.scripts.seed

docker compose down

Write-Host ""
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run the project:" -ForegroundColor Cyan
Write-Host "    docker compose up" -ForegroundColor White
Write-Host ""
Write-Host "  Access points:" -ForegroundColor Cyan
Write-Host "    Frontend:  http://localhost:3000" -ForegroundColor White
Write-Host "    API:       http://localhost:8000" -ForegroundColor White
Write-Host "    API Docs:  http://localhost:8000/api/v1/docs" -ForegroundColor White
Write-Host ""
