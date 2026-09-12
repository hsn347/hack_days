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

    # Check bossType 9 and 10
    for bt in [10, 9]:
        r = await conn.query('2011', '4', {'bossType': bt}, timeout=4)
        if r and str(r.get('err', '')) == '0':
            rsp = r.get('rspdata', {})
            bx = rsp.get('x')
            by = rsp.get('y')
            print(f"bossType {bt}: found at ({bx}, {by})")
            
            # Query 1006/25 or 1006/1000 or 1002/7 to inspect tile
            target_id = f"{bx}-{by}-24-0-{bt}"
            print(f"  target_id would be: {target_id}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
