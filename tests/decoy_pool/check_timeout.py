"""미끼 세션 타임아웃 자동 release 확인 (config.DECOY_TIMEOUT 값을 그대로 사용, 설정 파일은 바꾸지 않음).
확인 내용:
  1. 공격(위반 입력) → fork_ok, 세션이 미끼에 고정됨
  2. DECOY_TIMEOUT 안에 다시 요청하면 타이머가 갱신되어 계속 미끼로 감
  3. DECOY_TIMEOUT 넘게 요청이 없으면 session_timeout → release(reason=timeout) 기록
  4. 그 뒤 같은 세션의 요청은 타깃으로 가고, 다시 공격하면 새로 fork됨
실행 (저장소 루트에서): python tests/decoy_pool/check_timeout.py
소요 시간: 약 DECOY_TIMEOUT × 2 + 4초 (기본 30초 → 약 1분)
주의: logs/defender.jsonl 을 지우고 새로 기록함. 포트 8080·9000·9101·9102 가 비어 있어야 함."""
import json, os, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.client import send
from demo.run_demo import wait_up

LOG = os.path.join(ROOT, "logs", "defender.jsonl")
T = config.DECOY_TIMEOUT
results = []

def check(name, ok):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

def py(*args):
    return subprocess.Popen([sys.executable, *args], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def events():
    with open(LOG, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def last_route(sid):
    return [e for e in events() if e["event"] == "route" and e["session"] == sid][-1]["to"]

def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if os.path.exists(LOG):
        os.remove(LOG)
    procs = [py("server/app.py", "--mode", "honeypatched", "--role", "target", "--port", str(config.TARGET_PORT)),
             py("proxy/proxy.py")]
    try:
        for p in [config.TARGET_PORT, *config.DECOY_PORTS, config.PROXY_PORT]:
            wait_up(p)
        t0 = time.time()
        el = lambda: f"[{time.time() - t0:5.1f}s]"
        print(f"DECOY_TIMEOUT = {T}s")
        print(el(), "공격:", send("attacker-1", "hi", 64)[0])
        check("공격 후 fork_ok", any(e["event"] == "fork_ok" for e in events()))

        time.sleep(T * 0.6)
        print(el(), "요청:", send("attacker-1", "ping", 4), "→", last_route("attacker-1"))
        time.sleep(T * 0.6)                  # 공격 시점 기준으로는 T를 넘었지만 타이머가 갱신됨
        print(el(), "요청:", send("attacker-1", "ping", 4), "→", last_route("attacker-1"))
        check("타임아웃 안에 요청하면 계속 미끼로", last_route("attacker-1") == "decoy"
              and not any(e["event"] == "session_timeout" for e in events()))

        time.sleep(T + 2.5)                  # 감시 주기(최대 1초) + 재기동 시간 여유
        print(el(), "요청:", send("attacker-1", "ping", 4), "→", last_route("attacker-1"))
        ev = events()
        check("session_timeout 기록", any(e["event"] == "session_timeout" and e["session"] == "attacker-1" for e in ev))
        check("release(reason=timeout, ok) 기록", any(e["event"] == "release" and e["reason"] == "timeout" and e["ok"] for e in ev))
        check("타임아웃 후 요청은 타깃으로", last_route("attacker-1") == "target")

        print(el(), "다시 공격:", send("attacker-1", "hi", 64)[0])
        time.sleep(0.2)
        check("다시 공격하면 새로 fork", sum(1 for e in events() if e["event"] == "fork_ok") == 2)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()

    print("defender.jsonl (attacker-1 / release):")
    for e in events():
        if e.get("session") == "attacker-1" or e["event"] == "release":
            print("  ", json.dumps(e, ensure_ascii=False))
    print(f"\n{sum(results)}/{len(results)} 통과")
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
