# -*- coding: utf-8 -*-
r"""
tests/test_live_conn_agent11.py — Empirical Live Connection & Init Tester
════════════════════════════════════════════════════════════════════════
Author: Agent 11 (Empirical Challenger & Live Init QA Specialist)
Workspace: e:\osmanli

This test suite executes empirical verification of:
1. Wire packet ingestion through GateClient._dispatch().
2. Whitelist filtering of 186 non-whitelisted controllers from real game dump.
3. Verification of 6 critical startup controllers and structural integrity:
   - cityCtrl: blist length, reslist contents.
   - lordInfoCtrl: base lord info with uid.
   - queueCtrl: queues map / list.
   - armyCtrl: army data present.
   - heroCtrl: heroes present.
   - backpackCtrl: items present.
4. CoW non-destructive partial update to blist (Anti-Shallow-Update test).
5. Strict memory readiness gate (wait_for_memory_ready).
6. Live session authentication test using database/session_cache.json credentials.
"""

import asyncio
import json
import os
import struct
import sys
import unittest

# Ensure root workspace is in sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.live_memory import (
    LiveMemoryEngine,
    ALLOWED_CONTROLLERS,
    CRITICAL_STARTUP_CONTROLLERS,
    BUILD_STATE,
)
from core.onemt_bot import xor_crypt, decode_gate_response, unpack_stream
from game_client import GateClient, GateCredentials, AccountSession, async_login


