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

    r_bosses = await conn.query('2011', '3', {"mapType": 24, "num": 5, "x": 425, "y": 427, "range": 2000}, timeout=5)
    boss = r_bosses['result'][2]
    bx, by, tid = boss['x'], boss['y'], boss['id']
    print(f"Testing boss 3: {bx}, {by}, tid={tid}")

    for count in [50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000]:
        payload = {
            "needSend": True,
            "mapId": 87,
            "moveLineType": 7,
            "data": {
                "data": {"mainInstanceType": 24, "massTime": 300},
                "to": {"y": by, "x": bx, "id": tid},
                "army": [{"id": 412, "num": count}]
            },
            "needArmyList": {},
            "pets": [1272],
            "runePages": [3],
            "matrixType": 1,
            "heros": [5501036, 5501003]
        }
        r = await conn.query('1007', '2', payload, timeout=6)
        print(f"Count {count}: err={r.get('err')}, qid={r.get('queueId')}")
        if r.get('err') == '0':
            print("SUCCESS! March launched!")
            break

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
