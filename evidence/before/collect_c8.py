"""C8·C9·C10 수정 전 증거 수집. 소스 코드는 건드리지 않고 현재 코드 그대로 실행한다.
  C8: 외부 클라이언트가 프록시에 POST /__hp/fork → 세션 고정, 미끼 상태 주입, 미끼 풀 고갈
  C9: 절대 URI 요청(GET http://127.0.0.1:9101/__health)에 프록시가 응답 없이 연결을 끊음 (타깃 직접은 404)
  C10: 프록시를 거치지 않고 미끼 포트(9101)에 직접 POST /__hp/restore
실행 (저장소 루트에서): python3 evidence/before/collect_c8.py
주의: 포트 8080·9000·9101·9102 가 비어 있어야 함. 요청 줄을 정규화 없이 보내려고 소켓을 직접 쓴다."""
import json, os, socket, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.run_demo import wait_up, leaks

H, P = config.HOST, config.PROXY_PORT
DLOG = os.path.join(ROOT, "logs", "defender.jsonl")
ALOG = os.path.join(ROOT, "logs", "attacker.jsonl")

def raw(method, target, sid, body=b"", port=P):
    """요청 줄을 그대로 보내고 (status, 본문)을 돌려준다. 응답 없이 끊기면 ("끊김", b"")."""
    s = socket.create_connection((H, port), timeout=5)
    head = (f"{method} {target} HTTP/1.1\r\nHost: {H}\r\nX-Session-Id: {sid}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n")
    data = b""
    try:
        s.sendall(head.encode("latin-1") + body)
        while True:
            c = s.recv(65536)
            if not c:
                break
            data += c
    except OSError as e:
        return "ERR " + type(e).__name__, b""
    finally:
        s.close()
    if not data:
        return "끊김", b""
    hdr, _, b = data.partition(b"\r\n\r\n")
    return int(hdr.split()[1]), b

def nlines(p):
    return sum(1 for _ in open(p, encoding="utf-8")) if os.path.exists(p) else 0

def since(p, n):
    return [json.loads(l) for l in open(p, encoding="utf-8")][n:] if os.path.exists(p) else []

def hb(sid, payload="hi", length=64):
    return raw("POST", "/heartbeat", sid, json.dumps({"payload": payload, "length": length}).encode())

def start():
    py = lambda *a: subprocess.Popen([sys.executable, *a], cwd=ROOT,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ps = [py("server/app.py", "--mode", "honeypatched", "--role", "target", "--port", str(config.TARGET_PORT)),
          py("proxy/proxy.py")]
    for p in [config.TARGET_PORT, *config.DECOY_PORTS, P]:
        wait_up(p)
    return ps

def stop(ps):
    for p in ps:
        p.terminate()
    for p in ps:
        p.wait()

def step(label, fn):
    """요청 하나를 보내고 응답과 로그 증가분을 출력한다."""
    d0, a0 = nlines(DLOG), nlines(ALOG)
    st, b = fn()
    d, a = since(DLOG, d0), since(ALOG, a0)
    print(f"[{label}]")
    print(f"  응답: {st}, {len(b)}바이트, 진짜 비밀 {leaks(b)}건, 본문 {b[:70]!r}")
    for e in d:
        print("  defender:", json.dumps({k: v for k, v in e.items() if k != "t"}, ensure_ascii=False))
    for e in a:
        print("  attacker:", json.dumps({k: v for k, v in e.items() if k != "t"}, ensure_ascii=False))
    return st, b

def main():
    print("== C8: 외부 POST /__hp/fork (허니패치 모드)")
    ps = start()
    try:
        step("1. 진짜 user-normal hello/5 (fork 전)", lambda: hb("user-normal", "hello", 5))
        step("2. 진짜 user-normal GET /files/users.csv (fork 전)", lambda: raw("GET", "/files/users.csv", "user-normal"))
        step("3. 외부 클라이언트(세션 anyone) POST /__hp/fork {session:user-normal, state:{sessions:[]}}",
             lambda: raw("POST", "/__hp/fork", "anyone",
                         json.dumps({"session": "user-normal", "state": {"sessions": []}}).encode()))
        step("4. 진짜 user-normal hello/5 (fork 후)", lambda: hb("user-normal", "hello", 5))
        step("5. 진짜 user-normal GET /files/users.csv (fork 후)", lambda: raw("GET", "/files/users.csv", "user-normal"))
        step("6. 외부 POST /__hp/fork로 상태 주입 {session:attacker-9, sessions:[INJECTED_BY_FORK]}",
             lambda: raw("POST", "/__hp/fork", "x", json.dumps({"session": "attacker-9", "state": {"sessions": [
                 {"sid": "zz", "token": "INJECTED_BY_FORK", "user": "evil", "ip": "6.6.6.6"}]}}).encode()))
        step("7. attacker-9 hi/64 (주입한 미끼)", lambda: hb("attacker-9"))
        step("8. 풀 고갈 뒤 진짜 공격 attacker-1 hi/64", lambda: hb("attacker-1"))
    finally:
        stop(ps)

    print("\n== C9: 절대 URI 요청 (허니패치 모드)")
    ps = start()
    try:
        step("1. 프록시에 GET http://127.0.0.1:9101/__health", lambda: raw("GET", "http://127.0.0.1:9101/__health", "probe"))
        step("2. 타깃 직접 GET http://127.0.0.1:9101/__health (비교용)",
             lambda: raw("GET", "http://127.0.0.1:9101/__health", "probe", port=config.TARGET_PORT))
        step("3. 프록시에 GET /nope (비교용)", lambda: raw("GET", "/nope", "probe"))
    finally:
        stop(ps)

    print("\n== C10: 미끼 포트 직접 접근 (허니패치 모드)")
    ps = start()
    try:
        step("1. attacker-1 공격 hi/64 (프록시 경유, 미끼 고정)", lambda: hb("attacker-1"))
        step("2. 미끼 9101에 직접 POST /__hp/restore {INJECTED00000000}",
             lambda: raw("POST", "/__hp/restore", "x", json.dumps({"session": "attacker-1", "state": {"sessions": [
                 {"sid": "attacker-1", "token": "INJECTED00000000", "user": "INJ", "ip": "6.6.6.6"}]}}).encode(),
                 port=config.DECOY_PORTS[0]))
        step("3. attacker-1 hi/64 (프록시 경유)", lambda: hb("attacker-1"))
        step("4. 미끼 9101에 직접 GET /__health", lambda: raw("GET", "/__health", "x", port=config.DECOY_PORTS[0]))
    finally:
        stop(ps)

if __name__ == "__main__":
    main()
