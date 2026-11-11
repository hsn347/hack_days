# -*- coding: utf-8 -*-
"""
game_client.py — Async wrapper لبروتوكول Empire
════════════════════════════════════════════════
يعيد استخدام الكريبتو الصحيح من onemt_bot.py ويضيف asyncio لدعم 500+ حساب.

الاستخدام:
    from game_client import GameConnection, MultiAccountManager, AccountSession

    # حساب واحد
    conn = GameConnection(AccountSession("email", "userId", "sessionId"))
    await conn.connect()
    data = await conn.query('1033', '2', {})   # مهمة الميناء

    # عدة حسابات
    mgr = MultiAccountManager()
    mgr.load_from_cache('session_cache.json')
    await mgr.connect_all()
    results = await mgr.query_all('1033', '2', {})
"""
import asyncio
import json
import logging
import os
import random
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── استيراد محرك الذاكرة الحية الموحد وقوائم الفلترة ─────────────
try:
    from core.live_memory import (
        LiveMemoryEngine,
        ALLOWED_CONTROLLERS,
        CRITICAL_STARTUP_CONTROLLERS,
        FALLBACK_QUERIES,
        smart_deep_merge,
    )
except ImportError as _e:
    log_err = logging.getLogger("game_client")
    log_err.warning(f"[WARN] core.live_memory غير متاح: {_e}")
    LiveMemoryEngine = None
    ALLOWED_CONTROLLERS = frozenset()
    CRITICAL_STARTUP_CONTROLLERS = frozenset()
    FALLBACK_QUERIES = {}
    smart_deep_merge = None

# ── استيراد الكريبتو المثبتة من onemt_bot.py ─────────────────────
try:
    from core.onemt_bot import (
        dh_exchange, dh_secret, hmac64, skynet_des_encode,
        skynet_hashkey, random_key,
        xor_crypt, pack_request, pack_gate_handshake,
        unpack_stream, decode_gate_response,
        encode_token, LoginServer,
        LOGIN_SERVER, CMD_PREFIX,
    )

    _BOT_AVAILABLE = True
except ImportError as _e:
    _BOT_AVAILABLE = False
    print(f"[WARN] onemt_bot.py غير متاح: {_e}")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

log = logging.getLogger("game_client")


# ════════════════════════════════════════════════════════════════════
#  قاموس الأوامر الشبكية الشامل والتوثيق الموحد
# ════════════════════════════════════════════════════════════════════

SILENT_NETWORK_COMMANDS = {
    ('1037', '1'),  # Heartbeat دوري كل 15 ثانية
    ('1037', ''),
    ('1000', '1'),  # حزمة تهيئة المقبس الأولية
    ('1009', '36'), # حزم مزامنة داخلية لمصافحة الاتصال
    ('1005', '1'),  # حزم مزامنة داخلية لمصافحة الاتصال
}

# استعلامات القراءة والمزامنة الدورية (تُسجل في debug فقط لعدم حشو السجلات بالضوضاء)
ROUTINE_READ_COMMANDS = {
    ('1001', '1'),   # مزامنة عامة أولية
    ('1002', '1'),   # استعلام رصيد الذهب والموارد
    ('1002', '7'),   # استعلام معلومات اللاعب
    ('1003', '1'),   # استعلام طوابير البناء
    ('1004', '1'),   # استعلام الحقيبة
    ('1005', '1'),   # استعلام الفيالق
    ('1006', '15'),  # استعلام بلاطة بالخريطة
    ('1006', '22'),  # استعلام إحداثيات هدف
    ('1006', '25'),  # استعلام معلومات القلعة
    ('1006', '1000'),# استعلام حالة البلاطة
    ('1007', '16'),  # استعلام المسيرات النشطة
    ('1007', '1000'),# مزامنة الفيالق النشطة
    ('1010', '39'),  # استعلام متجر التحالف
    ('1010', '75'),  # استعلام قائمة علوم التحالف
    ('1010', '81'),  # استعلام رصيد تبرعات التحالف
    ('1012', '1'),   # استعلام طلبات المساعدة
    ('1013', '1'),   # استعلام مهام الهيبة
    ('1015', '1'),   # استعلام قائمة البريد
    ('1017', '3'),   # استعلام قائمة علوم التحالف
    ('1018', '1'),   # استعلام بيانات التحالف
    ('1018', '2'),   # استعلام أعضاء التحالف
    ('1019', '1'),   # استعلام بوفات القلعة
    ('1024', '1'),   # فحص صندوق VIP اليومي
    ('1028', '5'),   # استعلام معلومات المهمة
    ('2011', '3'),   # بحث بالخريطة
    ('2011', '4'),   # رادار البحث عن الوحوش
    ('2015', '1'),   # استعلام كنز التحالف
    ('2031', '1'),   # استعلام فعالية خاصة
    ('2057', '1'),   # استعلام واجهة الأبطال
    ('2059', '36'),  # مزامنة بيانات الفيلق
    ('2064', '9'),   # استعلام متجر الفعالية
    ('3081', '5'),   # استعلام جوائز الحيوان الأليف
    ('3129', '4'),   # استعلام مهام يومية
    ('3137', '1'),   # استعلام نشاط
    ('3139', '6'),   # استعلام مسيرة القافلة
    ('3139', '14'),  # فحص أحداث طريق القافلة
    ('3148', '1'),   # استعلام رحلات الأبطال
    ('6023', '2'),   # استعلام ودائع دار الادخار
}

# الأكواد التي تدل على حالات طبيعية وليست أخطاء فشل
BENIGN_STATUS_CODES = {
    "0",
    "Err_CARRIAGE_ESCORT_NOT_DOING",  # لا توجد قافلة تسير حالياً (حالة طبيعية)
    "Err_ALLIANCE_NOT_HAVE",          # الحساب ليس في تحالف بعد
    "17001",                          # تم استلام جائزة الميناء مسبقاً (Err_RECEIVED_REWARD)
    "17002",                          # تم استلام جميع سفن الميناء لليوم (Err_ALL_RECEIVED_TODAY)
}

