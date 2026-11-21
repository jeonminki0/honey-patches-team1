"""한 줄 실행: python demo/run_demo.py
3모드(미패치/패치/허니패치) × 고정 사례 3종을 같은 입력으로 실행하고 비교표를 만든다.
판정 기준(11주차 기대 결과를 코드·출력값으로 구체화):
  - 비밀 노출 수 = 응답 본문에 config.SEED_USERS 의 token/user/ip 문자열이 나타난 개수
  - fork 수     = logs/defender.jsonl 의 fork_ok 이벤트 수 (해당 사례 실행 구간)
  - 라우팅      = defender 로그의 route 이벤트 (target / decoy)"""
import argparse, json, os, subprocess, sys, threading, time, urllib.request
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.client import send

LOG = os.path.join(ROOT, "logs", "defender.jsonl")
RES = os.path.join(ROOT, "results")
MODES = ["unpatched", "patched", "honeypatched"]
SECRETS = [s.encode() for s in config.real_secrets()]
REAL_HEAP0 = config.SEED_USERS[0]["token"][0].encode()   # 힙 첫 바이트(진짜)

def py(*args):
    return subprocess.Popen([sys.executable, *args], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_up(port, tries=50):
    for _ in range(tries):
        try:
            urllib.request.urlopen(f"http://{config.HOST}:{port}/__health", timeout=0.5)
            return True
        except Exception as e:
            if getattr(e, "code", None):      # 프록시는 /__health 를 타깃으로 넘김 → 응답 오면 OK
                return True
            time.sleep(0.1)
    raise RuntimeError(f"port {port} 기동 실패 (이미 사용 중인지 확인)")

def read_log():
    if not os.path.exists(LOG):
        return []
    with open(LOG, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def leaks(body):
    return sum(1 for s in SECRETS if s in body)

def run_mode(mode):
    procs = [py("server/app.py", "--mode", mode, "--role", "target", "--port", str(config.TARGET_PORT))]
    procs.append(py("proxy/proxy.py"))       # 미끼(config.DECOY_PORTS)는 proxy/pool.py가 띄움
    try:
        for p in [config.TARGET_PORT, *config.DECOY_PORTS, config.PROXY_PORT]:
            wait_up(p)
        cases = json.load(open(os.path.join(ROOT, "demo", "fixed_cases.json"), encoding="utf-8"))["cases"]
        out = {}
        for c in cases:
            n0 = len(read_log())
            st, body = send(c["session"], c["request"]["payload"], c["request"]["length"])
            r = {"status": st, "len": len(body), "body": body.decode("latin-1"), "leaks": leaks(body)}
            if c["id"] == "violation":
                # 동시 정상 사용자 + 같은 공격자 세션의 후속 요청
                box = {}
                t = threading.Thread(target=lambda: box.update(n=send("user-concurrent", "hello", 5)))
                t.start()
                f_st, f_body = send(c["session"], "ping", 4)
                t.join()
                r["followup"] = {"status": f_st, "body": f_body.decode("latin-1")}
                r["concurrent"] = {"status": box["n"][0], "body": box["n"][1].decode("latin-1")}
            time.sleep(0.1)
            ev = read_log()[n0:]
            r["forks"] = sum(1 for e in ev if e["event"] == "fork_ok")
            r["routes"] = [(e["session"], e["to"]) for e in ev if e["event"] == "route"]
            out[c["id"]] = r
        return out
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()

def judge(all_res):
    """모드별 기대 결과 대조. (check 이름, 통과 여부) 목록 반환."""
    U, P, Hn = (all_res[m] for m in MODES)
    rt = lambda r, sid, to: all(t == to for s, t in r["routes"] if s == sid)
    checks = {
        "normal": [
            ("세 모드 모두 200·'hello'", all(all_res[m]["normal"]["status"] == 200 and all_res[m]["normal"]["body"] == "hello" for m in MODES)),
            ("세 모드 fork 0회", all(all_res[m]["normal"]["forks"] == 0 for m in MODES)),
            ("허니패치: 타깃으로만 전달", rt(Hn["normal"], "user-normal", "target")),
        ],
        "violation": [
            ("미패치: 200·64B·비밀 포함", U["violation"]["status"] == 200 and U["violation"]["len"] == 64 and U["violation"]["leaks"] > 0),
            ("패치: 400 거부", P["violation"]["status"] == 400),
            ("허니패치: fork 1회", Hn["violation"]["forks"] == 1),
            ("허니패치: 200·64B", Hn["violation"]["status"] == 200 and Hn["violation"]["len"] == 64),
            ("허니패치: 실제 비밀 0건", Hn["violation"]["leaks"] == 0),
            ("허니패치: 후속 요청 미끼로", any(s == "attacker-1" and t == "decoy" for s, t in Hn["violation"]["routes"][-3:])),
            ("허니패치: 동시 정상 사용자 타깃·200 hello", Hn["violation"]["concurrent"]["status"] == 200 and Hn["violation"]["concurrent"]["body"] == "hello" and rt(Hn["violation"], "user-concurrent", "target")),
        ],
        "boundary": [
            ("패치: 400 거부", P["boundary"]["status"] == 400),
            ("허니패치: fork 1회", Hn["boundary"]["forks"] == 1),
            ("허니패치: 200·6B", Hn["boundary"]["status"] == 200 and Hn["boundary"]["len"] == 6),
            ("허니패치: 6번째 바이트가 진짜 값과 다름", Hn["boundary"]["len"] == 6 and Hn["boundary"]["body"][5].encode() != REAL_HEAP0),
            ("허니패치: 실제 비밀 0건", Hn["boundary"]["leaks"] == 0),
        ],
    }
    return checks

def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if os.path.exists(LOG):
        os.remove(LOG)
    all_res = {}
    for m in MODES:
        print(f"[run] {m} ...")
        all_res[m] = run_mode(m)
    json.dump(all_res, open(os.path.join(RES, "raw_results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    lines = ["# 보호 적용 전·후(모드별) 결과 비교", "",
             "| 사례 | 모드 | status | 길이 | 비밀 노출 | fork | 응답(앞 40자) |", "|---|---|---|---|---|---|---|"]
    for cid in ["normal", "violation", "boundary"]:
        for m in MODES:
            r = all_res[m][cid]
            lines.append(f"| {cid} | {m} | {r['status']} | {r['len']} | {r['leaks']} | {r['forks']} | `{r['body'][:40]!r}` |")
    lines += ["", "## 기대 결과 대조", ""]
    total = ok = 0
    for cid, cs in judge(all_res).items():
        for name, passed in cs:
            total += 1; ok += passed
            lines.append(f"- [{'PASS' if passed else 'FAIL'}] {cid}: {name}")
    lines += ["", f"**{ok}/{total} 통과**"]
    report = "\n".join(lines)
    open(os.path.join(RES, "compare.md"), "w", encoding="utf-8").write(report)
    print(report)

if __name__ == "__main__":
    main()
