"""미끼 풀 관리 (원논문 3절 LXC Controller 대응).
- start_all(): 미끼 서버 프로세스를 config.DECOY_PORTS 마다 하나씩 띄움
- acquire():   사용 가능한 미끼 포트를 하나 꺼냄 (없으면 None)
- release(p):  해당 미끼 프로세스 종료(destroy) → 같은 포트로 새로 띄움(clone·start) → 풀에 되돌림
- stop_all():  모든 미끼 프로세스 종료
미끼는 proxy/decoy_launcher.py로 감싸 띄운다 (C7, Issue #16). pool은 launcher의 stdin 파이프를 쥐고 있고,
파이프가 닫히면(정상 종료, release, 또는 프록시가 강제 종료되어 운영체제가 닫음) launcher가 미끼를 정리하고 끝난다.
종료는 항상 "파이프 닫기"로 하고, STOP_TIMEOUT 안에 안 끝날 때만 강제 종료한다.
원논문과 차이: LXC 컨테이너 + overlayfs 재생성 대신 로컬 프로세스 재시작(빈 상태로 다시 시작)."""
import os, signal, subprocess, sys, threading, time, urllib.request
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from honeypatch import config

LOCK = threading.Lock()
AVAILABLE = list(config.DECOY_PORTS)   # 미끼 풀 (사용 가능)
PROCS = {}                             # port -> subprocess.Popen
_log = lambda event, **kw: None        # proxy.py가 dlog를 넘겨 줌 (방어자 내부 로그)
LAUNCHER = os.path.join(ROOT, "proxy", "decoy_launcher.py")
WINDOWS = os.name == "nt"
STOP_TIMEOUT = 5.0                     # 파이프를 닫은 뒤 launcher가 끝나기를 기다리는 시간(초)

def init(log=None):
    global _log
    if log is not None:
        _log = log

def _spawn(port):
    """launcher를 띄우고 stdin 파이프를 쥔다. POSIX는 새 세션으로 띄워 마지막 수단(killpg)이 미끼까지 닿게 한다."""
    extra = {} if WINDOWS else {"start_new_session": True}
    return subprocess.Popen(
        [sys.executable, LAUNCHER, "--mode", "honeypatched", "--role", "decoy", "--port", str(port)],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra)

def _wait_up(port, tries=50):
    for _ in range(tries):
        try:
            urllib.request.urlopen(f"http://{config.HOST}:{port}/__health", timeout=0.5)
            return True
        except Exception:
            time.sleep(0.1)
    return False

def _close(proc):
    """파이프를 닫아 launcher에 종료를 알린다 (launcher가 미끼를 정리하고 끝남)."""
    try:
        proc.stdin.close()
    except (OSError, AttributeError):
        pass

def _finish(proc):
    """launcher가 끝나기를 기다린다. STOP_TIMEOUT 안에 안 끝날 때만 강제 종료."""
    try:
        proc.wait(timeout=STOP_TIMEOUT)
        return
    except subprocess.TimeoutExpired:
        pass
    _log("decoy_force_kill", pid=proc.pid)
    if WINDOWS:                             # terminate()는 launcher만 죽이므로 자식까지 트리째 종료
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        proc.terminate()                    # launcher의 SIGTERM 처리가 미끼를 정리
        try:
            proc.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)   # launcher와 미끼(같은 세션)를 함께
            except OSError:
                pass
    proc.wait()

def _kill(proc):
    if proc is None:
        return
    _close(proc)
    _finish(proc)

def start_all():
    """미끼 프로세스를 모두 띄운다 (기동 완료를 기다리지는 않음)."""
    with LOCK:
        for p in config.DECOY_PORTS:
            if p not in PROCS:
                PROCS[p] = _spawn(p)

def stop_all():
    with LOCK:
        procs = list(PROCS.values())
        PROCS.clear()
    for proc in procs:                       # 파이프를 먼저 모두 닫고(동시에 정리 시작) 하나씩 기다림
        _close(proc)
    for proc in procs:
        _finish(proc)

def acquire():
    """사용 가능한 미끼 포트 하나를 꺼낸다. 풀이 비었으면 None."""
    with LOCK:
        return AVAILABLE.pop(0) if AVAILABLE else None

def release(port, reason="manual"):
    """destroy → clone → start 후 풀에 되돌린다. 재기동에 성공하면 True."""
    with LOCK:
        if port in AVAILABLE or port not in config.DECOY_PORTS:
            return False                     # 이미 풀에 있거나 미끼 포트가 아님
        old = PROCS.pop(port, None)
    _kill(old)                               # destroy: 공격자 상태가 남은 프로세스 제거
    new = _spawn(port)                       # clone·start: 깨끗한 미끼를 같은 포트로
    ok = _wait_up(port)
    with LOCK:
        PROCS[port] = new
        if ok:
            AVAILABLE.append(port)
    _log("release", decoy=port, reason=reason, ok=ok,
         old_pid=old.pid if old else None, new_pid=new.pid)
    return ok
