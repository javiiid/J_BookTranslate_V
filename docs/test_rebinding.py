"""Does the Host check actually work?

`urllib` overwrites the Host header with the URL's authority, so the previous
test never really sent `Host: attacker.example`. This uses a raw socket so the
header genuinely reaches the server - which is exactly what a DNS-rebinding
attack does.
"""
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST, PORT = "127.0.0.1", 8765


def raw_get(host_header, path="/api/jobs"):
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    raw = b"".join(chunks)
    status = raw.split(b"\r\n", 1)[0].decode("latin-1")
    return status, len(raw)


print("=== raw-socket Host test (what DNS rebinding looks like) ===")
print("-" * 62)
failures = 0
cases = [
    ("127.0.0.1:8765", "403 expected?" , False),
    ("localhost:8765", "legit", False),
    ("attacker.example", "rebind attack", True),
    ("127.0.0.1.attacker.example", "lookalike", True),
]
for host, why, expect_block in cases:
    status, size = raw_get(host)
    blocked = "403" in status
    ok = blocked == expect_block
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {status:24} Host: {host:32} ({why})")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
