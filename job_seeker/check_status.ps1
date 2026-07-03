$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
$found = $listeners | Where-Object { $_.Port -eq 9222 }
Write-Host "Port 9222 listening: " ($found -ne $null)
$chromeCount = (Get-Process chrome -ErrorAction SilentlyContinue).Count
Write-Host "Chrome processes: $chromeCount"
