"""
game_state/state.py — مخزن البيانات Thread-Safe في الذاكرة
════════════════════════════════════════════════════════════
• يخزن كل بيانات اللعبة في RAM مباشرة (بدون قراءة ملف)
• جميع العمليات محمية بـ RLock لضمان التزامن الكامل
• يوفر دوال استعلام جاهزة وسريعة جداً (<0.1ms)
• يُحدّث الحالة المنظّمة (Hero, March, ...) تلقائياً
"""
import threading
import time
from typing import List, Dict, Optional, Set, Any
from .models import Hero, March, Resources, Player


class GameState:
    """
    مخزن البيانات المركزي — خيط آمن (Thread-Safe).
    يُستخدم مباشرة من daemon.py لتحديث البيانات،
    ومن __init__.py لاستعلام البيانات.
    """

    def __init__(self):
        self._lock = threading.RLock()  # RLock يسمح بالتداخل من نفس الخيط

        # البيانات الخام من السيرفر
        self._raw: Dict[str, Any] = {}

        # البيانات المنظّمة (تُبنى تلقائياً)
        self._heroes: Dict[int, Hero] = {}        # id → Hero
        self._marches: Dict[int, March] = {}      # team_id → March
        self._player: Player = Player()
        self._busy_hero_ids: Set[int] = set()

        # إحصائيات
        self.pkt_count: int = 0
        self.last_update: float = 0.0
        self.connected: bool = False
        self.init_done: bool = False

    # ══════════════════════════════════
    #  دوال التحديث (يستدعيها daemon فقط)
    # ══════════════════════════════════

    def set_raw(self, key: str, value: Any) -> None:
        """تخزين قيمة خام وتحديث النماذج المنظّمة"""
        with self._lock:
            self._raw[key] = value
            self.last_update = time.time()

    def process_init_data(self, data: dict) -> None:
        """معالجة حزمة تسجيل الدخول (cmd=1000)"""
        with self._lock:
            for k, v in data.items():
                self._raw[f'_init_{k}'] = v

            # heroCtrl — قائمة الأبطال
            hero_ctrl = None
            if 'heroCtrl' in data and isinstance(data['heroCtrl'], list):
                hero_ctrl = data['heroCtrl']
            elif 'retdata' in data and isinstance(data['retdata'], dict):
                hero_ctrl = data['retdata'].get('heroCtrl')

            if hero_ctrl:
                self._raw['heroCtrl'] = hero_ctrl
                self._rebuild_heroes(hero_ctrl)

            # بيانات اللاعب
            lord = data.get('lordInfo') or data.get('retdata', {}).get('lordInfo', {})
            if isinstance(lord, dict):
                self._player.uid = lord.get('uid', self._player.uid)
                self._player.name = lord.get('name', self._player.name)
                self._player.level = lord.get('level', lord.get('lv', self._player.level))
                self._player.castle_lv = lord.get('castleLv', self._player.castle_lv)
                self._player.power = lord.get('totalFc', lord.get('power', self._player.power))
                self._player.kingdom_id = lord.get('mapId', lord.get('kingdomId', self._player.kingdom_id))
                self._player.x = lord.get('x', self._player.x)
                self._player.y = lord.get('y', self._player.y)

            self.init_done = True

    def process_notify(self, notify_id: str, notify_data: Any) -> None:
        """معالجة إشعارات السيرفر (cmd=1009)"""
        with self._lock:
            self._raw[notify_id] = notify_data

            if notify_id == 'NOTIFY_LOCAL_QUEUE_SYNC':
                self._update_busy_heroes_from_queues(notify_data)

            elif notify_id == 'NOTIFY_HERO':
                self._update_heroes_from_notify(notify_data)

            elif notify_id == 'NOTIFY_ARMY':
                # يمكن تحديث معلومات الجيش لاحقاً
                pass

            self.last_update = time.time()

    def process_queue_data(self, subcmd: str, data: dict) -> None:
        """معالجة بيانات المسيرات (cmd=1007)"""
        with self._lock:
            self._raw[f'_queue_{subcmd}'] = data
            if subcmd == '16':  # ALL_QUEUE
                self._rebuild_marches_from_raw(data)
            elif subcmd == '2':  # SEND_MARCH
                new_busy = set()
                self._extract_hero_ids(data, new_busy)
                if new_busy:
                    self._busy_hero_ids.update(new_busy)
                    for hid in new_busy:
                        if hid in self._heroes:
                            self._heroes[hid].state = 1
                            self._heroes[hid].raw.setdefault('status', {})['state'] = 1
            self.last_update = time.time()

    # ══════════════════════════════════
    #  دوال إعادة البناء الداخلية
    # ══════════════════════════════════

    def _rebuild_heroes(self, hero_list: list) -> None:
        """يبني heroes dict من قائمة الأبطال الخام"""
        new_heroes = {}
        for h in hero_list:
            if not isinstance(h, dict): continue
            hid = h.get('id')
            if hid is None: continue
            status = h.get('status', {})
            state = status.get('state', 0) if isinstance(status, dict) else 0
            # حافظ على الحالة الحالية إذا كنا نعرفها من المسيرات
            if hid in self._busy_hero_ids:
                state = 1
            hero = Hero(
                id=hid,
                lv=h.get('lv', 1),
                star=h.get('star', 0),
                stage=h.get('stage', 0),
                state=state,
                exp=h.get('exp', 0),
                raw=h,
            )
            new_heroes[hid] = hero
        self._heroes = new_heroes

    def _update_busy_heroes_from_queues(self, queue_list: Any) -> None:
        """يستخرج الأبطال المشغولين من NOTIFY_LOCAL_QUEUE_SYNC ويحدّث حالتهم"""
        busy = set()
        if isinstance(queue_list, list):
            for q in queue_list:
                if isinstance(q, dict):
                    self._extract_hero_ids(q, busy)

        old_busy = self._busy_hero_ids
        self._busy_hero_ids = busy

        # تحديث حالة كل بطل
        for hid, hero in self._heroes.items():
            new_state = 1 if hid in busy else 0
            if hero.state != new_state:
                hero.state = new_state
                hero.raw.setdefault('status', {})['state'] = new_state

        # تحديث المسيرات من قائمة الانتظار
        self._rebuild_marches_from_notify(queue_list)

    def _extract_hero_ids(self, q: dict, out: Set[int]) -> None:
        """يستخرج أرقام الأبطال من كل أشكال حزمة المسيرة"""
        if not isinstance(q, dict): return

        qd = q.get('data', {})
        if isinstance(qd, dict):
            # الشكل الأساسي: q.data.from.heros = {uid: [{id: X}]}
            fr = qd.get('from', {})
            if isinstance(fr, dict):
                hm = fr.get('heros', {})
                if isinstance(hm, dict):
                    for uid, hl in hm.items():
                        if isinstance(hl, list):
                            for h in hl:
                                if isinstance(h, dict) and 'id' in h:
                                    out.add(h['id'])

            # الشكل البديل: q.data.heros = [id, ...]
            for x in qd.get('heros', []) or []:
                if isinstance(x, int): out.add(x)
                elif isinstance(x, dict) and 'id' in x: out.add(x['id'])

        # الشكل المباشر: q.heros = [id, ...]
        for x in q.get('heros', []) or []:
            if isinstance(x, int): out.add(x)
            elif isinstance(x, dict) and 'id' in x: out.add(x['id'])

    def _rebuild_marches_from_notify(self, queue_list: Any) -> None:
        """يبني قاموس المسيرات من NOTIFY_LOCAL_QUEUE_SYNC"""
        if not isinstance(queue_list, list): return
        new_marches = {}
        for q in queue_list:
            if not isinstance(q, dict): continue
            qd = q.get('data', {})
            if not isinstance(qd, dict): continue

            team_id = q.get('teamId') or qd.get('teamId')
            if team_id is None: continue

            hero_ids: Set[int] = set()
            self._extract_hero_ids(q, hero_ids)

            to = qd.get('to', {})
            march = March(
                team_id=team_id,
                queue_type=qd.get('queueType', 0),
                status=qd.get('status', 1),
                start_time=qd.get('startTime', 0),
                end_time=qd.get('endTime', qd.get('statusEndTime', 0)),
                hero_ids=list(hero_ids),
                to_x=to.get('x', 0) if isinstance(to, dict) else 0,
                to_y=to.get('y', 0) if isinstance(to, dict) else 0,
                to_type=to.get('type', 0) if isinstance(to, dict) else 0,
                raw=q,
            )
            new_marches[team_id] = march
        self._marches = new_marches

    def _rebuild_marches_from_raw(self, data: dict) -> None:
        """يبني المسيرات من رد cmd=1007/16"""
        if not isinstance(data, dict): return
        queue_list = data.get('list') or data.get('data') or data.get('queues', [])
        if isinstance(queue_list, list):
            self._rebuild_marches_from_notify(queue_list)

    def _update_heroes_from_notify(self, notify_data: Any) -> None:
        """تحديث بيانات الأبطال من NOTIFY_HERO"""
        if not isinstance(notify_data, list): return
        for item in notify_data:
            if not isinstance(item, dict): continue
            hid = item.get('id') or item.get('heroId')
            if hid and hid in self._heroes:
                hero = self._heroes[hid]
                hero.lv = item.get('lv', hero.lv)
                hero.star = item.get('star', hero.star)
                hero.exp = item.get('exp', hero.exp)
                hero.raw.update(item)
                # لا نغيّر state من NOTIFY_HERO — فقط من NOTIFY_LOCAL_QUEUE_SYNC

    # ══════════════════════════════════
    #  دوال الاستعلام (يستخدمها البوت)
    # ══════════════════════════════════

    def get_hero(self, hero_id: int) -> Optional[Hero]:
        """جلب بطل واحد بـ ID — أسرع من 0.01ms"""
        with self._lock:
            return self._heroes.get(hero_id)

    def get_all_heroes(self) -> List[Hero]:
        """جلب قائمة جميع الأبطال"""
        with self._lock:
            return list(self._heroes.values())

    def get_idle_heroes(self) -> List[Hero]:
        """جلب الأبطال المتاحين فقط (state=0)"""
        with self._lock:
            return [h for h in self._heroes.values() if h.is_available]

    def get_busy_heroes(self) -> List[Hero]:
        """جلب الأبطال المشغولين فقط (state=1)"""
        with self._lock:
            return [h for h in self._heroes.values() if h.is_busy]

    def is_hero_available(self, hero_id: int) -> bool:
        """هل البطل متاح حالياً؟"""
        with self._lock:
            h = self._heroes.get(hero_id)
            return h.is_available if h else False

    def get_active_marches(self) -> List[March]:
        """جلب المسيرات النشطة حالياً"""
        with self._lock:
            return [m for m in self._marches.values() if m.is_active]

    def get_march(self, team_id: int) -> Optional[March]:
        """جلب مسيرة واحدة بـ team_id"""
        with self._lock:
            return self._marches.get(team_id)

    def get_player(self) -> Player:
        """جلب معلومات اللاعب"""
        with self._lock:
            return self._player

    def get_raw(self, key: str, default=None) -> Any:
        """جلب قيمة خام بمفتاحها"""
        with self._lock:
            return self._raw.get(key, default)

    def get_raw_snapshot(self) -> dict:
        """نسخة كاملة من البيانات الخام (للحفظ في ملف)"""
        with self._lock:
            # ضمان وجود heroCtrl المحدّث في الخام وفي _init_retdata
            if self._heroes:
                updated_raw_list = [h.raw for h in self._heroes.values()]
                self._raw['heroCtrl'] = updated_raw_list
                if '_init_retdata' in self._raw and isinstance(self._raw['_init_retdata'], dict):
                    self._raw['_init_retdata']['heroCtrl'] = updated_raw_list
            return dict(self._raw)

    def get_summary(self) -> dict:
        """ملخص سريع للحالة الحالية"""
        with self._lock:
            idle = sum(1 for h in self._heroes.values() if h.is_available)
            busy = sum(1 for h in self._heroes.values() if h.is_busy)
            return {
                'connected': self.connected,
                'init_done': self.init_done,
                'heroes_total': len(self._heroes),
                'heroes_idle': idle,
                'heroes_busy': busy,
                'active_marches': len([m for m in self._marches.values() if m.is_active]),
                'raw_keys': len(self._raw),
                'packets': self.pkt_count,
                'last_update': self.last_update,
            }
