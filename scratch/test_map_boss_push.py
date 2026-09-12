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

    for _ in range(10):
        await asyncio.sleep(0.3)
        if 'cityCtrl' in conn.init_data:
            break

    boss_packets = []
    def on_packet(pkt):
        if not isinstance(pkt, dict):
            return
        cmd = str(pkt.get('cmd', ''))
        if cmd == '1006':
            d = pkt.get('data', {})
            if isinstance(d, dict):
                objs = d.get('objs', {})
                if isinstance(objs, dict):
                    for oid, obj in objs.items():
                        if isinstance(obj, dict):
                            boss_packets.append(obj)

    conn.add_packet_listener(on_packet)

    # Let's query 1006/1000 at the known boss positions
    print("Testing 1006/1000 at (211, 540)...")
    await conn.query('1006', '1000', {'centerKid': 23, 'centerX': 211, 'centerY': 540}, timeout=4)
    await asyncio.sleep(2)

    print("Testing 1006/1000 at (320, 458)...")
    await conn.query('1006', '1000', {'centerKid': 23, 'centerX': 320, 'centerY': 458}, timeout=4)
    await asyncio.sleep(2)

    print(f"\nCaptured {len(boss_packets)} total objects from 1006 pushes:")
    for b in boss_packets:
        mtype = b.get('type')
        if mtype in (24, 10, 9, 7) or 'boss' in str(b).lower():
            print(f"  --> MATCH: {b}")
        else:
            print(f"  obj type={mtype}, subType={b.get('subType')}, pos=({b.get('x')}, {b.get('y')})")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
