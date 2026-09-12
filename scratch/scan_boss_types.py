import asyncio
import os
import sys

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

    print('Scanning bossType 1 to 40...')
    results = {}
    for bt in range(1, 41):
        try:
            r = await conn.query('2011', '4', {'bossType': bt}, timeout=2)
            if r and str(r.get('err', '')) == '0':
                rsp = r.get('rspdata', {})
                print(f"bossType {bt:2d}: SUCCESS -> x={rsp.get('x')}, y={rsp.get('y')}, data={rsp}")
                results[bt] = rsp
            else:
                err = r.get('err') if r else 'no_resp'
                # only print non-standard errors
                if err not in ('7', 'no_resp'):
                    print(f"bossType {bt:2d}: err={err}")
        except Exception as e:
            pass

    print(f"\nTotal active bossTypes found: {len(results)}")
    for bt, rsp in results.items():
        print(f"  bossType={bt}: ({rsp.get('x')}, {rsp.get('y')})")

    # Also test if 2011/4 returns different bosses if we pass other parameters or subcmds
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
