Write-Host "Starting Chrome with remote debugging on port 9222..."
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$args = @(
    "--remote-debugging-port=9222",
    "--no-first-run",
    "--no-default-browser-check",
    "--user-data-dir=C:\chrome-profile-cdp",
    "--new-window",
    "https://www.51job.com"
)
$p = Start-Process -FilePath $chromePath -ArgumentList $args -WindowStyle Hidden -PassThru
Write-Host "Chrome started, PID: $($p.Id)"
Start-Sleep -Seconds 3

# Verify port is listening
$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
$found = $listeners | Where-Object { $_.Port -eq 9222 }
if ($found) {
    Write-Host "SUCCESS: Port 9222 is LISTENING"
} else {
    Write-Host "FAIL: Port 9222 is NOT listening"
    # Retry check after more time
    Start-Sleep -Seconds 5
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $found = $listeners | Where-Object { $_.Port -eq 9222 }
    if ($found) {
        Write-Host "SUCCESS: Port 9222 is LISTENING (after delay)"
    } else {
        Write-Host "FAIL: Port 9222 still NOT listening"
    }
}
