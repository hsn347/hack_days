"""
game_state/models.py — نماذج البيانات المنظّمة
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import time


@dataclass
class Hero:
    """بطل واحد مع كل بياناته"""
    id: int
    lv: int = 1
    star: int = 0
    stage: int = 0
    state: int = 0          # 0=متاح, 1=مشغول
    exp: int = 0
    raw: Dict = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        return self.state == 0

    @property
    def is_busy(self) -> bool:
        return self.state == 1

    def __repr__(self):
        tag = "🟢 متاح" if self.is_available else "🔴 مشغول"
        return f"Hero(id={self.id}, lv={self.lv}, star={self.star}, {tag})"


@dataclass
class March:
    """مسيرة نشطة"""
    team_id: int
    queue_type: int         # 4=هجوم, 2=بناء, ...
    status: int             # 1=متحرك
    start_time: int
    end_time: int
    hero_ids: List[int] = field(default_factory=list)
    to_x: int = 0
    to_y: int = 0
    to_type: int = 0
    raw: Dict = field(default_factory=dict)

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.end_time - int(time.time()))

    @property
    def is_active(self) -> bool:
        return self.status == 1 and self.remaining_seconds > 0

    def __repr__(self):
        r = self.remaining_seconds
        return f"March(heroes={self.hero_ids}, to=({self.to_x},{self.to_y}), remaining={r}s)"


@dataclass
class Resources:
    """موارد اللاعب الحالية"""
    food: int = 0
    wood: int = 0
    stone: int = 0
    gold: int = 0
    silver: int = 0

    def __repr__(self):
        return f"Resources(food={self.food:,}, wood={self.wood:,}, stone={self.stone:,}, gold={self.gold:,})"


@dataclass
class Player:
    """معلومات اللاعب الأساسية"""
    uid: int = 0
    name: str = ""
    level: int = 0
    castle_lv: int = 0
    power: int = 0
    kingdom_id: int = 0
    x: int = 0
    y: int = 0
    resources: Resources = field(default_factory=Resources)

    def __repr__(self):
        return f"Player(uid={self.uid}, name={self.name!r}, lv={self.level}, castle={self.castle_lv})"
