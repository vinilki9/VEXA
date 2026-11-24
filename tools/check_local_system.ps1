# Local reachability diagnostics. Run on the computer hosting VEXA.
$urls = @(
  @{ Name='Backend'; Url='http://127.0.0.1:8000/health' },
  @{ Name='VEXA MAP'; Url='http://127.0.0.1:8090/health' },
  @{ Name='Dispatcher'; Url='http://127.0.0.1:8081/' },
  @{ Name='Platform Admin'; Url='http://127.0.0.1:8082/' }
)
foreach ($item in $urls) {
  try {
    $response = Invoke-WebRequest -Uri $item.Url -TimeoutSec 6 -UseBasicParsing
    Write-Host ("{0}: HTTP {1}" -f $item.Name, $response.StatusCode)
    if ($item.Name -eq 'VEXA MAP') {
      $health = $response.Content | ConvertFrom-Json
      Write-Host ("  map_ready={0}, packages={1}, search_ready={2}, routing_configured={3}, vector_style_required={4}" -f $health.map_ready,$health.package_count,$health.search_ready,$health.routing_configured,$health.vector_style_required)
    }
  } catch {
    Write-Warning ("{0}: недоступен ({1})" -f $item.Name, $_.Exception.Message)
  }
}
