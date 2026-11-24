# VEXA MAP — explicitly download ONE Geofabrik federal-district OSM extract.
# Download only; no Docker, no map processing, no server or GitHub changes.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('central-fed-district', 'northwestern-fed-district', 'south-fed-district',
                 'north-caucasus-fed-district', 'volga-fed-district', 'ural-fed-district',
                 'siberian-fed-district', 'far-eastern-fed-district')]
    [string]$District,
    [ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $root 'VEXA_MAP\data\osm'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$name = "$District-latest.osm.pbf"
$target = Join-Path $dir $name
$temp = "$target.partial"
if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $temp)) {
    throw 'Файл или незавершённая загрузка уже существуют. Перезапись запрещена.'
}
# Geofabrik publishes extracts directly under /russia/ (not /russia/<district>/).
$url = "https://download.geofabrik.de/russia/$name"
Write-Host "Загружаю $District : $url"
try {
    Invoke-WebRequest -Uri $url -OutFile $temp -MaximumRedirection 5 -ErrorAction Stop
    if ((Get-Item -LiteralPath $temp).Length -lt 1024) { throw 'Получен слишком маленький файл' }
    $digest = (Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExpectedSha256 -and $digest -ne $ExpectedSha256.ToLowerInvariant()) {
        throw 'SHA-256 не совпадает. Проверяйте происхождение исходных данных.'
    }
    Move-Item -LiteralPath $temp -Destination $target -ErrorAction Stop
    Write-Host "Готово: $target | SHA-256 $digest"
    Write-Host 'Используйте build_region_0320.py --region ... для плана обработки.'
} catch {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    throw
}
