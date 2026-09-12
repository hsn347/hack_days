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

    # Check 1006/1000 around the two bosses found
    for (bx, by, bt) in [(211, 540, 10), (320, 458, 9)]:
        r = await conn.query('1006', '1000', {'centerKid': 23, 'centerX': bx, 'centerY': by}, timeout=4)
        if r and 'data' in r:
            objs = r['data'].get('objs', {})
            print(f"\n=== Viewport at ({bx}, {by}) [bossType {bt}]: {len(objs)} objs ===")
            for k, v in objs.items():
                mtype = v.get('type')
                subt = v.get('subType')
                ox = v.get('x')
                oy = v.get('y')
                if abs(ox - bx) <= 2 and abs(oy - by) <= 2:
                    print(f"  MATCH obj {k}: pos=({ox}, {oy}), type={mtype}, subType={subt}")
                    print(f"    full={json.dumps(v, ensure_ascii=False)}")
                elif mtype in (24, 10, 9, 7, 26):
                    print(f"  BOSS-LIKE obj {k}: pos=({ox}, {oy}), type={mtype}, subType={subt}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
