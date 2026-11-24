"""13주차 추가 사례(반례 탐색) 실행기.  고정 사례(fixed_cases.json)와 run_demo.py는 건드리지 않는다.

실행 (저장소 루트에서):
  python3 demo/run_extra.py                               # demo/extra_cases/*.json 전체
  python3 demo/run_extra.py --file proxy.json             # 파일 하나
  python3 demo/run_extra.py --case C1-negative-length     # 사례 하나 (--file과 함께 써도 됨)

동작:
  - 사례 × 모드마다 타깃(해당 모드)과 프록시(미끼 자동 기동)를 새로 띄워 이전 상태가 섞이지 않게 한다.
  - steps를 순서대로 보내고, 단계마다 logs/defender.jsonl·logs/attacker.jsonl 증가분으로 forks·route를 판정한다.
  - leaks는 run_demo.py의 leaks()를 그대로 쓴다 (config.SEED_USERS의 token·user·ip가 응답에 나타난 개수).
  - 결과: results/extra_results.md (사례×모드별 기대/실제/PASS·FAIL, FAIL은 반례 후보 목록).
  - 실행 전 포트가 비어 있는지 확인하고, 끝나면 띄운 프로세스를 일반 종료(terminate)로 정리한다.
  - FAIL이 있어도 종료 코드는 0이다 (탐색용). 실행 자체가 실패하면 1.
사례 형식은 demo/extra_cases/README.md 참고."""
import argparse, glob, http.client, json, os, socket, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.run_demo import leaks, wait_up          # run_demo.py는 import만 한다

CASE_DIR = os.path.join(ROOT, "demo", "extra_cases")
DLOG = os.path.join(ROOT, "logs", "defender.jsonl")
ALOG = os.path.join(ROOT, "logs", "attacker.jsonl")
OUT = os.path.join(ROOT, "results", "extra_results.md")
PORTS = [config.PROXY_PORT, config.TARGET_PORT, *config.DECOY_PORTS]
KEYS = ["status", "len", "leaks", "forks", "route", "body", "body_contains", "body_not_contains", "same_as_step"]

def port_busy(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((config.HOST, port)) == 0

def wait_ports_free(tries=50):
    for _ in range(tries):
        busy = [p for p in PORTS if port_busy(p)]
        if not busy:
            return
        time.sleep(0.1)
    raise RuntimeError(f"포트 사용 중: {busy}. 남은 proxy.py·app.py 프로세스를 먼저 정리하세요.")

def log_len(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())

def log_since(path, n):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()][n:]

def send(step):
    port = config.TARGET_PORT if step.get("target", "proxy") == "target_direct" else config.PROXY_PORT
    body = step.get("body")
    raw = None if body is None else (json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, str) else body.encode())
    headers = {"X-Session-Id": step["session"], "Content-Type": "application/json"}
    headers.update(step.get("headers") or {})
    c = http.client.HTTPConnection(config.HOST, port, timeout=10)
    try:
        c.request(step.get("method", "POST"), step["path"], body=raw, headers=headers)
        r = c.getresponse()
        return r.status, r.read()
    except Exception as e:
        return "ERR " + type(e).__name__, b""
    finally:
        c.close()

