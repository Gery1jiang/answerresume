# Check any remaining Chrome
$chrome = Get-Process chrome -ErrorAction SilentlyContinue
if ($chrome) {
    Write-Host "Chrome still running:" ($chrome.Count) "processes"
    Write-Host "Killing all..."
    $chrome | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Start-Sleep -Seconds 3
}

Write-Host "Starting Chrome with CDP..."
$p = Start-Process -FilePath "C:\Program Files\Google\Chrome\Application\chrome.exe" `
    -ArgumentList "--remote-debugging-port=9222", "--no-first-run", "--no-default-browser-check", "--new-window", "https://www.51job.com" `
    -WindowStyle Hidden -PassThru
Write-Host "Started PID:" $p.Id

# Wait longer
Start-Sleep -Seconds 8

$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
$found = $listeners | Where-Object { $_.Port -eq 9222 }
if ($found) {
    Write-Host "SUCCESS: Port 9222 is LISTENING"
} else {
    Write-Host "FAIL: Port 9222 is NOT listening"
    # Try alternative: use cmd /c start
    Write-Host "Trying alternative launch method..."
    $env:CURRENT_DIR = "C:\"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    $psi.Arguments = "--remote-debugging-port=9222 --no-first-run --no-default-browser-check --new-window https://www.51job.com"
    $psi.UseShellExecute = $true
    $psi.CreateNoWindow = $true
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    Start-Sleep -Seconds 8
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $found = $listeners | Where-Object { $_.Port -eq 9222 }
    if ($found) {
        Write-Host "SUCCESS (alt): Port 9222 is LISTENING"
    } else {
        Write-Host "FAIL (alt): Port 9222 still NOT listening"
    }
}
