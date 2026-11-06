# -*- coding: utf-8 -*-
"""
tasks/transport.py — مهمة نقل وإمداد الموارد (Resource Transport / Aid)
════════════════════════════════════════════════════════════════════════

تُرسل فيالق نقل موارد إلى قلعة محددة بالإحداثيات (x, y) حتى امتلاء الطوابير.

معرفات الموارد (Resource IDs):
    1002 : 🌾 قمح (Food)
    1003 : 🪵 خشب (Wood)
    1004 : ⛏️ حديد / حجر (Iron / Stone)
    1005 : 💎 ألماس / ذهب (Diamond / Gold).


python tasks/transport.py --email "azadibrahim63@hotmail.com"


الإعدادات (config / Firebase):
    target_x          : إحداثي X للقلعة الهدف [افتراضي: 487]
    target_y          : إحداثي Y للقلعة الهدف [افتراضي: 290]
    resource_ids      : قائمة الموارد للتبرع بها، مثل [1002] أو [1002, 1003] [افتراضي: [1002]]
    max_capacity      : سعة الحمولة الكلية (يتم اكتشافها تلقائياً من لفل السوق إذا تُركت فارغة)
    tax_rate          : نسبة ضريبة السوق (تُكتشف تلقائياً)
    max_marches       : الحد الأقصى للمسيرات المتتالية [افتراضي: 6]
"""

from __future__ import annotations

import sys
import os

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection



# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_TARGET_X           = 488              # إحداثي X للهدف
DEFAULT_TARGET_Y           = 499              # إحداثي Y للهدف
DEFAULT_RESOURCE_IDS       = [1002,1005,1004]           # [1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس/ذهب]


DEFAULT_MAX_CAPACITY       = 690000           # سعة الحمولة لمبنى السوق بالحد الأقصى (المستوى 30)
DEFAULT_TAX_RATE           = 0.10             # نسبة ضريبة السوق الافتراضية للفل 30 (10%)
DEFAULT_MAX_MARCHES        = 18               # الحد الأقصى للفيالق المتتالية

# أوزان الموارد في نظام اللعبة (Resource Weights)
# 1 قمح = 1 خشب | 1 حديد = 6 قمح | 1 ألماس = 24 قمح
RESOURCE_WEIGHTS = {
    1002: 1,   # 🌾 قمح (Food)
    1003: 1,   # 🪵 خشب (Wood)
    1004: 6,   # ⛏️ حديد / حجر (Iron / Stone)
    1005: 24,  # 💎 ألماس / ذهب (Diamond / Gold)
}

RESOURCE_NAMES = {
    1002: "🌾 قمح",
    1003: "🪵 خشب",
    1004: "⛏️ حديد/حجر",
    1005: "💎 ألماس/ذهب",
}

# ════════════════════════════════════════════════════════════════════
#  ذاكرة التخزين المؤقت للحد اليومي لمساعدة الموارد (Daily Limit Cache)
# ════════════════════════════════════════════════════════════════════
_DAILY_TRANSPORT_LIMIT_CACHE: Dict[str, str] = {}


def _get_utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def is_transport_daily_limit_reached(account_id: str, target_x: int, target_y: int) -> bool:
    """فحص ما إذا كانت القلعة الهدف قد بلغت الحد الأقصى اليومي لاستقبال الموارد اليوم (توقيت UTC الرسمي للعبة)"""
    try:
        key = f"{str(account_id).strip().lower()}:{int(target_x)}:{int(target_y)}"
        return _DAILY_TRANSPORT_LIMIT_CACHE.get(key) == _get_utc_today_str()
    except Exception:
        return False


def set_transport_daily_limit_reached(account_id: str, target_x: int, target_y: int) -> None:
    """تسجيل بلوغ القلعة الهدف للحد الأقصى اليومي لليوم الحالي"""
    try:
        key = f"{str(account_id).strip().lower()}:{int(target_x)}:{int(target_y)}"
        _DAILY_TRANSPORT_LIMIT_CACHE[key] = _get_utc_today_str()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  جدول سعة السوق والضريبة الرسمية من بيانات اللعبة (build112.lua)
