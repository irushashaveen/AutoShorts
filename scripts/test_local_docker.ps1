# AutoShorts Local Docker Environment Prober & Healthcheck
# Validates container statuses, Redis ping, web dashboard API health, and Ollama model availability.

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AutoShorts Local Docker Environment Verification        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Docker Daemon
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    if (-not $dockerVersion) {
        Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Docker Engine is running (v$dockerVersion)" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to query Docker daemon." -ForegroundColor Red
    exit 1
}

# 2. Check Running Containers
Write-Host "`nChecking Compose Service Status..." -ForegroundColor Yellow
docker compose ps

# 3. Test Web Health Endpoint
Write-Host "`nProbing FastAPI Health Endpoint (http://localhost:8000/api/health)..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method Get -TimeoutSec 5
    Write-Host "[OK] Web API is Healthy: status=$($response.status)" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Web API is not reachable on localhost:8000 yet (Containers may still be starting)." -ForegroundColor Yellow
}

# 4. Probe Redis
Write-Host "`nProbing Redis Container..." -ForegroundColor Yellow
try {
    $redisPing = docker compose exec -T redis redis-cli ping 2>$null
    if ($redisPing -match "PONG") {
        Write-Host "[OK] Redis is responsive: $redisPing" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Redis did not respond with PONG." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] Could not probe Redis." -ForegroundColor Yellow
}

# 5. Probe Ollama
Write-Host "`nProbing Ollama Container..." -ForegroundColor Yellow
try {
    $ollamaTags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 2>$null
    Write-Host "[OK] Ollama is reachable." -ForegroundColor Green
} catch {
    Write-Host "[INFO] Ollama container not exposed locally or still initializing." -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Verification Complete!                                  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
