"""요청 줄(request target)을 바꿔 보낼 때 프록시 응답이 기준 응답과 같은지 본다 (반례 C9).
서버는 미리 띄워 둔다 (타깃 9000, 프록시 8080).

urllib 은 절대 URI 를 요청 줄에 그대로 실어 보내지 못하므로 소켓으로 직접 쓴다.

판정 기준은 둘로 나뉜다. 공격자는 프록시(8080)만 두드리므로, 어느 쪽이든 "앞에
프록시가 있다"는 사실이 응답 차이로 드러나면 안 된다는 목적은 같다.

1. 보통 경로는 같은 요청을 타깃에 직접 보낸 응답과 같아야 한다. 프록시가 요청 줄을
   고쳐서 보내면 여기서 어긋난다. C9 가 잡는 지점이다.
2. 내부 제어 경로(`/__`)는 오히려 타깃 직접과 같으면 안 된다. 타깃은 `/__health` 에
   미끼인지 아닌지를 그대로 답하는데(반례 C2), 프록시는 PR #20 에서 이 경로를 막기로
   했다. 그래서 기준을 타깃 직접이 아니라 "없는 경로(`/nope`)에 프록시가 주는 404"로
   잡는다. 공격자가 실제로 맞대어 볼 수 있는 것이 그 둘이고, 구분이 안 되면 프록시는
   그냥 그런 경로가 없는 서버로 보인다. `/nope` 자체는 1번 기준으로 따로 재므로,
   2번이 통과하면 내부 경로 = 프록시의 없는 경로 = 타깃의 없는 경로 로 이어진다.

내부 경로는 `forward()` 에 닿기 전에 막히므로 C9 의 원인(요청 줄 재해석)이 거기까지
가지 않는다. 2번 기준이 C9 를 가려 주지는 않는다.
"""
import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from honeypatch import config  # noqa: E402

HB = b'{"payload":"hi","length":2}'
ABSENT = "GET /nope HTTP/1.1"          # 내부 경로의 기준이 되는 "없는 경로"


def raw(port, request_line, body=b""):
    """요청 줄을 글자 그대로 보내고 status 와 본문을 돌려준다."""
    head = (f"{request_line}\r\n"
            f"Host: {config.HOST}:{port}\r\n"
            f"X-Session-Id: c9-parity\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n").encode()
    s = socket.create_connection((config.HOST, port), timeout=5)
    try:
        s.sendall(head + body)
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        return "시간 초과", b""
    finally:
        s.close()
    if not buf:
        return "응답 없음(연결 끊김)", b""
    head_bytes, _, body_bytes = buf.partition(b"\r\n\r\n")
    status = head_bytes.decode("latin-1").split("\r\n")[0].replace("HTTP/1.0 ", "")
    return status, body_bytes


def internal(request_line):
    """프록시가 내부 제어 경로로 보고 막는 요청인지 본다.

    proxy.py 의 차단 조건(`self.path.startswith("/__")`)과, 그 앞에서
    `BaseHTTPRequestHandler.parse_request` 가 앞의 `//` 를 `/` 하나로 줄이는
    처리(CPython `http/server.py`)를 그대로 따라 쓴다."""
    path = request_line.split(" ")[1]
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    return path.startswith("/__")


CASES = [
    ("절대 URI (미끼 포트)", f'GET http://{config.HOST}:{config.DECOY_PORTS[0]}/__health HTTP/1.1', b""),
    ("절대 URI (타깃 포트)", f'GET http://{config.HOST}:{config.TARGET_PORT}/__health HTTP/1.1', b""),
    ("절대 URI (외부 호스트)", 'GET http://example.com/ HTTP/1.1', b""),
    ("조각(#) 붙은 경로", 'POST /heartbeat#x HTTP/1.1', HB),
    ("조각(#) 붙은 내부 경로", 'GET /__health#x HTTP/1.1', b""),
    ("경로가 / 로 시작하지 않음", 'GET nope HTTP/1.1', b""),
    ("질의문(?) 붙은 경로", 'POST /heartbeat?a=1 HTTP/1.1', HB),
    ("점 경로", 'GET /files/../__health HTTP/1.1', b""),
    ("슬래시 두 개", 'GET //__health HTTP/1.1', b""),
    ("퍼센트 인코딩", 'GET /%5f%5fhealth HTTP/1.1', b""),
    ("대문자 경로", 'GET /__HEALTH HTTP/1.1', b""),
    ("없는 경로 (대조군)", 'GET /nope HTTP/1.1', b""),
    ("정상 heartbeat (대조군)", 'POST /heartbeat HTTP/1.1', HB),
]

print(f"{'사례':<24} {'기준':<10} {'프록시(8080)':<34} {'기준 응답':<34} 판정")
print("-" * 118)
absent = raw(config.PROXY_PORT, ABSENT)
broke = 0
for label, line, body in CASES:
    got = raw(config.PROXY_PORT, line, body)
    if internal(line):
        kind, want = "없는 경로", absent
    else:
        kind, want = "타깃 직접", raw(config.TARGET_PORT, line, body)
    same = got == want
    if not same:
        broke += 1
    p = f"{got[0]} {got[1][:18]!r}"
    w = f"{want[0]} {want[1][:18]!r}"
    print(f"{label:<24} {kind:<10} {p:<34} {w:<34} {'같음' if same else '다름'}")

print()
print(f"{len(CASES)}건 중 {broke}건이 기준과 다름")
print("[PASS] 모든 요청 줄에서 프록시 응답이 기준과 같다" if broke == 0
      else "[FAIL] 프록시 응답이 기준과 다른 사례가 있다")
sys.exit(0 if broke == 0 else 1)
