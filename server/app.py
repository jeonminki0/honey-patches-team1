"""대상 서버: Heartbleed 구조를 흉내 낸 /heartbeat (원논문 Listing 1·2 대응).
--mode unpatched | patched | honeypatched,  --role target | decoy"""
import argparse, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from honeypatch import config, hp

LOCK = threading.Lock()
STATE = {"sessions": []}     # 서버 '메모리'에 있는 세션 테이블
MODE = "unpatched"
ROLE = "target"

def get_state():
    with LOCK:
        return json.loads(json.dumps(STATE))

def heap_bytes():
    """payload 바로 뒤에 놓인 힙 영역: 세션 레코드가 연속으로 배치됨.
    레코드 = token|user|ip;  (첫 바이트부터 비밀이 시작되도록 배치)"""
    with LOCK:
        return "".join(f'{s["token"]}|{s["user"]}|{s["ip"]};' for s in STATE["sessions"]).encode()

def ensure_session(sid):
    with LOCK:
        if not any(s["sid"] == sid for s in STATE["sessions"]):
            STATE["sessions"].append({"sid": sid, "token": "0" * 16, "user": sid[:8], "ip": "127.0.0.1"})

def heartbeat(payload: bytes, length: int, sid: str):
    """반환: (status, body, extra_headers)"""
    reject = lambda: (400, b"bad heartbeat", {})
    if length > len(payload):                       # ← 원래 패치의 탐지 조건
        if MODE == "patched":
            return reject()
        if MODE == "honeypatched":
            if hp.hp_fork(sid):                     # 타깃: 미끼로 분기 성공
                return 200, b"", {"X-HP-Forked": "1"}
            r = hp.hp_skip(reject)                  # 타깃+fork 실패 → 거부 / 미끼 → 건너뜀
            if r is not None:
                return r
    memory = payload + heap_bytes()                 # 취약 코드: 선언 길이만큼 그대로 읽음
    return 200, memory[:length], {}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body, headers=None, ctype="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/__health":
            return self._send(200, f"{ROLE}:{MODE}".encode(), ctype="text/plain")
        self._send(404, b"not found")

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/__hp/restore" and ROLE == "decoy":     # 미끼: 상태 복원
            with LOCK:
                STATE.update(json.loads(raw)["state"])
            return self._send(200, b"restored", ctype="text/plain")
        if self.path == "/heartbeat":
            sid = self.headers.get("X-Session-Id", "anonymous")
            ensure_session(sid)
            try:
                req = json.loads(raw)
                payload, length = req["payload"].encode(), int(req["length"])
            except Exception:
                return self._send(400, b"malformed")
            status, body, hdr = heartbeat(payload, length, sid)
            return self._send(status, body, hdr)
        self._send(404, b"not found")

def main():
    global MODE, ROLE
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["unpatched", "patched", "honeypatched"], default="unpatched")
    ap.add_argument("--role", choices=["target", "decoy"], default="target")
    ap.add_argument("--port", type=int, default=config.TARGET_PORT)
    a = ap.parse_args()
    MODE, ROLE = a.mode, a.role
    if ROLE == "target":
        STATE["sessions"] = [dict(u) for u in config.SEED_USERS]
    hp.hp_init(ROLE, get_state)
    ThreadingHTTPServer((config.HOST, a.port), H).serve_forever()

if __name__ == "__main__":
    main()
