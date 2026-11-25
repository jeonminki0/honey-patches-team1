"""요청 줄(request target)을 바꿔 보낼 때 프록시 응답이 타깃 직접 응답과 같은지 확인 (반례 C9).
서버는 미리 띄워 둔다 (타깃 9000, 프록시 8080).

urllib 은 절대 URI 를 요청 줄에 그대로 실어 보내지 못하므로 소켓으로 직접 쓴다.
판정 기준은 "프록시를 거친 응답이 같은 요청을 타깃에 직접 보낸 응답과 같다"다.
프록시가 있다는 사실이 응답 차이로 드러나면 안 된다.
"""
import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from honeypatch import config  # noqa: E402

HB = b'{"payload":"hi","length":2}'


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

print(f"{'사례':<24} {'프록시(8080)':<40} {'타깃(9000)':<40} 판정")
print("-" * 118)
broke = 0
for label, line, body in CASES:
    pst, pbody = raw(config.PROXY_PORT, line, body)
    tst, tbody = raw(config.TARGET_PORT, line, body)
    same = (pst, pbody) == (tst, tbody)
    if not same:
        broke += 1
    p = f"{pst} {pbody[:20]!r}"
    t = f"{tst} {tbody[:20]!r}"
    print(f"{label:<24} {p:<40} {t:<40} {'같음' if same else '다름'}")

print()
print(f"{len(CASES)}건 중 {broke}건이 타깃과 다름")
print("[PASS] 프록시 응답이 타깃 직접 응답과 모두 같다" if broke == 0
      else "[FAIL] 프록시 응답이 타깃 직접 응답과 다른 사례가 있다")
sys.exit(0 if broke == 0 else 1)
