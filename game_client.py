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
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# ── استيراد الكريبتو المثبتة من onemt_bot.py ─────────────────────
try:
    from onemt_bot import (
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

async def async_login(account: AccountSession) -> Optional[GateCredentials]:
    """يتصل بـ Login Server ويستقبل Gate credentials (async via executor)"""
    loop = asyncio.get_event_loop()

    def _do_login():
        token = {"subtoken": account.session_id, "userid": account.user_id}
        srv   = LoginServer(*LOGIN_SERVER)
        srv.connect()
        try:
            result = srv.do_handshake(token)
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

    # ── ثوابت حماية الحساب من الحظر ──────────────────────────────
    RATE_LIMIT_DELAY = 0.8   # ثانية بين كل طلب API (حماية أساسية من الحظر)

    def __init__(self, creds: GateCredentials):
        self.creds    = creds
        self._session = 1
        self._reader  = None
        self._writer  = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._cmd_pending: Dict[Tuple[str, str], asyncio.Future] = {}
        self.heroes: list = []
        self.init_data: dict = {}
        self.spy_mode: bool = False
        self._buf = b""
        self.cached_packets: dict = {}
        self.local_queues: list = []
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

    @property
    def is_connected(self) -> bool:
        return self._alive and self._writer is not None

    async def connect(self) -> bool:
        if self._alive:
            return True
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.creds.gate_ip, self.creds.gate_port),
                timeout=15
            )
        except Exception as e:
            log.error(f"[Gate] Connect failed: {e}")
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

        self._alive = True
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._init_flow_task = asyncio.create_task(self._init_flow())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return True

    async def _heartbeat_loop(self):
        """إرسال ping دوري للسيرفر كل 25 ثانية للإبقاء على الاتصال حياً"""
        # انتظار انتهاء _init_flow أولاً (في 5 خطوات من 3 ثوان)
        for _ in range(15):
            if not self._alive:
                return
            await asyncio.sleep(1)
        while self._alive:
            try:
                self.send_nowait('1009', '36', {})
                # نوم قصير متقطع بدلاً من sleep(30) واحدة حتى نستجيب لـ _alive=False فوراً
                for _ in range(25):
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
            for _ in range(6):
                await asyncio.sleep(0.5)
                if not self._alive: break
                self.send_nowait('1009', '36', {})
                self.send_nowait('1005', '1', {})
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
            cmd_key = (cmd, sub)

            # وضع التجسس على الحزم (Spy Mode)
            if self.spy_mode:
                summary = f"👁️ [SPY S2C] CMD={cmd}/{sub} (session={sess})"
                if isinstance(c, dict) and 'data' in c:
                    d_keys = list(c['data'].keys()) if isinstance(c['data'], dict) else type(c['data'])
                    summary += f" | data keys: {d_keys}"
                print(summary)

            # تخزين الحزمة في الذاكرة المؤقتة
            if isinstance(c, dict) and cmd:
                self.cached_packets[cmd_key] = c
                # حفظ بيانات التهيئة والأبطال فوراً
                retdata = c.get('data', {}).get('retdata', {}) or c.get('retdata', {})
                if isinstance(retdata, dict) and retdata:
                    self.init_data.update(retdata)
                    if 'heroCtrl' in retdata:
                        h_ctrl = retdata.get('heroCtrl', [])
                        if isinstance(h_ctrl, list) and h_ctrl:
                            self.heroes = list(h_ctrl)
                    # حفظ نسخة JSON محلية فقط عند تفعيل وضع التطوير BOT_DEBUG_DUMP لمنع استهلاك القرص في الإنتاج
                    if os.environ.get("BOT_DEBUG_DUMP") == "1" and len(retdata) > 5:
                        try:
                            os.makedirs('dumps', exist_ok=True)
                            safe_name = str(getattr(self.creds, 'email', None) or getattr(self.creds, 'uid', 'acc')).replace('@', '_at_')
                            dump_file = os.path.join('dumps', f"{safe_name}_login_init.json")
                            with open(dump_file, 'w', encoding='utf-8') as df:
                                json.dump(retdata, df, indent=2, ensure_ascii=False)
                        except Exception:
                            pass

                data_obj = c.get('data', {})
                if isinstance(data_obj, dict):
                    notify_id = str(data_obj.get('notifyID', ''))
                    notify_data = data_obj.get('notifyData', [])
                    if notify_id == 'NOTIFY_LOCAL_QUEUE_SYNC' and isinstance(notify_data, list):
                        self.local_queues = notify_data
                    if notify_id in ('100', 'NOTIFY_SERVER_STATUS', 'SERVER_STATUS'):
                        if isinstance(notify_data, list):
                            for item in notify_data:
                                if isinstance(item, dict):
                                    status = item.get('status')
                                    if status == 'kick':
                                        self.kick_reason = "other_device"
                                    elif status == 'seal':
                                        self.kick_reason = "account_sealed"
                                    elif status == 'server_maintenance':
                                        self.kick_reason = "server_maintenance"
                        elif isinstance(notify_data, dict):
                            status = notify_data.get('status')
                            if status == 'kick': self.kick_reason = "other_device"
                            elif status == 'seal': self.kick_reason = "account_sealed"

                    if data_obj.get('status') == 'kick':
                        self.kick_reason = "other_device"
                    elif data_obj.get('status') == 'seal':
                        self.kick_reason = "account_sealed"

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
                    if p_cmd == cmd and not p_fut.done():
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

    async def query(self, cmd: str, subcmd: str, data: dict = None, timeout: float = 15, client_data: list = None) -> Optional[dict]:
        """إرسال أمر والانتظار للرد — مع حماية تلقائية من السرعة الزائدة."""
        if not self._alive: return None
        str_cmd = str(cmd)
        str_sub = str(subcmd)
        cmd_key = (str_cmd, str_sub)

        # 🛡️ حماية من الحظر: تأخير تلقائي بين الطلبات
        now = time.time()
        elapsed = now - self._last_query_time
        if elapsed < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)
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

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            if not result or not result.get('ok'):
                return None
            return result.get('content')
        except (asyncio.TimeoutError, ConnectionError):
            return None
        finally:
            self._pending.pop(sess, None)
            self._cmd_pending.pop(cmd_key, None)

    def send_nowait(self, cmd: str, subcmd: str, data: dict = None):
        """إرسال بدون انتظار"""
        if not self._alive or not self._writer: return
        sess = self._session
        self._session += 1
        if self.spy_mode:
            print(f"🚀 [SPY C2S] NOWAIT CMD={cmd}/{subcmd} (session={sess}) | data={data}")
        self._writer.write(pack_request(cmd, str(subcmd), data or {}, sess))

    def on_notify(self, notify_id: str, handler: Callable):
        self._notifies[notify_id] = handler

    async def close(self):
        self._explicit_close = True
        self._alive = False
        # إلغاء جميع المهام الخلفية فوراً
        for task in (self._recv_task, self._heartbeat_task, self._init_flow_task):
            if task and not task.done():
                task.cancel()
        if self._writer:
            try: self._writer.close(); await self._writer.wait_closed()
            except: pass

    @property
    def is_connected(self) -> bool:
        return self._alive


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

    def __init__(self, account: AccountSession, on_disconnect: Optional[Callable[[str], Any]] = None):
        self.account = account
        self.on_disconnect = on_disconnect
        self.creds:  Optional[GateCredentials] = None
        self._gate:  Optional[GateClient]      = None
        self._spy_mode: bool                   = False
        self._packet_listeners: List[Callable] = []

    @property
    def init_data(self) -> dict:
        return self._gate.init_data if self._gate else {}

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
        self.creds = await async_login(self.account)
        if not self.creds: return False
        if hasattr(self.creds, 'email') or not getattr(self.creds, 'email', None):
            self.creds.email = self.account.email
        self._gate = GateClient(self.creds)
        self._gate.on_disconnect = self.on_disconnect
        self._gate.spy_mode = self._spy_mode
        self._gate._packet_listeners = list(self._packet_listeners)
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

    async def close(self):
        if self._gate: await self._gate.close()

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

    def load_from_cache(self, cache_file: str = "session_cache.json"):
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
