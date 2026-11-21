"""메모리 redaction (원논문 4.1절 대응).
같은 길이·같은 형식의 가짜 값으로 바꾸고, 모든 글자가 원래 값과 다르게 만든다."""
import random, string

HEX = "0123456789abcdef"

def _diff_char(c, pool):
    return random.choice([x for x in pool if x != c])

def fake_like(value):
    """hex 문자는 hex로, 알파벳은 알파벳으로 (형식 유지), 글자마다 원본과 다르게."""
    out = []
    for c in value:
        if c in HEX:
            out.append(_diff_char(c, HEX))
        elif c.isalpha():
            out.append(_diff_char(c, string.ascii_lowercase))
        else:
            out.append(c)
    return "".join(out)

def fake_ip(ip):
    """같은 길이·같은 점 위치의 유효한 IP, 숫자 자리는 모두 원래와 다르게."""
    for _ in range(5000):
        octs = []
        for o in ip.split("."):
            n = len(o)
            lo, hi = (0, 9) if n == 1 else ((10, 99) if n == 2 else (100, 255))
            octs.append(str(random.randint(lo, hi)))
        cand = ".".join(octs)
        if len(cand) == len(ip) and all(a != b for a, b in zip(cand, ip) if a != "."):
            return cand
    raise RuntimeError("fake_ip 생성 실패: " + ip)

def redact_sessions(sessions, keep_sid):
    """공격자(keep_sid)를 제외한 모든 세션의 비밀을 가짜 값으로 치환."""
    out = []
    for s in sessions:
        if s["sid"] == keep_sid:
            out.append(dict(s))
            continue
        out.append({"sid": s["sid"], "token": fake_like(s["token"]),
                    "user": fake_like(s["user"]), "ip": fake_ip(s["ip"])})
    return out
