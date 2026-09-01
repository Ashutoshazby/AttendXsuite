$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$PortableMongo = Join-Path $Root "tools\mongodb-win32-x86_64-windows-8.0.29\bin\mongod.exe"
$MongoData = Join-Path $Backend "mongo-data"

foreach ($port in 8060, 8061, 8062, 8070) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
  $mongo = docker ps -a --filter "name=attendxsuite-mongo" --format "{{.Names}}" 2>$null
  if ($mongo -contains "attendxsuite-mongo") {
    docker start attendxsuite-mongo | Out-Null
  } else {
    docker run -d --name attendxsuite-mongo -p 27018:27017 -v attendxsuite-mongo-data:/data/db mongo:7 | Out-Null
  }
}

$MongoUri = "mongodb://127.0.0.1:27018/attendxsuite"
$port27018 = Test-NetConnection 127.0.0.1 -Port 27018 -InformationLevel Quiet
if (-not $port27018) {
  if (Test-Path $PortableMongo) {
    New-Item -ItemType Directory -Force $MongoData | Out-Null
    Start-Process -FilePath $PortableMongo -ArgumentList @("--dbpath", $MongoData, "--bind_ip", "127.0.0.1", "--port", "27018", "--quiet") -WorkingDirectory $Root -RedirectStandardOutput (Join-Path $Root ".mongo.log") -RedirectStandardError (Join-Path $Root ".mongo.err.log") -WindowStyle Hidden
    Start-Sleep -Seconds 4
    $port27018 = Test-NetConnection 127.0.0.1 -Port 27018 -InformationLevel Quiet
  }
  if (-not $port27018) {
    $port27017 = Test-NetConnection 127.0.0.1 -Port 27017 -InformationLevel Quiet
    if ($port27017) {
      $MongoUri = "mongodb://127.0.0.1:27017/attendxsuite"
    } else {
      Write-Host "MongoDB is not reachable on 27018 or 27017. Backend will use local fallback storage."
    }
  } else {
    Write-Host "Portable MongoDB started on 27018."
  }
}

if (!(Test-Path (Join-Path $Backend ".venv"))) {
  python -m venv (Join-Path $Backend ".venv")
}
& (Join-Path $Backend ".venv\Scripts\python.exe") -m pip install -r (Join-Path $Backend "requirements.txt") | Out-Host
if (!(Test-Path (Join-Path $Frontend "node_modules"))) { npm --prefix $Frontend install | Out-Host }

$envContent = @"
PORT=8070
MONGODB_URI=$MongoUri
JWT_SECRET=attendxsuite_local_secret
CLIENT_ORIGINS=http://127.0.0.1:8061,http://localhost:8061
FACE_ENGINE=opencv
HF_FACE_API_TOKEN=replace_with_secret_token
FACE_MATCH_THRESHOLD=0.48
FACE_MATCH_MARGIN=0.06
FACE_SCAN_FRAME_COUNT=5
FACE_SCAN_CONSENSUS=3
"@
Set-Content -Path (Join-Path $Backend ".env") -Value $envContent

Start-Process -FilePath (Join-Path $Backend ".venv\Scripts\python.exe") -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8070") -WorkingDirectory $Backend -RedirectStandardOutput (Join-Path $Root ".backend.log") -RedirectStandardError (Join-Path $Root ".backend.err.log") -WindowStyle Hidden
Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "0.0.0.0", "--port", "8061") -WorkingDirectory $Frontend -RedirectStandardOutput (Join-Path $Root ".frontend.log") -RedirectStandardError (Join-Path $Root ".frontend.err.log") -WindowStyle Hidden

Start-Sleep -Seconds 7

Write-Host "AttendXsuite running:"
Write-Host "Backend:   http://127.0.0.1:8070/health"
Write-Host "Dashboard: http://127.0.0.1:8061"
Write-Host "PWA:       on hold"
