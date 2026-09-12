import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

    # Get elite boss
    r_bosses = await conn.query('2011', '3', {"mapType": 24, "num": 5, "x": 425, "y": 427, "range": 2000}, timeout=5)
    print("Bosses 2011/3:", r_bosses)
    boss = r_bosses['result'][0]
    bx = boss['x']
    by = boss['y']
    tid = boss['id']
    print(f"Targeting: {bx}, {by}, tid={tid}")

    # Let's inspect map tile first!
    r_tile = await conn.query('1006', '1000', {"centerKid": 87, "centerX": bx, "centerY": by}, timeout=5)
    print("1006/1000 tile resp:", r_tile)

    # Let's test 1007/2
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
            "army": [{"id": 412, "num": 1000}]
        },
        "needArmyList": {},
        "pets": [1272],
        "runePages": [3],
        "matrixType": 1,
        "heros": [5501036, 5501003]
    }
    r_atk = await conn.query('1007', '2', payload, timeout=6)
    print("Attack response:", r_atk)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
