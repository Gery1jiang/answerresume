"""
WSL-side HTTP server that auto-starts Chrome CDP + crawler_server on demand.

Runs in WSL (Linux Python). When the backend calls /start, it:
  1. Starts Chrome with --remote-debugging-port=9222 on Windows
  2. Starts crawler_server.py on Windows via python.exe

Usage:
  python3 job_seeker/crawler_launcher.py &
  # Backend will auto-detect and call /start when crawler is down
"""
import subprocess, time, json, os, signal, sys, socket, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
# Always use Windows paths — python.exe runs on Windows and needs D:\... paths
CRAWLER_DIR = "D:\\trae\\projects\\answerresume\\job_seeker"
CRAWLER_SCRIPT = "D:\\trae\\projects\\answerresume\\job_seeker\\crawler_server.py"
LAUNCHER_PORT = 8801
CHROME_PORT = 9222
CRAWLER_PORT = 8800

_starting = False


def _port_open(port: int) -> bool:
    # From WSL, we must check Windows ports via cmd.exe (localhost resolves to WSL VM)
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", f"netstat -ano | findstr :{port}"],
            capture_output=True, timeout=5, cwd="/tmp")
        output = result.stdout.decode("gbk", errors="replace")
        for line in output.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                return True
        return False
    except Exception:
        return False


def _start_chrome():
    """Start Chrome with CDP and wait until port 9222 is ready."""
    if _port_open(CHROME_PORT):
        return True
    print("[Launcher] Starting Chrome CDP...")
    # Use ProcessStartInfo with separate profile (proven to work)
    ps_cmd = (
        '$psi = New-Object System.Diagnostics.ProcessStartInfo;'
        "$psi.FileName = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';"
        "$psi.Arguments = '--remote-debugging-port=9222 --no-first-run --no-default-browser-check "
        "--user-data-dir=C:\\chrome-cdp-profile --new-window https://www.51job.com';"
        '$psi.UseShellExecute = $false;'
        '$psi.CreateNoWindow = $true;'
        '[System.Diagnostics.Process]::Start($psi) | Out-Null'
    )
    subprocess.run(["powershell.exe", "-Command", ps_cmd],
                   capture_output=True, timeout=15, cwd="/tmp")
    # Wait up to 15 seconds for port 9222
    for i in range(15):
        time.sleep(1)
        if _port_open(CHROME_PORT):
            print(f"[Launcher] Chrome CDP ready after {i+1}s")
            return True
    print("[Launcher] Chrome CDP failed to start")
    return False


def _start_crawler():
    """Start crawler server and wait until port 8800 is ready."""
    if _port_open(CRAWLER_PORT):
        return True
    print("[Launcher] Starting crawler server...")
    log_path = "/tmp/crawler_server.log"
    log_file = open(log_path, "a", encoding="utf-8")
    subprocess.Popen(
        ["python.exe", CRAWLER_SCRIPT],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    for i in range(10):
        time.sleep(1)
        if _port_open(CRAWLER_PORT):
            print(f"[Launcher] Crawler server ready after {i+1}s")
            return True
    print("[Launcher] Crawler server failed to start")
    return False


def _background_start():
    global _starting
    _starting = True
    chrome_ok = _start_chrome()
    time.sleep(3)  # Let crawler_server's Chrome CDP connection settle
    crawler_ok = _start_crawler()
    _starting = False
    return chrome_ok and crawler_ok


class LauncherHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"status": "ok" if _port_open(CRAWLER_PORT) else "down"})
        elif self.path == "/status":
            self._json({
                "chrome": _port_open(CHROME_PORT),
                "crawler": _port_open(CRAWLER_PORT),
                "starting": _starting,
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/start":
            if _port_open(CRAWLER_PORT) and _port_open(CHROME_PORT):
                self._json({"success": True, "message": "already running"})
                return
            try:
                ok = _background_start()
                self._json({"success": ok, "message": "ready" if ok else "failed"})
            except Exception as e:
                print(f"[Launcher] /start error: {e}")
                self._json({"success": False, "message": str(e)})
        elif self.path == "/start-blocking":
            _background_start()
            ok = _port_open(CHROME_PORT) and _port_open(CRAWLER_PORT)
            self._json({"success": ok, "chrome": _port_open(CHROME_PORT),
                        "crawler": _port_open(CRAWLER_PORT)})
        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[Launcher] {args[0]} {args[1]} {args[2]}")


def main():
    server = HTTPServer(("0.0.0.0", LAUNCHER_PORT), LauncherHandler)
    print(f"[Launcher] Ready on http://localhost:{LAUNCHER_PORT}")
    print(f"[Launcher] Chrome:{_port_open(CHROME_PORT)} Crawler:{_port_open(CRAWLER_PORT)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
