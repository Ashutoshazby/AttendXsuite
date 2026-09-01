$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PwaLog = Join-Path $Root ".tunnel-pwa.log"
$PwaErr = Join-Path $Root ".tunnel-pwa.err.log"

Remove-Item $PwaLog, $PwaErr -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -Filter "name = 'node.exe'" |
  Where-Object { $_.CommandLine -like "*cloudflared*tunnel*8062*" -or $_.CommandLine -like "*localtunnel*8062*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Process -FilePath "npx.cmd" -ArgumentList @("--yes", "cloudflared", "tunnel", "--url", "http://127.0.0.1:8062") -WorkingDirectory $Root -RedirectStandardOutput $PwaLog -RedirectStandardError $PwaErr -WindowStyle Hidden

for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 2
  $content = (Get-Content $PwaLog, $PwaErr -ErrorAction SilentlyContinue) -join "`n"
  $pwaUrl = ($content | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches).Matches.Value | Select-Object -Last 1
  if ($pwaUrl) { break }
}

if (!$pwaUrl) { throw "Cloudflare PWA tunnel not found" }

$finalUrl = "$pwaUrl/?fresh=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
npm exec --yes qrcode -- -o attendxsuite-pwa-qr.png $finalUrl | Out-Null
[pscustomobject]@{ PwaTunnel = $finalUrl; Qr = (Join-Path $Root "attendxsuite-pwa-qr.png"); ApiMode = "same-origin proxy to local backend" } | ConvertTo-Json -Compress
