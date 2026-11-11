import getpass
import logging

from auth import mask_secret, sdk_login
from notifications import LiveMemory
from protocol import fetch_init_snapshot, login_to_login_server


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s"
)


def main():
    print("=== Step 1: ONEMT SDK HTTPS Login ===")
    email = input("Email: ").strip()
    password = getpass.getpass("Password (hidden while typing): ")

    logging.info("Sending HTTPS login request to ONEMT SDK...")
    sdk_res = sdk_login(email, password)

    if not sdk_res["success"]:
        logging.error(
            f"SDK Login failed (code={sdk_res.get('error_code')}): "
            f"{sdk_res.get('error_msg')}"
        )
        return

    logging.info("SDK Login succeeded!")
    print(f"  userId    : {sdk_res['userId']}")
    print(f"  sessionId : {mask_secret(sdk_res['sessionId'])}")

    print("\n=== Step 2: Login Server TCP Exchange ===")
    login_res = login_to_login_server(sdk_res["userId"], sdk_res["sessionId"])

    if not login_res["success"]:
        logging.error(
            f"Login Server failed (code={login_res.get('error_code')}): "
            f"{login_res.get('error_msg')}"
        )
        return

    gate = login_res["gate"]
    print("\n=== Gate Ticket Received ===")
    print(f"  kingdomId  : {gate.get('kingdomId')}")
    print(f"  servername : {gate.get('servername')}")
    print(f"  gateip     : {gate.get('gateip')}")
    print(f"  gateport   : {gate.get('gateport')}")
    print(f"  uid        : {gate.get('uid')}")
    print(f"  subid      : {gate.get('subid')}")
    print(f"  secret     : {mask_secret(login_res['secret'].hex())}")

    print("\n=== Step 3 & 4: Gate Handshake + 1000/1 Init Snapshot ===")
    memory = LiveMemory()
    init_res = fetch_init_snapshot(gate, login_res["secret"], memory, index=1)
    if not init_res["success"]:
        logging.error(
            f"Gate Init failed (code={init_res.get('error_code')}): "
            f"{init_res.get('error_msg')}"
        )
        return

    summary = memory.summary()
    print("\n=== LiveMemory Snapshot Loaded ===")
    print(f"  init err       : {init_res['err']}")
    print(f"  packet bytes   : {init_res['raw_bytes']}")
    print(f"  modules count  : {summary['modules_count']}")
    print(f"  modules sample : {summary['modules_sample']}")
    print(f"  lord keys      : {summary['lord_keys']}")
    print(f"  city keys      : {summary['city_keys']}")


if __name__ == "__main__":
    main()
