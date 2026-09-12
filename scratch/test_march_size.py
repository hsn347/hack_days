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

    # Get elite boss
    r_bosses = await conn.query('2011', '3', {"mapType": 24, "num": 5, "x": 425, "y": 427, "range": 2000}, timeout=5)
    boss = r_bosses['result'][0]
    bx, by, tid = boss['x'], boss['y'], boss['id']
    print(f"Targeting: {bx}, {by}, tid={tid}")

    # Use formation 3 heroes: [5501024, 5501033]
    heroes = [5501024, 5501033]

    for count in [200000, 250000, 300000, 350000, 400000, 500000, 1000000]:
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
            "pets": [1262],
            "runePages": [4],
            "matrixType": 1,
            "heros": heroes
        }
        r = await conn.query('1007', '2', payload, timeout=6)
        err = r.get('err')
        qid = r.get('queueId')
        print(f"Troop count {count:,}: err={err}, qid={qid}")
        if err == '0':
            print(f"SUCCESS at count={count:,}! queueId={qid}")
            # Immediately recall / cancel rally
            r_c = await conn.query('1007', '4', {"queueId": qid}, timeout=4)
            print("Cancelled rally:", r_c)
            break

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