CMD_REGISTRY: Dict[Tuple[str, str], str] = {
    # ── الاتصال والمزامنة ──────────────────────────────────────────
    ('1000', '1'):    "تهيئة المقبس الأولي",
    ('1001', '1'):    "مزامنة عامة للحساب",
    ('1001', '2'):    "تشييد مبنى جديد",
    ('1001', '8'):    "ترقية مبنى إضافي",
    ('1001', '9'):    "تطبيق مظهر / ترقيات المدينة",

    # ── الموارد والمهارات والمعلومات ──────────────────────────────
    ('1002', '1'):    "استعلام رصيد الذهب والموارد",
    ('1002', '7'):    "استعلام معلومات اللاعب والقلعة",
    ('1002', '22'):   "تفعيل مهارة اللورد / البطل",
    ('1002', '23'):   "تبديل طقم المواهب",
    ('1002', '45'):   "استعلام الحيوان الأليف",

    # ── الطوابير والحقيبة والفيالق ──────────────────────────────────
    ('1003', '1'):    "استعلام طوابير القلعة",
    ('1003', '2'):    "تسريع طابور (تسريع مجاني / أدوات)",
    ('1004', '1'):    "استعلام محتويات الحقيبة",
    ('1004', '2'):    "استخدام عنصر / فتح صندوق",
    ('1005', '1'):    "استعلام الفيالق والقوات",
    ('1005', '2'):    "تغيير اسم فيلق",
    ('1005', '4'):    "علاج جرحى المشفى",
    ('1005', '5'):    "تسريع علاج الجرحى",
    ('1005', '7'):    "ضبط تشكيلة الفيلق",

    # ── الخريطة والأهداف ───────────────────────────────────────────
    ('1006', '15'):   "استعلام بيانات بلاطة بالخريطة",
    ('1006', '22'):   "استعلام هدف بالخريطة",
    ('1006', '25'):   "استعلام معلومات القلعة الخارجية",
    ('1006', '1000'): "استعلام حالة الهدف بالخريطة",
    ('1007', '2'):    "إرسال مسيرة عسكرية",
    ('1007', '3'):    "استدعاء مسيرة عسكرية",
    ('1007', '16'):   "استعلام المسيرات العسكرية النشطة",
    ('1007', '1000'): "مزامنة الفيالق النشطة",

    # ── المباني والترقية والتدريب ───────────────────────────────────
    ('1008', '1'):    "ترقية مبنى بالقلعة",
    ('1008', '2'):    "تسريع مجاني لمبنى",
    ('1008', '7'):    "تدريب قوات بالثكنة",
    ('1008', '10'):   "تسريع علاج المشفى",

    # ── التحالف والمساعدات والتبرعات ───────────────────────────────
    ('1010', '39'):   "استعلام متجر التحالف",
    ('1010', '40'):   "شراء من متجر التحالف",
    ('1010', '47'):   "تحديث متجر التحالف",
    ('1010', '48'):   "تبرع علوم التحالف",
    ('1010', '75'):   "استعلام قائمة علوم التحالف",
    ('1010', '81'):   "استعلام رصيد تبرعات التحالف",
    ('1012', '1'):    "استعلام طلبات مساعدة التحالف",
    ('1012', '2'):    "تقديم مساعدة لأعضاء التحالف",
    ('1017', '1'):    "تبرع علوم التحالف",
    ('1017', '3'):    "استعلام قائمة علوم التحالف",
    ('1018', '1'):    "استعلام بيانات التحالف",
    ('1018', '2'):    "استعلام أعضاء التحالف",

    # ── الهيبة والبريد والبوفات ─────────────────────────────────────
    ('1013', '1'):    "استعلام مهام الهيبة",
    ('1015', '1'):    "استعلام قائمة البريد",
    ('1015', '4'):    "حذف رسائل بريد",
    ('1015', '18'):   "جمع مكافآت بريد",
    ('1015', '19'):   "جمع شامل لجوائز البريد",
    ('1019', '1'):    "استعلام بوفات القلعة",
    ('1019', '6'):    "تفعيل بوف للقلعة",
    ('1024', '1'):    "فحص صندوق VIP اليومي",
    ('1024', '2'):    "استلام صندوق VIP اليومي",
    ('1024', '3'):    "تفعيل نقاط VIP",
    ('1028', '5'):    "استعلام معلومات المهمة",

    # ── الفعاليات والموانئ والأنشطة ────────────────────────────────
    ('1032', '2'):    "مبادلة القافلة",
    ('1033', '1'):    "استعلام بيانات سفن الميناء",
    ('1033', '2'):    "استلام جوائز سفن الميناء",
    ('1034', '1'):    "مزايدة في المزاد",
    ('1034', '2'):    "شراء فوري من المزاد",
    ('1035', '1'):    "تجنيد الأبطال",
    ('1040', '1'):    "تشغيل طاحونة الماء",
    ('1041', '1'):    "نافورة الأمنيات",
    ('1043', '2'):    "استلام مكافأة الهيبة",
    ('1045', '1'):    "مهمة خاصة",
    ('1046', '1'):    "دورية الحيوان الأليف",
    ('1067', '1'):    "استلام مكافآت الفعالية",
    ('1067', '2'):    "تفاعل فعالية",
    ('1087', '3'):    "استلام مكافأة",

    # ── الكنوز والخرائط والأبطال ────────────────────────────────────
    ('2011', '3'):    "بحث بالخريطة",
    ('2011', '4'):    "رادار البحث عن الوحوش",
    ('2015', '1'):    "استعلام كنز التحالف",
    ('2015', '3'):    "حفر صندوق تحالف",
    ('2015', '4'):    "طلب مساعدة لصندوق تحالف",
    ('2015', '6'):    "استلام جوائز صندوق تحالف",
    ('2031', '1'):    "استعلام فعالية خاصة",
    ('2031', '2'):    "تفاعل فعالية خاصة",
    ('2031', '5'):    "استلام مكافأة فعالية",
    ('2057', '1'):    "استعلام واجهة الأبطال",
    ('2058', '1'):    "سحب بطاقات الأبطال",
    ('2059', '36'):   "مزامنة بيانات الفيلق",
    ('2060', '1'):    "شراء صندوق المشاعل",
    ('2063', '2'):    "استلام صناديق الهيبة",
    ('2064', '9'):    "استعلام متجر الفعالية",
    ('2064', '10'):   "شراء من متجر الفعالية",
    ('2064', '11'):   "تحديث متجر الفعالية",

    # ── الأنشطة الإمبراطورية والحيوانات الأليفة ─────────────────────
    ('3078', '1'):    "إنهاء إرشاد الدليل",
    ('3080', '1'):    "رمي مكعب الضريح",
    ('3081', '1'):    "فتح / ترقية الحيوان الأليف",
    ('3081', '4'):    "إرسال دورية الحيوان الأليف",
    ('3081', '5'):    "استلام جوائز الحيوان الأليف",
    ('3105', '2'):    "استلام مكافأة نشاط",
    ('3120', '1'):    "إيداع دار الادخار",
    ('3129', '4'):    "استعلام مهام يومية",
    ('3130', '1'):    "استكشاف كنز طروادة",
    ('3137', '1'):    "بدء بحث تكتيكي",
    ('3137', '2'):    "استلام بحث تكتيكي",
    ('3139', '1'):    "إرسال القافلة وحراسة الكنز",
    ('3139', '6'):    "استعلام مسيرة القافلة",
    ('3139', '7'):    "استلام جوائز وصول القافلة",
    ('3139', '14'):   "معالجة أحداث طريق القافلة",
    ('3140', '1'):    "تفعيل قاعة التكتيك",
    ('3142', '2'):    "استكشاف جناح الكنز",
    ('3148', '1'):    "استعلام رحلات الأبطال",
    ('3148', '3'):    "استدعاء رحلة الأبطال",
    ('3148', '4'):    "إرسال رحلة الأبطال",
    ('3148', '5'):    "استلام مكافأة رحلة الأبطال",
    ('3148', '7'):    "تسريع رحلة الأبطال",
    ('5011', '1'):    "تفعيل ميزة خاصة",
    ('6023', '1'):    "إيداع دار الادخار (خطة شهرية/أسبوعية)",
    ('6023', '2'):    "استعلام ودائع دار الادخار",
}


def _deep_merge(source: dict, destination: dict) -> dict:
    """
    دمج ذكي عميق يمنع استبدال الكائنات الكاملة أو مسح القوائم التراكمية.
    يفوض تلقائياً لمحرك smart_deep_merge لمنع مسح مباني المدينة أو الفيالق أو الأبطال.
    """
    if smart_deep_merge is not None:
        return smart_deep_merge(destination, source, in_place=True)
    for key, value in source.items():
        if key in destination and isinstance(destination[key], dict) and isinstance(value, dict):
            _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


