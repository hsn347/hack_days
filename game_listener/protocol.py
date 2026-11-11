"""Login Server TCP protocol (Step 2 of the login pipeline)."""

import base64
import json
import logging
import zlib
from typing import Any, Dict, Optional

import config
from connection import GameConnection
from framing import GateFramer, LineFramer
from notifications import LiveMemory
from skynet_crypt import (
    des_encode,
    dh_exchange,
    dh_secret,
    hmac64,
    random_key,
    skynet_hashkey,
    xor_crypt,
)

# Error codes from game file/lua_src/login_dec.lua (lines 10-19)
LOGIN_ERROR_MESSAGES = {
    400: "Login handshake failed (400)",
    401: "Unauthorized token (401)",
    403: "Forbidden login handler error (403)",
    406: "Account already logging in elsewhere (406)",
    501: "Game server under maintenance / not found (501)",
    502: "Account sealed (502)",
    503: "Game version mismatch (503)",
    504: "SDK token error or expired (504)",
    505: "Cross-server transfer in progress (505)",
}

GATE_TICKET_FIELDS = (
    "kingdomId",
    "servername",
    "gateip",
    "gateport",
    "subid",
    "uid",
    "gateProxyHost",
    "gateProxyPort",
)


def encode_login_token(user_id: str, session_id: str, password_field: str = "password") -> str:
    """Format token string matching login_dec.lua encodetoken()."""
    b64_user = base64.b64encode(user_id.encode("utf-8")).decode("ascii")
    b64_pass = base64.b64encode(password_field.encode("utf-8")).decode("ascii")
    b64_sub = base64.b64encode(session_id.encode("utf-8")).decode("ascii")
    return f"{b64_user}@{b64_pass}:{b64_sub}"


def _encrypt_field(text: str, secret: bytes) -> str:
    encrypted = des_encode(text.encode("utf-8"), secret)
    return base64.b64encode(encrypted).decode("ascii")


def _parse_status_line(line: str) -> tuple[int, str]:
    if len(line) < 3 or not line[:3].isdigit():
        raise ValueError(f"Unexpected Login Server line: {line!r}")
    code = int(line[:3])
    submsg = line[4:] if len(line) > 4 else ""
    return code, submsg


def _decode_gate_ticket(submsg: str) -> Dict[str, str]:
    decoded = base64.b64decode(submsg).decode("utf-8")
    parts = decoded.split("@")
    ticket: Dict[str, str] = {}
    for index, field in enumerate(GATE_TICKET_FIELDS):
        raw_part = parts[index] if index < len(parts) else ""
        ticket[field] = base64.b64decode(raw_part).decode("utf-8") if raw_part else ""
    return ticket


def login_to_login_server(
    user_id: str,
    session_id: str,
    host: str = config.LOGIN_SERVER_HOST,
    port: int = config.LOGIN_SERVER_PORT,
    game_version: str = config.GAME_VERSION,
) -> Dict[str, Any]:
    """Run the 4-step Skynet DH + DES login flow and return Gate ticket + secret."""
    conn = GameConnection(host, port)
    framer = LineFramer()

    try:
        conn.connect()

        # 1) S2C_CHALLENGE -> send client DH public key
        challenge_b64 = framer.read_line(conn.receive)
        challenge = base64.b64decode(challenge_b64)
        client_priv = random_key()
        client_pub_b64 = base64.b64encode(dh_exchange(client_priv)).decode("ascii")
        conn.send(framer.pack(client_pub_b64))
        logging.info("[Login TCP 1/4] Received challenge and sent client DH key")

        # 2) S2C_SERVERKEY -> derive shared secret and send hmac64(challenge, secret)
        server_pub_b64 = framer.read_line(conn.receive)
        server_pub = base64.b64decode(server_pub_b64)
        secret = dh_secret(server_pub, client_priv)
        mac_b64 = base64.b64encode(hmac64(challenge, secret)).decode("ascii")
        conn.send(framer.pack(mac_b64))
        logging.info("[Login TCP 2/4] Derived shared secret and sent HMAC proof")

        # 3) S2C_HANDSHAKE -> verify 200 and send DES-encrypted token + device fields
        hs_line = framer.read_line(conn.receive)
        hs_code, _ = _parse_status_line(hs_line)
        if hs_code != 200:
            return {
                "success": False,
                "error_code": str(hs_code),
                "error_msg": LOGIN_ERROR_MESSAGES.get(hs_code, hs_line),
            }
        logging.info("[Login TCP 3/4] Handshake accepted (200); sending encrypted token")

        token_str = encode_login_token(user_id, session_id)
        auth_payload = "@".join(
            [
                _encrypt_field(token_str, secret),
                _encrypt_field(game_version, secret),
                _encrypt_field(config.DEFAULT_DEVICE_PLATFORM, secret),
                _encrypt_field(config.DEFAULT_DEVICE_MODEL, secret),
                _encrypt_field(config.DEFAULT_DEVICE_CARRIER, secret),
            ]
        )
        conn.send(framer.pack(auth_payload))

        # 4) S2C_AUTH_TOKEN -> parse Gate ticket
        auth_line = framer.read_line(conn.receive)
        auth_code, submsg = _parse_status_line(auth_line)
        if auth_code != 200:
            return {
                "success": False,
                "error_code": str(auth_code),
                "error_msg": LOGIN_ERROR_MESSAGES.get(auth_code, auth_line),
            }

        gate_ticket = _decode_gate_ticket(submsg)
        logging.info("[Login TCP 4/4] Auth token accepted; received Gate ticket")
        return {
            "success": True,
            "gate": gate_ticket,
            "secret": secret,
        }

    except (OSError, ConnectionError, ValueError) as exc:
        return {"success": False, "error_code": "LOGIN_TCP_ERROR", "error_msg": str(exc)}
    finally:
        conn.close()


