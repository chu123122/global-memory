"""统一检测器注册表 + Signal 数据类。

每个 check 是一个无参函数，返回 list[Signal]。
runner.py 调度全部 checks 并聚合结果。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

CheckFunc = Callable[[], "list[Signal]"]


@dataclass
class Signal:
    check_id: str
    status: str  # ok | warning | critical | info
    headline: str
    value: str = ""
    evidence: list[str] = field(default_factory=list)
    fix_hint: str = ""
    ts: str = ""

    def to_dict(self) -> dict:
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return asdict(self)


_REGISTRY: dict[str, CheckFunc] = {}


def register(check_id: str):
    def deco(fn: CheckFunc) -> CheckFunc:
        _REGISTRY[check_id] = fn
        return fn

    return deco


def all_checks() -> dict[str, CheckFunc]:
    return dict(_REGISTRY)


def run_check(check_id: str) -> list[Signal]:
    fn = _REGISTRY.get(check_id)
    if fn is None:
        raise KeyError(check_id)
    return fn()