# ════════════════════════════════════════════════════════════════════
MARKET_LEVEL_DATA: Dict[int, Tuple[int, float]] = {
    1:  (20000, 0.45),   # ضريبة: 45.0%
    2:  (40000, 0.44),   # ضريبة: 44.0%
    3:  (60000, 0.43),   # ضريبة: 43.0%
    4:  (80000, 0.42),   # ضريبة: 42.0%
    5:  (100000, 0.41),  # ضريبة: 41.0%
    6:  (120000, 0.40),  # ضريبة: 40.0%
    7:  (140000, 0.39),  # ضريبة: 39.0%
    8:  (160000, 0.38),  # ضريبة: 38.0%
    9:  (180000, 0.37),  # ضريبة: 37.0%
    10: (200000, 0.36),  # ضريبة: 36.0%
    11: (220000, 0.35),  # ضريبة: 35.0%
    12: (240000, 0.34),  # ضريبة: 34.0%
    13: (270000, 0.33),  # ضريبة: 33.0%
    14: (290000, 0.32),  # ضريبة: 32.0%
    15: (320000, 0.31),  # ضريبة: 31.0%
    16: (340000, 0.30),  # ضريبة: 30.0%
    17: (370000, 0.29),  # ضريبة: 29.0%
    18: (390000, 0.28),  # ضريبة: 28.0%
    19: (420000, 0.27),  # ضريبة: 27.0%
    20: (440000, 0.26),  # ضريبة: 26.0%
    21: (470000, 0.25),  # ضريبة: 25.0%
    22: (490000, 0.24),  # ضريبة: 24.0%
    23: (520000, 0.23),  # ضريبة: 23.0%
    24: (540000, 0.22),  # ضريبة: 22.0%
    25: (570000, 0.21),  # ضريبة: 21.0%
    26: (590000, 0.19),  # ضريبة: 19.0%
    27: (620000, 0.17),  # ضريبة: 17.0%
    28: (640000, 0.15),  # ضريبة: 15.0%
    29: (670000, 0.13),  # ضريبة: 13.0%
    30: (690000, 0.10),  # ضريبة: 10.0%
}


def get_market_capacity_for_level(level: int) -> Tuple[int, float]:
    """
    استرجاع سعة السوق الأساسية ونسبة الضريبة لمستوى السوق من الجدول الرسمي (1 إلى 30).
    """
    lv = max(1, min(30, int(level)))
    return MARKET_LEVEL_DATA.get(lv, (180000, 0.37))


def get_market_capacity_from_conn(conn: GameConnection) -> Tuple[int, float]:
    """
    استخراج مستوى مبنى السوق (bid=112) تلقائياً من بيانات القلعة واستنتاج السعة والضريبة الأساسية.
    """
    try:
        blist = conn.init_data.get('cityCtrl', {}).get('blist', [])
        for b in blist:
            binfo = b.get('binfo', {})
            if str(binfo.get('bid', '')) == '112':
                return get_market_capacity_for_level(int(binfo.get('lv', 1)))
    except Exception:
        pass

    return DEFAULT_MAX_CAPACITY, DEFAULT_TAX_RATE


