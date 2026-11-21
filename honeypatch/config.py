"""공통 설정: 포트, 시드 사용자(진짜 비밀). 모든 모듈이 이 값을 공유한다."""
PROXY_PORT = 8080
TARGET_PORT = 9000
DECOY_PORTS = [9101, 9102]          # 미끼 풀 크기 = 2
HOST = "127.0.0.1"
DECOY_TIMEOUT = 30                 # 미끼에 고정된 세션이 이 시간(초) 동안 요청이 없으면 release

# 타깃 서버 메모리에 미리 올라가 있는 '다른 사용자'의 비밀 (검증 시 노출 여부 확인용)
SEED_USERS = [
    {"sid": "s-alice", "token": "9f2c4e81a7b3d065", "user": "alice", "ip": "10.0.0.23"},
    {"sid": "s-bob",   "token": "51d8e0c29b7fa364", "user": "bob",   "ip": "172.16.4.150"},
]

def real_secrets():
    out = []
    for u in SEED_USERS:
        out += [u["token"], u["user"], u["ip"]]
    return out
