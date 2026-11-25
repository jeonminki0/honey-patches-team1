"""리버스 프록시 + 미끼 풀 관리 (원논문 3절 Reverse Proxy / LXC Controller 대응).
- 평소: 요청을 타깃으로 전달 (페이로드를 검사하지 않음)
- 타깃이 /__hp/fork 요청 → 미끼 acquire → 상태 restore → 세션을 미끼에 고정
- 타깃 응답에 X-HP-Forked 가 있으면 같은 요청을 미끼로 재전송(replay)
- 미끼로 간 요청, 위반 입력, 형식이 깨진 요청을 attacker.jsonl 에 기록
  (타깃 모드, 입력 길이(바이트), 응답 길이, 비밀 노출 수)
원논문과 차이: 프로세스/TCP 연결 이전 대신 '상태 복원 + 요청 재전송'."""
import argparse, json, os, signal, sys, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from honeypatch import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pool                            # proxy/pool.py: 미끼 풀 acquire/release

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "defender.jsonl")
ATTACK_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "attacker.jsonl")
LOCK = threading.Lock()
PINNED = {}                            # session_id -> decoy port
TARGET_MODE = None                     # 타깃 모드(unpatched/patched/honeypatched). 첫 요청 때 읽는다
LAST_SEEN = {}                         # session_id -> 미끼에 고정된 세션의 마지막 요청 시각

