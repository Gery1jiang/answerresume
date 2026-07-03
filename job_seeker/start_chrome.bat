@echo off
C:
cd \
start /B "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --no-first-run --no-default-browser-check --new-window https://www.51job.com
echo Chrome started
