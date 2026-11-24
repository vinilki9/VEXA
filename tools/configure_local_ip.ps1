# Run on Windows in PowerShell from the project root:
# powershell -ExecutionPolicy Bypass -File .\tools\configure_local_ip.ps1
param([string]$LanIP = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $LanIP) {
  $found = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
    Where-Object { $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Sort-Object -Property InterfaceMetric |
    Select-Object -First 1
  if (-not $found) { throw "Не удалось определить локальный IP. Укажите -LanIP 192.168.x.x" }
  $LanIP = $found.IPAddress
}
$parsed = [System.Net.IPAddress]::None
if (-not [System.Net.IPAddress]::TryParse($LanIP,[ref]$parsed) -or
    $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $LanIP -notmatch '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)') {
  throw "Укажите IPv4 частной локальной сети, например 192.168.1.100: $LanIP"
}
foreach ($app in @('client','driver')) {
  $path = Join-Path $root "android\$app\gradle.properties"
  if (-not (Test-Path $path)) { throw "Нет файла $path" }
  $s = [System.IO.File]::ReadAllText($path)
  $s = [regex]::Replace($s,'(?m)^vexaServerHost=.*$',"vexaServerHost=$LanIP")
  [System.IO.File]::WriteAllText($path,$s,[System.Text.UTF8Encoding]::new($false))
  Write-Host "Настроено $app -> $LanIP"
}
$envPath = Join-Path $root '.env'
if (Test-Path -LiteralPath $envPath) {
  $envText = [System.IO.File]::ReadAllText($envPath)
  $newValue = "PUBLIC_API_BASE_URL=http://${LanIP}:8000"
  if ($envText -match '(?m)^PUBLIC_API_BASE_URL=') {
    $envText = [regex]::Replace($envText, '(?m)^PUBLIC_API_BASE_URL=.*$', $newValue)
  } else {
    $envText += "`n$newValue`n"
  }
  [System.IO.File]::WriteAllText($envPath, $envText, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Локальный API обновлён в .env: $newValue"
}
Write-Host "Локальный адрес ПК для Android: $LanIP"
Write-Host "Проверьте, что телефон в одной сети Wi-Fi; затем соберите debug APK в Android Studio."
