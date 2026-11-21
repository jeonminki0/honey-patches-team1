"""허니패치 라이브러리 (원논문 3절 hp_init / hp_fork / hp_skip 대응).
원논문: CRIU로 프로세스 전체를 체크포인트·복원.
축소판: 세션 상태(JSON)만 직렬화 → redaction → 프록시에 fork 요청."""
import json
import urllib.request
from . import config
from .redact import redact_sessions

CONTEXT = "target"          # "target" 또는 "decoy"
_get_state = None           # 서버가 등록하는 '현재 상태 꺼내기' 함수

def hp_init(context, state_getter):
    global CONTEXT, _get_state
    CONTEXT, _get_state = context, state_getter

def hp_fork(session_id):
    """Listing 3 대응. 미끼 안에서는 아무것도 안 함(False 반환).
    타깃에서는 체크포인트+redaction 후 프록시에 fork 요청. 성공 True / 실패 False."""
    if CONTEXT == "decoy":
        return False
    state = _get_state()
    state["sessions"] = redact_sessions(state["sessions"], keep_sid=session_id)  # 비밀 제거
    body = json.dumps({"session": session_id, "state": state}).encode()
    req = urllib.request.Request(
        f"http://{config.HOST}:{config.PROXY_PORT}/__hp/fork", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False        # 미끼 풀 고갈 등 → fork 실패

def hp_skip(block):
    """미끼에서는 block(거부 동작)을 건너뛰고 None, 타깃에서는 block을 실행해 결과 반환."""
    if CONTEXT == "decoy":
        return None
    return block()
