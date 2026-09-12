import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from auto_elf_boss import sdk_login
from game_client import GameConnection, AccountSession

async def main():
    auth = sdk_login("fahed.K140@gmail.com", "mn@123450")
    acc = AccountSession("fahed.K140@gmail.com", auth['userId'], auth['sessionId'])
    conn = GameConnection(acc)
    await conn.connect()
    for _ in range(10):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data:
            break

    # Get elite boss #2: (414, 454)
    r_bosses = await conn.query('2011', '3', {"mapType": 24, "num": 5, "x": 425, "y": 427, "range": 2000}, timeout=5)
    boss = r_bosses['result'][1]
    bx, by, tid = boss['x'], boss['y'], boss['id']
    print(f"Testing boss 2: {bx}, {by}, tid={tid}")

    # Full formation 1 army
    full_army = [{'id': 610, 'num': 330000}, {'id': 612, 'num': 435120}, {'id': 606, 'num': 50000}, {'id': 412, 'num': 90000}, {'id': 608, 'num': 170000}]

    payload = {
        "needSend": True,
        "mapId": 87,
        "moveLineType": 7,
        "data": {
            "data": {
                "mainInstanceType": 24,
                "massTime": 300
            },
            "to": {
                "y": by,
                "x": bx,
                "id": tid
            },
            "army": full_army
        },
        "needArmyList": {},
        "pets": [1272],
        "runePages": [3],
        "matrixType": 1,
        "heros": [5501036, 5501003]
    }
    r = await conn.query('1007', '2', payload, timeout=6)
    print("Attack with full army (1,075,120 troops):", r)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