async def get_full_market_capacity(conn: GameConnection) -> Tuple[int, float, int, int]:
    """
    حساب سعة حمولة القافلة الإجمالية بدقة 100% كما في كود اللعبة (buildLogic.getMarketWeight):
    1. استخراج مستوى مبنى السوق (bid=112) من cityCtrl.blist.
    2. قراءة السعة الأساسية والضريبة من جدول build112.lua.
    3. جلب علوم التحالف (cmd: 1010, subcmd: 75) واستخراج تقنية قدرة التجارة TRADING_WEIGHT (id: 33002).
    4. السعة الإجمالية = السعة الأساسية + (السعة الأساسية * نسبة علوم التحالف).

    ترجع: (إجمالي_السعة, نسبة_الضريبة, السعة_الأساسية, الزيادة_الإضافية)
    """
    _log = logging.getLogger("task.transport")
    try:
        blist = conn.init_data.get('cityCtrl', {}).get('blist', [])
        market_lv = None
        for b in blist:
            binfo = b.get('binfo', {})
            if str(binfo.get('bid', '')) == '112':
                market_lv = int(binfo.get('lv', 1))
                break

        if market_lv is None:
            market_lv = 9
            _log.warning(f"⚠️ لم يُعثر على مبنى السوق (bid=112) في blist ({len(blist)} مباني) — استخدام لفل افتراضي: {market_lv}")

        base_cap, tax = get_market_capacity_for_level(market_lv)

        # فحص علوم التحالف لتقنية TRADING_WEIGHT (33002) من الذاكرة الحية (Zero-Request)
        sci_bonus_pct = 0.0
        scilist = None
        init_data = getattr(conn, 'init_data', {}) if isinstance(getattr(conn, 'init_data', None), dict) else {}
        for k, v in init_data.items():
            if isinstance(v, dict) and 'sciencelist' in v:
                scilist = v['sciencelist'].get('scilist')
                if scilist:
                    break

        if isinstance(scilist, dict):
            for group in scilist.values():
                if isinstance(group, list):
                    for item in group:
                        if isinstance(item, dict) and item.get('id') == 33002:
                            sci_lv = int(item.get('lv', 0))
                            sci_bonus_pct = sci_lv * 0.01
                            break
        else:
            # خطة احتياطية فقط عند فراغ الذاكرة
            try:
                r_sci = await conn.query('1010', '75', {}, timeout=5)
                if r_sci and 'data' in r_sci:
                    s_data = r_sci['data'].get('retdata', {}).get('scilist', {})
                    if isinstance(s_data, dict):
                        for group in s_data.values():
                            if isinstance(group, list):
                                for item in group:
                                    if isinstance(item, dict) and item.get('id') == 33002:
                                        sci_lv = int(item.get('lv', 0))
                                        sci_bonus_pct = sci_lv * 0.01
                                        break
            except Exception:
                pass

        add_cap = int(base_cap * sci_bonus_pct)
        total_cap = base_cap + add_cap
        return total_cap, tax, base_cap, add_cap

    except Exception as e:
        _log.error(f"❌ فشل حساب سعة السوق بالكامل: {e} — استخدام القيم الافتراضية (لفل 30: {DEFAULT_MAX_CAPACITY:,})")

    return DEFAULT_MAX_CAPACITY, DEFAULT_TAX_RATE, DEFAULT_MAX_CAPACITY, 0


def calculate_resource_allocation(res_ids: List[int], total_capacity: int = DEFAULT_MAX_CAPACITY) -> List[Dict[str, int]]:
    """
    حساب الكميات لكل مورد بناءً على السعة الإجمالية للقافلة وأوزان الموارد.
    (ملاحظة: اللعبة تخصم الضريبة عند الاستلام، بينما ترسل القافلة بكامل سعتها).
    """
    if not res_ids:
        return []

    n = len(res_ids)
    result = []
    for rid in res_ids:
        w = RESOURCE_WEIGHTS.get(int(rid), 1)
        amount = int(total_capacity / (n * w))
        result.append({
            "id": int(rid),
            "num": amount
        })

    return result


