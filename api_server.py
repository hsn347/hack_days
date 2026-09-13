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


def _is_running(castle_id: str) -> bool:
    if castle_id in _reserved:
        return True
    proc = _procs.get(castle_id)
    return proc is not None and proc.poll() is None


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

def _update_firebase_status(user_id: str, castle_id: str, state: str, message: str = ""):
    """يحدّث bot_status في Firestore (اختياري — إذا firebase-admin مثبت)."""
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
            updates: dict = {
                "bot_status.state":            state,
                "bot_status.last_run_message": message,
            }
            if state == "running":
                updates["bot_status.last_run_time"] = datetime.now(timezone.utc).isoformat()
            ref.update(updates)
    except Exception as e:
        log.debug(f"Firebase status update skipped: {e}")


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
        "--email",          email,
        "--firebase-config", config_path,
        "--loop",
        "--loop-interval",  str(req.loop_interval),
    ]
    log.info(f"▶️  [{email}] cmd: bot_manager.py --firebase-config ... --loop")
    log_q.put(f"[{datetime.now():%H:%M:%S}] ▶️  بدء البوت...")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

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

        # 6. قراءة stdout في thread آخر وإرساله للـ queue والملف
        def _reader():
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
                            pass  # الـ queue ممتلئة — تجاهل (لا نريد تعطيل البوت)
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
        _update_firebase_status(user_id, castle_id, "error", str(e))
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
    with _lock:
        _procs.pop(castle_id, None)
        _log_qs.pop(castle_id, None)

    end_msg = f"[{datetime.now():%H:%M:%S}] {'✅ انتهى بنجاح' if ret == 0 else f'⚠️ توقف (كود={ret})'}"
    log_q.put(end_msg)
    log.info(f"{'✅' if ret == 0 else '⚠️'} [{email}] انتهى (exit={ret})")
    _update_firebase_status(
        user_id, castle_id,
        "idle",
        "انتهت الدورة بنجاح" if ret == 0 else f"توقف (كود={ret})"
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
    """إيقاف بوت قلعة معينة."""
    with _lock:
        proc = _procs.get(castle_id)

    if proc and proc.poll() is None:
        proc.terminate()
        log.info(f"⏹️  إيقاف القلعة {castle_id[:16]}...")
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
    with _lock:
        if castle_id in _reserved:
            return {"castle_id": castle_id, "status": "starting"}
        proc = _procs.get(castle_id)
        running = proc is not None and proc.poll() is None
    return {"castle_id": castle_id, "status": "running" if running else "idle"}


@app.websocket("/ws/logs/{castle_id}")
async def ws_logs(websocket: WebSocket, castle_id: str):
    """
    WebSocket للـ logs المباشرة لبوت قلعة معينة.
    الاتصال: ws://localhost:8000/ws/logs/{castle_id}
    """
    await websocket.accept()
    log.info(f"📡 WebSocket connection: {castle_id[:16]}")

    # إرسال رسالة ترحيب
    await websocket.send_text(f"[{datetime.now():%H:%M:%S}] 📡 متصل — مراقبة القلعة {castle_id[:12]}...")

    # انتظار ظهور الـ queue (حتى 30 ثانية)
    for _ in range(60):
        with _lock:
            q = _log_qs.get(castle_id)
        if q:
            break
        await asyncio.sleep(0.5)

    if not q:
        await websocket.send_text(f"[{datetime.now():%H:%M:%S}] ℹ️ البوت غير نشط حالياً")
        await websocket.close()
        return

    try:
        while True:
            # تحقق من وجود سطور في الـ queue
            lines_sent = 0
            while lines_sent < 20:  # أرسل حتى 20 سطر في كل دورة
                try:
                    line = q.get_nowait()
                    await websocket.send_text(line)
                    lines_sent += 1
                except queue.Empty:
                    break

            # تحقق هل البوت لا يزال يعمل
            with _lock:
                still_running = _is_running(castle_id)
            if not still_running and q.empty():
                await websocket.send_text(f"[{datetime.now():%H:%M:%S}] 🏁 انتهى البوت")
                break

            await asyncio.sleep(0.2)

    except WebSocketDisconnect:
        log.info(f"📡 WebSocket disconnected: {castle_id[:16]}")
    except Exception as e:
        log.debug(f"WebSocket error: {e}")


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