def _summarize_payload(data: Any) -> str:
    """استخلاص ملخص بشري ذكي وموجز من حمولة الطلب لمنع حشو السجلات."""
    if not isinstance(data, dict) or not data:
        return ""
    try:
        parts = []
        if "skillID" in data:
            parts.append(f"مهارة #{data['skillID']}")
        if "scienceId" in data or "techId" in data:
            s_id = data.get("scienceId") or data.get("techId")
            parts.append(f"تقنية #{s_id}")
        if "buildingId" in data or "bid" in data:
            b_id = data.get("buildingId") or data.get("bid")
            parts.append(f"مبنى #{b_id}")
        if "itemid" in data or "itemId" in data:
            item_id = data.get("itemid") or data.get("itemId")
            count = data.get("count", 1)
            parts.append(f"عنصر #{item_id} ×{count}")
        if "mailIds" in data:
            m_len = len(data["mailIds"]) if isinstance(data["mailIds"], list) else 1
            parts.append(f"{m_len} رسالة")
        if "to" in data and isinstance(data["to"], dict):
            parts.append(f"هدف ({data['to'].get('x')}, {data['to'].get('y')})")
        if "cId" in data or "heroId" in data:
            parts.append(f"بطل #{data.get('cId') or data.get('heroId')}")
        if "boxId" in data or "box_id" in data:
            parts.append(f"صندوق #{data.get('boxId') or data.get('box_id')}")
        if "dest" in data:
            parts.append(f"وجهة #{data['dest']}")
        if "bossType" in data:
            parts.append(f"نوع #{data['bossType']}")
        if parts:
            return f"({', '.join(parts)})"
    except Exception:
        pass
    return ""

def _format_network_event(cmd: str, subcmd: str, data: Any, content: Any, elapsed: float, error: str = "", is_nowait: bool = False) -> str:
    """صياغة سطر شبكي موحد وموجز وأنيق يوضح الطلب والنتيجة."""
    try:
        cmd_str = str(cmd)
        sub_str = str(subcmd)
        desc = CMD_REGISTRY.get((cmd_str, sub_str)) or CMD_REGISTRY.get((cmd_str, "")) or f"طلب {cmd_str}/{sub_str}"
        summary = _summarize_payload(data)
        summary_str = f" {summary}" if summary else ""

        if is_nowait:
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ 🚀 تم الإرسال"

        t_str = f" ({elapsed:.2f}ث)" if elapsed > 0 else ""

        if error:
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ ⚠️ خطأ شبكة: {error}{t_str}"

        if not content:
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ ❌ لا توجد استجابة{t_str}"

        # فحص كود الخطأ في الرد
        err_code = "0"
        if isinstance(content, dict):
            err_code = str(content.get("err", content.get("code", "0")))

        if err_code == "0":
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ ✅ نجاح{t_str}"
        elif err_code in BENIGN_STATUS_CODES:
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ ℹ️ {err_code}{t_str}"
        else:
            return f"🌐 [{cmd_str}/{sub_str}] {desc}{summary_str} ➔ ❌ كود: {err_code}{t_str}"
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════════
#  نماذج البيانات
# ════════════════════════════════════════════════════════════════════

@dataclass
class AccountSession:
    email:      str
    user_id:    str
    session_id: str


@dataclass
class GateCredentials:
    kingdom_id:  str = ""
    server_name: str = ""
    gate_ip:     str = ""
    gate_port:   int = 0
    sub_id:      str = ""
    uid:         str = ""
    secret:      bytes = b""


# ════════════════════════════════════════════════════════════════════
#  Async Login (wrapper حول LoginServer من onemt_bot.py)
# ════════════════════════════════════════════════════════════════════

async def async_login(account: AccountSession, proxy_url: Optional[str] = None) -> Optional[GateCredentials]:
    """يتصل بـ Login Server ويستقبل Gate credentials (async via executor)"""
    loop = asyncio.get_event_loop()

    def _do_login():
        token = {"subtoken": account.session_id, "userid": account.user_id}
        # بصمة جهاز حقيقية فريدة لكل حساب (lazy import لعدم استهلاك الموارد)
        dev_profile = None
        try:
            from core.device_profiles import get_device_profile
            dev_profile = get_device_profile(account.email or account.user_id)
        except Exception:
            pass
        srv   = LoginServer(*LOGIN_SERVER, proxy_url=proxy_url)
        srv.connect()
        try:
            result = srv.do_handshake(token, device_profile=dev_profile)
        finally:
            srv.close()
        return result

    try:
        result = await loop.run_in_executor(None, _do_login)
    except Exception as e:
        log.error(f"[Login] {account.email}: {e}")
        return None

    if not result.get('success'):
        return None

    gate   = result['gate']
    creds  = GateCredentials(
        kingdom_id  = gate.get('kingdomId', ''),
        server_name = gate.get('servername', ''),
        gate_ip     = gate.get('gateip', ''),
        gate_port   = int(gate.get('gateport', 0)),
        sub_id      = gate.get('subid', ''),
        uid         = gate.get('uid', ''),
        secret      = result['secret'],
    )
    log.info(f"[Login] ✓ {account.email} → Gate {creds.gate_ip}:{creds.gate_port} uid={creds.uid}")
    return creds


# ════════════════════════════════════════════════════════════════════
#  Gate Async Client
# ════════════════════════════════════════════════════════════════════

def _compute_gate_handshake(creds: GateCredentials, index: int = 1):
    """يحسب username و hmac للـ Gate handshake"""
    import base64
    uid_b64 = base64.b64encode(creds.uid.encode()).decode()
    srv_b64 = base64.b64encode(creds.server_name.encode()).decode()
    sub_b64 = base64.b64encode(creds.sub_id.encode()).decode()
    username = f"{uid_b64}@{srv_b64}#{sub_b64}"
    key_mat  = f"{username}:{index}".encode()
    hash_key = skynet_hashkey(key_mat)
    mac_val  = hmac64(hash_key, creds.secret)
    import base64
    return username, base64.b64encode(mac_val).decode()


