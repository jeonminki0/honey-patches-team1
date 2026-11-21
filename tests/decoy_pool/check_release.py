"""미끼 풀 release(destroy → clone → start) 확인.
확인 내용:
  1. 풀 크기(config.DECOY_PORTS)만큼 acquire되고, 그 이상은 None
  2. release 후 미끼 프로세스가 새 pid로 다시 뜨고 풀에 되돌아와 다시 acquire됨
  3. 재생성된 미끼에는 이전에 복원한 공격자 상태가 남아 있지 않음
  4. 미끼 포트가 아닌 포트의 release는 거부(False)
  5. logs/defender.jsonl 에 release 이벤트가 기록됨
실행 (저장소 루트에서): python tests/decoy_pool/check_release.py
주의: 미끼 포트(config.DECOY_PORTS)가 비어 있어야 함. 실행 중인 run_demo.py와 동시에 돌리지 말 것."""
import json, os, sys, urllib.request
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "proxy"))
sys.path.insert(0, ROOT)
import proxy, pool                         # proxy.dlog → logs/defender.jsonl
from honeypatch import config

LOG = os.path.join(ROOT, "logs", "defender.jsonl")
results = []

def check(name, ok):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    n0 = sum(1 for _ in open(LOG, encoding="utf-8")) if os.path.exists(LOG) else 0
    pool.init(log=proxy.dlog)
    pool.start_all()
    try:
        for p in config.DECOY_PORTS:
            assert pool._wait_up(p), f"미끼 {p} 기동 실패"
        got = [pool.acquire() for _ in range(len(config.DECOY_PORTS) + 1)]
        print("acquire:", got)
        check("풀 크기만큼 acquire, 그 이상은 None", got == list(config.DECOY_PORTS) + [None])

        a = got[0]
        old_pid = pool.PROCS[a].pid
        body = json.dumps({"session": "attacker-x", "state": {"sessions": [
            {"sid": "attacker-x", "token": "f" * 16, "user": "x", "ip": "1.2.3.4"}]}}).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"http://{config.HOST}:{a}/__hp/restore", data=body, method="POST"), timeout=5)

        ok = pool.release(a)
        new_pid = pool.PROCS[a].pid
        print(f"release({a}) = {ok}, pid {old_pid} -> {new_pid}, AVAILABLE = {pool.AVAILABLE}")
        check("release 성공 + 새 pid", ok and new_pid != old_pid)
        check("release 후 다시 acquire됨", pool.acquire() == a)

        hb = json.dumps({"payload": "hi", "length": 30}).encode()
        r = urllib.request.urlopen(urllib.request.Request(
            f"http://{config.HOST}:{a}/heartbeat", data=hb, method="POST",
            headers={"X-Session-Id": "probe"}), timeout=5).read()
        print("재생성된 미끼 heartbeat:", r)
        check("재생성된 미끼에 이전 공격자 상태 없음", b"ffffffffffffffff" not in r)

        check("미끼 포트가 아닌 포트(TARGET_PORT) release 거부", pool.release(config.TARGET_PORT) is False)
    finally:
        pool.stop_all()

    ev = [json.loads(l) for l in list(open(LOG, encoding="utf-8"))[n0:]]
    rel = [e for e in ev if e["event"] == "release"]
    for e in rel:
        print("  log:", json.dumps(e, ensure_ascii=False))
    check("defender.jsonl 에 release 이벤트 기록", any(e["decoy"] == a and e["ok"] for e in rel))

    print(f"\n{sum(results)}/{len(results)} 통과")
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
