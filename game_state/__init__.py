"""
game_state/__init__.py — الواجهة العامة للوسيط
════════════════════════════════════════════════
الاستخدام في البوت:
    from game_state import game, start_sync, wait_ready

    # تشغيل الوسيط في الخلفية
    start_sync()
    wait_ready()

    # استعلام مباشر وسريع
    heroes = game.get_idle_heroes()
    if game.is_hero_available(5502002):
        print("البطل جاهز!")

    for march in game.get_active_marches():
        print(march)
"""

import time
import os
import json
import threading
from typing import List, Optional

from .state import GameState
from .daemon import GameDaemon
from .models import Hero, March, Player, Resources

# ─── الكائن المركزي (Singleton) ───
_state  = GameState()
_daemon: Optional[GameDaemon] = None
_lock   = threading.Lock()
_save_timer: Optional[threading.Timer] = None

# المسار الافتراضي لملف JSON
_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game_data_captured.json")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  دوال التهيئة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def start_sync(verbose: bool = False, background: bool = True, tap_timeout: int = 60) -> bool:
    """
    يشغّل الوسيط ويبدأ المزامنة اللحظية.

    Args:
        verbose:     طباعة تفاصيل الحزم
        background:  تشغيل في خيط خلفية (True) أو الانتظار حتى اكتشاف الجلسة (False)
        tap_timeout: ثوانٍ الانتظار حتى يضغط المستخدم على الشاشة

    Returns:
        True إذا نجح الاتصال، False إذا فشل
    """
    global _daemon

    with _lock:
        if _daemon is not None:
            return True  # الوسيط شغّال بالفعل

        _daemon = GameDaemon(_state, verbose=verbose)

    # تفعيل الحفظ التلقائي لملف JSON
    _schedule_save()

    if background:
        _daemon.start_background(tap_timeout=tap_timeout)
        return True
    else:
        return _daemon.start(tap_timeout=tap_timeout)