class GateClient:
    """
    Async Gate Client — يتصل بـ Gate Server ويرسل أوامر ويستقبل ردود.
    يستخدم نفس كريبتو onemt_bot.py (xor_crypt, pack_request, etc.)
    """

    # ── ثوابت حماية الحساب من الحظر (محاكاة التردد البشري Dynamic Jitter) ────────
    RATE_LIMIT_DELAY = 1.0   # القيمة الأساسية
    RATE_LIMIT_MIN   = 0.85  # الحد الأدنى للفترة الفاصلة بين الطلبات
    RATE_LIMIT_MAX   = 1.45  # الحد الأقصى للفترة الفاصلة لمحاكاة النقر البشري العشوائي

    def __init__(self, creds: GateCredentials, proxy_url: Optional[str] = None):
        self.creds    = creds
        self.proxy_url: Optional[str] = proxy_url
        self._session = 1
        self._reader  = None
        self._writer  = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._cmd_pending: Dict[Tuple[str, str], asyncio.Future] = {}

        # ── محرك الذاكرة الحية المركزي وقفل التزامن ────────────────────
        owner_uid = getattr(creds, 'uid', '') if creds is not None else ''
        if LiveMemoryEngine is not None:
            self.memory_engine = LiveMemoryEngine(owner_uid=owner_uid)
        else:
            from core.live_memory import LiveMemoryEngine as _LME
            self.memory_engine = _LME(owner_uid=owner_uid)
        self.init_data: dict = self.memory_engine.init_data

        self.heroes: list = []
        self.spy_mode: bool = False
        self._buf = b""
        self.cached_packets: dict = {}
        self.local_queues: list = []
        self.local_queues_map: dict = self.memory_engine.local_queues_map
        self.kick_reason: str = ""
        self._lock    = asyncio.Lock()
        self._alive   = False
        self._notifies: Dict[str, Callable] = {}
        self._packet_listeners: List[Callable] = []
        self._recv_task = None
        self._heartbeat_task = None
        self._init_flow_task = None
        self.on_disconnect: Optional[Callable[[str], Any]] = None
        self._explicit_close: bool = False
        self._last_query_time: float = 0.0  # توقيت آخر طلب API
        self.log_callback: Optional[Callable[[str], Any]] = None
        self.memory_terminal_trace: bool = True
        self._connect_started_at: float = 0.0
        self._last_notify_at: float = 0.0
        self._last_idle_notify_log_at: float = 0.0
        self._notify_count: int = 0
        self._notify_merged_count: int = 0
        self._notify_failed_count: int = 0
        self._notify_unhandled_count: int = 0

    @property
    def is_connected(self) -> bool:
        return self._alive and self._writer is not None

    async def connect(self) -> bool:
        if self._alive:
            return True
        try:
            if self.proxy_url:
                from python_socks.async_.asyncio import Proxy
                proxy = Proxy.from_url(self.proxy_url)
                sock = await asyncio.wait_for(
                    proxy.connect(dest_host=self.creds.gate_ip, dest_port=self.creds.gate_port),
                    timeout=15
                )
                self._reader, self._writer = await asyncio.open_connection(sock=sock)
                log.info(f"[Gate] ✓ متصل بأمان عبر SOCKS5 باتجاه {self.creds.gate_ip}:{self.creds.gate_port}")
            else:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.creds.gate_ip, self.creds.gate_port),
                    timeout=15
                )
        except Exception as e:
            log.error(f"[Gate] 🛑 فشل الاتصال عبر البروكسي وتم إيقاف المحاولة لمنع تسريب الـ IP: {e}")
            return False

        # Gate Handshake
        username, hmac_b64 = _compute_gate_handshake(self.creds, index=1)
        hs_pkt = pack_gate_handshake(username, 1, hmac_b64)
        self._writer.write(hs_pkt)
        await self._writer.drain()

        try:
            # رد handshake: [2-byte len][content]
            head = await asyncio.wait_for(self._reader.readexactly(2), timeout=15)
            sz   = head[0] * 256 + head[1]
            resp = await asyncio.wait_for(self._reader.readexactly(sz), timeout=15)
            if b'200' not in resp:
                log.error(f"[Gate] Handshake failed: {resp[:40]!r}")
                return False
            log.info(f"[Gate] ✓ {self.creds.gate_ip}:{self.creds.gate_port} uid={self.creds.uid}")
        except Exception as e:
            log.error(f"[Gate] Handshake error: {e}")
            return False

        self.active_connection_info: Dict[str, Any] = {}
        now_ts = time.time()
        self._connect_started_at = now_ts
        self._last_idle_notify_log_at = now_ts
        self._alive = True
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._init_flow_task = asyncio.create_task(self._init_flow())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # تسجيل بيانات المقبس والـ IP الفعلي اللحظي لمنع التسريب
        try:
            peer = self._writer.get_extra_info('peername')
        except Exception:
            peer = None

        if self.proxy_url:
            raw_ip = ""
            try:
                raw_ip = self.proxy_url.split("@")[-1].split(":")[0]
            except Exception:
                raw_ip = ""
            self.active_connection_info = {
                "type": "socks5",
                "real_ip": raw_ip,
                "peer": f"{peer[0]}:{peer[1]}" if peer else raw_ip,
                "is_proxied": True,
                "connected_at": time.time(),
            }
        else:
            from proxy import get_server_public_ip
            self.active_connection_info = {
                "type": "direct",
                "real_ip": get_server_public_ip(),
                "peer": f"{peer[0]}:{peer[1]}" if peer else f"{self.creds.gate_ip}:{self.creds.gate_port}",
                "is_proxied": False,
                "connected_at": time.time(),
            }
        return True


    _MARCH_STATUS_LABELS: Dict[Any, str] = {
        0: "حشد/انتظار",
        1: "سائرة للهدف",
        2: "تجمع/تعمل",
        3: "عائدة للقلعة",
        4: "مرابطة",
        7: "دفاع/مشاركة",
    }

    _MEMORY_STATUS_BADGES: Dict[str, str] = {
        "merged": "✅ تم الدمج بنجاح في الذاكرة الحية",
        "failed": "❌ فشل الدمج في الذاكرة الحية",
        "unhandled_notify": "⚠️ وصل إشعار غير معرّف في LiveMemoryEngine (لم يُدمج)",
        "missing_notify_id": "⚠️ وصلت حزمة 1009 بدون notifyID (لم يُدمج)",
        "empty_notify_data": "⚠️ وصل إشعار بدون notifyData (لم يُدمج)",
        "skipped_empty": "⚠️ وصل إشعار بلا تغييرات قابلة للتطبيق (فارغ/غير مطابق)",
        "ignored": "ℹ️ استجابة بدون حقول ذاكرة مسموح بها",
    }

    def _terminal_prefix(self) -> str:
        ts = time.strftime("%H:%M:%S")
        raw_email = getattr(self.creds, "email", "") or ""
        uid = getattr(self.creds, "uid", "") or ""
        label = raw_email.split("@")[0] if "@" in raw_email else (raw_email or str(uid) or "account")
        return f"[{ts}][{label}]"

    @staticmethod
    def _safe_terminal_print(text: str) -> None:
        try:
            print(text, flush=True)
        except UnicodeEncodeError:
            try:
                encoded = (text + "\n").encode("utf-8", errors="replace")
                if hasattr(sys.stdout, "buffer"):
                    sys.stdout.buffer.write(encoded)
                    sys.stdout.buffer.flush()
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _safe_json(obj: Any, max_len: int = 160) -> str:
        try:
            raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)
        except Exception:
            raw = repr(obj)
        if max_len > 0 and len(raw) > max_len:
            return raw[:max_len] + "...(مختصر)"
        return raw

    def _march_sync_label(self, report: Optional[Dict[str, Any]] = None) -> str:
        synced = report.get("local_queues_synced") if report is not None else getattr(self.memory_engine, "local_queues_synced", False)
        return "sync=✅" if synced else "sync=❌ لم يصل 202"

    def _format_march_summary_lines(self, queues: List[Any], report: Optional[Dict[str, Any]] = None) -> List[str]:
        own_cnt = len(queues)
        list_cnt = len(self.local_queues)
        init_q = self.init_data.get("local_queues")
        init_cnt = len(init_q) if isinstance(init_q, list) else -1
        all_cnt = report.get("all_local_queues_count") if report and "all_local_queues_count" in report else len(self.local_queues_map)
        other_cnt = max(0, int(all_cnt) - own_cnt)
        sync_note = "" if (own_cnt == list_cnt == init_cnt) else f" ⚠️ عدم تطابق(own={own_cnt},list={list_cnt},init={init_cnt})"
        extra_other = f", بث كلي={all_cnt} (لغيري={other_cnt})" if other_cnt > 0 else ""
        lines = [f"   ├─ 🐎 مسيرات قلعتي ({own_cnt}{extra_other}) [{self._march_sync_label(report)}]{sync_note}:"]
        for q in queues:
            if not isinstance(q, dict):
                continue
            qid = q.get("id") or q.get("queueId") or "?"
            st = q.get("status")
            st_lbl = self._MARCH_STATUS_LABELS.get(st, f"status={st}")
            mlt = q.get("moveLineType", "?")
            to_info = q.get("to") if isinstance(q.get("to"), dict) else {}
            tx, ty, mt = to_info.get("x", "?"), to_info.get("y", "?"), to_info.get("mapType", "?")
            lines.append(
                f"   │  • {qid}: {st_lbl} (st={st}, type={mlt}) -> ({tx},{ty}) mType={mt}"
            )
        return lines

    def _emit_log(self, line: str) -> None:
        """إرسال السطر إلى log_callback للظهور في اللوق وتيرمنال api_server، أو طباعته في CLI."""
        if not line:
            return
        if hasattr(self, "log_callback") and callable(self.log_callback):
            try:
                self.log_callback(line)
                return
            except Exception:
                pass
        self._safe_terminal_print(f"{self._terminal_prefix()} {line}")

    def _print_live_memory_report(
        self, packet: Dict[str, Any], cmd: str, sub: str, sess: int, report: Dict[str, Any]
    ) -> None:
        # طباعة الإشعارات فقط (إخفاء تحديثات الذاكرة الناتجة عن استعلامات عادية)
        if not report.get("is_notification"):
            return

        status_key = report.get("overall_status", "ignored")
        nid = report.get("notify_id")

        # 1. إشعار غير معرّف لدينا — طباعة بسيطة جداً جداً
        if status_key in ("unhandled_notify", "missing_notify_id"):
            if nid is not None and str(nid).strip() != "":
                self._emit_log(f"📨 إشعار غير معرّف: {nid}")
            else:
                self._emit_log(f"📨 إشعار غير معرّف ({cmd}/{sub})")
            return

        # 2. إشعار معرّف لدينا — ذكر المتحكم، نجاح/فشل الدمج، والقيمة الجديدة باختصار
        ctrls = report.get("notify_controllers") or report.get("updated_keys") or []
        ctrl_str = ", ".join(ctrls) if ctrls else "غير محدد"

        if status_key == "merged":
            merge_str = "نجح ✅"
        elif status_key == "failed":
            err_txt = report.get("error") or "خطأ"
            merge_str = f"فشل ❌ ({err_txt})"
        elif status_key == "skipped_empty":
            merge_str = "لم يُدمج ⚠️"
        elif status_key == "empty_notify_data":
            merge_str = "فشل ❌ (بيانات فارغة)"
        else:
            merge_str = str(status_key)

        val_summary = report.get("new_value_summary") or ""
        if val_summary:
            self._emit_log(f"📨 إشعار {nid} [{ctrl_str}] | الدمج: {merge_str} | الجديد: {val_summary}")
        else:
            self._emit_log(f"📨 إشعار {nid} [{ctrl_str}] | الدمج: {merge_str}")

    def _maybe_report_idle_notifications(self) -> None:
        """صامت — لا يطبع تنبيه الخمول كل 30 ثانية لتقليل الضجيج."""
        return

    async def _heartbeat_loop(self):
        """إرسال نبضات القلب الدورية (Heartbeat 1037/1) المطابقة لبروتوكول اللعبة الرسمي كل 15 ثانية"""
        # انتظار انتهاء _init_flow أولاً
        for _ in range(10):
            if not self._alive:
                return
            await asyncio.sleep(1)
        while self._alive:
            try:
                # بروتوكول اللعبة الرسمي: CMD_HEARTBEAT_MODULE (1037) / REQ_HEARTBEAT (1)
                now_ms = int(time.time() * 1000)
                self.send_nowait('1037', '1', {'time': now_ms})
                self._maybe_report_idle_notifications()
                # فاصل زمني 15 ثانية مطابق لـ HEARTBEAT_INV في اللعبة مع نوم متقطع للاستجابة السريعة
                for _ in range(15):
                    if not self._alive:
                        return
                    await asyncio.sleep(1)
            except Exception:
                break

    async def _init_flow(self):
        """إرسال طلبات التهيئة وتدفق بيانات السيرفر الأولية"""
        try:
            # الانتظار قليلاً حتى يُكمل خادم الـ Gate ربط الجلسة داخلياً وتجنب خطأ 16001
            await asyncio.sleep(0.6)
            if not self._alive: return
            pkt_init = pack_request('1000', '1', {}, session=0)
            self._writer.write(pkt_init)
            await self._writer.drain()
            self._log_sent_request('1000', '1')
            await asyncio.sleep(1)
        except Exception:
            pass


    async def _recv_loop(self):
        try:
            while self._alive:
                chunk = await asyncio.wait_for(self._reader.read(65536), timeout=90)
                if not chunk: break
                self._buf += chunk
                self._dispatch()
        except asyncio.TimeoutError:
            if self._alive:
                log.warning("[Gate] ⏰ انتهت مهلة الاستقبال (90s) — الاتصال قد ينقطع")
        except Exception as e:
            if self._alive: log.warning(f"[Gate] recv: {e}")
        finally:
            was_alive = self._alive
            self._alive = False
            for fut in list(self._pending.values()) + list(self._cmd_pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("Gate disconnected"))
            self._pending.clear()
            self._cmd_pending.clear()
            
            if was_alive and not self._explicit_close:
                if not self.kick_reason:
                    # انقطاع شبكي غير متوقع — ليس بالضرورة دخولاً من جهاز آخر
                    self.kick_reason = "connection_lost"
                log.warning(f"[Gate] ⚠️ انقطع الاتصال بالحساب (السبب: {self.kick_reason})")
                if self.on_disconnect:
                    try:
                        if asyncio.iscoroutinefunction(self.on_disconnect):
                            asyncio.create_task(self.on_disconnect(self.kick_reason))
                        else:
                            self.on_disconnect(self.kick_reason)
                    except Exception:
                        pass

    def _dispatch(self):
        pkts, self._buf = unpack_stream(self._buf)
        for pkt in pkts:
            r = decode_gate_response(pkt)
            if not r: continue
            sess = r.get('session', 0)
            c    = r.get('content', {})
            cmd  = str(c.get('cmd', '')) if isinstance(c, dict) else ''
            sub  = str(c.get('subcmd', '')) if isinstance(c, dict) else ''
            subcmd = sub
            cmd_key = (cmd, sub)

            # وضع التجسس على الحزم (Spy Mode)
            if self.spy_mode:
                summary = f"👁️ [SPY S2C] CMD={cmd}/{sub} (session={sess})"
                if isinstance(c, dict) and 'data' in c:
                    d_keys = list(c['data'].keys()) if isinstance(c['data'], dict) else type(c['data'])
                    summary += f" | data keys: {d_keys}"
                print(summary)

            # ── 1. تخزين محكوم ومحدد السقف للحزم المؤقتة لمنع تراكم الذاكرة العشوائي ──
            if isinstance(c, dict) and cmd:
                self.cached_packets[cmd_key] = c
                if len(self.cached_packets) > 64:
                    oldest_k = next(iter(self.cached_packets))
                    self.cached_packets.pop(oldest_k, None)

            # ── 2. تمرير فوري للحزمة إلى محرك الذاكرة الحية المركزي ────────────
            mem_report = None
            if isinstance(c, dict):
                try:
                    _, mem_report = self.memory_engine.ingest_packet_with_report(c)
                    if mem_report.get("is_notification"):
                        self._last_notify_at = time.time()
                        self._notify_count += 1
                        n_st = mem_report.get("notify_status")
                        if n_st == "merged":
                            self._notify_merged_count += 1
                        elif n_st == "failed":
                            self._notify_failed_count += 1
                        elif n_st == "unhandled_notify":
                            self._notify_unhandled_count += 1
                except Exception as _e:
                    self._notify_failed_count += 1
                    log.debug(f"[LiveMemory] ingest error: {_e}")
                    if self.memory_terminal_trace:
                        self._emit_log(f"❌ فشل قراءة الحزمة {cmd}/{sub}: {_e}")

            # ── 3. تحديث مراجع التوافقية السريعة (heroes, local_queues) ───────
            h_ctrl = self.init_data.get('heroCtrl')
            if isinstance(h_ctrl, list):
                self.heroes = h_ctrl
            elif isinstance(h_ctrl, dict) and 'heroes' in h_ctrl and isinstance(h_ctrl['heroes'], list):
                self.heroes = h_ctrl['heroes']

            self.local_queues = self.memory_engine.get_own_local_queues()

            if self.memory_terminal_trace and mem_report and mem_report.get("should_log"):
                self._print_live_memory_report(c, cmd, sub, sess, mem_report)

            # ── 4. فحص حالات انقطاع أو تجميد الحساب من السيرفر ────────────────
            if isinstance(c, dict):
                data_obj = c.get('data', {})
                if isinstance(data_obj, dict):
                    status = data_obj.get('status')
                    if status == 'kick':
                        self.kick_reason = "other_device"
                    elif status == 'seal':
                        self.kick_reason = "account_sealed"
                    elif status == 'server_maintenance':
                        self.kick_reason = "server_maintenance"
                    notify_id = str(data_obj.get('notifyID', ''))
                    if notify_id in ('100', 'NOTIFY_SERVER_STATUS', 'SERVER_STATUS'):
                        n_data = data_obj.get('notifyData')
                        if isinstance(n_data, list) and n_data and isinstance(n_data[0], dict):
                            st = n_data[0].get('status')
                            if st == 'kick': self.kick_reason = "other_device"
                            elif st == 'seal': self.kick_reason = "account_sealed"
                            elif st == 'server_maintenance': self.kick_reason = "server_maintenance"
                        elif isinstance(n_data, dict):
                            st = n_data.get('status')
                            if st == 'kick': self.kick_reason = "other_device"
                            elif st == 'seal': self.kick_reason = "account_sealed"
                            elif st == 'server_maintenance': self.kick_reason = "server_maintenance"

            fut = None
            if sess != 0 and sess in self._pending:
                fut = self._pending.pop(sess)
                self._cmd_pending.pop(cmd_key, None)
            elif cmd_key in self._cmd_pending:
                fut = self._cmd_pending.pop(cmd_key)
            elif (cmd, '') in self._cmd_pending:
                fut = self._cmd_pending.pop((cmd, ''))
            else:
                for (p_cmd, p_sub), p_fut in list(self._cmd_pending.items()):
                    if p_cmd == cmd and (not p_sub or p_sub == sub) and not p_fut.done():
                        fut = self._cmd_pending.pop((p_cmd, p_sub))
                        break

            if fut and not fut.done():
                fut.get_loop().call_soon_threadsafe(fut.set_result, r)
            else:
                # Push notification
                if isinstance(c, dict):
                    data_obj = c.get('data', {})
                    nid = data_obj.get('notifyID', '') if isinstance(data_obj, dict) else ''
                    if nid and nid in self._notifies:
                        asyncio.create_task(self._notifies[nid](c))

            # General packet listeners
            if self._packet_listeners:
                for listener in list(self._packet_listeners):
                    try:
                        if asyncio.iscoroutinefunction(listener):
                            asyncio.create_task(listener(cmd, sub, c))
                        else:
                            listener(cmd, sub, c)
                    except Exception:
                        pass

    def add_packet_listener(self, listener: Callable):
        if listener not in self._packet_listeners:
            self._packet_listeners.append(listener)

    def remove_packet_listener(self, listener: Callable):
        if listener in self._packet_listeners:
            self._packet_listeners.remove(listener)

    def check_and_merge_controller(self, ctrl_name: str) -> Tuple[bool, dict]:
        """
        التحقق اللحظي الفوري من وجود المتحكم في الذاكرة الحية (O(1) Live State Check).
        تم إلغاء حلقة التكرار التاريخية البطيئة O(N) على cached_packets
        نظراً لأن محرك LiveMemoryEngine يعترض كافة الحزم ويدمج الحالات لحظياً في _dispatch.

        Args:
            ctrl_name: اسم المتحكم المطلوب فحصه (مثل "cityCtrl", "heroCtrl").

        Returns:
            (exists: bool, data: dict)
            - True  → المتحكم متوفر في الذاكرة الحية.
            - False → المتحكم غير متوفر بعد.
        """
        exists = ctrl_name in self.init_data
        return exists, self.init_data.get(ctrl_name, {})

    async def wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True, grace_period: float = 0.0) -> bool:
        """
        بوابة جاهزية الذاكرة الصارمة (Strict Memory Readiness Gate).
        تتحقق من اكتمال كافة المتحكمات الأساسية CRITICAL_STARTUP_CONTROLLERS في الذاكرة الحية.
        في حال نقص أي متحكم وكان auto_fetch_missing=True، ترسل الاستعلامات التعويضية المحددة:
          - cityCtrl: CMD 1001 / Sub 1
          - lordInfoCtrl: CMD 1002 / Sub 7
          - queueCtrl: CMD 1003 / Sub 1
          - armyCtrl: CMD 1005 / Sub 1
          - backpackCtrl: CMD 1004 / Sub 1
          - local_queues: CMD 1007 / Sub 1000
        تنتظر حتى اكتمال البيانات أو انقضاء مهلة timeout مع إعطاء مهلة سماح (grace_period) لبث السيرفر التلقائي.

        Returns:
            True إذا اكتملت الذاكرة وأصبحت جاهزة، False إذا انتهت المهلة دون اكتمالها.
        """
        start_time = time.time()
        fallback_sent = False
        effective_grace = grace_period if grace_period > 0.0 else (2.0 if timeout >= 5.0 else 0.0)

        while time.time() - start_time < timeout:
            if not self._alive:
                return False

            res = self.memory_engine.is_memory_ready()
            is_ready = res[0] if isinstance(res, tuple) else bool(res)
            missing = res[1] if (isinstance(res, tuple) and len(res) > 1) else []

            if is_ready:
                return True

            if auto_fetch_missing and not fallback_sent and (time.time() - start_time >= effective_grace):
                fallback_sent = True
                missing_set = set(missing) if missing else {
                    c for c in ("cityCtrl", "lordInfoCtrl", "queueCtrl", "armyCtrl", "heroCtrl", "backpackCtrl")
                    if c not in self.init_data
                }

                # إرسال استعلامات التعويض المحددة في CONTROLLER_WHITELIST_SPEC
                if any(k.startswith("cityCtrl") for k in missing_set):
                    self.send_nowait('1001', '1', {})
                if any(k.startswith("lordInfoCtrl") for k in missing_set):
                    uid = getattr(self.creds, 'uid', '') if hasattr(self, 'creds') else ''
                    self.send_nowait('1002', '7', {'uid': uid} if uid else {})
                if any(k.startswith("queueCtrl") for k in missing_set):
                    self.send_nowait('1003', '1', {})
                if any(k.startswith("armyCtrl") or k.startswith("heroCtrl") for k in missing_set):
                    self.send_nowait('1005', '1', {})
                if any(k.startswith("backpackCtrl") for k in missing_set):
                    self.send_nowait('1004', '1', {})
                if not getattr(self.memory_engine, 'local_queues_synced', False) or not self.local_queues_map:
                    self.send_nowait('1007', '1000', {})

            await asyncio.sleep(0.25)

        # فحص أخير عند انتهاء المهلة
        res = self.memory_engine.is_memory_ready()
        ready_final = res[0] if isinstance(res, tuple) else bool(res)
        missing_final = res[1] if (isinstance(res, tuple) and len(res) > 1) else []
        if self.memory_terminal_trace and not ready_final:
            self._emit_log(f"❌ مهلة الذاكرة ({timeout:.0f}ث) ناقص={missing_final}")
        return ready_final

    def _log_sent_request(self, cmd: str, subcmd: str) -> None:
        """طباعة مبسطة جداً لكل طلب شبكي مرسل (الرقم الأساسي والفرعي فقط) باستثناء نبض القلب 1037/1."""
        try:
            cmd_s = str(cmd).strip()
            sub_s = str(subcmd).strip()
            if (cmd_s, sub_s) in {('1037', '1'), ('1037', '')}:
                return
            req_txt = f"🌐 {cmd_s}/{sub_s}" if sub_s else f"🌐 {cmd_s}"
            self._emit_log(req_txt)
        except Exception:
            pass

    def _log_network_action(self, cmd: str, subcmd: str, data: Any, content: Any, elapsed: float, error: str = "", is_nowait: bool = False):
        """مُعطّل لصالح _log_sent_request المبسطة."""
        return

    async def query(self, cmd: str, subcmd: str, data: dict = None, timeout: float = 15, client_data: list = None) -> Optional[dict]:
        """إرسال أمر والانتظار للرد — مع حماية تلقائية من السرعة الزائدة."""
        if not self._alive: return None
        str_cmd = str(cmd)
        str_sub = str(subcmd)
        cmd_key = (str_cmd, str_sub)

        # 🛡️ حماية من الحظر: تأخير بشري ديناميكي عشوائي (Jitter) بين الطلبات
        now = time.time()
        elapsed = now - self._last_query_time
        target_delay = random.uniform(self.RATE_LIMIT_MIN, self.RATE_LIMIT_MAX)
        if elapsed < target_delay:
            await asyncio.sleep(target_delay - elapsed)
        self._last_query_time = time.time()

        sess = self._session
        self._session += 1
        pkt = pack_request(str_cmd, str_sub, data or {}, sess, client_data)

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[sess] = fut
        self._cmd_pending[cmd_key] = fut

        if self.spy_mode:
            print(f"📡 [SPY C2S] CMD={cmd}/{subcmd} (session={sess}) | data={data}")

        async with self._lock:
            self._writer.write(pkt)
            await self._writer.drain()
        self._log_sent_request(str_cmd, str_sub)

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            content = result.get('content') if (result and result.get('ok')) else None
            return content
        except (asyncio.TimeoutError, ConnectionError):
            return None
        finally:
            self._pending.pop(sess, None)
            self._cmd_pending.pop(cmd_key, None)

    def send_nowait(self, cmd: str, subcmd: str, data: dict = None):
        """إرسال بدون انتظار مع تسجيل توقيت الطلب لمنع التداخل"""
        if not self._alive or not self._writer: return
        self._last_query_time = time.time()
        sess = self._session
        self._session += 1
        if self.spy_mode:
            print(f"🚀 [SPY C2S] NOWAIT CMD={cmd}/{subcmd} (session={sess}) | data={data}")
        self._writer.write(pack_request(cmd, str(subcmd), data or {}, sess))
        self._log_sent_request(str(cmd), str(subcmd))

    def on_notify(self, notify_id: str, handler: Callable):
        self._notifies[notify_id] = handler

    def abort(self):
        """إغلاق فوري قسري لمقبس الشبكة وإلغاء كافة المهام دون أي انتظار."""
        self._explicit_close = True
        self._alive = False
        for task in (self._recv_task, self._heartbeat_task, self._init_flow_task):
            if task and not task.done():
                try:
                    task.cancel()
                except Exception:
                    pass
        for fut in list(self._pending.values()):
            if fut and not fut.done():
                try:
                    fut.cancel()
                except Exception:
                    pass
        for fut in list(self._cmd_pending.values()):
            if fut and not fut.done():
                try:
                    fut.cancel()
                except Exception:
                    pass
        self._pending.clear()
        self._cmd_pending.clear()
        if self._writer:
            try:
                if hasattr(self._writer, "transport") and self._writer.transport:
                    self._writer.transport.abort()
            except Exception:
                pass

    async def close(self):
        self._explicit_close = True
        self._alive = False
        self.abort()
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass

    @property
    def is_connected(self) -> bool:
        return self._alive