# Gate handshake error codes from game file/lua_src/gate_dec.lua (lines 13-17)
GATE_ERROR_MESSAGES = {
    400: "Gate bad request (400)",
    401: "Gate unauthorized (401)",
    403: "Gate index expired (403)",
    404: "Gate user not found (404)",
}


def build_gate_handshake(
    uid: str,
    servername: str,
    subid: str,
    secret: bytes,
    index: int = 1,
) -> Dict[str, Any]:
    """Build Gate handshake JSON dict matching gate_dec.lua gate:handshake()."""
    b64_uid = base64.b64encode(uid.encode("utf-8")).decode("ascii")
    b64_srv = base64.b64encode(servername.encode("utf-8")).decode("ascii")
    b64_sub = base64.b64encode(subid.encode("utf-8")).decode("ascii")
    username = f"{b64_uid}@{b64_srv}#{b64_sub}"

    digest = skynet_hashkey(f"{username}:{index}".encode("utf-8"))
    mac = hmac64(digest, secret)
    return {
        "username": username,
        "index": index,
        "hmac": base64.b64encode(mac).decode("ascii"),
    }


def gate_handshake(
    conn: GameConnection,
    framer: GateFramer,
    gate_ticket: Dict[str, str],
    secret: bytes,
    index: int = 1,
) -> Dict[str, Any]:
    """Send Gate handshake over an open GateConnection and verify 200 response."""
    payload_dict = build_gate_handshake(
        uid=gate_ticket.get("uid", ""),
        servername=gate_ticket.get("servername", ""),
        subid=gate_ticket.get("subid", ""),
        secret=secret,
        index=index,
    )
    payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    conn.send(framer.pack(payload_bytes))
    logging.info("[Gate TCP 1/2] Sent handshake packet")

    raw_reply = framer.read_packet(conn.receive)
    reply_text = raw_reply.decode("utf-8", errors="replace").strip()
    code, submsg = _parse_status_line(reply_text)
    if code != 200:
        return {
            "success": False,
            "error_code": str(code),
            "error_msg": GATE_ERROR_MESSAGES.get(code, reply_text),
        }

    logging.info("[Gate TCP 2/2] Gate handshake accepted (200)")
    return {"success": True, "code": code, "submsg": submsg}


def connect_gate_handshake(
    gate_ticket: Dict[str, str],
    secret: bytes,
    index: int = 1,
) -> Dict[str, Any]:
    """Connect to Gate Server, perform handshake, and close cleanly (Step 3 test)."""
    gate_ip = gate_ticket.get("gateip", "")
    gate_port_raw = gate_ticket.get("gateport", "")
    if not gate_ip or not gate_port_raw:
        return {"success": False, "error_code": "INVALID_TICKET", "error_msg": "Missing gateip/gateport"}

    conn = GameConnection(gate_ip, int(gate_port_raw))
    framer = GateFramer()
    try:
        conn.connect()
        return gate_handshake(conn, framer, gate_ticket, secret, index=index)
    except (OSError, ConnectionError, ValueError) as exc:
        return {"success": False, "error_code": "GATE_TCP_ERROR", "error_msg": str(exc)}
    finally:
        conn.close()


