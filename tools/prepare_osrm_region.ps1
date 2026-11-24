# VEXA MAP | Build a local car-routing graph from a lawful OSM.PBF extract.
# Requires Docker Desktop/WSL2. This script never connects to VEXA VPS.
param(
    [Parameter(Mandatory = $true)][string]$PbfPath,
    [switch]$ReplacePrevious
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = (Resolve-Path -LiteralPath $PbfPath).Path
if ($source -notmatch '\.osm\.pbf$') { throw 'Требуется исходный файл .osm.pbf' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop не найден' }
& docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon недоступен. Запустите Docker Desktop.' }
$dir = Join-Path $root 'VEXA_MAP\data\osrm'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$target = Join-Path $dir 'region.osm.pbf'
$existing = @(Get-ChildItem -LiteralPath $dir -File | Where-Object { $_.Name -ne '.gitkeep' })
if ($existing.Count -gt 0 -and -not $ReplacePrevious) {
    throw 'В каталоге уже есть дорожный граф. Для удаления старого используйте -ReplacePrevious (необратимо).'
}
if ($ReplacePrevious) {
    Get-ChildItem -LiteralPath $dir -File | Where-Object { $_.Name -ne '.gitkeep' } | Remove-Item -Force
}
Copy-Item -LiteralPath $source -Destination $target
$dockerMount = $dir.Replace('\', '/')
$image = 'ghcr.io/project-osrm/osrm-backend:latest'
Write-Host 'Подготовка автомобильного графа для одного выбранного региона...'
foreach ($arguments in @(
    @('osrm-extract', '-p', '/opt/car.lua', '/data/region.osm.pbf'),
    @('osrm-partition', '/data/region.osrm'),
    @('osrm-customize', '/data/region.osrm')
)) {
    & docker run --rm -v "${dockerMount}:/data" $image @arguments
    if ($LASTEXITCODE -ne 0) { throw "Ошибка OSRM: $($arguments[0]); проверьте память и свободное место" }
}
Write-Host 'OSRM-граф подготовлен. Для запуска:'
Write-Host '  В .env задайте VEXA_MAP_OSRM_URL=http://osrm:5000 и OSRM_BASE_URL=http://osrm:5000'
Write-Host '  docker compose -f infrastructure/docker-compose.yml --profile routing up -d osrm vexa_map api'
Write-Host 'Для разных федеральных округов потребуются отдельные графы и маршрутизатор переходов между ними.'
