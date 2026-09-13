# -*- coding: utf-8 -*-
"""
api_server.py — خادم FastAPI لإدارة البوتات
══════════════════════════════════════════════════════════════════════
يستقبل أوامر من لوحة التحكم (React) ويشغّل/يوقف bot_manager.py.

يعمل محلياً على المنفذ 8000 — وعلى Hostinger VPS بنفس الكود.

التشغيل:
  python api_server.py
  python api_server.py --port 8000 --host 0.0.0.0
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os, sys, json, time, logging, argparse, subprocess, threading, asyncio, queue
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── FastAPI imports ────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_ROOT, "api_server.log"), encoding="utf-8"),
    ]
)
log = logging.getLogger("api_server")

# ══════════════════════════════════════════════════════════════════
# FastAPI App
# ══════════════════════════════════════════════════════════════════

app = FastAPI(title="Empire Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # في الإنتاج: حدد domain لوحة التحكم
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════
# إدارة العمليات (Thread-safe)
# ══════════════════════════════════════════════════════════════════

_lock       = threading.Lock()
_procs:   Dict[str, subprocess.Popen]   = {}   # castle_id → subprocess
_reserved: Set[str]                     = set() # castle_ids محجوزة (بدأت لكن لم تُسجَّل بعد)
_log_qs:  Dict[str, "queue.Queue[str]"] = {}    # castle_id → queue للـ logs
_conn_states: Dict[str, str]            = {}    # castle_id → 'connected' | 'disconnected' | 'reconnecting'
_user_stopped: Set[str]                 = set() # castle_ids التي تم إيقافها يدوياً من المستخدم
_castle_emails: Dict[str, str]          = {}    # castle_id → email


def _is_running(castle_id: str) -> bool:
    if castle_id in _reserved:
        return True
    proc = _procs.get(castle_id)
    return proc is not None and proc.poll() is None


def _get_real_status(castle_id: str) -> str:
    """الحالة الحقيقية: العملية + حالة اتصال اللعبة معاً."""
    with _lock:
        if castle_id in _reserved:
            return 'starting'
        proc = _procs.get(castle_id)
        if proc is None or proc.poll() is not None:
            return 'idle'  # العملية متوقفة
        # العملية شغالة — هل الاتصال بالجيم سيرفر نشط؟
        conn = _conn_states.get(castle_id, 'connected')  # إذا لم يُبلَّغ بعد → نفترض متصل
        if conn == 'disconnected':
            return 'disconnected'  # شخص دخل من الجوال
        if conn == 'reconnecting':
            return 'reconnecting'
        if conn == 'waiting':
            return 'waiting'
        return 'running'


# ══════════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════════

class StartBotRequest(BaseModel):
    castle_id:  str
    user_id:    str
    email:      str
    password:   Optional[str] = None
    config:     Dict[str, Any] = {}
    loop_interval: int = 90   # دقيقة

class StopBotRequest(BaseModel):
    castle_id: str


# ══════════════════════════════════════════════════════════════════
# Firebase helper (لتحديث bot_status)
# ══════════════════════════════════════════════════════════════════

def _update_firebase_status(user_id: str, castle_id: str, state: str, message: str = "", conn_state: Optional[str] = None):
    """يحدّث bot_status في Firestore (state + conn_state + message)."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_fs

        sak = os.path.join(_ROOT, "firebase_service_account.json")
        if not firebase_admin._apps:
            if os.path.exists(sak):
                cred = credentials.Certificate(sak)
                firebase_admin.initialize_app(cred)

        if firebase_admin._apps:
            db = fb_fs.client()
            ref = db.collection("users").document(user_id).collection("castles").document(castle_id)
            now_iso = datetime.now(timezone.utc).isoformat()
            updates: dict = {
                "bot_status.state":            state,
                "bot_status.last_run_message": message,
            }
            if conn_state is not None:
                updates["bot_status.conn_state"]   = conn_state
                updates["bot_status.conn_message"] = message
                updates["bot_status.conn_updated"] = now_iso
            elif state in ("idle", "error"):
                updates["bot_status.conn_state"]   = state
                updates["bot_status.conn_message"] = message
                updates["bot_status.conn_updated"] = now_iso
            elif state == "running":
                updates["bot_status.conn_state"]   = "connected"
                updates["bot_status.conn_message"] = message or "البوت متصل بالقلعة ويعمل الآن"
                updates["bot_status.last_run_time"] = now_iso
                updates["bot_status.conn_updated"] = now_iso
            elif state == "waiting":
                updates["bot_status.conn_state"]   = "waiting"
                updates["bot_status.conn_message"] = message or "بانتظار الدورة القادمة"
                updates["bot_status.conn_updated"] = now_iso

            ref.update(updates)
    except Exception as e:
        log.debug(f"Firebase status update skipped: {e}")