def calculate_dynamic_resource_allocation(
    available_dict: Dict[int, int],
    res_ids: List[int],
    total_capacity: int = DEFAULT_MAX_CAPACITY
) -> List[Dict[str, int]]:
    """
    توزيع ديناميكي ذكي بنسبة 100% من سعة السوق على الموارد المتوفرة بالقلعة:
    - يقسم السعة الإجمالية للقافلة على الموارد المتاحة مع مراعاة أوزان الموارد (Food=1, Wood=1, Iron=6, Diamond=24).
    - إذا كان أحد الموارد غير كافٍ، يأخذ المتاح منه ويعيد توزيع المتبقي على بقية الموارد.
    - يستغل 100% من سعة القافلة دون خصم الضريبة من كمية الإرسال (اللعبة تخصم الضريبة من المستلم).
    """
    capacity = float(total_capacity)

    # 1. فلترة الموارد التي لها رصيد متاح > 0
    active_rids = [int(rid) for rid in res_ids if available_dict.get(int(rid), 0) > 0]
    if not active_rids:
        return []

    allocated: Dict[int, int] = {rid: 0 for rid in active_rids}
    remaining_capacity = capacity
    remaining_rids = list(active_rids)

    while remaining_rids and remaining_capacity > 1.0:
        n = len(remaining_rids)
        share_per_res = remaining_capacity / n
        newly_exhausted = []

        for rid in remaining_rids:
            w = float(RESOURCE_WEIGHTS.get(rid, 1))
            max_units_for_share = int(share_per_res / w)
            avail_units = available_dict.get(rid, 0) - allocated[rid]

            if avail_units <= max_units_for_share:
                allocated[rid] += avail_units
                remaining_capacity -= avail_units * w
                newly_exhausted.append(rid)
            else:
                allocated[rid] += max_units_for_share
                remaining_capacity -= max_units_for_share * w

        if not newly_exhausted or newly_exhausted == remaining_rids:
            break
        for rid in newly_exhausted:
            remaining_rids.remove(rid)

    return [{"id": rid, "num": int(allocated[rid])} for rid in active_rids if allocated[rid] > 0]


# ════════════════════════════════════════════════════════════════════
#  دالة جلب معرف القلعة الهدف (Castle ID Lookup)
# ════════════════════════════════════════════════════════════════════

async def get_target_castle_info(conn: GameConnection, tx: int, ty: int, search_range: int = 5) -> Optional[Dict[str, Any]]:
    """
    البحث على الخريطة عن القلعة الموجودة عند الإحداثي (tx, ty) لجلب الـ id والاسم
    """
    try:
        r = await conn.query('2011', '3', {
            "mapType": 4,     # 4 = قلاع اللاعبين (Player Castles)
            "num": 20,
            "x": tx,
            "y": ty,
            "range": search_range
        }, timeout=4)

        if r and 'result' in r:
            results = r['result']
            for obj in results:
                if obj.get('x') == tx and obj.get('y') == ty:
                    return obj

            logger = getattr(conn, 'log', None) or logging.getLogger("transport")
            if results:
                logger.warning(f"⚠️ لم يُعثر على قلعة بالضبط عند ({tx}, {ty}) — النتائج الأقرب: {[(o.get('x'), o.get('y'), o.get('id')) for o in results[:3]]}")
    except Exception as e:
        logger = getattr(conn, 'log', None) or logging.getLogger("transport")
        logger.warning(f"خطأ في استعلام موقع القلعة ({tx}, {ty}): {e}")

    return None


# ════════════════════════════════════════════════════════════════════
#  مهمة نقل الموارد (TransportTask)
# ════════════════════════════════════════════════════════════════════