# ── الاسم المستعار المعتمد لمحرك العميل ─────────────────────────────
GameClient = GateClient


# ════════════════════════════════════════════════════════════════════
#  GameConnection — الواجهة الشاملة
# ════════════════════════════════════════════════════════════════════

class GameConnection:
    """
    واجهة شاملة لحساب واحد:
    1. Login → Gate credentials
    2. Gate connect → handshake
    3. query() / send_nowait() / on_notify()
    """

    def __init__(self, account: AccountSession, on_disconnect: Optional[Callable[[str], Any]] = None, proxy_url: Optional[str] = None):
        self.account = account
        self.on_disconnect = on_disconnect
        if proxy_url is None:
            try:
                from proxy import get_proxy_for_account
                self.proxy_url = get_proxy_for_account(account.email or account.user_id)
            except Exception:
                self.proxy_url = None
        else:
            self.proxy_url = proxy_url
        self.creds:  Optional[GateCredentials] = None
        self._gate:  Optional[GateClient]      = None
        self._spy_mode: bool                   = False
        self._packet_listeners: List[Callable] = []
        self._log_callback: Optional[Callable[[str], Any]] = None

    @property
    def log_callback(self) -> Optional[Callable[[str], Any]]:
        return self._log_callback

    @log_callback.setter
    def log_callback(self, cb: Optional[Callable[[str], Any]]):
        self._log_callback = cb
        if self._gate:
            self._gate.log_callback = cb

    @property
    def init_data(self) -> dict:
        return self._gate.init_data if self._gate else {}

    @property
    def memory_engine(self):
        """الوصول المباشر لمحرك الذاكرة الحية."""
        return self._gate.memory_engine if self._gate else None

    @property
    def cached_packets(self) -> dict:
        return self._gate.cached_packets if self._gate else {}

    @property
    def local_queues(self) -> list:
        return self._gate.local_queues if self._gate else []

    @property
    def spy_mode(self) -> bool:
        return self._gate.spy_mode if self._gate else self._spy_mode

    @spy_mode.setter
    def spy_mode(self, val: bool):
        self._spy_mode = bool(val)
        if self._gate:
            self._gate.spy_mode = bool(val)

    async def connect(self) -> bool:
        self.creds = await async_login(self.account, proxy_url=self.proxy_url)
        if not self.creds: return False
        if hasattr(self.creds, 'email') or not getattr(self.creds, 'email', None):
            self.creds.email = self.account.email
        self._gate = GateClient(self.creds, proxy_url=self.proxy_url)
        self._gate.on_disconnect = self.on_disconnect
        self._gate.spy_mode = self._spy_mode
        self._gate._packet_listeners = list(self._packet_listeners)
        self._gate.log_callback = self._log_callback
        return await self._gate.connect()

    @property
    def kick_reason(self) -> Optional[str]:
        return self._gate.kick_reason if self._gate else None

    async def query(self, cmd: str, subcmd: str, data: dict = None, timeout: float = 15, client_data: list = None) -> Optional[dict]:
        if not self._gate or not self._gate.is_connected: return None
        return await self._gate.query(cmd, subcmd, data, timeout, client_data)

    def send_nowait(self, cmd: str, subcmd: str, data: dict = None):
        if self._gate: self._gate.send_nowait(cmd, subcmd, data)

    def on_notify(self, notify_id: str, handler: Callable):
        if self._gate: self._gate.on_notify(notify_id, handler)

    def add_packet_listener(self, listener: Callable):
        if listener not in self._packet_listeners:
            self._packet_listeners.append(listener)
        if self._gate:
            self._gate.add_packet_listener(listener)

    def remove_packet_listener(self, listener: Callable):
        if listener in self._packet_listeners:
            self._packet_listeners.remove(listener)
        if self._gate:
            self._gate.remove_packet_listener(listener)

    def check_and_merge_controller(self, ctrl_name: str) -> Tuple[bool, dict]:
        """تفويض مباشر لـ GateClient.check_and_merge_controller."""
        if self._gate:
            return self._gate.check_and_merge_controller(ctrl_name)
        return False, {}

    async def wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True, grace_period: float = 0.0) -> bool:
        """تفويض مباشر لبوابة جاهزية الذاكرة في GateClient."""
        if self._gate:
            return await self._gate.wait_for_memory_ready(timeout=timeout, auto_fetch_missing=auto_fetch_missing, grace_period=grace_period)
        return False

    async def close(self):
        if self._gate: await self._gate.close()

    def abort(self):
        """قطع فوري قسري للاتصال دون أي انتظار."""
        if self._gate:
            self._gate.abort()

    @property
    def is_connected(self) -> bool:
        return self._gate is not None and self._gate.is_connected

    @property
    def uid(self) -> str:
        return self.creds.uid if self.creds else ""

    @property
    def kingdom_id(self) -> str:
        return self.creds.kingdom_id if self.creds else ""

    @property
    def server_name(self) -> str:
        return self.creds.server_name if self.creds else ""

    @property
    def active_connection_info(self) -> Dict[str, Any]:
        """معلومات المقبس والـ IP الحقيقي الفعلي للاتصال اللحظي في الذاكرة."""
        if self._gate and hasattr(self._gate, "active_connection_info") and self._gate.active_connection_info:
            info = dict(self._gate.active_connection_info)
            info["is_live"] = self.is_connected
            return info
        return {
            "type": "socks5" if self.proxy_url else "direct",
            "real_ip": self.proxy_url.split("@")[-1].split(":")[0] if self.proxy_url else "direct",
            "peer": "",
            "is_proxied": bool(self.proxy_url),
            "is_live": self.is_connected
        }



