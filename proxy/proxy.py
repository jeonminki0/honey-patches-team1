"""리버스 프록시 + 미끼 풀 관리 (원논문 3절 Reverse Proxy / LXC Controller 대응).
- 평소: 요청을 타깃으로 전달 (페이로드를 검사하지 않음)
- 타깃이 /__hp/fork 요청 → 미끼 acquire → 상태 restore → 세션을 미끼에 고정
- 타깃 응답에 X-HP-Forked 가 있으면 같은 요청을 미끼로 재전송(replay)
원논문과 차이: 프로세스/TCP 연결 이전 대신 '상태 복원 + 요청 재전송'."""
import argparse, json, os, sys, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from honeypatch import config

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "defender.jsonl")
LOCK = threading.Lock()
AVAILABLE = list(config.DECOY_PORTS)   # 미끼 풀 (사용 가능)
PINNED = {}                            # session_id -> decoy port

def dlog(event, **kw):
    """방어자 내부 로그 (공격자 응답과 분리해 기록)."""
    rec = {"t": round(time.time(), 4), "event": event, **kw}
    with LOCK, open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def acquire():
    with LOCK:
        return AVAILABLE.pop(0) if AVAILABLE else None

def forward(port, method, path, body, headers):
    req = urllib.request.Request(f"http://{config.HOST}:{port}{path}", data=body if method == "POST" else None,
                                 method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            if k.lower() in ("content-type",):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fork(self, raw):
        msg = json.loads(raw)
        sid = msg["session"]
        port = acquire()
        if port is None:
            dlog("fork_fail", session=sid, reason="decoy pool empty")
            return self._reply(503, b"no decoy")
        st, _, _ = forward(port, "POST", "/__hp/restore", raw, {"Content-Type": "application/json"})
        if st != 200:
            dlog("fork_fail", session=sid, reason=f"restore {st}")
            return self._reply(503, b"restore failed")
        with LOCK:
            PINNED[sid] = port
        dlog("fork_ok", session=sid, decoy=port)
        self._reply(200, b"forked")

    def _handle(self, method):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))) if method == "POST" else None
        if self.path == "/__hp/fork":
            return self._fork(raw)
        sid = self.headers.get("X-Session-Id", "anonymous")
        hdr = {"X-Session-Id": sid, "Content-Type": self.headers.get("Content-Type", "application/json")}
        port = PINNED.get(sid, config.TARGET_PORT)
        st, rh, body = forward(port, method, self.path, raw, hdr)
        dlog("route", session=sid, to="decoy" if port != config.TARGET_PORT else "target", status=st)
        if rh.get("X-HP-Forked") == "1":                 # 타깃이 미끼로 넘김 → 재전송
            port = PINNED[sid]
            st, rh, body = forward(port, method, self.path, raw, hdr)
            dlog("route", session=sid, to="decoy", status=st, replay=True)
        self._reply(st, body, rh)                         # 내부 헤더(X-HP-*)는 제거됨

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=config.PROXY_PORT)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ThreadingHTTPServer((config.HOST, a.port), H).serve_forever()

if __name__ == "__main__":
    main()
