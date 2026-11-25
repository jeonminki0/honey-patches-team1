"""미끼 launcher (C7, Issue #16): 미끼 서버(server/app.py)를 자식으로 띄우고, 부모(프록시)가 사라지면 함께 정리한다.

pool.py가 이 launcher를 stdin=PIPE로 띄우고 파이프의 쓰기 쪽을 쥐고 있는다. 부모는 아무것도 쓰지 않는다.
- 부모가 어떻게 끝나든(정상 종료, SIGKILL, Windows의 TerminateProcess) 운영체제가 쓰기 쪽을 닫는다
  → launcher의 stdin 읽기가 EOF(빈 바이트)를 받는다 → 미끼를 종료하고 launcher도 끝난다.
- pool.py가 release()/stop_all()에서 파이프를 닫아도 같은 경로로 정리된다.
- 미끼가 스스로 끝나면(예: 포트 충돌로 기동 실패) launcher도 바로 끝난다.
부모 생존을 os.kill(pid, 0)로 확인하지 않는다 (Windows에서는 Ctrl+C 이벤트가 된다).

실행: pool.py가 띄운다. 인자는 그대로 server/app.py에 넘긴다.
  python proxy/decoy_launcher.py --mode honeypatched --role decoy --port 9101   (stdin을 닫으면 정리)"""
import os, signal, subprocess, sys, threading
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STOP_TIMEOUT = 3.0          # 미끼가 terminate() 후 이 시간 안에 안 끝나면 kill()

def stop(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()

def main():
    child = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "server", "app.py"), *sys.argv[1:]],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def watch_child():                      # 미끼가 먼저 끝나면 launcher도 끝낸다
        child.wait()
        os._exit(0)
    threading.Thread(target=watch_child, daemon=True).start()

    if os.name != "nt":                     # pool.py의 마지막 수단(terminate) 때도 미끼를 정리
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while sys.stdin.buffer.read(1024):  # 부모는 쓰지 않으므로 EOF(b"")가 올 때까지 대기
            pass
    except BaseException:                   # SIGTERM(SystemExit), Ctrl+C, 읽기 오류 모두 정리로
        pass
    finally:
        stop(child)

if __name__ == "__main__":
    main()
