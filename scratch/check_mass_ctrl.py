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

    for k in sorted(conn.init_data.keys()):
        if "mass" in k.lower() or "rally" in k.lower() or "queue" in k.lower() or "march" in k.lower() or "battle" in k.lower():
            print(k, conn.init_data[k])

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
