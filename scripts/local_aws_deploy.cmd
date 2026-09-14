@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
set "REGION=ap-southeast-1"
set "REPOSITORY=medical-rag-backend"
set "IMAGE=medical-rag-backend:local"
set "LOCAL_IMAGE=localhost:4566/%REPOSITORY%:local"
set "REGISTRY_IMAGE=localhost:5000/%REPOSITORY%:local"

echo [1/6] Starting LocalStack AWS simulator...
docker compose -f "%ROOT%\docker-compose.aws-local.yml" up -d
if errorlevel 1 exit /b 1

echo [2/6] Waiting for LocalStack...
for /l %%N in (1,1,30) do (
  docker exec medical-rag-localstack curl -sf http://localhost:4566/_localstack/health >nul 2>nul
  if not errorlevel 1 goto localstack_ready
  timeout /t 2 /nobreak >nul
)
echo LocalStack did not become ready.
exit /b 1

:localstack_ready
echo [3/6] Creating local ECR repository...
docker exec medical-rag-localstack awslocal ecr describe-repositories --repository-names "%REPOSITORY%" >nul 2>nul
if errorlevel 1 docker exec medical-rag-localstack awslocal ecr create-repository --repository-name "%REPOSITORY%" --region "%REGION%" >nul 2>nul
if errorlevel 1 echo LocalStack Community does not implement ECR; using local Docker Registry instead.

echo [4/6] Building backend image...
docker build -t "%IMAGE%" "%ROOT%"
if errorlevel 1 exit /b 1

echo [5/6] Pushing image to LocalStack ECR...
docker tag "%IMAGE%" "%REGISTRY_IMAGE%"
docker push "%REGISTRY_IMAGE%"
if errorlevel 1 exit /b 1

echo [6/6] Starting application stack...
docker compose -f "%ROOT%\docker-compose.yml" up -d --build
if errorlevel 1 exit /b 1

echo.
echo Local AWS simulator: http://localhost:4566
echo Backend health:      http://localhost:8000/healthz/
echo Frontend:            http://localhost/
echo Local image registry: %REGISTRY_IMAGE%
endlocal
