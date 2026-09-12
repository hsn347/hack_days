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

    # Check 1007/16 for active marches
    r = await conn.query('1007', '16', {}, timeout=4)
    print("1007/16 active marches:")
    if r and 'data' in r:
        marches = r['data']
        print(f"Total marches in data: {len(marches) if isinstance(marches, list) else type(marches)}")
        if isinstance(marches, list):
            for m in marches:
                print(f"  March: to=({m.get('toX')}, {m.get('toY')}), type={m.get('moveLineType')}, targetId={m.get('targetId')}, state={m.get('state')}, massTime={m.get('massTime')}")
    else:
        print("1007/16 response:", r)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
