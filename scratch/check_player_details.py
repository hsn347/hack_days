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

    # Look for hero data in conn.init_data
    hd = conn.init_data.get('heroCtrl', {}) or conn.init_data.get('heroAgCtrl', {})
    print("Hero keys:", list(hd.keys()) if isinstance(hd, dict) else type(hd))
    
    # Check player lord level or city level
    city = conn.init_data.get('cityCtrl', {})
    print("City level:", city.get('level'), city.get('name'))
    
    # Check max march size or player attributes
    player = conn.init_data.get('playerCtrl', {})
    print("Player keys:", list(player.keys()) if isinstance(player, dict) else type(player))
    print("Lord level:", player.get('level'), "Vip:", player.get('vipLevel'))

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
