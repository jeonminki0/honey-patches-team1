"""C7 확인: 프록시가 정리 코드 없이 죽었을 때 미끼 프로세스가 남는지 본다 (Issue #16).
Windows의 Popen.terminate()는 TerminateProcess라서 프록시의 SIGTERM 처리·finally가 실행되지 않는다.
POSIX에서는 SIGKILL이 같은 상황이므로, 같은 조건을 운영체제별로 재현한다.

순서: 포트 비었는지 확인 → 타깃·프록시 기동 → 미끼 2개(config.DECOY_PORTS) 기동 확인
      → 프록시 강제 종료 (POSIX: SIGKILL, Windows: Popen.terminate())
      → 2초 뒤 미끼 포트 점유·미끼 프로세스 잔류 확인 → 남으면 FAIL, 없으면 PASS
      → 마지막에 타깃과 남은 미끼 프로세스를 반드시 정리
실행 (저장소 루트에서): python tests/decoy_pool/check_orphan.py     (FAIL이면 종료 코드 1)"""
import os, signal, socket, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.run_demo import wait_up

WINDOWS = os.name == "nt"
PORTS = [config.PROXY_PORT, config.TARGET_PORT, *config.DECOY_PORTS]
WAIT_AFTER_KILL = 2.0

def port_busy(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((config.HOST, port)) == 0

def list_procs():
    """(pid, 명령줄) 목록. 외부 패키지 없이 운영체제 기본 도구로 읽는다."""
    if WINDOWS:
        cmd = ["powershell", "-NoProfile", "-Command",
               "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"]
        sep = "\t"
    else:
        cmd = ["ps", "-eo", "pid=,args="]
        sep = None
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         universal_newlines=True, check=False).stdout
    procs = []
    for line in out.splitlines():
        parts = line.strip().split(sep, 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            procs.append((int(parts[0]), parts[1]))
    return procs

def decoy_procs():
    """미끼 포트로 띄운 미끼 서버(--role decoy) 또는 미끼 launcher 프로세스."""
    found = []
    for pid, args in list_procs():
        if pid == os.getpid():
            continue
        is_decoy = ("app.py" in args and "--role decoy" in args) or "decoy_launcher.py" in args
        if is_decoy and any(f"--port {p}" in args or args.rstrip().endswith(f" {p}") for p in config.DECOY_PORTS):
            found.append((pid, args))
    return found

def force_kill(pid):
    if WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

def main():
    busy = [p for p in PORTS if port_busy(p)]
    if busy:
        print(f"실행 실패: 포트 사용 중 {busy}. 남은 proxy.py·app.py 프로세스를 먼저 정리하세요.")
        return 1
    py = lambda *a: subprocess.Popen([sys.executable, *a], cwd=ROOT,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    target = py("server/app.py", "--mode", "honeypatched", "--role", "target", "--port", str(config.TARGET_PORT))
    proxy = py("proxy/proxy.py")
    result = 1
    try:
        for p in PORTS:
            wait_up(p)
        before = decoy_procs()
        print(f"기동: 타깃 pid {target.pid}, 프록시 pid {proxy.pid}")
        print(f"강제 종료 전 미끼 관련 프로세스 {len(before)}개:")
        for pid, args in before:
            print(f"   {pid}  {args}")
        print(f"강제 종료 전 미끼 포트 점유: { {p: port_busy(p) for p in config.DECOY_PORTS} }")

        how = "Popen.terminate() (TerminateProcess)" if WINDOWS else "SIGKILL"
        if WINDOWS:
            proxy.terminate()
        else:
            os.kill(proxy.pid, signal.SIGKILL)
        proxy.wait()
        print(f"프록시 강제 종료: {how}, 종료 코드 {proxy.returncode}")
        time.sleep(WAIT_AFTER_KILL)

        occupied = [p for p in config.DECOY_PORTS if port_busy(p)]
        left = decoy_procs()
        print(f"{WAIT_AFTER_KILL:.0f}초 뒤 미끼 포트 점유: {occupied or '없음'}")
        print(f"{WAIT_AFTER_KILL:.0f}초 뒤 남은 미끼 관련 프로세스 {len(left)}개:")
        for pid, args in left:
            print(f"   {pid}  {args}")
        ok = not occupied and not left
        print(f"[{'PASS' if ok else 'FAIL'}] 프록시 강제 종료 후 미끼 잔류 없음")
        result = 0 if ok else 1
    finally:
        if proxy.poll() is None:
            proxy.kill()
            proxy.wait()
        target.terminate()
        target.wait()
        left = decoy_procs()
        for pid, _ in left:
            force_kill(pid)
        if left:
            time.sleep(0.5)
        remain = decoy_procs()
        print(f"정리: 남은 미끼 관련 프로세스 {len(left)}개 강제 종료, 정리 후 {len(remain)}개, "
              f"포트 점유 {[p for p in PORTS if port_busy(p)] or '없음'}")
    return result

if __name__ == "__main__":
    sys.exit(main())
