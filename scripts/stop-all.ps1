$ErrorActionPreference = "SilentlyContinue"
foreach ($port in 8060, 8061, 8062, 8070, 27018) {
  Get-NetTCPConnection -LocalPort $port -State Listen |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker stop attendxsuite-mongo *> $null
}
Write-Host "AttendXsuite stopped."