class TransportTask(BaseTask):
    """
    مهمة إرسال فيالق نقل وتبرع بالموارد للقلعة المحددة.
    """
    name = "transport"

    async def run(self) -> TaskResult:
        cfg              = self.config
        target_x         = int(cfg.get('target_x', DEFAULT_TARGET_X))
        target_y         = int(cfg.get('target_y', DEFAULT_TARGET_Y))
        res_ids          = cfg.get('resource_ids', DEFAULT_RESOURCE_IDS)
        max_marches      = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))

        if not isinstance(res_ids, list):
            res_ids = [res_ids]

        account_id = getattr(self.conn, 'email', '') or str(self.uid)

        # 0. فحص استباقي: هل بلغت القلعة الهدف الحد الأقصى اليومي مسبقاً؟
        if is_transport_daily_limit_reached(account_id, target_x, target_y):
            today_str = _get_utc_today_str()
            self.log.info(f"⏭️ القلعة الهدف عند ({target_x}, {target_y}) بلغت الحد الأقصى اليومي لاستقبال الموارد مسبقاً — تم تخطي النقل لليوم ({today_str}).")
            return TaskResult.ok(
                f"تم تخطي مساعدة الموارد (الهدف بلغ الحد الأقصى اليومي)",
                daily_limit_reached=True,
                sent=0,
                total=0
            )

        res_desc = ", ".join([RESOURCE_NAMES.get(rid, str(rid)) for rid in res_ids])
        self.log.info(f"🚚 بدء مهمة نقل الموارد إلى ({target_x}, {target_y}) | الموارد: [{res_desc}] | الحد الأقصى للمسيرات: {max_marches}")

        # 1. جلب معرف القلعة الهدف (Target Castle ID) أولاً لاستخراج البارتشن بدقة
        self.log.info(f"🔍 جلب بيانات ومعرف القلعة عند ({target_x}, {target_y})...")
        castle_info = await get_target_castle_info(self.conn, target_x, target_y)

        if castle_info and castle_info.get('id'):
            target_id = castle_info['id']
            actual_x  = castle_info.get('x', target_x)
            actual_y  = castle_info.get('y', target_y)
            c_lv      = castle_info.get('level', '?')
            self.log.info(f"🎯 تم العثور على القلعة: ID={target_id} عند ({actual_x}, {actual_y}) لفل={c_lv}")
        else:
            self.log.warning(f"🛑 لم يتم العثور على القلعة الهدف عند ({target_x}, {target_y}) — إنهاء مهمة النقل.")
            return TaskResult.fail(
                f"لم يتم العثور على القلعة الهدف عند ({target_x}, {target_y})",
                data={"sent": 0, "reason": "TARGET_NOT_FOUND"}
            )


        # 2. جلب معرف المملكة (kingdom_id / mapId)
        kingdom_id = 0
        if target_id and '-' in target_id:
            parts = target_id.split('-')
            if len(parts) >= 3 and parts[2].isdigit() and int(parts[2]) > 0:
                kingdom_id = int(parts[2])

        if not kingdom_id:
            if getattr(self.conn, 'kingdom_id', None):
                try: kingdom_id = int(self.conn.kingdom_id)
                except Exception: pass

        if not kingdom_id:
            lord_base = self.conn.init_data.get('lordInfoCtrl', {}).get('base', {}) if hasattr(self.conn, 'init_data') else {}
            if isinstance(lord_base, dict):
                kingdom_id = int(lord_base.get('partition', 0))

        if not kingdom_id:
            kingdom_id = getattr(self.conn, 'server_id', 0) or 4


        # 3. حساب سعة الحمولة والضريبة بدقة
        if cfg.get('max_capacity'):
            max_cap = int(cfg['max_capacity'])
            tax_rate = float(cfg.get('tax_rate', DEFAULT_TAX_RATE))
            self.log.info(f"🏛️ سعة السوق المحددة يدوياً: {max_cap:,} (ضريبة: {int(tax_rate*100)}%)")
        else:
            total_cap, tax_rate, base_cap, add_cap = await get_full_market_capacity(self.conn)
            max_cap = total_cap
            bonus_str = f" [أساسي: {base_cap:,} + علوم تحالف: {add_cap:,}]" if add_cap > 0 else ""
            self.log.info(f"🏛️ سعة السوق المعتمدة: {max_cap:,}{bonus_str} (ضريبة: {int(tax_rate*100)}%)")

        # 4. إرسال فيالق متتالية بتوزيع ديناميكي 100%
        sent_count = 0
        total_transported = 0

        city = self.conn.init_data.get('cityCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        reslist = city.get('reslist', {}) if isinstance(city, dict) else {}

        # تشخيص: طباعة أرصدة الموارد الأولية
        for rid in res_ids:
            rid_str = str(rid)
            tot = float(reslist.get(rid_str, 0))
            r_name = RESOURCE_NAMES.get(int(rid), rid_str)
            self.log.info(f"📦 رصيد {r_name}: {int(tot):,} (إجمالي)")

        cmd_opting_retries = 0
        while sent_count < max_marches:
            self.log.info(f"⚔️ محاولة إرسال فيلق النقل رقم ({sent_count + 1}/{max_marches})...")

            # النقل يرسل من كل الموارد — لا نخصم saferes (المحمي يحمي فقط من النهب)
            avail_dict = {}
            for rid in res_ids:
                rid_str = str(rid)
                tot = float(reslist.get(rid_str, 0))
                avail_dict[int(rid)] = max(0, int(tot))

            current_march_resources = calculate_dynamic_resource_allocation(
                available_dict=avail_dict,
                res_ids=res_ids,
                total_capacity=max_cap
            )

            if not current_march_resources:
                self.log.warning("⚠️ لا توجد موارد كافية قابلة للنقل لإرسال فيلق جديد.")
                for rid in res_ids:
                    rid_str = str(rid)
                    r_name = RESOURCE_NAMES.get(int(rid), rid_str)
                    self.log.warning(f"   📦 {r_name}: متاح={avail_dict.get(int(rid), 0):,}")
                break

            current_payload_units = sum(r['num'] for r in current_march_resources)
            current_payload_weight = sum(r['num'] * RESOURCE_WEIGHTS.get(r['id'], 1) for r in current_march_resources)

            # تشخيص: تحذير إذا الحمولة أقل من سعة السوق
            if current_payload_weight < max_cap * 0.95:  # أقل من 95% من السعة
                self.log.warning(f"⚠️ الحمولة ({current_payload_weight:,} وزن) أقل من سعة السوق ({max_cap:,}) — الموارد المتاحة محدودة")

            march_payload = {
                "matrixType": 4,      # 4 = نقل موارد
                "moveLineType": 5,    # 5 = مسار خط النقل
                "mapId": int(kingdom_id),
                "data": {
                    "to": {
                        "x": int(actual_x),
                        "y": int(actual_y),
                        "id": str(target_id)
                    },
                    "data": {
                        "resourceList": current_march_resources
                    },
                }
            }

            r_send = await self.conn.query('1007', '2', march_payload)
            if not r_send:
                self.log.error("❌ لم يستجب السيرفر لأمر النقل!")
                break

            err = str(r_send.get('err', '0'))
            if err == '0':
                sent_count += 1
                cmd_opting_retries = 0
                total_transported += current_payload_weight
                res_detail = " + ".join([f"{RESOURCE_NAMES.get(r['id'], r['id'])}:{r['num']:,}" for r in current_march_resources])
                self.log.info(f"✅ تم إرسال فيلق النقل ({sent_count}) بنجاح! 🚚 وزن: {current_payload_weight:,}/{max_cap:,} | {res_detail}")

                for itm in current_march_resources:
                    r_str = str(itm['id'])
                    if r_str in reslist:
                        try:
                            reslist[r_str] = max(0.0, float(reslist[r_str]) - float(itm['num']))
                        except Exception:
                            pass

                if sent_count < max_marches:
                    delay = round(random.uniform(10.0, 15.0), 2)
                    try:
                        self.log.info(f"⏳ [نقل الموارد] انتظار {delay} ثانية قبل إرسال الفيلق التالي...")
                        await asyncio.sleep(delay)
                    except (asyncio.CancelledError, ConnectionError):
                        self.log.warning(f"⚠️ انقطع الاتصال أثناء الانتظار بين المسيرات — تم إرسال {sent_count} فيلق قبل الانقطاع")
                        break
            elif err == '16001':
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة إرسال فيلق النقل نظيفاً من البداية ({cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif err in ('8004', '9007004'):
                self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (الحد الأقصى - كود {err}).")
                if sent_count == 0:
                    return TaskResult.queue_full()
                break
            elif err == '8009':
                self.log.warning(f"⚠️ الموارد غير كافية بالقلعة لإرسال هذه الكمية (كود 8009).")
                break
            elif err in ('8062', '8063', '8060'):
                self.log.warning(f"⚠️ تعذر الإرسال للهدف (كود {err})")
                break
            elif err == '8095':
                # Err_MAP_QUEUE_RESOURCE_HELP_OUT_ONE_DAY (8095):
                # القلعة الهدف بلغت الحد الأقصى اليومي لاستقبال الموارد من التحالف
                err_data = r_send.get('data') or {}
                err_parms = err_data.get('errParms') if isinstance(err_data, dict) else {}
                capped_res = err_parms.get('resId') if isinstance(err_parms, dict) else None
                res_name = RESOURCE_NAMES.get(int(capped_res), f"المورد #{capped_res}") if capped_res else "الموارد"

                self.log.warning(f"🛑 بلغت القلعة الهدف عند ({actual_x}, {actual_y}) الحد الأقصى اليومي لاستقبال {res_name} (كود 8095: Err_MAP_QUEUE_RESOURCE_HELP_OUT_ONE_DAY).")
                self.log.info("⏭️ سيتم تخطي مهمة نقل الموارد بالكامل لبقية اليوم الحالي لتجنب المحاولات الفاشلة واستغلال الفيالق في بقية المهام.")
                set_transport_daily_limit_reached(account_id, target_x, target_y)
                return TaskResult.ok(
                    f"القلعة الهدف بلغت الحد الأقصى اليومي لاستقبال الموارد (كود 8095)",
                    daily_limit_reached=True,
                    sent=sent_count,
                    total=total_transported,
                    capped_res_id=capped_res,
                )
            else:
                self.log.error(f"❌ فشل إرسال فيلق النقل - كود الخطأ: {err}")
                break

        self.log.info(f"🏁 ملخص النقل: تم إرسال {sent_count} فيلق | إجمالي الموارد المنقولة: {total_transported:,} | سعة الفيلق: {max_cap:,}")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} فيلق نقل", sent=sent_count, total=total_transported)
        return TaskResult.fail("لم يتم إرسال أي فيلق نقل", retry_after=180)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Transport Bot — نقل وإمداد الموارد")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--x", type=int, default=DEFAULT_TARGET_X, help=f"إحداثي X للقلعة الهدف [افتراضي: {DEFAULT_TARGET_X}]")
    parser.add_argument("--y", type=int, default=DEFAULT_TARGET_Y, help=f"إحداثي Y للقلعة الهدف [افتراضي: {DEFAULT_TARGET_Y}]")
    parser.add_argument("--res", type=int, nargs="+", default=DEFAULT_RESOURCE_IDS, help="معرفات الموارد: 1002=قمح 1003=خشب 1004=حديد 1005=ألماس [افتراضي: 1002]")
    parser.add_argument("--capacity", "-c", type=int, help="سعة الحمولة الكلية (اختياري، يكتشف تلقائياً)")
    parser.add_argument("--tax", "-t", type=float, help="نسبة ضريبة السوق (اختياري، يكتشف تلقائياً)")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES, help=f"عدد الفيالق [افتراضي: {DEFAULT_MAX_MARCHES}]")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    from core.session_manager import SessionManager

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_email = args.email or next(iter(accounts.keys()))
        acc = accounts.get(target_email)
        if not acc:
            print(f"❌ الحساب {target_email} غير موجود!")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(10):
            await asyncio.sleep(2.0)  # حماية من الحظر
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "target_x": args.x,
            "target_y": args.y,
            "resource_ids": args.res,
            "max_capacity": args.capacity,
            "tax_rate": args.tax,
            "max_marches": args.marches
        }

        task = TransportTask(conn, task_cfg)
        try:
            result = await task.run()
            print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        except (asyncio.CancelledError, ConnectionError, KeyboardInterrupt) as e:
            print(f"\n⚠️ انقطع التنفيذ: {type(e).__name__}")
        finally:
            try:
                await conn.close()
            except Exception:
                pass

    asyncio.run(_main())
    