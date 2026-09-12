# -*- coding: utf-8 -*-
"""
auto_elf_boss.py — البوت التلقائي المستمر للهجوم على نخبة العفريت (Infinite Elf Boss Runner)
════════════════════════════════════════════════════════════════════════════════════════════════
يقوم هذا البرنامج المستقل بتشغيل مهمة الهجوم على نخبة العفريت (Elite Boss - فئة 10) بشكل لا نهائي:
  1. يسجل الدخول مباشرة بالبريد وكلمة المرور عبر سيرفر ONEMT Passport دون الحاجة لأي ملفات إضافية.
  2. يبدأ بفحص الخريطة وإرسال كافة الفيالق المتوفرة بالقلعة ضد نخبة العفريت.
  3. عند امتلاء طوابير المسيرات بالكامل (QUEUE_FULL)، يدخل تلقائياً في وضع المراقبة والانتظار.
  4. ينتظر مدة الحشود ومسيرة العودة، مع عرض مؤقت حي متفاعل.
  5. فور عودة أي فيلق للقلعة، يكتشفه فوراً ويطلق هجوماً جديداً على نخبة عفريت جديدة.
  6. يستمر التكرار إلى ما لا نهاية حتى يوقفه المستخدم بالضغط على (Ctrl + C).
  7. ميزة الحماية الذكية للدخول من الجوال (other_device):
     - إذا دخل أحد على الحساب من جوال آخر، يكتشفه البوت فوراً في نفس اللحظة.
     - يتوقف البوت بأمان وينتظر دقيقة كاملة (60 ثانية) مع عداد تنازلي لإفساح المجال للاعب.
     - بعد انتهاء الدقيقة، يعيد تسجيل الدخول تلقائياً (ويجدد الجلسة بكلمة المرور) ويكمل هجوم نخبة العفريت مباشرة!
     - إذا كان اللاعب ما زال يلعب، ينتظر دقيقة أخرى وهكذا بدون أي توقف أو أخطاء.

طريقة التشغيل:
  python auto_elf_boss.py --email "fahed.K140@gmail.com" --password "mn@123450"
  python auto_elf_boss.py --email "daysofempire2024@gmail.com" --password "mercedes123"
  python auto_elf_boss.py --email "your_email@gmail.com"
  python auto_elf_boss.py
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import argparse
import asyncio
import hashlib
import json
import logging
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

from game_client import GameConnection, AccountSession
from tasks.elf_boss import ElfBossTask, DEFAULT_FORMATION_ID, DEFAULT_ATTACK_DELAY

# ── إعداد نظام التسجيل ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("auto_elf_boss")


# ════════════════════════════════════════════════════════════════════
#  بروتوكول المصادقة المباشرة عبر خوادم اللعبة (ONEMT SDK Passport)
# ════════════════════════════════════════════════════════════════════
APP_ID = "100002001"
APP_KEY_STR = "d252596f076c9213dce69cdb39d488ea"
APP_SIGN_MD5 = "47965E93AD48A1D34F9EF116405AA6CF"
API_URL = "https://apiuc.menaapp.net/v5/passport/login"


def encrypt_sdk_pwd(pwd: str) -> str:
    """خوارزمية تشفير كلمة المرور الخاصة بشركة ONEMT SDK."""
    inner = hashlib.md5(f"gqY6DBt{pwd}Oed76U0".encode('utf-8')).hexdigest()
    return hashlib.md5(inner.encode('utf-8')).hexdigest()


def sdk_login(email: str, password: str, device_id: Optional[str] = None) -> dict:
    """
    تسجيل الدخول المباشر إلى خوادم اللعبة عبر الإيميل وكلمة المرور فقط
    بدون الحاجة لأي ملفات خارجية أو محاكي أو استخراج مسبق للجلسة.
    """
    if not device_id:
        device_id = hashlib.md5(email.encode('utf-8')).hexdigest()

    pwd_hash = encrypt_sdk_pwd(password)

    reqdata_obj = {
        "name": email,
        "password": pwd_hash,
        "identifytype": "email"
    }
    reqdata_json = json.dumps(reqdata_obj, separators=(',', ':'), ensure_ascii=False)
    reqdata_encoded = urllib.parse.quote(reqdata_json, safe='')

    ts = str(int(time.time()))
    body_map = {
        "platform": "android",
        "appid": APP_ID,
        "timestamp": ts,
        "packagename": "and.onemt.boe.tr",
        "lang": "ar",
        "sdid": "",
        "channel": "googleplay",
        "rstatus": "0",
        "clientversion": "5.33.0",
        "sessionid": "",
        "originalid": "",
        "deviceid": device_id,
        "reqdata": reqdata_encoded,
        "securemode": "MD5"
    }

    sorted_map = {k: body_map[k] for k in sorted(body_map.keys())}
    json_to_sign = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)

    sign_str = json_to_sign + APP_KEY_STR + APP_SIGN_MD5
    sign_hash = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    sorted_map["sign"] = sign_hash

    final_json = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "appid": APP_ID,
        "User-Agent": "okhttp/3.14.9"
    }

    raw_text = ""
    try:
        try:
            import requests
            resp = requests.post(API_URL, data=final_json, headers=headers, timeout=12)
            raw_text = resp.text
            data = resp.json()
        except ImportError:
            req = urllib.request.Request(API_URL, data=final_json.encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_text = resp.read().decode('utf-8')
                data = json.loads(raw_text)

        rtncode = data.get('rtncode', '')
        if rtncode in ('0', '00000', 'SUCCESS', 0):
            rspdata = data.get('rspdata')
            if isinstance(rspdata, str) and rspdata:
                rspdata = json.loads(urllib.parse.unquote(rspdata))
            return {
                "success": True,
                "userId": rspdata.get('userid') or rspdata.get('userId'),
                "sessionId": rspdata.get('sessionid') or rspdata.get('sessionId'),
                "raw": data
            }
        else:
            return {
                "success": False,
                "error_code": rtncode,
                "error_msg": data.get('rtnmsg', 'Login failed'),
                "raw": data
            }
    except Exception as e:
        return {
            "success": False,
            "error_msg": f"فشل الاتصال بخادم المصادقة: {e}",
            "raw": raw_text
        }


# ════════════════════════════════════════════════════════════════════
#  محرك البوت المستمر لنخبة العفريت (Infinite Runner)
# ════════════════════════════════════════════════════════════════════

class InfiniteElfBossRunner:
    """
    محرك التشغيل المستمر لمهمة نخبة العفريت مع:
      1. تسجيل الدخول المباشر سحابياً بالبريد وكلمة المرور.
      2. المراقبة الذكية لعودة الفيالق.
      3. الحماية الكاملة والانتظار دقيقة عند الدخول من جوال آخر (other_device).
    """

    def __init__(
        self,
        email: str,
        password: Optional[str] = None,
        formation_id: int = DEFAULT_FORMATION_ID,
        max_distance: Optional[float] = None,
        count: Optional[int] = None,
        all_legions: bool = True,
        attack_delay: float = DEFAULT_ATTACK_DELAY,
        poll_interval: int = 30,
        reconnect_wait: int = 60,
        ultra_safe: bool = False
    ):
        self.email = email
        self.password = password
        self.formation_id = formation_id
        self.max_distance = max_distance
        self.count = count
        self.all_legions = all_legions
        self.ultra_safe = ultra_safe
        self.attack_delay = max(28.0, attack_delay) if ultra_safe else attack_delay
        self.poll_interval = max(40, poll_interval) if ultra_safe else poll_interval
        self.reconnect_wait = reconnect_wait

        self.account: Optional[AccountSession] = None
        self.conn: Optional[GameConnection] = None
        self.task: Optional[ElfBossTask] = None

        self._disconnected_event = asyncio.Event()
        self._last_kick_reason = ""
        self._stop_requested = False

        # إحصائيات الجلسة
        self.total_attacks = 0
        self.total_rounds = 0
        self.session_start_time = time.time()

        # تتبع الأهداف المستهدفة عبر الدورات لمنع استهداف نفس الهدف
        self.shared_targeted_coords: Set[tuple] = set()
        self.shared_targeted_ids: Set[str] = set()
        self.target_timestamps: Dict[str, float] = {}

    def _on_disconnect(self, reason: str):
        """التعامل الفوري مع إشعار انقطاع الاتصال من السيرفر."""
        self._last_kick_reason = reason or "connection_lost"
        self._disconnected_event.set()
        if reason == "other_device":
            log.warning(f"⚠️ [تنبيه السيرفر] انقطع اتصال الحساب {self.email} (السبب: دخول من جهاز آخر)")
        else:
            log.warning(f"⚠️ [تنبيه السيرفر] انقطع اتصال الحساب {self.email} (السبب: {self._last_kick_reason})")

    def _try_load_cache(self) -> Dict[str, AccountSession]:
        """محاولة تحميل الجلسات المحفوظة محلياً كخيار احتياطي."""
        try:
            cache_file = os.path.join(_ROOT_DIR, "session_cache.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                res = {}
                for em, info in data.get("accounts", {}).items():
                    res[em] = AccountSession(
                        email=em,
                        user_id=info.get("userId", ""),
                        session_id=info.get("sessionId", "")
                    )
                return res
        except Exception:
            pass
        return {}

    def _try_save_cache(self, email: str, user_id: str, session_id: str):
        """حفظ الجلسة الجديدة في الكاش المحلي كإجراء اختياري دون التأثير على عمل البوت."""
        try:
            cache_file = os.path.join(_ROOT_DIR, "session_cache.json")
            data = {"accounts": {}}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {"accounts": {}}
            data.setdefault("accounts", {})[email] = {
                "userId": user_id,
                "sessionId": session_id,
                "timestamp": time.time(),
                "source": "sdk_password_login"
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def connect(self, force_new_login: bool = False) -> bool:
        """
        الاتصال بسيرفر اللعبة.

        force_new_login=True  → يستدعي sdk_login للحصول على session جديد
                                 (يُستخدم عند أول اتصال أو عند other_device)
        force_new_login=False → يُعيد الاتصال بنفس account الموجود دون sdk_login
                                 (يُستخدم عند reconnect الشبكي العادي)
        """
        self._disconnected_event.clear()
        self._last_kick_reason = ""

        # ── تسجيل الدخول السحابي: فقط عند الحاجة ──────────────────────────
        needs_sdk = self.password and (not self.account or force_new_login)
        if needs_sdk:
            log.info(f"🔐 جاري تسجيل الدخول سحابياً عبر خوادم ONEMT: {self.email}...")
            auth_res = await asyncio.to_thread(sdk_login, self.email, self.password)
            if auth_res.get('success'):
                uid = auth_res['userId']
                sid = auth_res['sessionId']
                self.account = AccountSession(email=self.email, user_id=uid, session_id=sid)
                log.info(f"✅ تم توثيق الحساب بنجاح! UID={uid}")
                self._try_save_cache(self.email, uid, sid)
            else:
                log.error(f"❌ فشل تسجيل الدخول: {auth_res.get('error_msg')} (كود: {auth_res.get('error_code')})")
                return False
        elif self.account:
            log.info(f"♻️ إعادة الاتصال بنفس الجلسة (UID={self.account.user_id}) دون login جديد...")
        else:
            # لا توجد كلمة مرور ولا account محفوظ — جرّب الكاش
            accounts = self._try_load_cache()
            self.account = accounts.get(self.email)

        if not self.account:
            log.error(f"❌ لا تتوفر جلسة أو كلمة مرور للحساب {self.email}!")
            return False

        self.conn = GameConnection(self.account, on_disconnect=self._on_disconnect)

        log.info(f"🌐 جاري الاتصال ببوابة اللعبة للحساب: {self.email}...")
        if not await self.conn.connect():
            log.warning("⚠️ تعذر الاتصال ببوابة اللعبة.")
            return False

        # انتظار تحميل حزم البداية
        for _ in range(20):
            await asyncio.sleep(0.3)
            if "cityCtrl" in self.conn.init_data:
                break
        await asyncio.sleep(0.3)
        log.info("✅ تم الاتصال ومزامنة بيانات القلعة بنجاح!")
        return True

    async def interruptible_sleep(self, seconds: float) -> bool:
        """
        نوم ذكي ينتبه فوراً لانقطاع الاتصال بدخول جوال آخر أو طلب الإيقاف دون تعليق.
        يعيد False فوراً إذا حدث انقطاع اتصال أو إيقاف.
        """
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self._stop_requested or self._disconnected_event.is_set():
                return False
            remaining = end_time - time.time()
            step = min(1.0, max(0.1, remaining))
            await asyncio.sleep(step)
        return True

    async def ensure_connected(self) -> bool:
        """
        التحقق المستمر من سلامة الاتصال:
        إذا رُصد دخول من جوال آخر، يتوقف فوراً وينتظر دقيقة ثم يعيد الدخول ويستأنف العمل.
        """
        if self._stop_requested:
            return False

        is_alive = bool(self.conn and self.conn.is_connected)
        if not is_alive or self._disconnected_event.is_set():
            return await self.wait_and_reconnect()

        return True

    async def wait_and_reconnect(self) -> bool:
        """
        الانتظار الذكي عند انقطاع الاتصال:
          - انقطاع شبكي (connection_lost): يعيد الاتصال فوراً بدون انتظار طويل.
          - دخول جهاز آخر (other_device): ينتظر دقيقة كاملة (60 ثانية) لإفساح المجال للاعب.
        """
        reason = self._last_kick_reason or "connection_lost"
        is_other_device = (reason == "other_device")

        if is_other_device:
            print("\n" + "!" * 75)
            log.warning("📱 [تنبيه: دخول من جوال آخر] تم رصد تسجيل دخول إلى الحساب من جهاز آخر!")
            log.warning("⏳ سيتوقف البوت مؤقتاً وينتظر دقيقة كاملة (60 ثانية) لإفساح المجال لك باللعب...")
            print("!" * 75 + "\n")
            wait_seconds = self.reconnect_wait  # 60 ثانية
        else:
            # انقطاع شبكي عادي: إعادة الاتصال بسرعة (5 ثوان فقط)
            log.warning(f"🔄 [انقطاع شبكي] جاري إعادة الاتصال تلقائياً خلال 5 ثوان...")
            wait_seconds = 5

        cycle = 0
        while not self._stop_requested:
            cycle += 1
            if cycle > 1 and is_other_device:
                log.info(f"⏳ [دورة انتظار ثانية] جاري الانتظار دقيقة أخرى (60 ثانية)...")
            elif cycle > 1:
                wait_seconds = min(wait_seconds * 2, 60)  # تضاعف تدريجي حتى 60 ثانية
                log.warning(f"🔄 [محاولة {cycle}] إعادة الاتصال خلال {wait_seconds} ثانية...")

            # عداد تنازلي
            wait_left = wait_seconds
            while wait_left > 0 and not self._stop_requested:
                if is_other_device and wait_left in (60, 50, 40, 30, 20, 10, 5):
                    log.info(f"⏳ [متبقي على محاولة الدخول]: {wait_left} ثانية...")
                step = min(5, wait_left)
                await asyncio.sleep(step)
                wait_left -= step

            if self._stop_requested:
                return False

            print("\n" + "━" * 70)
            if is_other_device:
                log.info("🔄 انتهت الدقيقة! جاري تسجيل الدخول الآن واستئناف هجوم نخبة العفريت...")
            else:
                log.info("🔄 جاري إعادة الاتصال بعد انقطاع الشبكة...")
            print("━" * 70)

            # إغلاق الاتصال القديم بأمان
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass

            self._disconnected_event.clear()
            self._last_kick_reason = ""

            # محاولة الدخول — بدون login جديد للانقطاع الشبكي، مع login جديد لـ other_device
            connected = await self.connect(force_new_login=is_other_device)
            if connected:
                log.info("🎉 تم تسجيل الدخول بنجاح تام! استئناف مهمة نخبة العفريت فوراً... ✅")
                await self._init_task()
                return True
            else:
                if is_other_device:
                    log.warning("⚠️ ما زال الحساب مشغولاً (اللاعب ما زال متصلاً من الجوال).")
                    log.info("⏳ سيتم الانتظار دقيقة أخرى (60 ثانية) وإعادة المحاولة تلقائياً...")
                    wait_seconds = self.reconnect_wait
                else:
                    log.warning("⚠️ فشل إعادة الاتصال، سيتم المحاولة مجدداً...")

        return False

    async def _init_task(self):
        """تهيئة مهمة نخبة العفريت وحقن سجل الأهداف المشترك."""
        task_cfg = {
            "formation_id": self.formation_id,
            "boss_type": 10,  # نخبة العفريت حصراً
            "max_distance": self.max_distance,
            "count": self.count,
            "all_legions": self.all_legions,
            "delay": self.attack_delay,
            "max_march_troops": 200000,
            "ultra_safe": self.ultra_safe,
        }
        self.task = ElfBossTask(self.conn, task_cfg)
        await self.task.on_start()

        # دمج الأهداف المشتركة
        self.task._targeted_bosses.update(self.shared_targeted_coords)
        self.task._targeted_boss_ids.update(self.shared_targeted_ids)

    def _clean_expired_boss_targets(self, ttl_seconds: float = 900.0):
        """تنظيف الأهداف القديمة المنتهية (أكثر من 15 دقيقة) للسماح باستهداف الزعماء الجدد في نفس الإحداثيات."""
        now = time.time()
        expired_ids = [tid for tid, ts in self.target_timestamps.items() if (now - ts) > ttl_seconds]
        for tid in expired_ids:
            self.target_timestamps.pop(tid, None)
            self.shared_targeted_ids.discard(tid)
            if self.task:
                self.task._targeted_boss_ids.discard(tid)

    def _record_target(self, bx: int, by: int, tid: str):
        """تسجيل هدف حشد نشط."""
        self.shared_targeted_coords.add((bx, by))
        if tid:
            self.shared_targeted_ids.add(tid)
            self.target_timestamps[tid] = time.time()
        if self.task:
            self.task._targeted_bosses.add((bx, by))
            if tid:
                self.task._targeted_boss_ids.add(tid)

    async def run_single_round(self, round_num: int) -> int:
        """
        تنفيذ دورة هجوم واحدة:
        إرسال مسيرات متتالية حتى امتلاء كافة طوابير القلعة (QUEUE_FULL).
        تعيد عدد الفيالق التي تم إطلاقها بنجاح في هذه الدورة.
        """
        if not await self.ensure_connected():
            return 0

        self._clean_expired_boss_targets()

        # تفريغ السجلات المؤقتة للدورة السابقة
        self.task._busy_heroes.clear()
        self.task._used_army.clear()
        await self.task._load_heroes()
        self.task._detect_busy_heroes()

        log.info("━" * 65)
        log.info(f"🔄 [دورة رقم {round_num}] بدء فحص وتجهيز هجوم نخبة العفريت (فئة 10)...")
        log.info("━" * 65)

        successful_attacks = 0
        attempt = 0
        max_attempts = self.task.attack_count * 3

        while successful_attacks < self.task.attack_count and attempt < max_attempts:
            if self._stop_requested:
                break

            # التحقق من الاتصال قبل تجهيز كل فيلق
            if not await self.ensure_connected():
                break

            if attempt > 1:
                # مهلة هادئة وطبيعية وآمنة بين محاولات التجهيز لمنع تسارع الطلبات ومحاكاة السلوك البشري
                await self.interruptible_sleep(random.uniform(3.0, 5.0))

            current_legion = successful_attacks + 1
            log.info(f"⚔️ [الفيلق {current_legion}/{self.task.attack_count}] جاري البحث عن أقرب نخبة عفريت شاغرة...")

            bx, by, btype, itype, tid, dist, status = await self.task._find_unique_elf_boss()

            if not (self.conn and self.conn.is_connected) or self._disconnected_event.is_set():
                await self.ensure_connected()
                break

            if status != "OK" or bx is None or by is None or btype is None:
                if successful_attacks > 0:
                    log.info(f"🏁 تم استهداف جميع زعماء النخبة المتاحين حالياً ({successful_attacks} فيالق).")
                else:
                    log.warning(f"⚠️ لم يتم العثور على أي نخبة عفريت حالياً: {status}")
                break

            # إرسال الهجوم
            success, err_or_qid = await self.task._send_elf_attack(
                bx, by,
                boss_type=10,
                boss_instance_type=itype or 24,
                target_map_id=tid,
                legion_idx=current_legion
            )

            if success:
                successful_attacks += 1
                march_qid = err_or_qid
                self._record_target(bx, by, tid)
                log.info(f"🎉 الفيلق ({successful_attacks}) أُطلق بنجاح على نخبة العفريت عند ({bx-1}, {by-1})! 🏹 [معرف المسيرة: {march_qid}]")

                if successful_attacks < self.task.attack_count:
                    min_wait = 28.0 if self.ultra_safe else 20.0
                    safe_delay = max(min_wait, round(self.attack_delay + random.uniform(3.5, 11.5), 2))
                    log.info(f"🛡️ [أمان بشري فائق ومكافحة حظر] انتظار {safe_delay:.1f} ثانية بمؤقت عشوائي غير منتظم قبل تجهيز الفيلق التالي...")
                    if not await self.interruptible_sleep(safe_delay):
                        # انقطع الاتصال أثناء الانتظار
                        await self.ensure_connected()
                        break
            else:
                err_msg = str(err_or_qid)
                log.warning(f"⚠️ تعذر إرسال الفيلق {current_legion}: {err_msg}")

                if "QUEUE_FULL" in err_msg:
                    log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break
                if "NO_ARMY" in err_msg:
                    log.info("🛑 نفدت القوات المتاحة بالقلعة.")
                    break
                if "STAMINA_EMPTY" in err_msg:
                    log.info("🛑 نفدت طاقة اللورد.")
                    break
                if "NO_HEROES" in err_msg:
                    log.info("🛑 لا يتوفر أبطال شاغرون بالقلعة حالياً (جميع أبطال الحرب في مسيرات قائمة).")
                    break
                if "9007020" in err_msg or "HEROES_BUSY" in err_msg:
                    log.warning(f"⚠️ أبطال التشكيلة مشغولون في مسيرة/حشد قائم لم يعد بعد (كود: 9007020). جاري الانتقال للتشكيلة التالية أو الأبطال البدلاء...")
                    await self.interruptible_sleep(random.uniform(5.5, 9.5))
                    continue
                if "16001" in err_msg or "انقطع الاتصال" in err_msg or "Gate disconnected" in err_msg or "ConnectionError" in err_msg:
                    self._disconnected_event.set()
                    await self.ensure_connected()
                    break
                if not (self.conn and self.conn.is_connected) or self._disconnected_event.is_set():
                    await self.ensure_connected()
                    break
                # فحص أخطاء الخريطة والهدف (8035: الهدف مشغول بمعركة/حشد آخر، 8026: حشد نشط، 8002: انتهى/تغير)
                if "8035" in err_msg or "8026" in err_msg or "8002" in err_msg or ("80" in err_msg and "8004" not in err_msg):
                    self._record_target(bx, by, tid)
                    if "8035" in err_msg:
                        log.warning(f"⚠️ نخبة العفريت عند ({bx-1}, {by-1}) مشغولة بمعركة/حشد آخر وصل للحد الأقصى (كود: 8035). تم استبعادها والبحث عن نخبة أخرى...")
                    elif "8026" in err_msg:
                        log.warning(f"⚠️ نخبة العفريت عند ({bx-1}, {by-1}) لديها حشد نشط بالفعل (كود: 8026). تم استبعادها والبحث عن نخبة أخرى...")
                    elif "8002" in err_msg:
                        log.warning(f"⚠️ نخبة العفريت عند ({bx-1}, {by-1}) اختفت أو قُتلت (كود: 8002). تم استبعادها والبحث عن نخبة أخرى...")
                    else:
                        log.warning(f"⚠️ نخبة العفريت عند ({bx-1}, {by-1}) غير متاحة على الخريطة ({err_msg}). تم استبعادها والبحث عن نخبة أخرى...")
                    await self.interruptible_sleep(random.uniform(5.0, 9.0))
                    continue
                else:
                    await self.interruptible_sleep(random.uniform(5.0, 9.0))

        return successful_attacks

    async def wait_for_legions_to_return(self, last_attacks_count: int):
        """
        مرحلة انتظار عودة الفيالق:
          1. انتظار مبدئي آمن (مدة حشد العفريت 5 دقائق = 300 ثانية).
          2. فحص دوري متكرر كل (poll_interval) ثانية حتى تعود المسيرات إلى القلعة.
          3. فور توفر طابور أو أبطال، يتم استئناف الهجوم فوراً.
          4. إذا دخل أحد من الجوال أثناء الانتظار، ينتظر دقيقة ثم يكمل المراقبة.
        """
        log.info("╭" + "─" * 63 + "╮")
        log.info(f"│ ⏳ [مرحلة الانتظار] الفيالق تخوض حشود نخبة العفريت ({last_attacks_count} فيالق نشطة)")
        log.info("│ ⏳ مدة تجمع الحشد 5 دقائق (300ث) تليها مسيرة الهجوم والعودة")
        log.info(f"│ ⏳ جاري المراقبة الآلية حتى عودة الفيالق إلى القلعة...")
        log.info("╰" + "─" * 63 + "╯")

        # 1. انتظار مبدئي ذكي لمدة 380-420 ثانية (6.5 إلى 7 دقائق كاملة لتجمع الحشد والزحف والقتال) قبل بدء الفحص النشط
        initial_wait = (420 if self.ultra_safe else 380) if last_attacks_count > 0 else 45
        wait_step = 30
        passed = 0

        while passed < initial_wait and not self._stop_requested:
            if not await self.ensure_connected():
                break

            remaining = initial_wait - passed
            log.info(f"⏳ [حشود نشطة] متبقي تقديرياً على بدء زحف الفيالق وعودتها: {remaining} ثانية...")
            sleep_chunk = min(wait_step, remaining)
            if not await self.interruptible_sleep(sleep_chunk):
                # تم رصد دخول من جوال آخر أثناء النوم
                await self.ensure_connected()
                continue
            passed += sleep_chunk

        # 2. وضع الفحص الدوري النشط (Active Polling) كل poll_interval ثانية
        poll_count = 0
        while not self._stop_requested:
            if not await self.ensure_connected():
                break

            poll_count += 1
            log.info(f"🔍 [فحص رقم {poll_count}] التحقق من عودة الفيالق وجاهزية القلعة لإرسال هجوم جديد...")

            # تفريغ المشغولين وإعادة فحص حالة القلعة
            self.task._busy_heroes.clear()
            self.task._used_army.clear()
            await self.task._load_heroes()
            self.task._detect_busy_heroes()

            if not (self.conn and self.conn.is_connected) or self._disconnected_event.is_set():
                await self.ensure_connected()
                continue

            # البحث عن هدف لتجربة إرسال فيلق
            bx, by, btype, itype, tid, dist, status = await self.task._find_unique_elf_boss()

            if not (self.conn and self.conn.is_connected) or self._disconnected_event.is_set():
                await self.ensure_connected()
                continue

            if status == "OK" and bx and by:
                # تجربة إرسال الفيلق الأول العائد
                success, err_or_qid = await self.task._send_elf_attack(
                    bx, by,
                    boss_type=10,
                    boss_instance_type=itype or 24,
                    target_map_id=tid,
                    legion_idx=1
                )
                if success:
                    self.total_attacks += 1
                    self._record_target(bx, by, tid)
                    log.info(f"🎉 [عودة فيلق] عادت مسيرة للقلعة! تم إطلاق فيلق جديد فوراً على نخبة العفريت ({bx-1}, {by-1})! 🏹")
                    # تم إطلاق أول فيلق بنجاح! الخروج من حلقة الانتظار لإكمال بقية الفيالق المتاحة
                    break
                else:
                    err_msg = str(err_or_qid)
                    if "QUEUE_FULL" in err_msg:
                        log.info(f"⏳ [طوابير ممتلئة] الفيالق ما زالت في طريق العودة... إعادة الفحص بعد {self.poll_interval} ثانية.")
                    elif "NO_HEROES" in err_msg or "NO_ARMY" in err_msg or "HEROES_BUSY" in err_msg or "9007020" in err_msg:
                        log.info(f"⏳ [الأبطال/القوات مشغولون في الحشد] الفيالق ما زالت في طريق العودة للقلعة... إعادة الفحص بعد {self.poll_interval} ثانية.")
                    elif "16001" in err_msg or "انقطع الاتصال" in err_msg or "Gate disconnected" in err_msg or "ConnectionError" in err_msg:
                        self._disconnected_event.set()
                        await self.ensure_connected()
                        continue
                    elif "8035" in err_msg or "8026" in err_msg or "8002" in err_msg or ("80" in err_msg and "8004" not in err_msg):
                        self._record_target(bx, by, tid)
                        log.info(f"⚠️ نخبة العفريت عند ({bx-1}, {by-1}) غير متاحة ({err_msg})، تم استبعادها...")
                        continue
                    else:
                        log.debug(f"نتيجة الفحص: {err_msg}")
            else:
                log.info(f"ℹ️ لم يتم العثور على نخبة عفريت شاغرة في هذا الفحص ({status})، إعادة المحاولة بعد {self.poll_interval}ث...")

            if not (self.conn and self.conn.is_connected) or self._disconnected_event.is_set():
                await self.ensure_connected()
                continue

            # مؤقت فحص عشوائي غير منتظم يحاكي تفقد اللاعب لشاشة الهاتف
            sleep_step = max(35, int(self.poll_interval + random.uniform(-4, 12)))
            if not await self.interruptible_sleep(sleep_step):
                await self.ensure_connected()

    async def run_forever(self):
        """الحلقة الرئيسية اللانهائية لتشغيل مهمة العفريت باستمرار."""
        if not await self.connect():
            # إذا فشل الاتصال الأولي (مثلاً المستخدم داخل من الهاتف)، ادخل في وضع انتظار الدقيقة
            if not await self.wait_and_reconnect():
                return

        await self._init_task()

        print("\n" + "═" * 70)
        print("  👹 بدأ البوت التلقائي المستمر للهجوم على نخبة العفريت (Elf Boss Auto-Runner)")
        print(f"  • الحساب: {self.email}")
        print(f"  • التشكيلة الأساسية: {self.formation_id}")
        print(f"  • الهدف: نخبة العفريت (Elite Boss - فئة 10)")
        print(f"  • مهلة الأمان بين الهجمات: {self.attack_delay} ثوانٍ (+ تباين عشوائي غير منتظم)")
        print(f"  • فترة فحص عودة الفيالق: كل {self.poll_interval} ثانية")
        if self.ultra_safe:
            print("  🛡️ وضع الأمان الفائق الشامل (Ultra-Safe Mode): مُفعّل ✅ (فترات تأخير واستراحات بشرية مضاعفة)")
        print("  • حماية الجوال: عند دخولك من الهاتف ينتظر دقيقة (60ث) ثم يدخل ويكمل تلقائياً")
        print("  • للإيقاف في أي وقت: اضغط Ctrl + C")
        print("═" * 70 + "\n")

        round_num = 1
        try:
            while not self._stop_requested:
                if not await self.ensure_connected():
                    break

                # 1. إرسال دورة هجمات بكافة الفيالق المتوفرة
                attacks_sent = await self.run_single_round(round_num)
                if self._stop_requested:
                    break

                if attacks_sent > 0:
                    self.total_attacks += attacks_sent
                    self.total_rounds += 1
                    elapsed = str(timedelta(seconds=int(time.time() - self.session_start_time)))
                    log.info(
                        f"📊 [ملخص دورة {round_num}] أُرسل في هذه الدورة: {attacks_sent} فيالق | "
                        f"الإجمالي الكلي: {self.total_attacks} فيلق | وقت التشغيل: {elapsed}"
                    )

                # 2. انتظار عودة الفيالق ومراقبة جاهزيتها
                await self.wait_for_legions_to_return(attacks_sent)

                # 3. استراحة بشرية ذكية كل دورتين لمكافحة الحظر وتشتيت خوارزميات كشف البوتات
                if round_num % 2 == 0 and not self._stop_requested:
                    rest_time = random.randint(180, 360) if self.ultra_safe else random.randint(90, 210)
                    rest_mins = rest_time // 60
                    rest_secs = rest_time % 60
                    log.info("╭" + "─" * 65 + "╮")
                    log.info(f"│ ☕ [استراحة بشرية فائقة الأمان لمكافحة الحظر] توقف مؤقت: {rest_time} ثانية ({rest_mins} دقيقة و {rest_secs} ثانية)")
                    log.info("│ ☕ لمحاكاة إغلاق الهاتف أو انشغال اللاعب البشري وتشتيت أنظمة المراقبة...")
                    log.info("╰" + "─" * 65 + "╯")
                    if not await self.interruptible_sleep(rest_time):
                        await self.ensure_connected()

                round_num += 1

        except (KeyboardInterrupt, asyncio.CancelledError):
            log.info("\n🛑 تم استلام إشارة إيقاف البرنامج من المستخدم (Ctrl+C)...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """إغلاق الاتصال بأمان وعرض ملخص الإحصائيات النهائي."""
        self._stop_requested = True
        if self.conn:
            try:
                await self.conn.close()
            except Exception:
                pass

        uptime = str(timedelta(seconds=int(time.time() - self.session_start_time)))
        print("\n" + "═" * 70)
        print("  🛑 تم إيقاف البوت التلقائي بنجاح.")
        print("  📊 ملخص نتائج الجلسة:")
        print(f"     • إجمالي الدورات المنفذة: {self.total_rounds}")
        print(f"     • إجمالي فيالق نخبة العفريت المطلقة: {self.total_attacks} فيلق 🏹")
        print(f"     • مدة التشغيل الكلية: {uptime}")
        print("  👋 مع السلامة!")
        print("═" * 70 + "\n")


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول الرئيسية لسطر الأوامر (Main CLI Entrypoint)
# ════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Auto Elf Boss Runner — البوت المستمر التلقائي للهجوم على نخبة العفريت"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب [افتراضي: meik.gaertner2306.MGr@gmail.com أو أول حساب متاح]")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب للتسجيل المباشر سحابياً بدون الحاجة لملفات")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, help="رقم التشكيلة الأساسية (1..6) [افتراضي: 1]")
    parser.add_argument("--delay", "-d", type=float, default=DEFAULT_ATTACK_DELAY, help=f"مهلة الأمان الأساسية بين كل هجوم والآخر بالثواني [افتراضي: {DEFAULT_ATTACK_DELAY}]")
    parser.add_argument("--poll-interval", "-p_int", type=int, default=30, help="فترة الانتظار بالثواني بين كل فحص لعودة الفيالق [افتراضي: 30 ثانية]")
    parser.add_argument("--max-distance", type=float, default=None, help="أقصى مسافة مسموحة للعفريت بالكيلومتر [افتراضي: بدون حد]")
    parser.add_argument("--count", "-c", type=int, default=None, help="عدد الفيالق المستهدفة في كل دورة [افتراضي: كل الفيالق المتاحة]")
    parser.add_argument("--reconnect-wait", type=int, default=60, help="فترة الانتظار بالثواني عند دخول جوال آخر [افتراضي: 60 ثانية (دقيقة كاملة)]")
    parser.add_argument("--ultra-safe", "-safe", action="store_true", help="تفعيل وضع الأمان الفائق الشامل (فترات تأخير بشرية موسعة واستراحات عشوائية ضد الحظر)")
    args = parser.parse_args()

    if args.ultra_safe:
        args.delay = max(args.delay, 28.0)
        args.poll_interval = max(args.poll_interval, 45)

    target_email = args.email
    target_password = args.password

    # فحص الكاش الاحتياطي كخيار إضافي إن وجد
    cache_file = os.path.join(_ROOT_DIR, "session_cache.json")
    cached_accounts = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_accounts = json.load(f).get("accounts", {})
        except Exception:
            pass

    if not target_email:
        if "meik.gaertner2306.MGr@gmail.com" in cached_accounts:
            target_email = "meik.gaertner2306.MGr@gmail.com"
        elif cached_accounts:
            target_email = next(iter(cached_accounts.keys()))
        else:
            try:
                target_email = input("📧 أدخل البريد الإلكتروني للحساب: ").strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

    if not target_password and target_email not in cached_accounts:
        print(f"\nℹ️ الحساب '{target_email}' لا توجد له جلسة مسجلة مسبقاً.")
        try:
            target_password = input(f"🔑 أدخل كلمة المرور للحساب ({target_email}): ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

    runner = InfiniteElfBossRunner(
        email=target_email,
        password=target_password,
        formation_id=args.formation,
        max_distance=args.max_distance,
        count=args.count,
        all_legions=args.count is None,
        attack_delay=args.delay,
        poll_interval=args.poll_interval,
        reconnect_wait=args.reconnect_wait,
        ultra_safe=args.ultra_safe
    )

    try:
        asyncio.run(runner.run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
