# Verify HTML and assets for the two independent local VEXA portals.
# This does not verify a successful login: it checks HTTP reachability and JS MIME types.
$ErrorActionPreference = 'Stop'
$portals = @(
    @{Name='Dispatcher'; Url='http://127.0.0.1:8081/'},
    @{Name='Platform Admin'; Url='http://127.0.0.1:8082/'}
)
$failed = $false
foreach ($portal in $portals) {
    try {
        $response = Invoke-WebRequest -Uri $portal.Url -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -ne 200) { throw "HTML HTTP $($response.StatusCode)" }
        $html = [string]$response.Content
        $match = [regex]::Match($html, '<script[^>]+src="([^"]+\.js)"')
        if (-not $match.Success) { throw 'Bundled JavaScript script was not found in HTML; Docker build may be missing' }
        $jsUrl = [Uri]::new([Uri]$portal.Url, $match.Groups[1].Value).AbsoluteUri
        $js = Invoke-WebRequest -Uri $jsUrl -UseBasicParsing -TimeoutSec 10
        $mime = [string]$js.Headers['Content-Type']
        if ($mime -match 'text/html' -or $mime -notmatch 'javascript') {
            throw "JavaScript URL returned '$mime' instead of JS: $jsUrl"
        }
        Write-Host "[OK] $($portal.Name): $($portal.Url), JS: $jsUrl" -ForegroundColor Green
    } catch {
        $failed = $true
        Write-Host "[FAIL] $($portal.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}
if ($failed) { exit 1 } else { exit 0 }
