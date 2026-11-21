"""수동 요청용 CLI.  예) python demo/client.py --session attacker-1 --payload hi --length 64"""
import argparse, json, os, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from honeypatch import config

def send(session, payload, length, port=None):
    port = port or config.PROXY_PORT
    body = json.dumps({"payload": payload, "length": length}).encode()
    req = urllib.request.Request(f"http://{config.HOST}:{port}/heartbeat", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Session-Id": session})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="user-cli")
    ap.add_argument("--payload", default="hello")
    ap.add_argument("--length", type=int, default=5)
    a = ap.parse_args()
    st, body = send(a.session, a.payload, a.length)
    print(f"status={st} len={len(body)} body={body!r}")
