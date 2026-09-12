import asyncio
import os
import sys
import math

_ROOT_DIR = 'E:/osmanli'
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection

ELF_BOSS_TYPES = [10, 9, 6, 5]

async def test_search():
    sm = SessionManager()
    accounts = sm.load()
    acc = accounts.get('meik.gaertner2306.MGr@gmail.com')
    conn = GameConnection(acc)
    if not await conn.connect():
        print('Connect failed')
        return

    lord = conn.init_data.get('lord', {})
    castle_x = lord.get('x', 319)
    castle_y = lord.get('y', 451)
    print(f"Castle at ({castle_x}, {castle_y})")

    targeted_bosses = set()

    for legion_idx in range(1, 7):
        print(f"\n--- Searching for Legion {legion_idx} (targeted so far: {len(targeted_bosses)}) ---")
        candidates = []
        for btype in ELF_BOSS_TYPES:
            r = await conn.query('2011', '4', {'bossType': btype}, timeout=4)
            if r and str(r.get('err', '')) == '0':
                rsp = r.get('rspdata', {})
                bx = rsp.get('x')
                by = rsp.get('y')
                if bx is None or by is None:
                    continue
                if (bx, by) in targeted_bosses:
                    print(f"  bossType {btype}: ({bx-1}, {by-1}) already targeted, skipping")
                    continue
                
                tx = bx - 1
                ty = by - 1
                dist = math.hypot(tx - castle_x, ty - castle_y)
                candidates.append((bx, by, btype, dist))
                print(f"  bossType {btype}: AVAILABLE at ({tx}, {ty}) [tile {bx}, {by}] | dist: {dist:.1f} km")

        if not candidates:
            print(f"No more new bosses available on map for Legion {legion_idx}!")
            break

        candidates.sort(key=lambda c: c[3])
        best_bx, best_by, best_btype, best_dist = candidates[0]
        print(f"🎯 Legion {legion_idx} TARGET: bossType {best_btype} at ({best_bx-1}, {best_by-1}) | dist: {best_dist:.1f} km")
        targeted_bosses.add((best_bx, best_by))

    print(f"\nTotal unique bosses found and queued: {len(targeted_bosses)}")
    for b in targeted_bosses:
        print(f"  Target: tile ({b[0]}, {b[1]}) -> client ({b[0]-1}, {b[1]-1})")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(test_search())