# ════════════════════════════════════════════════════════════════════
#  MultiAccountManager — 500+ حساب متزامن
# ════════════════════════════════════════════════════════════════════

class MultiAccountManager:
    """
    يدير عدة حسابات بشكل متزامن (asyncio).

    مثال:
        mgr = MultiAccountManager()
        mgr.load_from_cache('session_cache.json')
        await mgr.connect_all(max_concurrent=50)
        results = await mgr.query_all('1033', '2', {})  # مهمة الميناء
    """

    def __init__(self):
        self._accounts:    List[AccountSession]       = []
        self._connections: Dict[str, GameConnection]  = {}

    def load_from_cache(self, cache_file: Optional[str] = None):
        if cache_file is None:
            cand = os.path.join(os.path.dirname(__file__), "database", "session_cache.json")
            cache_file = cand if os.path.exists(cand) else os.path.join(os.path.dirname(__file__), "session_cache.json")
        with open(cache_file, encoding='utf-8') as f:
            cache = json.load(f)
        for email, info in cache.get('accounts', {}).items():
            self._accounts.append(AccountSession(
                email      = email,
                user_id    = info['userId'],
                session_id = info['sessionId'],
            ))
        log.info(f"[MGR] Loaded {len(self._accounts)} accounts")
        return self

    def add_account(self, email: str, user_id: str, session_id: str):
        self._accounts.append(AccountSession(email, user_id, session_id))
        return self

    async def connect_all(self, max_concurrent: int = 50) -> Dict[str, bool]:
        """اتصال جماعي مع throttling"""
        sem     = asyncio.Semaphore(max_concurrent)
        results = {}

        async def _connect(acc: AccountSession):
            async with sem:
                conn = GameConnection(acc)
                ok   = await conn.connect()
                if ok:
                    self._connections[acc.email] = conn
                results[acc.email] = ok
                log.info(f"[MGR] {'✅' if ok else '❌'} {acc.email}")

        await asyncio.gather(*[_connect(a) for a in self._accounts])
        n = sum(v for v in results.values())
        log.info(f"[MGR] Connected: {n}/{len(self._accounts)}")
        return results

    async def query_all(self, cmd: str, subcmd: str, data: dict = None) -> Dict[str, Any]:
        tasks   = {e: c.query(cmd, subcmd, data) for e, c in self._connections.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), results))

    def get(self, email: str) -> Optional[GameConnection]:
        return self._connections.get(email)

    async def close_all(self):
        await asyncio.gather(*[c.close() for c in self._connections.values()])
        self._connections.clear()

    @property
    def connected_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_connected)

    @property
    def connections(self) -> Dict[str, GameConnection]:
        return self._connections