def pack_gate_request(
    framer: GateFramer,
    cmd: str,
    subcmd: str,
    data: Optional[Dict[str, Any]] = None,
    session: int = 0,
) -> bytes:
    """Build JSON request, apply XOR + 4-byte session, and wrap in Gate length header."""
    msg = {
        "cmd": f"{config.GATE_CMD_PREFIX}{cmd}",
        "subcmd": subcmd,
        "data": data if data is not None else {},
    }
    json_bytes = json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    xor_bytes = xor_crypt(json_bytes, config.GATE_XOR_KEY.encode("ascii"))
    if len(xor_bytes) + 4 > config.GATE_MAX_REQUEST_SIZE:
        raise ValueError(f"Gate request exceeds max size: {len(xor_bytes) + 4} bytes")
    return framer.pack(xor_bytes + session.to_bytes(4, "big"))


def _inflate_if_needed(raw_bytes: bytes, session: int) -> bytes:
    if session != 0:
        return raw_bytes
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 32):
        try:
            return zlib.decompress(raw_bytes, wbits)
        except zlib.error:
            continue
    return raw_bytes


def decode_gate_response(packet: bytes) -> Dict[str, Any]:
    """Decode Gate packet: tail 5 bytes (ok+session) -> zlib (if session==0) -> XOR -> JSON."""
    if len(packet) < 5:
        raise ValueError(f"Gate response packet too short: {len(packet)} bytes")

    content_bytes = packet[:-5]
    ok = packet[-5] != 0
    session = int.from_bytes(packet[-4:], "big")

    if not ok:
        return {"ok": False, "session": session, "content": None}

    inflated = _inflate_if_needed(content_bytes, session)
    plain_bytes = xor_crypt(inflated, config.GATE_XOR_KEY.encode("ascii"))
    parsed = json.loads(plain_bytes.decode("utf-8"))

    if isinstance(parsed, dict):
        cmd = parsed.get("cmd")
        if isinstance(cmd, str) and cmd.startswith(config.GATE_CMD_PREFIX):
            parsed["cmd"] = cmd[len(config.GATE_CMD_PREFIX) :]

    return {"ok": True, "session": session, "content": parsed}


def fetch_init_snapshot(
    gate_ticket: Dict[str, str],
    secret: bytes,
    memory: LiveMemory,
    index: int = 1,
    max_packets: int = 20,
) -> Dict[str, Any]:
    """Connect to Gate, handshake, send 1000/1, and load retdata into LiveMemory."""
    gate_ip = gate_ticket.get("gateip", "")
    gate_port_raw = gate_ticket.get("gateport", "")
    if not gate_ip or not gate_port_raw:
        return {"success": False, "error_code": "INVALID_TICKET", "error_msg": "Missing gateip/gateport"}

    conn = GameConnection(gate_ip, int(gate_port_raw))
    framer = GateFramer()
    try:
        conn.connect()
        hs = gate_handshake(conn, framer, gate_ticket, secret, index=index)
        if not hs["success"]:
            return hs

        init_pkt = pack_gate_request(
            framer,
            cmd=config.CMD_LOGIN_DATA_INIT,
            subcmd=config.REQ_LOGIN_DATA_INIT,
            data={},
            session=0,
        )
        conn.send(init_pkt)
        logging.info("[Gate 1000/1] Sent LoginDataInit request (session=0)")

        for _ in range(max_packets):
            raw_pkt = framer.read_packet(conn.receive)
            decoded = decode_gate_response(raw_pkt)
            if not decoded["ok"]:
                logging.warning(f"[Gate] Received ok=0 packet (session={decoded['session']})")
                continue

            content = decoded["content"]
            cmd = str(content.get("cmd", ""))
            subcmd = str(content.get("subcmd", ""))
            logging.info(
                f"[Gate RX] cmd={cmd}/{subcmd} session={decoded['session']} raw_bytes={len(raw_pkt)}"
            )

            if cmd == config.CMD_LOGIN_DATA_INIT and subcmd == config.REQ_LOGIN_DATA_INIT:
                err = content.get("err")
                data_obj = content.get("data") or {}
                retdata = data_obj.get("retdata")
                if not isinstance(retdata, dict):
                    return {
                        "success": False,
                        "error_code": str(err),
                        "error_msg": f"1000/1 returned without retdata (err={err})",
                    }
                memory.load_snapshot(retdata)
                return {
                    "success": True,
                    "err": err,
                    "raw_bytes": len(raw_pkt),
                }

        return {"success": False, "error_code": "NO_INIT_RSP", "error_msg": "Did not receive 1000/1 response"}
    except (OSError, ConnectionError, ValueError, json.JSONDecodeError) as exc:
        return {"success": False, "error_code": "GATE_INIT_ERROR", "error_msg": str(exc)}
    finally:
        conn.close()