def dlog(event, **kw):
    """방어자 내부 로그 (공격자 응답과 분리해 기록)."""
    rec = {"t": round(time.time(), 4), "event": event, **kw}
    with LOCK, open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def alog(event, **kw):
    """공격자 행위 로그. 방어자 로그와 파일을 나눠 둔다."""
    rec = {"t": round(time.time(), 4), "event": event, **kw}
    with LOCK, open(ATTACK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

SECRETS = config.real_secrets()          # 진짜 비밀 문자열 (노출 여부 판정용)

def count_leaks(body):
    """응답에 진짜 비밀이 몇 개 섞였는지 센다. 비밀 값 자체는 로그에 남기지 않는다."""
    try:
        text = body.decode("latin-1")
    except Exception:
        return None
    return sum(1 for s in SECRETS if s in text)

def req_fields(raw):
    """공격자 요청에서 기록할 값만 뽑는다. 본문 전체는 남기지 않는다.

    서버(app.py)가 payload 를 encode() 한 뒤 길이를 비교하므로 바이트로 센다.
    서버가 받아들이지 못할 형식이면 over 를 계산할 수 없으니 malformed 로 남긴다."""
    if not raw:
        return {}
    out = {"body_len": len(raw)}
    try:
        msg = json.loads(raw)
        if not isinstance(msg["payload"], str):
            raise TypeError("payload 가 문자열이 아님")
        payload_len = len(msg["payload"].encode())   # 서버와 같게 바이트로 센다
        length = int(msg["length"])
    except Exception:
        # 서버가 받아들이지 못하는 입력은 종류를 가리지 않고 malformed 로 둔다.
        # length=1e999 는 OverflowError, payload 의 고립 서로게이트는
        # UnicodeEncodeError 처럼 예외 종류가 제각각이라 하나씩 나열하지 않는다.
        out["malformed"] = True
        return out
    out["payload_len"] = payload_len
    out["declared_len"] = length
    out["over"] = length - payload_len               # 0보다 크면 위반 입력
    return out

def touch(sid):
    with LOCK:
        if sid in PINNED:
            LAST_SEEN[sid] = time.time()

def reap_idle():
    """DECOY_TIMEOUT 동안 요청이 없는 고정 세션을 풀고 미끼를 release(재생성)."""
    now = time.time()
    with LOCK:
        idle = [(s, p) for s, p in PINNED.items() if now - LAST_SEEN.get(s, now) >= config.DECOY_TIMEOUT]
        for s, _ in idle:                      # 먼저 고정 해제 → 이후 요청은 타깃으로
            del PINNED[s]
            LAST_SEEN.pop(s, None)
    for s, p in idle:
        dlog("session_timeout", session=s, decoy=p, idle=config.DECOY_TIMEOUT)
        pool.release(p, reason="timeout")

def _reaper():
    while True:
        time.sleep(max(0.2, min(1.0, config.DECOY_TIMEOUT / 4)))
        reap_idle()

def forward(port, method, path, body, headers):
    req = urllib.request.Request(f"http://{config.HOST}:{port}{path}", data=body if method == "POST" else None,
                                 method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

def target_mode():
    """타깃이 어느 모드인지 /__health 에서 읽어 한 번만 저장한다 (응답 형식: target:unpatched).
    run_demo.py 가 세 모드를 같은 로그 파일에 쌓으므로, 기록이 어느 모드 것인지 구분하려면 필요하다."""
    global TARGET_MODE
    if TARGET_MODE:
        return TARGET_MODE
    try:
        st, _, body = forward(config.TARGET_PORT, "GET", "/__health", None, {})
        if st == 200:
            TARGET_MODE = body.decode("utf-8", "replace").split(":")[-1]
    except Exception:
        pass                                    # 타깃이 아직 안 떴으면 다음 요청에서 다시 읽는다
    return TARGET_MODE or "unknown"

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
        port = pool.acquire()
        if port is None:
            dlog("fork_fail", session=sid, reason="decoy pool empty")
            return self._reply(503, b"no decoy")
        st, _, _ = forward(port, "POST", "/__hp/restore", raw, {"Content-Type": "application/json"})
        if st != 200:
            dlog("fork_fail", session=sid, reason=f"restore {st}")
            return self._reply(503, b"restore failed")
        with LOCK:
            PINNED[sid] = port
            LAST_SEEN[sid] = time.time()
        dlog("fork_ok", session=sid, decoy=port)
        self._reply(200, b"forked")

    def _handle(self, method):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))) if method == "POST" else None
        if self.path == "/__hp/fork":
            return self._fork(raw)
        if self.path.startswith("/__"):
            # 내부 제어 경로는 밖으로 열지 않는다. 타깃이나 미끼로 넘기면
            # /__health 로 미끼 정체가 드러나고(원논문 7절의 환경 차이 탐지),
            # /__hp/restore 로 공격자가 미끼 상태를 덮어쓸 수 있다.
            # 타깃이 모르는 경로에 주는 것과 똑같은 404 로 답해 구분되지 않게 한다.
            dlog("blocked", session=self.headers.get("X-Session-Id", "anonymous"),
                 method=method, path=self.path)
            return self._reply(404, b"not found")
        sid = self.headers.get("X-Session-Id", "anonymous")
        hdr = {"X-Session-Id": sid, "Content-Type": self.headers.get("Content-Type", "application/json")}
        port = PINNED.get(sid, config.TARGET_PORT)
        st, rh, body = forward(port, method, self.path, raw, hdr)
        dlog("route", session=sid, to="decoy" if port != config.TARGET_PORT else "target", status=st)
        if rh.get("X-HP-Forked") == "1":                 # 타깃이 미끼로 넘김 → 재전송
            port = PINNED[sid]
            st, rh, body = forward(port, method, self.path, raw, hdr)
            dlog("route", session=sid, to="decoy", status=st, replay=True)
        # 기록은 공격자가 받는 응답에 영향을 주면 안 된다. 어떤 이유로 실패해도
        # 아래 _reply 는 그대로 나가야 하므로 통째로 감싼다.
        try:
            f = req_fields(raw)
            to_decoy = port != config.TARGET_PORT
            # 미끼로 갔거나, 위반 입력이거나, 서버가 못 읽는 형식일 때만 남긴다.
            # 정상 사용자 요청과 내부 경로(/__)는 제외한다.
            if not self.path.startswith("/__") and (to_decoy or f.get("over", 0) > 0 or f.get("malformed")):
                alog("request", session=sid, mode=target_mode(), method=method, path=self.path,
                     to="decoy" if to_decoy else "target",
                     status=st, resp_len=len(body), leaks=count_leaks(body), **f)
        except Exception:
            pass
        touch(sid)                                        # 미끼 고정 세션이면 마지막 요청 시각 갱신
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
    os.makedirs(os.path.dirname(ATTACK_LOG_PATH), exist_ok=True)
    pool.init(log=dlog)
    pool.start_all()                                   # 미끼 프로세스는 pool이 띄우고 관리
    threading.Thread(target=_reaper, daemon=True).start()   # 미끼 세션 타임아웃 감시
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # terminate() 시 미끼도 함께 정리
    try:
        ThreadingHTTPServer((config.HOST, a.port), H).serve_forever()
    finally:
        pool.stop_all()

if __name__ == "__main__":
    main()