def run_steps(case, mode):
    """타깃·프록시를 새로 띄우고 steps를 실행. 단계별 실제 값 목록을 돌려준다."""
    wait_ports_free()
    py = lambda *a: subprocess.Popen([sys.executable, *a], cwd=ROOT,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs = [py("server/app.py", "--mode", mode, "--role", "target", "--port", str(config.TARGET_PORT)),
             py("proxy/proxy.py")]
    actual = []
    try:
        for p in PORTS:
            wait_up(p)
        for step in case["steps"]:
            d0, a0 = log_len(DLOG), log_len(ALOG)
            st, body = send(step)
            time.sleep(0.1)                                   # 로그 기록 대기
            ev = log_since(DLOG, d0)
            routes = [e["to"] for e in ev if e["event"] == "route" and e.get("session") == step["session"]]
            direct = step.get("target", "proxy") == "target_direct"
            actual.append({
                "status": st, "len": len(body), "leaks": leaks(body), "body": body.decode("latin-1"),
                "forks": sum(1 for e in ev if e["event"] == "fork_ok"),
                "route": "-" if direct else (routes[-1] if routes else "-"),
                "attacker_log": len(log_since(ALOG, a0))})
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
    return actual

def check(key, want, act, actual_steps):
    """(통과 여부, 실제 값 표시)"""
    if key == "body_contains":
        return want in act["body"], ("포함" if want in act["body"] else "없음")
    if key == "body_not_contains":
        return want not in act["body"], ("없음" if want not in act["body"] else "포함")
    if key == "same_as_step":
        ref = actual_steps[want - 1]
        same = (ref["status"], ref["body"]) == (act["status"], act["body"])
        return same, f"{act['status']} {act['body'][:30]!r}" + ("" if same else f" ≠ {want}단계 {ref['status']} {ref['body'][:30]!r}")
    val = act[key]
    if isinstance(want, str) and want[:1] in "<>=" and key != "body":
        op = want[:2] if want[1:2] == "=" else want[:1]
        num = float(want[len(op):])
        ok = isinstance(val, (int, float)) and {"<": val < num, ">": val > num, "<=": val <= num,
                                                ">=": val >= num, "==": val == num}[op]
        return ok, val
    return val == want, (val[:40] if key == "body" else val)

def judge(case, mode, actual):
    """단계별 expect와 최종 expect를 대조. [(단계 번호, 키, 기대, 실제, 통과)]"""
    rows = []
    for i, step in enumerate(case["steps"], 1):
        exp = (step.get("expect") or {}).get(mode)
        if exp:
            for k, w in exp.items():
                ok, shown = check(k, w, actual[i - 1], actual)
                rows.append((i, k, w, shown, ok))
    last = len(case["steps"])
    for k, w in (case.get("expect") or {}).get(mode, {}).items():
        ok, shown = check(k, w, actual[last - 1], actual)
        rows.append((last, k, w, shown, ok))
    return rows

def load_cases(file_arg, case_arg):
    files = [os.path.join(CASE_DIR, file_arg)] if file_arg else sorted(glob.glob(os.path.join(CASE_DIR, "*.json")))
    out = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            for c in json.load(f)["cases"]:
                if case_arg and c["id"] != case_arg:
                    continue
                exps = [c.get("expect") or {}] + [s.get("expect") or {} for s in c["steps"]]
                unknown = [k for e in exps for m in e.values() for k in m if k not in KEYS]
                if unknown:
                    raise ValueError(f"{c['id']}: 모르는 expect 키 {unknown}")
                out.append((os.path.basename(path), c))
    if not out:
        raise ValueError("실행할 사례가 없음 (--file/--case 확인)")
    return out

def fmt(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)

def main():
    ap = argparse.ArgumentParser(description="13주차 추가 사례 실행기")
    ap.add_argument("--file", help="demo/extra_cases/ 안의 파일 이름 (예: proxy.json)")
    ap.add_argument("--case", help="사례 id (예: C1-negative-length)")
    a = ap.parse_args()
    cases = load_cases(a.file, a.case)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    os.makedirs(os.path.dirname(DLOG), exist_ok=True)

    lines = ["# 추가 사례 실행 결과 (13주차 반례 탐색)", "",
             f"명령: `python3 demo/run_extra.py" + (f" --file {a.file}" if a.file else "") + (f" --case {a.case}" if a.case else "") + "`", "",
             "| 사례 | 담당 | 모드 | 단계 | 항목 | 기대(실행 전) | 실제 | 판정 |", "|---|---|---|---|---|---|---|---|"]
    fails, summary = [], []
    for fname, case in cases:
        for mode in case["modes"]:
            print(f"[run] {case['id']} / {mode} ...", flush=True)
            actual = run_steps(case, mode)
            rows = judge(case, mode, actual)
            ok_all = all(r[4] for r in rows)
            summary.append((case["id"], mode, ok_all))
            for step_no, k, w, shown, ok in rows:
                lines.append(f"| {case['id']} | {case['owner']} | {mode} | {step_no} | {k} | {fmt(w)} | {fmt(shown)} | {'PASS' if ok else '**FAIL**'} |")
            if not ok_all:
                fails.append((fname, case, mode, [r for r in rows if not r[4]], actual))

    lines += ["", "## 요약", "", "| 사례 | 모드 | 판정 |", "|---|---|---|"]
    lines += [f"| {cid} | {m} | {'PASS' if ok else '**FAIL**'} |" for cid, m, ok in summary]
    n_ok = sum(1 for *_, ok in summary if ok)
    lines += ["", f"**{n_ok}/{len(summary)} 통과** (사례×모드 기준)", "", "## 반례 후보 (FAIL)", ""]
    if not fails:
        lines.append("없음")
    for fname, case, mode, bad, actual in fails:
        lines.append(f"### {case['id']} / {mode}  ({fname}, 담당 {case['owner']}, {case['direction']})")
        lines.append(f"- 설명: {case['description']}")
        for step_no, k, w, shown, _ in bad:
            lines.append(f"- {step_no}단계 `{k}`: 기대 {fmt(w)} / 실제 {fmt(shown)}")
        last = actual[-1]
        lines.append(f"- 마지막 단계 응답: status {last['status']}, {last['len']}바이트, 비밀 {last['leaks']}건, "
                     f"route {last['route']}, attacker.jsonl 기록 {last['attacker_log']}건, 본문 앞부분 `{last['body'][:50]!r}`")
        lines.append("")
    report = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as e:
        print("실행 실패:", e)
        sys.exit(1)
