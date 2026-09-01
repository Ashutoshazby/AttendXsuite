$ErrorActionPreference = "SilentlyContinue"
foreach ($port in 8060, 8061, 8062, 8070, 27018) {
  Get-NetTCPConnection -LocalPort $port -State Listen |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
docker stop attendxsuite-mongo | Out-Null
Write-Host "AttendXsuite stopped."
