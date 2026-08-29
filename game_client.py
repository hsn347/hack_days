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

    def __init__(self, creds: GateCredentials):
        self.creds    = creds
        self._session = 1
        self._reader  = None
        self._writer  = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._cmd_pending: Dict[Tuple[str, str], asyncio.Future] = {}
        self.cached_packets: Dict[Tuple[str, str], dict] = {}
        self.heroes: List[dict] = []
        self._buf     = b""
        self._lock    = asyncio.Lock()
        self._alive   = False
        self._notifies: Dict[str, Callable] = {}
        self._recv_task = None

    async def connect(self) -> bool:
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

        # إرسال طلب التهيئة 1000/1 فوراً لاستقبال بيانات الأبطال
        self.send_nowait('1000', '1', {})
        return True

    async def _recv_loop(self):
        try:
            while self._alive:
                chunk = await asyncio.wait_for(self._reader.read(65536), timeout=120)
                if not chunk: break
                self._buf += chunk
                self._dispatch()
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            if self._alive: log.warning(f"[Gate] recv: {e}")
        finally:
            self._alive = False
            for fut in list(self._pending.values()) + list(self._cmd_pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("Gate disconnected"))
            self._pending.clear()
            self._cmd_pending.clear()

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

            # تخزين الحزمة في الذاكرة المؤقتة
            if isinstance(c, dict) and cmd:
                self.cached_packets[cmd_key] = c
                # إذا كانت الحزمة تحتوي على heroCtrl، حفظ الأبطال فوراً
                retdata = c.get('data', {}).get('retdata', {}) or c.get('retdata', {})
                if isinstance(retdata, dict) and 'heroCtrl' in retdata:
                    h_ctrl = retdata.get('heroCtrl', [])
                    if isinstance(h_ctrl, list) and h_ctrl:
                        self.heroes = list(h_ctrl)

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

    async def query(self, cmd: str, subcmd: str, data: dict = None, timeout: float = 15) -> Optional[dict]:
        """إرسال أمر والانتظار للرد"""
        if not self._alive: return None
        str_cmd = str(cmd)
        str_sub = str(subcmd)
        cmd_key = (str_cmd, str_sub)

        # استرجاع فوري إذا كانت الحزمة مخزنة مسبقاً وغير فارغة
        if cmd_key in self.cached_packets and not data and self.cached_packets[cmd_key]:
            return self.cached_packets[cmd_key]

        sess = self._session
        self._session += 1
        pkt = pack_request(str_cmd, str_sub, data or {}, sess)

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[sess] = fut
        self._cmd_pending[cmd_key] = fut

        async with self._lock:
            self._writer.write(pkt)
            await self._writer.drain()

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            if not result or not result.get('ok'):
                return None
            return result.get('content')
        except (asyncio.TimeoutError, ConnectionError):
            self._pending.pop(sess, None)
            self._cmd_pending.pop(cmd_key, None)
            return None

    def send_nowait(self, cmd: str, subcmd: str, data: dict = None):
        """إرسال بدون انتظار"""
        if not self._alive or not self._writer: return
        sess = self._session
        self._session += 1
        self._writer.write(pack_request(cmd, str(subcmd), data or {}, sess))

    def on_notify(self, notify_id: str, handler: Callable):
        self._notifies[notify_id] = handler

    async def close(self):
        self._alive = False
        if self._recv_task: self._recv_task.cancel()
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

    def __init__(self, account: AccountSession):
        self.account = account
        self.creds:  Optional[GateCredentials] = None
        self._gate:  Optional[GateClient]      = None

    async def connect(self) -> bool:
        self.creds = await async_login(self.account)
        if not self.creds: return False
        self._gate = GateClient(self.creds)
        return await self._gate.connect()

    async def query(self, cmd: str, subcmd: str, data: dict = None, timeout: float = 15) -> Optional[dict]:
        if not self._gate or not self._gate.is_connected: return None
        return await self._gate.query(cmd, subcmd, data, timeout)

    def send_nowait(self, cmd: str, subcmd: str, data: dict = None):
        if self._gate: self._gate.send_nowait(cmd, subcmd, data)

    def on_notify(self, notify_id: str, handler: Callable):
        if self._gate: self._gate.on_notify(notify_id, handler)

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
