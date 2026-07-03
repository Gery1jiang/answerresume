"""TCP relay: forward incoming connections → Kimi WebBridge daemon.
   In Docker: connects to host.docker.internal:10086 (or $KIMI_HOST:$KIMI_PORT).
   Listens on 0.0.0.0:10087 (or $RELAY_PORT)."""
import socket, threading, os, signal, sys

RELAY_PORT = int(os.environ.get("RELAY_PORT", "10087"))
KIMI_HOST = os.environ.get("KIMI_HOST", "host.docker.internal")
KIMI_PORT = int(os.environ.get("KIMI_PORT", "10086"))


SOCK_TIMEOUT = 60

def forward(src, dst, name):
    try:
        src.settimeout(SOCK_TIMEOUT)
        dst.settimeout(SOCK_TIMEOUT)
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except:
                pass


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", RELAY_PORT))
    srv.listen(50)
    print(f"relay listening 0.0.0.0:{RELAY_PORT} → {KIMI_HOST}:{KIMI_PORT}")

    while True:
        try:
            client, addr = srv.accept()
            backend = socket.create_connection((KIMI_HOST, KIMI_PORT), timeout=30)
            threading.Thread(target=forward, args=(client, backend, "c2b"), daemon=True).start()
            threading.Thread(target=forward, args=(backend, client, "b2c"), daemon=True).start()
        except Exception as e:
            print(f"relay error: {e}")
            try:
                client.close()
            except:
                pass


if __name__ == "__main__":
    main()