# ════════════════════════════════════════════════════════════════════
#  اختبار
# ════════════════════════════════════════════════════════════════════

async def _test():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    CACHE = os.path.join(os.path.dirname(__file__), 'database', 'session_cache.json')
    if not os.path.exists(CACHE):
        CACHE = os.path.join(os.path.dirname(__file__), 'session_cache.json')
    with open(CACHE, encoding='utf-8') as f:
        cache = json.load(f)

    print(f"\n{'═'*55}")
    print(f"  🔌 اختبار game_client.py")
    print(f"{'═'*55}")

    # اختبار حساب واحد
    email, info = next(iter(cache['accounts'].items()))
    acc  = AccountSession(email, info['userId'], info['sessionId'])
    conn = GameConnection(acc)

    ok = await conn.connect()
    if not ok:
        print("  [✗] فشل الاتصال!")
        return

    print(f"  [✓] متصل! uid={conn.uid} server={conn.server_name}\n")

    # مهمة الميناء
    print("  → cmd=1033 (مهمة الميناء)...")
    r = await conn.query('1033', '2', {})
    print(f"  ← {json.dumps(r, ensure_ascii=False)[:150] if r else 'None'}")

    await conn.close()
    print(f"\n  [✓] اكتمل الاختبار")
    print(f"{'═'*55}\n")


if __name__ == '__main__':
    asyncio.run(_test())