def make_wire_packet(content: dict, session: int = 1) -> bytes:
    """Builds authentic skynet/gate wire-framed packet bytes."""
    raw_json = json.dumps(content, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    xored = xor_crypt(raw_json)
    pkt_body = xored + b'\x01' + struct.pack('>I', session)
    sz = len(pkt_body)
    if sz < 0xFFFF:
        header = struct.pack('>H', sz)
    else:
        header = b'\xff\xff' + bytes([(sz >> 16) & 0xFF, (sz >> 8) & 0xFF, sz & 0xFF])
    return header + pkt_body


class TestLiveConnectionAndInitVerification(unittest.TestCase):
    """Empirical verification suite for Agent 11."""

    @classmethod
    def setUpClass(cls):
        cls.dump_path = os.path.join(_ROOT, "docs", "burcudemr_live_memory.json")
        cls.session_cache_path = os.path.join(_ROOT, "database", "session_cache.json")
        cls.assertTrue(os.path.exists(cls.dump_path), f"Missing authentic dump: {cls.dump_path}")

        with open(cls.dump_path, 'r', encoding='utf-8') as f:
            cls.raw_dump = json.load(f)

    def setUp(self):
        self.creds = GateCredentials(
            kingdom_id="87",
            server_name="s87",
            gate_ip="127.0.0.1",
            gate_port=9999,
            sub_id="sub1",
            uid="100999888",
            secret=b"01234567",
        )
        self.client = GateClient(self.creds)

    def test_01_wire_packet_dispatch_and_ingestion(self):
        """Verify that authentic wire packets unpack, decode, and flow through _dispatch()."""
        packet_payload = {
            "cmd": "1001",
            "subcmd": "1",
            "data": {
                "retdata": self.raw_dump
            }
        }
        wire_bytes = make_wire_packet(packet_payload, session=101)

        # Confirm unpacking and decoding work as expected
        pkts, rem = unpack_stream(wire_bytes)
        self.assertEqual(len(pkts), 1, "Failed to unpack wire packet")
        self.assertEqual(len(rem), 0, "Unpack buffer remnant non-zero")

        decoded = decode_gate_response(pkts[0])
        self.assertTrue(decoded.get('ok'), "Decoded response not ok")
        self.assertEqual(decoded.get('session'), 101, "Session mismatch")

        # Ingest directly through client._buf and client._dispatch()
        self.client._buf = wire_bytes
        self.client._dispatch()

        # Buffer must be fully consumed
        self.assertEqual(self.client._buf, b"", "Dispatch buffer was not fully consumed")

        # init_data must now be populated
        self.assertGreater(len(self.client.init_data), 0, "init_data is empty after dispatch")

    def test_02_whitelist_filtering_enforcement(self):
        """Verify all 186 non-whitelisted controllers are stripped from init_data."""
        wire_bytes = make_wire_packet({"cmd": "1001", "subcmd": "1", "data": {"retdata": self.raw_dump}})
        self.client._buf = wire_bytes
        self.client._dispatch()

        dump_keys = set(self.raw_dump.keys())
        init_keys = set(self.client.init_data.keys())

        # Excluded keys
        expected_excluded = dump_keys - ALLOWED_CONTROLLERS
        leaked_keys = init_keys.intersection(expected_excluded)

        self.assertEqual(len(leaked_keys), 0, f"Leaked controllers detected: {leaked_keys}")
        self.assertGreaterEqual(len(expected_excluded), 180, "Expected at least 180 excluded controllers")

        # Common noisy controllers must strictly NOT be in init_data
        for forbidden in ("chatCtrl", "chatroomCtrl", "RedPointCtrl", "videoAdCtrl", "dungeonCtrl", "fishermanAgCtrl"):
            if forbidden in self.raw_dump:
                self.assertNotIn(forbidden, self.client.init_data, f"Forbidden controller {forbidden} leaked into init_data")

        # Allowed controllers present in dump must all be in init_data
        expected_allowed = dump_keys.intersection(ALLOWED_CONTROLLERS)
        self.assertTrue(expected_allowed.issubset(init_keys), "Some allowed controllers were missed")
        self.assertEqual(len(init_keys), len(expected_allowed))

    def test_03_critical_startup_controllers_and_structural_validity(self):
        """Verify the 6 critical controllers and their structural data validity."""
        wire_bytes = make_wire_packet({"cmd": "1001", "subcmd": "1", "data": {"retdata": self.raw_dump}})
        self.client._buf = wire_bytes
        self.client._dispatch()

        # 1. Check all 6 critical controllers exist in init_data
        for c in CRITICAL_STARTUP_CONTROLLERS:
            self.assertIn(c, self.client.init_data, f"Critical controller {c} missing from init_data")

        # 2. Structural checks on cityCtrl
        city = self.client.init_data.get("cityCtrl")
        self.assertIsInstance(city, dict, "cityCtrl is not a dict")
        blist = city.get("blist")
        self.assertIsInstance(blist, list, "blist is not a list")
        self.assertEqual(len(blist), 57, f"Expected 57 buildings in blist, got {len(blist)}")

        reslist = city.get("reslist")
        self.assertIsInstance(reslist, dict, "reslist is not a dict")
        self.assertGreaterEqual(len(reslist), 5, f"Expected >= 5 resources, got {len(reslist)}")
        for rk in ("1002", "1003", "1004", "1005"):
            self.assertIn(rk, reslist, f"Resource {rk} missing from reslist")

        # 3. Structural checks on lordInfoCtrl
        lord = self.client.init_data.get("lordInfoCtrl")
        self.assertIsInstance(lord, dict, "lordInfoCtrl is not a dict")
        base = lord.get("base")
        self.assertIsInstance(base, dict, "lordInfoCtrl.base is not a dict")
        self.assertIn("uid", base, "lord base is missing uid")
        self.assertTrue(bool(base.get("uid")), "lord base uid is empty")

        # 4. Structural checks on queueCtrl
        queue = self.client.init_data.get("queueCtrl")
        self.assertIsInstance(queue, dict, "queueCtrl is not a dict")
        self.assertEqual(len(queue), 9, f"Expected 9 queues, got {len(queue)}")

        # 5. Structural checks on armyCtrl
        army = self.client.init_data.get("armyCtrl")
        self.assertIsInstance(army, dict, "armyCtrl is not a dict")
        self.assertIn("totalArmy", army, "totalArmy missing from armyCtrl")

        # 6. Structural checks on heroCtrl
        heroes = self.client.init_data.get("heroCtrl")
        self.assertIsInstance(heroes, list, "heroCtrl is not a list")
        self.assertEqual(len(heroes), 44, f"Expected 44 heroes, got {len(heroes)}")
        # Check compatibility reference self.client.heroes
        self.assertEqual(len(self.client.heroes), 44, "client.heroes alias was not synced")

        # 7. Structural checks on backpackCtrl
        backpack = self.client.init_data.get("backpackCtrl")
        self.assertIsInstance(backpack, dict, "backpackCtrl is not a dict")
        self.assertEqual(len(backpack), 608, f"Expected 608 items, got {len(backpack)}")

    def test_04_cow_non_destructive_partial_building_update(self):
        """Stress test: Partial blist update with 1 building must NOT wipe the other 56 buildings."""
        # Initial full load
        wire_bytes = make_wire_packet({"cmd": "1001", "subcmd": "1", "data": {"retdata": self.raw_dump}})
        self.client._buf = wire_bytes
        self.client._dispatch()

        initial_count = len(self.client.init_data["cityCtrl"]["blist"])
        self.assertEqual(initial_count, 57)

        # Pick building #1 index
        target_b = self.client.init_data["cityCtrl"]["blist"][0]
        target_idx = target_b.get("index") or (target_b.get("binfo", {}).get("index"))

        # Send server update packet containing ONLY this one building with updated level
        partial_update = {
            "cmd": "1001",
            "subcmd": "2",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [
                            {"index": target_idx, "binfo": {"index": target_idx, "lv": 99, "state": "0"}}
                        ]
                    }
                }
            }
        }
        self.client._buf = make_wire_packet(partial_update, session=202)
        self.client._dispatch()

        # Check: blist count must still be 57!
        new_blist = self.client.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(new_blist), 57, f"CRITICAL BUG: blist wiped! count is {len(new_blist)} instead of 57")

        # Verify the updated building level was updated in place
        found = False
        for b in new_blist:
            idx = b.get("index") or (b.get("binfo", {}).get("index"))
            if idx == target_idx:
                found = True
                binfo = b.get("binfo") if isinstance(b.get("binfo"), dict) else b
                self.assertEqual(binfo.get("lv"), 99, "Building level was not updated")
                break
        self.assertTrue(found, "Updated building was lost")

    def test_05_strict_memory_readiness_gate(self):
        """Verify wait_for_memory_ready succeeds on populated memory and fails when unready."""
        # Unready client
        empty_client = GateClient(self.creds)
        is_ready, missing = empty_client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready, "Empty memory reported ready")
        self.assertGreater(len(missing), 0, "Missing list empty for unready memory")

        # Populated client
        self.client._buf = make_wire_packet({"cmd": "1001", "subcmd": "1", "data": {"retdata": self.raw_dump}})
        self.client._dispatch()

        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertTrue(is_ready, f"Populated memory failed readiness: {missing}")
        self.assertEqual(len(missing), 0)

        # Async wait_for_memory_ready
        async def _test_gate():
            self.client._alive = True
            ready = await self.client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=False)
            self.assertTrue(ready, "wait_for_memory_ready returned False on ready memory")
        asyncio.run(_test_gate())

    def test_06_real_session_cache_live_auth_attempt(self):
        """
        Attempts real live authentication against the game LoginServer using credentials
        from database/session_cache.json, connects to the Live Gate Server, verifies live
        packet ingestion via _dispatch(), checks whitelist isolation and structural integrity.
        """
        if not os.path.exists(self.session_cache_path):
            self.skipTest("session_cache.json not found")

        with open(self.session_cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        accounts = cache_data.get("accounts", {})
        if not accounts:
            self.skipTest("No accounts found in session_cache.json")

        async def _connect_live_candidate():
            # Try active accounts until one connects to Gate
            target_candidates = ["ossso5040@gmail.com", "hmzawyha44@gmail.com", "king7moe1990@gmail.com", "zzoro8290@gmail.com"]
            for email in target_candidates:
                if email not in accounts:
                    continue
                info = accounts[email]
                acc = AccountSession(email=email, user_id=info.get("userId", ""), session_id=info.get("sessionId", ""))
                try:
                    creds = await async_login(acc)
                    if isinstance(creds, GateCredentials):
                        client = GateClient(creds)
                        connected = await client.connect()
                        if connected:
                            # Allow live server to push initialization packets
                            await asyncio.sleep(5.0)
                            return email, client
                        client.abort()
                except Exception as ex:
                    print(f"[AUTH TEST] Candidate {email} failed: {ex}")
            return None, None

        email, live_client = asyncio.run(_connect_live_candidate())
        self.assertIsNotNone(live_client, "Failed to connect to Live Gate with any candidate account")
        try:
            print(f"\n[LIVE GATE VERIFICATION] Successfully connected to Gate for: {email}")
            print(f"  Live init_data controllers ({len(live_client.init_data)}): {list(live_client.init_data.keys())}")

            # 1. Whitelist Isolation: All received controllers must be in ALLOWED_CONTROLLERS
            for k in live_client.init_data.keys():
                self.assertIn(k, ALLOWED_CONTROLLERS, f"Non-whitelisted controller leaked in live connection: {k}")

            # 2. Critical Controllers Check
            for critical in CRITICAL_STARTUP_CONTROLLERS:
                self.assertIn(critical, live_client.init_data, f"Critical controller {critical} missing from live gate session")

            # 3. Structural Validity Check
            city = live_client.init_data["cityCtrl"]
            self.assertIsInstance(city.get("blist"), list)
            self.assertGreaterEqual(len(city["blist"]), 30, f"blist too small: {len(city['blist'])}")
            self.assertIsInstance(city.get("reslist"), dict)
            self.assertGreaterEqual(len(city["reslist"]), 4, "reslist missing resources")

            lord = live_client.init_data["lordInfoCtrl"]
            self.assertIn("uid", lord.get("base", {}))
            self.assertTrue(bool(lord["base"]["uid"]))

            # 4. Strict Memory Readiness Gate Check
            is_ready, missing = live_client.memory_engine.is_memory_ready()
            self.assertTrue(is_ready, f"Live gate memory not ready: {missing}")
            self.assertEqual(len(missing), 0)
            print(f"  [LIVE GATE VERIFICATION] ✓ Memory Readiness Gate PASSED: is_memory_ready={is_ready}")
        finally:
            live_client.abort()


if __name__ == "__main__":
    unittest.main()
