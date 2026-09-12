import asyncio
import os
import sys
import json

_ROOT_DIR = 'E:/osmanli'
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection

async def main():
    sm = SessionManager()
    accounts = sm.load()
    acc = accounts.get('meik.gaertner2306.MGr@gmail.com')
    conn = GameConnection(acc)
    if not await conn.connect():
        print('Connect failed')
        return

    # 1. Test 2011 subcmds
    for sub in ['1', '2', '5', '6', '7']:
        for data in [{"bossType": 10}, {"type": 10}, {}]:
            try:
                r = await conn.query('2011', sub, data, timeout=2)
                if r and str(r.get('err', '')) == '0':
                    print(f"2011/{sub} with {data}: {r}")
                elif r and r.get('err') != '7':
                    print(f"2011/{sub} err: {r.get('err')}")
            except Exception:
                pass

    # 2. Test 2014 subcmds (CMD_HERO_BATTLE_BOSS_MODULE)
    for sub in range(1, 15):
        try:
            r = await conn.query('2014', str(sub), {}, timeout=2)
            if r and str(r.get('err', '')) == '0':
                print(f"2014/{sub}: {r}")
            elif r and r.get('err') not in ('7', 'no_resp'):
                print(f"2014/{sub} err: {r.get('err')}")
        except Exception:
            pass

    # 3. Can 2011/4 take other keys in payload?
    # e.g., bossType: [9, 10], or exclude, or id, or bossId, etc.
    tests = [
        {"bossType": 10, "num": 5},
        {"bossType": 10, "next": 1},
        {"bossType": 10, "refresh": 1},
        {"bossType": 10, "change": 1},
        {"bossType": 10, "exclude": "211-540"},
        {"bossType": 10, "id": 1},
        {"bossType": 10, "id": 2},
        {"bossType": 10, "level": 1},
        {"bossType": 10, "level": 2},
        {"bossType": 10, "bossId": 1},
        {"bossType": 10, "bossId": 2},
    ]
    for t in tests:
        try:
            r = await conn.query('2011', '4', t, timeout=2)
            if r and str(r.get('err', '')) == '0':
                rsp = r.get('rspdata', {})
                print(f"2011/4 with {t} -> ({rsp.get('x')}, {rsp.get('y')})")
        except Exception:
            pass

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
