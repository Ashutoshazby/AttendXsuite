$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$BackupRoot = Join-Path $Root "backups"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $BackupRoot $Stamp

New-Item -ItemType Directory -Force $BackupDir | Out-Null

$LocalJson = Join-Path $Backend "local-data\attendxsuite.json"
if (Test-Path $LocalJson) {
  Copy-Item -LiteralPath $LocalJson -Destination (Join-Path $BackupDir "attendxsuite.json")
  Write-Host "Local JSON database backup created: $BackupDir"
  exit 0
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker exec attendxsuite-mongo mongodump --archive=/tmp/attendxsuite.archive --db attendxsuite *> $null
  if ($LASTEXITCODE -eq 0) {
    docker cp attendxsuite-mongo:/tmp/attendxsuite.archive (Join-Path $BackupDir "attendxsuite-mongo.archive") *> $null
    Write-Host "MongoDB Docker backup created: $BackupDir"
    exit 0
  }
}

Write-Host "No local AttendXsuite data found to back up yet."
