Write-Host 'Starting Chrome with CDP (separate profile, proven method)...'
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$psi.Arguments = '--remote-debugging-port=9222 --no-first-run --no-default-browser-check --user-data-dir=C:\chrome-cdp-profile --new-window https://www.51job.com'
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
[System.Diagnostics.Process]::Start($psi) | Out-Null
Write-Host 'Chrome launched, waiting 6 seconds...'
Start-Sleep -Seconds 6
$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
$found = $listeners | Where-Object { $_.Port -eq 9222 }
if ($found) {
    Write-Host 'SUCCESS: Port 9222 is LISTENING'
} else {
    Write-Host 'FAIL: Port 9222 is NOT listening'
}
