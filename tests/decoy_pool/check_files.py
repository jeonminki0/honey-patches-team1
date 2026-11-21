"""미끼 허니파일(GET /files/<이름>) 확인.
확인 내용:
  1. 정상 사용자는 타깃의 data/ 진짜 파일을 받음
  2. fork된 공격자는 미끼의 decoy_template/ 가짜 파일을 받고, 실제 비밀은 0건
  3. 경로 조작(../, %2e%2e, %2f, 역슬래시, //, 숨김 파일, 빈 이름)은 정상 사용자·공격자 모두 404
실행 (저장소 루트에서): python tests/decoy_pool/check_files.py
주의: 포트 8080·9000·9101·9102 가 비어 있어야 함."""
import http.client, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from honeypatch import config
from demo.client import send
from demo.run_demo import wait_up

results = []
TRAVERSAL = ["/files/../honeypatch/config.py", "/files/..%2fhoneypatch%2fconfig.py",
             "/files/%2e%2e/data/users.csv", "/files/../../etc/passwd", "/files//etc/passwd",
             "/files/.gitkeep", "/files/", "/files/nope.txt", "/files/..\\data\\users.csv"]

def check(name, ok):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

def py(*args):
    return subprocess.Popen([sys.executable, *args], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get(path, sid):
    """http.client 는 경로를 정규화하지 않고 그대로 보냄 (경로 조작 시험용)."""
    c = http.client.HTTPConnection(config.HOST, config.PROXY_PORT, timeout=5)
    c.request("GET", path, headers={"X-Session-Id": sid})
    r = c.getresponse()
    return r.status, r.read()

def real_values():
    """진짜 비밀 = 시드 사용자 값 + data/ 파일의 모든 값."""
    out = set(config.real_secrets())
    with open(os.path.join(ROOT, "data", "config.txt"), encoding="utf-8") as f:
        out |= {l.split("=", 1)[1].strip() for l in f if "=" in l}
    with open(os.path.join(ROOT, "data", "users.csv"), encoding="utf-8") as f:
        out |= {v.strip() for l in list(f)[1:] for v in l.split(",")}
    return [v.encode() for v in out if v]

def main():
    secrets = real_values()
    procs = [py("server/app.py", "--mode", "honeypatched", "--role", "target", "--port", str(config.TARGET_PORT)),
             py("proxy/proxy.py")]
    try:
        for p in [config.TARGET_PORT, *config.DECOY_PORTS, config.PROXY_PORT]:
            wait_up(p)
        with open(os.path.join(ROOT, "data", "users.csv"), "rb") as f:
            real_csv = f.read()
        st, b = get("/files/users.csv", "user-normal")
        print("정상 사용자 users.csv:", st, b.splitlines()[1])
        check("정상 사용자는 data/ 진짜 파일", st == 200 and b == real_csv)

        send("attacker-1", "hi", 64)        # fork → 미끼 고정
        for name in ["users.csv", "config.txt"]:
            with open(os.path.join(ROOT, "decoy_template", name), "rb") as f:
                fake = f.read()
            st, b = get("/files/" + name, "attacker-1")
            n = sum(s in b for s in secrets)
            print(f"공격자(미끼) {name}: {st}, 실제 비밀 {n}건")
            check(f"공격자는 decoy_template/{name} 가짜 파일, 실제 비밀 0건", st == 200 and b == fake and n == 0)

        for sid in ["user-normal", "attacker-1"]:
            bad = []
            for path in TRAVERSAL:
                st, b = get(path, sid)
                print(f"  {sid:11s} {path:36s} -> {st} {b[:20]!r}")
                if st != 404:
                    bad.append(path)
            check(f"{sid}: 경로 조작 {len(TRAVERSAL)}종 모두 404", not bad)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
    print(f"\n{sum(results)}/{len(results)} 통과")
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