def wait_ready(timeout: float = 120) -> bool:
    """
    ينتظر حتى يكتمل الجلب الأولي للبيانات.

    Args:
        timeout: أقصى وقت انتظار بالثوانٍ

    Returns:
        True إذا جهزت البيانات، False إذا انتهت المهلة
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _state.init_done:
            return True
        time.sleep(0.5)
    return False


def stop_sync():
    """إيقاف الوسيط"""
    global _daemon
    if _daemon:
        _daemon.stop()
        _daemon = None
    _force_save()


def is_running() -> bool:
    """هل الوسيط يعمل حالياً؟"""
    return _daemon is not None and _state.connected


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  كائن الاستعلام الرئيسي (game)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _GameAPI:
    """
    الواجهة التي يستخدمها البوت — دوال نظيفة وسريعة.
    جميع الدوال آمنة للاستخدام من أي خيط في أي وقت.
    """

    # ── الأبطال ──

    def get_hero(self, hero_id: int) -> Optional[Hero]:
        """جلب بطل واحد بـ ID"""
        return _state.get_hero(hero_id)

    def get_all_heroes(self) -> List[Hero]:
        """جلب جميع الأبطال"""
        return _state.get_all_heroes()

    def get_idle_heroes(self) -> List[Hero]:
        """جلب الأبطال المتاحين (غير المشغولين)"""
        return _state.get_idle_heroes()

    def get_busy_heroes(self) -> List[Hero]:
        """جلب الأبطال المشغولين في مسيرات"""
        return _state.get_busy_heroes()

    def is_hero_available(self, hero_id: int) -> bool:
        """هل البطل متاح للاستخدام؟"""
        return _state.is_hero_available(hero_id)

    def get_best_idle_hero(self) -> Optional[Hero]:
        """جلب أفضل بطل متاح (الأعلى مستوى)"""
        idle = _state.get_idle_heroes()
        if not idle: return None
        return max(idle, key=lambda h: (h.lv, h.star))

    # ── المسيرات ──

    def get_active_marches(self) -> List[March]:
        """جلب المسيرات النشطة حالياً"""
        return _state.get_active_marches()

    def get_march(self, team_id: int) -> Optional[March]:
        """جلب مسيرة واحدة بـ team_id"""
        return _state.get_march(team_id)

    def has_available_march_slot(self) -> bool:
        """هل يوجد فتحة مسيرة متاحة؟ (مسيرات أقل من الحد الأقصى)"""
        return len(self.get_active_marches()) < self._get_max_marches()

    def _get_max_marches(self) -> int:
        """يحاول قراءة الحد الأقصى للمسيرات من البيانات"""
        # الحد الافتراضي = 1، يمكن تطويره لاحقاً
        return _state.get_raw('_march_slots', 1)

    # ── اللاعب ──

    def get_player(self) -> Player:
        """جلب معلومات اللاعب الكاملة"""
        return _state.get_player()

    @property
    def uid(self) -> int:
        return _state.get_player().uid

    @property
    def name(self) -> str:
        return _state.get_player().name

    @property
    def level(self) -> int:
        return _state.get_player().level

    # ── بيانات خام ──

    def get_raw(self, key: str, default=None):
        """جلب أي بيانات خام من السيرفر بالمفتاح"""
        return _state.get_raw(key, default)

    def get_notify(self, notify_id: str, default=None):
        """جلب بيانات إشعار محدد"""
        return _state.get_raw(notify_id, default)

    # ── إحصائيات ──

    def get_summary(self) -> dict:
        """ملخص حالة الوسيط"""
        return _state.get_summary()

    def print_status(self):
        """طباعة حالة الوسيط بشكل مقروء"""
        s = _state.get_summary()
        print("┌─────────────────────────────────────┐")
        print("│        Game State Middleware         │")
        print("├─────────────────────────────────────┤")
        print(f"│ الاتصال:   {'✅ متصل' if s['connected'] else '❌ غير متصل':<28} │")
        print(f"│ البيانات:  {'✅ جاهزة' if s['init_done'] else '⏳ جارٍ الجلب':<28} │")
        print(f"│ الأبطال:   متاح={s['heroes_idle']} / مشغول={s['heroes_busy']} / الكل={s['heroes_total']:<5} │")
        print(f"│ المسيرات:  {s['active_marches']} نشطة{'':<30}│")
        print(f"│ الحزم:     {s['packets']:<33}│")
        print(f"│ المفاتيح:  {s['raw_keys']:<33}│")
        print("└─────────────────────────────────────┘")

    def print_heroes(self):
        """طباعة جدول الأبطال"""
        heroes = _state.get_all_heroes()
        if not heroes:
            print("[game] لا يوجد أبطال في البيانات بعد.")
            return
        print(f"\n{'ID':<12} {'LV':<5} {'★':<4} {'الحالة'}")
        print("─" * 38)
        for h in sorted(heroes, key=lambda x: x.lv, reverse=True):
            tag = "🟢 متاح " if h.is_available else "🔴 مشغول"
            print(f"{h.id:<12} {h.lv:<5} {h.star:<4} {tag}")


# ─── الكائن الجاهز للاستخدام في البوت ───
game = _GameAPI()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  حفظ تلقائي لملف JSON (Debounced)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _schedule_save():
    """يجدول حفظ الملف كل ثانية (استجابة سريعة)"""
    global _save_timer
    _save_timer = threading.Timer(1.0, _periodic_save)
    _save_timer.daemon = True
    _save_timer.start()

def _periodic_save():
    """يحفظ الملف ويجدول الدورة القادمة"""
    _force_save()
    if _daemon is not None:
        _schedule_save()

def _force_save():
    """حفظ فوري للملف"""
    if not _state.init_done:
        return
    try:
        snapshot = _state.get_raw_snapshot()
        with open(_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[game_state] خطأ في الحفظ: {e}")
