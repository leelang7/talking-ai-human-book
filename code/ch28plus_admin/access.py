# -*- coding: utf-8 -*-
"""
Ch28+ §5 — 차단은 해제와 같은 문으로

*"차단만 있고 해제가 없는 콘솔은 반드시 사고가 난다."* 본문의 처방이다.
콘솔의 `/api/admin/block_ip` 가 이 파일의 `decide()` 를 부른다.

판단을 순수 함수로 뺀 이유 — **차단 규칙은 테스트할 수 있어야 한다.**
서버를 띄우지 않고도 "해제가 차단과 같은 코드를 지나가는가" 를 확인한다.
"""
import ipaddress

BLOCK, UNBLOCK, NOOP, REJECT = "block", "unblock", "noop", "reject"


def valid_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(str(s).strip())
        return True
    except ValueError:
        return False


def decide(blocked: set, ip: str, unblock: bool = False, dry_run: bool = True) -> dict:
    """차단·해제를 **한 함수** 로. 반환값에 '무엇을 할 것인가' 와 '왜' 가 같이 있다.

    dry_run 이 기본이다(§5). 실제로 바꾸려면 False 를 명시해야 한다.
    """
    ip = str(ip or "").strip()
    if not valid_ip(ip):
        return {"action": REJECT, "ip": ip, "dry_run": dry_run,
                "after": set(blocked), "msg": "IP 형식이 아닙니다"}

    if unblock:
        if ip not in blocked:
            return {"action": NOOP, "ip": ip, "dry_run": dry_run,
                    "after": set(blocked), "msg": "차단 목록에 없습니다"}
        after = set(blocked) - {ip}
        action = UNBLOCK
    else:
        if ip in blocked:
            return {"action": NOOP, "ip": ip, "dry_run": dry_run,
                    "after": set(blocked), "msg": "이미 차단되어 있습니다"}
        after = set(blocked) | {ip}
        action = BLOCK

    msg = (f"미리보기 — {action} {ip}. 실제로 적용하려면 dry_run=false"
           if dry_run else f"{action} {ip} 적용됨")
    return {"action": action, "ip": ip, "dry_run": dry_run,
            "after": after if not dry_run else set(blocked), "msg": msg}
