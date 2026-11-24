"""13주차 수정 전 증거 수집 (반례 후보 a~f). 소스 코드는 건드리지 않고 현재 코드 그대로 실행한다.
실행 (저장소 루트에서): python3 evidence/before/collect.py
출력: evidence/before/raw.json (사례별 요청·응답·로그 발췌)
주의: 포트 8080·9000·9101·9102 가 비어 있어야 함. logs/defender.jsonl, logs/attacker.jsonl 을 지우고 새로 기록함."""
import http.client, json, os, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.run_demo import wait_up

DLOG = os.path.join(ROOT, "logs", "defender.jsonl")
ALOG = os.path.join(ROOT, "logs", "attacker.jsonl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw.json")
SECRETS = config.real_secrets()

def lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

class Run:
    """타깃(mode) + 프록시(미끼 2개 자동 기동)를 띄우고, 요청마다 응답과 로그 증가분을 기록한다."""
    def __init__(self, mode):
        self.mode, self.steps = mode, []
        py = lambda *a: subprocess.Popen([sys.executable, *a], cwd=ROOT,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs = [py("server/app.py", "--mode", mode, "--role", "target", "--port", str(config.TARGET_PORT)),
                      py("proxy/proxy.py")]
        for p in [config.TARGET_PORT, *config.DECOY_PORTS, config.PROXY_PORT]:
            wait_up(p)
        # wait_up 의 /__health 요청이 남긴 로그는 사례 기록에서 제외
        self.d0, self.a0 = len(lines(DLOG)), len(lines(ALOG))

    def req(self, label, method, path, sid, body=None, port=None):
        port = port or config.PROXY_PORT
        raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
        c = http.client.HTTPConnection(config.HOST, port, timeout=5)
        try:
            c.request(method, path, body=raw, headers={"X-Session-Id": sid, "Content-Type": "application/json"})
            r = c.getresponse()
            st, hdrs, resp = r.status, dict(r.getheaders()), r.read()
        except Exception as e:
            st, hdrs, resp = "ERR " + type(e).__name__, {}, b""
        time.sleep(0.1)
        d, a = lines(DLOG), lines(ALOG)
        text = resp.decode("latin-1")
        self.steps.append({
            "label": label, "mode": self.mode, "method": method, "path": path, "session": sid,
            "via": "proxy:%d" % port if port == config.PROXY_PORT else "target direct:%d" % port,
            "request": raw.decode() if raw else None, "status": st, "resp_len": len(resp),
            "leaks": sum(1 for s in SECRETS if s in text), "leaked": [s for s in SECRETS if s in text],
            "headers": {k: v for k, v in hdrs.items() if k.lower().startswith("x-")},
            "body": text, "defender": d[self.d0:], "attacker": a[self.a0:]})
        self.d0, self.a0 = len(d), len(a)
        return st, resp

    def stop(self):
        for p in self.procs:
            p.terminate()
        for p in self.procs:
            p.wait()

def main():
    for p in (DLOG, ALOG):
        if os.path.exists(p):
            os.remove(p)
    out = {}

    # a, b: 음수·0 length, 세 모드
    for case, length in [("a", -1), ("b", 0)]:
        out[case] = []
        for mode in ["unpatched", "patched", "honeypatched"]:
            r = Run(mode)
            try:
                r.req(f"{case}: hello / length {length}", "POST", "/heartbeat", f"attacker-{case}",
                      {"payload": "hello", "length": length})
            finally:
                r.stop()
            out[case] += r.steps

    # c: 공격 후 같은 세션으로 /__health
    r = Run("honeypatched")
    try:
        r.req("정상 사용자 /__health (비교용)", "GET", "/__health", "user-normal")
        r.req("attacker-1 공격 hi/64", "POST", "/heartbeat", "attacker-1", {"payload": "hi", "length": 64})
        r.req("attacker-1 /__health", "GET", "/__health", "attacker-1")
    finally:
        r.stop()
    out["c"] = r.steps

    # d: 공격 후 같은 세션으로 /__hp/restore → 다시 공격
    r = Run("honeypatched")
    try:
        r.req("고정 안 된 세션의 /__hp/restore (비교용)", "POST", "/__hp/restore", "user-z", {"state": {"sessions": []}})
        r.req("attacker-1 공격 hi/64 (1차)", "POST", "/heartbeat", "attacker-1", {"payload": "hi", "length": 64})
        r.req("attacker-1 /__hp/restore 빈 세션", "POST", "/__hp/restore", "attacker-1", {"state": {"sessions": []}})
        r.req("attacker-1 공격 hi/64 (2차)", "POST", "/heartbeat", "attacker-1", {"payload": "hi", "length": 64})
    finally:
        r.stop()
    out["d"] = r.steps

    # e: 공격 전후 타깃 세션 테이블
    T = config.TARGET_PORT
    r = Run("honeypatched")
    try:
        r.req("공격 전: 타깃 직접 user-x hello/-1 (메모리 읽기)", "POST", "/heartbeat", "user-x", {"payload": "hello", "length": -1}, port=T)
        r.req("attacker-1 공격 hi/64 (프록시 경유)", "POST", "/heartbeat", "attacker-1", {"payload": "hi", "length": 64})
        r.req("공격 후: 타깃 직접 user-x hello/-1 (메모리 읽기)", "POST", "/heartbeat", "user-x", {"payload": "hello", "length": -1}, port=T)
        r.req("지시한 요청: 타깃 직접 user-x hi/200", "POST", "/heartbeat", "user-x", {"payload": "hi", "length": 200}, port=T)
        r.req("지시한 요청 이후: 타깃 직접 user-x hello/-1", "POST", "/heartbeat", "user-x", {"payload": "hello", "length": -1}, port=T)
    finally:
        r.stop()
    out["e"] = r.steps

    # f: 세션 ID 사칭
    r = Run("honeypatched")
    try:
        r.req("진짜 user-normal 정상 요청 (사칭 전)", "POST", "/heartbeat", "user-normal", {"payload": "hello", "length": 5})
        r.req("진짜 user-normal 파일 (사칭 전)", "GET", "/files/users.csv", "user-normal")
        r.req("attacker-9 가 X-Session-Id=user-normal 로 공격 hi/64", "POST", "/heartbeat", "user-normal", {"payload": "hi", "length": 64})
        r.req("진짜 user-normal 정상 요청 (사칭 후)", "POST", "/heartbeat", "user-normal", {"payload": "hello", "length": 5})
        r.req("진짜 user-normal 파일 (사칭 후)", "GET", "/files/users.csv", "user-normal")
    finally:
        r.stop()
    out["f"] = r.steps

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for case, steps in out.items():
        print(f"== {case}")
        for s in steps:
            print(f"  [{s['mode'][:5]}] {s['label']:48s} {s['status']} len={s['resp_len']:<4} leaks={s['leaks']} "
                  f"hdr={s['headers'] or ''} body={s['body'][:46]!r}")
            for e in s["defender"]:
                print("      D", {k: v for k, v in e.items() if k != "t"})
            for e in s["attacker"]:
                print("      A", {k: v for k, v in e.items() if k != "t"})

if __name__ == "__main__":
    main()