def update_firebase_status_async(user_id: str, castle_id: str, state: str, message: str = "", conn_state: Optional[str] = None):
    """تحديث Firestore في thread منفصل فوراً دون تعطيل القراءة من stdout."""
    threading.Thread(
        target=_update_firebase_status,
        args=(user_id, castle_id, state, message, conn_state),
        daemon=True,
        name=f"fb-sync-{castle_id[:8]}"
    ).start()


def _sync_castle_to_firebase(email: str, data: dict, user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """تحديث موارد وبيانات القلعة في Firestore فوراً."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_fs
        sak = os.path.join(_ROOT, "firebase_service_account.json")
        if not firebase_admin._apps:
            if os.path.exists(sak):
                firebase_admin.initialize_app(credentials.Certificate(sak))
        if firebase_admin._apps:
            db = fb_fs.client()
            target_ref = None
            if user_id and castle_id:
                target_ref = db.collection("users").document(user_id).collection("castles").document(castle_id)
            else:
                for u in db.collection("users").stream():
                    for c in db.collection("users").document(u.id).collection("castles").stream():
                        if c.to_dict().get("email", "").strip().lower() == email.strip().lower():
                            target_ref = db.collection("users").document(u.id).collection("castles").document(c.id)
                            break
                    if target_ref:
                        break
            if target_ref:
                flat_data = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        for subk, subv in v.items():
                            flat_data[f"{k}.{subk}"] = subv
                    else:
                        flat_data[k] = v
                target_ref.update(flat_data)
                log.info(f"💾 [API Sync] تم تحديث موارد وبيانات القلعة {email} في Firestore بنجاح ✅")
    except Exception as e:
        log.warning(f"⚠️ [API Sync Warning]: {e}")


# ══════════════════════════════════════════════════════════════════
# تشغيل البوت في thread منفصل
# ══════════════════════════════════════════════════════════════════

def _bot_thread(req: StartBotRequest):
    castle_id = req.castle_id
    user_id   = req.user_id
    email     = req.email

    # 1. إعداد queue للـ logs
    log_q: "queue.Queue[str]" = queue.Queue(maxsize=500)
    with _lock:
        _log_qs[castle_id] = log_q
        _castle_emails[castle_id] = email

    log.info(f"🚀 [{email}] بدء تشغيل البوت...")
    _update_firebase_status(user_id, castle_id, "running", "البوت يعمل الآن...")

    # 2. تسجيل الدخول إذا لم تكن الجلسة موجودة
    if req.password:
        try:
            from core.session_manager import SessionManager
            sm = SessionManager()
            sessions = sm.load()
            if email not in sessions:
                log.info(f"🔑 [{email}] تسجيل دخول جديد...")
                sm.login_and_save(email, req.password)
                log_q.put(f"[{datetime.now():%H:%M:%S}] 🔑 تسجيل دخول بنجاح")
        except Exception as e:
            log.warning(f"⚠️ [{email}] جلسة: {e}")
            log_q.put(f"[{datetime.now():%H:%M:%S}] ⚠️ تحذير: {e}")

    # 3. كتابة ملف إعدادات Firebase
    config_path = os.path.join(_ROOT, f".bot_cfg_{castle_id}.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(req.config, f, ensure_ascii=False)
    except Exception as e:
        log.error(f"❌ [{email}] فشل كتابة config: {e}")
        with _lock:
            _reserved.discard(castle_id)
        _update_firebase_status(user_id, castle_id, "error", str(e))
        return

    # 4. بناء الأمر
    cmd = [
        sys.executable,
        os.path.join(_ROOT, "bot_manager.py"),
        "--email",              email,
        "--firebase-user-id",   user_id,
        "--firebase-castle-id", castle_id,
        "--firebase-config",    config_path,
        "--loop",
        "--loop-interval",      str(req.loop_interval),
    ]
    log.info(f"▶️  [{email}] cmd: bot_manager.py --firebase-config ... --loop")
    log_q.put(f"[{datetime.now():%H:%M:%S}] ▶️  بدء البوت...")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    # 5. ملف log البوت
    bot_log_path = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")

    try:
        with open(bot_log_path, "a", encoding="utf-8", errors="replace") as lf:
            lf.write(f"\n{'='*60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] دورة جديدة\n{'='*60}\n")
            lf.flush()

            proc = subprocess.Popen(
                cmd, cwd=_ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1,
            )

        with _lock:
            _procs[castle_id] = proc
            _reserved.discard(castle_id)

        # 6. قراءة stdout في thread آخر — يحلل السطور لمعرفة حالة الاتصال ومزامنتها مع Firebase
        def _reader():
            """يقرأ stdout كل سطر ويُحدّث Firebase فوراً بمجرد ظهور إشارة الانقطاع أو الاتصال أو الانتظار."""
            DISCONNECT_SIGNALS = (
                "دخول من جهاز آخر",       # 📱 [تنبيه: دخول من جهاز آخر]
                "انقطع اتصال الحساب",     # ⚠️ [تنبيه السيرفر] انقطع اتصال الحساب
                "other_device",
                "Other Device Login",
            )
            RECONNECTING_SIGNALS = (
                "سيتوقف البوت مؤقتاً",    # ⏳ ينتظر 60 ثانية
                "جاري إعادة الاتصال",     # 🔄 [انقطاع شبكي]
                "متبقي على محاولة",       # ⏳ [متبقي] عداد تنازلي
            )
            CONNECTED_SIGNALS = (
                "تم الاتصال والمصافحة بنجاح 100%",  # ✅ login_and_connect
                "تم الاتصال بنجاح!",
            )
            WAITING_SIGNALS = (
                "انتظار",                 # 💤 انتظار X دقيقة...
                "الدورة القادمة الساعة",  # ✅ انتهت الدورة #X — الدورة القادمة الساعة: ...
            )
            try:
                with open(bot_log_path, "a", encoding="utf-8", errors="replace") as lf:
                    for line in proc.stdout:
                        line = line.rstrip("\n")
                        lf.write(line + "\n")
                        lf.flush()
                        stamped = f"[{datetime.now():%H:%M:%S}] {line}"
                        try:
                            log_q.put_nowait(stamped)
                        except queue.Full:
                            pass

                        # ── 1. فحص وسوم الأحداث الصريحة القادمة من البوت ──
                        if "[FIREBASE_EVENT]" in line:
                            try:
                                parts = line.split("[FIREBASE_EVENT]", 1)[1].strip()
                                ev_state = ""
                                ev_msg = ""
                                for token in parts.split():
                                    if token.startswith("conn_state="):
                                        ev_state = token.split("=", 1)[1]
                                    elif token.startswith("message="):
                                        ev_msg = token.split("=", 1)[1]
                                if ev_state:
                                    with _lock:
                                        _conn_states[castle_id] = ev_state
                                    bs = "idle" if ev_state == "idle" else ("waiting" if ev_state == "waiting" else "running")
                                    update_firebase_status_async(user_id, castle_id, bs, ev_msg or line, ev_state)
                            except Exception:
                                pass

                        elif "[RESOURCE_SYNC]" in line:
                            try:
                                parts = line.split("[RESOURCE_SYNC]", 1)[1].strip()
                                rmap = {}
                                for token in parts.split():
                                    if "=" in token:
                                        k, v = token.split("=", 1)
                                        if v.lstrip("-").isdigit():
                                            rmap[k] = int(v)
                                if rmap:
                                    now_iso = datetime.now(timezone.utc).isoformat()
                                    r_data = {
                                        "food":         rmap.get("food", 0),
                                        "wood":         rmap.get("wood", 0),
                                        "iron":         rmap.get("iron", 0),
                                        "diamond":      rmap.get("diamond", 0),
                                        "gold":         rmap.get("gold", 0),
                                        "stamina":      rmap.get("stamina", 100),
                                        "last_updated": now_iso,
                                    }
                                    c_data = {}
                                    if "power" in rmap:
                                        c_data["lord_power"] = rmap["power"]
                                    _sync_castle_to_firebase(
                                        email,
                                        {"resources": r_data, "castle_info": c_data} if c_data else {"resources": r_data},
                                        user_id=user_id,
                                        castle_id=castle_id,
                                    )
                            except Exception as ex:
                                log.debug(f"Resource sync parse error: {ex}")

                        # ── 2. فحص السطر بالكلمات المفتاحية لتحديث Firebase ──
                        elif any(s in line for s in DISCONNECT_SIGNALS):
                            with _lock:
                                _conn_states[castle_id] = 'disconnected'
                            log.info(f"📶 [{castle_id[:12]}] انقطاع الاتصال (دخول من جهاز آخر) → disconnected")
                            update_firebase_status_async(user_id, castle_id, 'running', 'تم تسجيل الدخول من جهاز آخر — البوت متوقف مؤقتاً', 'disconnected')
                        elif any(s in line for s in RECONNECTING_SIGNALS):
                            with _lock:
                                _conn_states[castle_id] = 'reconnecting'
                            update_firebase_status_async(user_id, castle_id, 'running', 'جاري إعادة الاتصال بالقلعة...', 'reconnecting')
                        elif any(s in line for s in CONNECTED_SIGNALS):
                            with _lock:
                                _conn_states[castle_id] = 'connected'
                            log.info(f"✅ [{castle_id[:12]}] اتصال نشط → connected")
                            update_firebase_status_async(user_id, castle_id, 'running', 'البوت متصل بالقلعة ويعمل الآن', 'connected')
                        elif any(s in line for s in WAITING_SIGNALS):
                            with _lock:
                                _conn_states[castle_id] = 'waiting'
                            log.info(f"💤 [{castle_id[:12]}] بانتظار الدورة القادمة → waiting")
                            update_firebase_status_async(user_id, castle_id, 'running', 'بانتظار موعد الدورة القادمة...', 'waiting')
            except Exception:
                pass

        reader_t = threading.Thread(target=_reader, daemon=True)
        reader_t.start()


        # 7. انتظار انتهاء العملية مع فحص إيقاف
        while proc.poll() is None:
            time.sleep(5)

        ret = proc.returncode

    except Exception as e:
        log.error(f"💥 [{email}] خطأ: {e}")
        log_q.put(f"[{datetime.now():%H:%M:%S}] 💥 خطأ: {e}")
        _update_firebase_status(user_id, castle_id, "error", str(e), conn_state="error")
        with _lock:
            _procs.pop(castle_id, None)
            _reserved.discard(castle_id)
        return
    finally:
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except Exception:
            pass

    # 8. تنظيف وتحديث الحالة
    was_user_stopped = False
    with _lock:
        _procs.pop(castle_id, None)
        _log_qs.pop(castle_id, None)
        _conn_states.pop(castle_id, None)  # تنظيف حالة الاتصال
        if castle_id in _user_stopped:
            _user_stopped.discard(castle_id)
            was_user_stopped = True

    if was_user_stopped:
        end_msg = f"[{datetime.now():%H:%M:%S}] ⏹️ تم إيقاف البوت بواسطة المستخدم"
        log_q.put(end_msg)
        log.info(f"⏹️ [{email}] تم الإيقاف يدوياً بواسطة المستخدم")
        _update_firebase_status(
            user_id, castle_id,
            "idle",
            "تم إيقاف البوت بواسطة المستخدم",
            conn_state="idle"
        )
    elif ret != 0:
        end_msg = f"[{datetime.now():%H:%M:%S}] 💥 توقف بسبب مشكلة فادحة (كود={ret})"
        log_q.put(end_msg)
        log.error(f"💥 [{email}] توقف بسبب خطأ فادح (exit={ret})")
        _update_firebase_status(
            user_id, castle_id,
            "error",
            f"توقف بسبب مشكلة فادحة في التشغيل (كود={ret})",
            conn_state="error"
        )
    else:
        # انتهت العملية بدون إيقاف يدوي — في وضع التكرار أو انتهاء دورة عادية
        end_msg = f"[{datetime.now():%H:%M:%S}] 💤 بانتظار موعد الدورة القادمة"
        log_q.put(end_msg)
        log.info(f"💤 [{email}] اكتمال دورة — البوت لا يزال مفعلاً وبانتظار الدورة التالية")
        _update_firebase_status(
            user_id, castle_id,
            "running",
            "بانتظار موعد الدورة القادمة",
            conn_state="waiting"
        )



# ══════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "online", "service": "Empire Bot API", "time": datetime.now().isoformat()}


@app.post("/api/bot/start")
def start_bot(req: StartBotRequest):
    """تشغيل بوت لقلعة معينة."""
    with _lock:
        if _is_running(req.castle_id):
            return {"status": "already_running", "castle_id": req.castle_id, "email": req.email}
        _reserved.add(req.castle_id)  # حجز فوري لمنع التكرار

    t = threading.Thread(target=_bot_thread, args=(req,), daemon=True, name=f"bot-{req.castle_id[:10]}")
    t.start()
    log.info(f"▶️  [{req.email}] طلب تشغيل قُبل")
    return {"status": "starting", "castle_id": req.castle_id, "email": req.email}


@app.post("/api/bot/stop/{castle_id}")
def stop_bot(castle_id: str):
    """إيقاف بوت قلعة معينة بناءً على طلب المستخدم."""
    with _lock:
        proc = _procs.get(castle_id)
        _user_stopped.add(castle_id)

    if proc and proc.poll() is None:
        proc.terminate()
        log.info(f"⏹️  إيقاف القلعة {castle_id[:16]} بواسطة المستخدم...")
        return {"status": "stopping", "castle_id": castle_id}

    return {"status": "not_running", "castle_id": castle_id}


@app.get("/api/bot/status")
def get_all_status():
    """حالة جميع البوتات النشطة."""
    with _lock:
        result = {}
        for cid, proc in _procs.items():
            result[cid] = "running" if proc.poll() is None else "idle"
        for cid in _reserved:
            result[cid] = "starting"
    return {"bots": result, "count": len(result)}


@app.get("/api/bot/status/{castle_id}")
def get_status(castle_id: str):
    """حالة بوت قلعة معينة."""
    return {"castle_id": castle_id, "status": _get_real_status(castle_id)}


# ── endpoint يستقبل حالة اتصال اللعبة من bot_manager مباشرةً ──────
class ConnStateRequest(BaseModel):
    castle_id: str
    state: str  # 'connected' | 'disconnected' | 'reconnecting'

@app.post("/api/bot/conn-state")
def update_conn_state(req: ConnStateRequest):
    """يُستدعى من bot_manager لإبلاغ الـ API عن حالة اتصال اللعبة الفعلية."""
    with _lock:
        if req.state in ('connected', 'disconnected', 'reconnecting'):
            _conn_states[req.castle_id] = req.state
        elif req.state == 'idle':
            _conn_states.pop(req.castle_id, None)
    log.info(f"📶 [{req.castle_id[:12]}] conn-state → {req.state}")
    return {"ok": True}


@app.get("/api/castle-data/{email}")
async def get_castle_data(email: str, user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """
    جلب بيانات القلعة والموارد الحية فوراً بالاتصال المباشر مع سيرفر اللعبة ومزامنتها مع Firestore.
    """
    try:
        from core.session_manager import SessionManager
        from game_client import GameConnection

        # 1. تحميل جلسة الحساب
        sm = SessionManager()
        sessions = sm.load()
        account = sessions.get(email)
        if not account:
            raise HTTPException(status_code=404, detail=f"الحساب {email} غير موجود في session_cache.json")

        # 2. الاتصال بالسيرفر
        conn = GameConnection(account)
        ok = await asyncio.wait_for(conn.connect(), timeout=15)
        if not ok:
            raise HTTPException(status_code=503, detail="تعذر الاتصال بسيرفر اللعبة")

        # 3. انتظار حزم التهيئة
        for _ in range(25):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0:
                break

        # 4. استخراج البيانات الأساسية والموارد
        lord_ctrl  = conn.init_data.get("lordInfoCtrl", {})
        base_info  = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
        fc_info    = lord_ctrl.get("fcInfo", {}) if isinstance(lord_ctrl, dict) else {}
        city_ctrl  = conn.init_data.get("cityCtrl", {})
        reslist    = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}

        food    = int(float(reslist.get("1002", 0)))
        wood    = int(float(reslist.get("1003", 0)))
        iron    = int(float(reslist.get("1004", 0)))
        diamond = int(float(reslist.get("1005", 0)))
        gold    = int(base_info.get("gold", 0))
        stamina = int(base_info.get("health", 100))
        pos     = base_info.get("sourcePos", {})
        coords  = {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))}

        castle_lv  = 0
        walls_lv   = 0

        # استعلام المباني لجلب مستوى القلعة
        try:
            r_city = await asyncio.wait_for(conn.query("1001", "1", {}, timeout=8), timeout=10)
            blist  = r_city.get("data", {}).get("blist", []) if r_city else []
            if not blist and "cityCtrl" in conn.init_data:
                blist = conn.init_data["cityCtrl"].get("blist", [])
            for b in blist:
                bid = int(b.get("bid", 0))
                lv  = int(b.get("lv", 0))
                if bid == 101:
                    castle_lv = lv
                elif bid == 102:
                    walls_lv  = lv
        except Exception:
            pass

        # 5. إغلاق الاتصال بأمان
        try:
            await conn.close()
        except Exception:
            pass

        now_iso = datetime.now(timezone.utc).isoformat()
        res_data = {
            "food":         food,
            "wood":         wood,
            "iron":         iron,
            "diamond":      diamond,
            "gold":         gold,
            "stamina":      stamina,
            "last_updated": now_iso,
        }
        cinfo_data = {
            "lord_name":    str(base_info.get("nickName", email.split("@")[0])),
            "lord_power":   int(fc_info.get("totalFc", 0)),
            "castle_level": max(1, castle_lv),
            "walls_level":  walls_lv,
            "server_id":    int(base_info.get("partition", 1)) if str(base_info.get("partition")).isdigit() else 1,
            "coordinates":  coords,
            "uid":          str(base_info.get("uid", getattr(account, "user_id", ""))),
        }

        # مزامنة فورية مع Firestore
        _sync_castle_to_firebase(email, {"resources": res_data, "castle_info": cinfo_data}, user_id=user_id, castle_id=castle_id)

        return {
            "success":      True,
            "email":        email,
            "lord_name":    cinfo_data["lord_name"],
            "lord_level":   int(base_info.get("level", 0)),
            "kingdom_id":   str(base_info.get("partition", "")),
            "gold":         gold,
            "total_power":  cinfo_data["lord_power"],
            "uid":          cinfo_data["uid"],
            "castle_level": castle_lv,
            "walls_level":  walls_lv,
            "coordinates":  coords,
            "resources":    res_data,
            "fetched_at":   now_iso,
        }

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بسيرفر اللعبة (timeout)")
    except Exception as e:
        log.error(f"❌ [castle-data] فشل جلب بيانات القلعة لـ {email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/errors")
def get_error_log(lines: int = 100):
    """
    قراءة آخر N سطر من سجل الأخطاء bot_errors.log لمراجعتها.
    مثال: GET /api/errors?lines=50
    """
    log_path = os.path.join(_ROOT, "bot_errors.log")
    if not os.path.exists(log_path):
        return {"errors": [], "count": 0, "message": "لا توجد أخطاء مسجلة حتى الآن ✅"}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        last_lines = [l.rstrip("\n") for l in all_lines[-lines:]]
        return {
            "errors": last_lines,
            "count":  len(all_lines),
            "showing": len(last_lines),
            "log_path": log_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/{castle_id}")
def get_castle_logs(castle_id: str, lines: int = 100):
    """
    قراءة آخر N سطر من ملف log الخاص بالقلعة محلياً من القرص دون أي اتصال بـ Firebase.
    مثال: GET /api/logs/{castle_id}?lines=50
    """
    email = _castle_emails.get(castle_id)
    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p

    if not log_path:
        candidates = [
            os.path.join(_ROOT, f) for f in os.listdir(_ROOT)
            if f.startswith("bot_") and f.endswith(".log") and f != "bot_errors.log"
        ]
        if candidates:
            log_path = max(candidates, key=os.path.getmtime)

    if not log_path or not os.path.exists(log_path):
        return {"logs": [], "count": 0, "message": "لا يوجد سجل محلي بعد"}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        last_lines = [l.rstrip("\r\n") for l in all_lines[-lines:]]
        return {
            "logs": last_lines,
            "count": len(all_lines),
            "showing": len(last_lines),
            "file": os.path.basename(log_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/logs/{castle_id}")
async def ws_logs(websocket: WebSocket, castle_id: str):
    """
    WebSocket للـ logs المباشرة لبوت قلعة معينة (محلياً 100% بدون أي اتصال بفايربيس).
    الاتصال: ws://localhost:8000/ws/logs/{castle_id}
    """
    await websocket.accept()
    log.info(f"📡 WebSocket logs connected: {castle_id[:16]}")

    # 1. إرسال أحدث 30 سطراً من ملف الـ log المحلي فور الاتصال
    email = _castle_emails.get(castle_id)
    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p
    if not log_path:
        candidates = [
            os.path.join(_ROOT, f) for f in os.listdir(_ROOT)
            if f.startswith("bot_") and f.endswith(".log") and f != "bot_errors.log"
        ]
        if candidates:
            log_path = max(candidates, key=os.path.getmtime)

    if log_path and os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                recent = [l.rstrip("\r\n") for l in f.readlines()[-35:]]
            for r in recent:
                await websocket.send_text(r)
        except Exception:
            pass

    # 2. البث المباشر لأي أسطر جديدة تخرج من البوت
    try:
        while True:
            with _lock:
                q = _log_qs.get(castle_id)

            if q:
                lines_sent = 0
                while lines_sent < 30:
                    try:
                        line = q.get_nowait()
                        await websocket.send_text(line)
                        lines_sent += 1
                    except queue.Empty:
                        break

            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        log.info(f"📡 WebSocket logs disconnected: {castle_id[:16]}")
    except Exception as e:
        log.debug(f"WebSocket error: {e}")


@app.websocket("/ws/status/{castle_id}")
async def ws_status(websocket: WebSocket, castle_id: str):
    """
    WebSocket خفيف لمراقبة حالة البوت الحقيقية في الوقت الفعلي.
    يُرسل الحالة فور الاتصال ثم فقط عند التغيير (لا polling على الشبكة).
    الحالات: running | starting | disconnected | reconnecting | idle | offline
    """
    await websocket.accept()

    last_status = _get_real_status(castle_id)
    await websocket.send_text(last_status)

    try:
        while True:
            await asyncio.sleep(1)  # فحص في الذاكرة فقط — بدون شبكة
            current = _get_real_status(castle_id)
            if current != last_status:
                last_status = current
                await websocket.send_text(current)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# نقطة الدخول
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Empire Bot API Server")
    parser.add_argument("--host",  default="0.0.0.0",  help="عنوان الاستماع [0.0.0.0]")
    parser.add_argument("--port",  type=int, default=8000, help="المنفذ [8000]")
    parser.add_argument("--reload", action="store_true", help="إعادة تحميل تلقائي عند التعديل (تطوير)")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("🚀 Empire Bot API Server")
    print(f"   العنوان  : http://{args.host}:{args.port}")
    print(f"   الوثائق  : http://localhost:{args.port}/docs")
    print(f"   الوقت    : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 60 + "\n")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="warning",  # نستخدم logging الخاص بنا
    )


if __name__ == "__main__":
    main()
