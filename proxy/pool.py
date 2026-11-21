"""미끼 풀 관리 (원논문 3절 LXC Controller 대응).
proxy.py는 acquire() / release(port)만 호출한다."""
import os, sys, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from honeypatch import config

LOCK = threading.Lock()
AVAILABLE = list(config.DECOY_PORTS)   # 미끼 풀 (사용 가능)

def acquire():
    """사용 가능한 미끼 포트 하나를 꺼낸다. 풀이 비었으면 None."""
    with LOCK:
        return AVAILABLE.pop(0) if AVAILABLE else None

def release(port):
    """사용이 끝난 미끼 포트를 풀에 되돌린다."""
    with LOCK:
        if port not in AVAILABLE:
            AVAILABLE.append(port)
