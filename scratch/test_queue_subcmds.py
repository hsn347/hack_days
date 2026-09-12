import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from auto_elf_boss import sdk_login
from game_client import GameConnection, AccountSession

async def main():
    auth = sdk_login("fahed.K140@gmail.com", "mn@123450")
    if not auth.get('success'):
        print("Login failed")
        return
    acc = AccountSession("fahed.K140@gmail.com", auth['userId'], auth['sessionId'])
    conn = GameConnection(acc)
    await conn.connect()
    for _ in range(10):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data:
            break

    # Test 1007/16, 1007/73, 1007/102
    for sc in ['16', '73', '102', '101']:
        try:
            r = await conn.query('1007', sc, {}, timeout=4)
            print(f"1007/{sc} resp:", r)
        except Exception as e:
            print(f"1007/{sc} error:", e)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
