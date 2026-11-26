"""차단된 내부 경로의 응답이 진짜 404와 헤더까지 같은지 확인.
서버는 미리 띄워 둔다 (타깃 9000, 프록시 8080).
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from honeypatch import config  # noqa: E402

PROXY = f"http://{config.HOST}:{config.PROXY_PORT}"
SKIP = {"server", "date"}          # 실행마다 달라지는 헤더는 뺀다


def send(method, path, sid, body=None):
    req = urllib.request.Request(PROXY + path, data=body, method=method,
                                 headers={"X-Session-Id": sid, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def sig(status, headers, body):
    hdr = {k.lower(): v for k, v in headers.items() if k.lower() not in SKIP}
    return status, tuple(sorted(hdr.items())), body


# 공격으로 미끼에 고정시킨다
send("POST", "/heartbeat", "hdr-1", json.dumps({"payload": "hi", "length": 64}).encode())

CASES = [
    ("진짜 404 (없는 경로)", "GET", "/nope", None),
    ("차단된 /__health", "GET", "/__health", None),
    ("차단된 /__hp/restore", "POST", "/__hp/restore", b'{"state":{"sessions":[]}}'),
    ("차단된 /__hp/fork 아닌 내부경로", "GET", "/__hp/anything", None),
]

base = None
print(f"{'사례':<32} {'status':<7} {'본문':<12} 헤더(server, date 제외)")
print("-" * 104)
ok = True
for label, method, path, body in CASES:
    st, rh, resp = send(method, path, "hdr-1", body)
    s = sig(st, rh, resp)
    if base is None:
        base = s
    elif s != base:
        ok = False
    hdrs = ", ".join(f"{k}: {v}" for k, v in s[1])
    print(f"{label:<32} {st:<7} {resp.decode('latin-1'):<12} {hdrs}")

print()
print("[PASS] 차단 응답이 진짜 404와 완전히 같다" if ok
      else "[FAIL] 차단 응답이 진짜 404와 구분된다")
sys.exit(0 if ok else 1)
