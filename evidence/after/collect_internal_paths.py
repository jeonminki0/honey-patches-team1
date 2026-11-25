"""반례 c, d 의 수정 후 재현. 서버는 미리 띄워 두고 요청만 보낸다.

  python server/app.py --mode honeypatched --role target --port 9000
  python proxy/proxy.py
  python evidence/after/collect_internal_paths.py

미끼(9101, 9102)는 프록시가 띄운다. 이 스크립트는 서버를 건드리지 않는다.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from honeypatch import config  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
PROXY = f"http://{config.HOST}:{config.PROXY_PORT}"
SECRETS = config.real_secrets()


def send(method, path, sid, body=None):
    req = urllib.request.Request(PROXY + path, data=body, method=method,
                                 headers={"X-Session-Id": sid, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def leaks(body):
    text = body.decode("latin-1")
    return sum(1 for s in SECRETS if s in text)


def tail(path, n0):
    p = os.path.join(ROOT, "logs", path)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        lines = [json.loads(x) for x in f if x.strip()]
    return [{k: v for k, v in e.items() if k != "t"} for e in lines[n0:]]


def count(path):
    p = os.path.join(ROOT, "logs", path)
    return sum(1 for _ in open(p, encoding="utf-8")) if os.path.exists(p) else 0


ATTACK = json.dumps({"payload": "hi", "length": 64}).encode()
INJECT = json.dumps({"state": {"sessions": [
    {"sid": "x", "token": "INJECTED_BY_ATTACKER", "user": "x", "ip": "1.1.1.1"}]}}).encode()

STEPS = [
    ("정상 사용자 /__health (비교용)", "GET", "/__health", "user-normal", None),
    ("attacker-1 공격 hi/64", "POST", "/heartbeat", "attacker-1", ATTACK),
    ("attacker-1 /__health", "GET", "/__health", "attacker-1", None),
    ("attacker-1 /__hp/restore 주입", "POST", "/__hp/restore", "attacker-1", INJECT),
    ("주입 뒤 attacker-1 공격 hi/64", "POST", "/heartbeat", "attacker-1", ATTACK),
    ("없는 경로 (대조군)", "GET", "/nope", "attacker-1", None),
]

rows, detail = [], []
for label, method, path, sid, body in STEPS:
    d0, a0 = count("defender.jsonl"), count("attacker.jsonl")
    st, rh, resp = send(method, path, sid, body)
    xh = ", ".join(f"{k}: {v}" for k, v in rh.items() if k.lower().startswith("x-")) or "-"
    rows.append((label, f"{method} {path}", st, len(resp), leaks(resp), xh,
                 resp.decode("latin-1")[:60]))
    detail.append((label, method, path, sid, resp,
                   tail("defender.jsonl", d0), tail("attacker.jsonl", a0)))

print("| 단계 | 요청 | status | 응답 길이 | 진짜 비밀 | 응답 헤더(X-) | 응답 본문(앞 60자) |")
print("|---|---|---|---|---|---|---|")
for label, req, st, n, lk, xh, prev in rows:
    print(f"| {label} | `{req}` | {st} | {n} | {lk} | {xh} | `{prev}` |")

print()
for label, method, path, sid, resp, dl, al in detail:
    print(f"**{label}**")
    print(f"- 요청: `{method} {path}` - `X-Session-Id: {sid}`")
    print(f"- 응답 본문 전체: `{resp.decode('latin-1')[:120]!r}`")
    print("- defender.jsonl:")
    for e in dl or []:
        print(f"  - `{json.dumps(e, ensure_ascii=False)}`")
    if not dl:
        print("  - (기록 없음)")
    print("- attacker.jsonl:")
    for e in al or []:
        print(f"  - `{json.dumps(e, ensure_ascii=False)}`")
    if not al:
        print("  - (기록 없음)")
    print()
