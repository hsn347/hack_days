"""ONEMT HTTPS SDK authentication (Step 1 of the login pipeline)."""

import hashlib
import json
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

import config


def hash_sdk_password(password: str) -> str:
    """Compute ONEMT's double-salted MD5 password hash."""
    salted = f"{config.SDK_PWD_PREFIX}{password}{config.SDK_PWD_SUFFIX}"
    first_round = hashlib.md5(salted.encode("utf-8")).hexdigest()
    return hashlib.md5(first_round.encode("utf-8")).hexdigest()


def build_device_id(email: str) -> str:
    """Derive a deterministic 32-character hex device ID from email."""
    return hashlib.md5(email.encode("utf-8")).hexdigest()


def sign_sdk_payload(body_map: Dict[str, str]) -> str:
    """Sort payload keys, attach MD5 request signature, and serialize JSON."""
    sorted_map = {key: body_map[key] for key in sorted(body_map)}
    json_to_sign = json.dumps(sorted_map, separators=(",", ":"), ensure_ascii=False)
    raw_sign = json_to_sign + config.SDK_APP_KEY + config.SDK_APP_SIGN_MD5
    sorted_map["sign"] = hashlib.md5(raw_sign.encode("utf-8")).hexdigest()
    return json.dumps(sorted_map, separators=(",", ":"), ensure_ascii=False)


def mask_secret(value: Optional[str], visible: int = 4) -> str:
    """Return a masked preview of a secret token safe for console display."""
    if not value:
        return "<empty>"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]} (len={len(value)})"


def _parse_rspdata(raw_rspdata: Any) -> Dict[str, Any]:
    if isinstance(raw_rspdata, dict):
        return raw_rspdata
    if isinstance(raw_rspdata, str) and raw_rspdata:
        decoded = urllib.parse.unquote(raw_rspdata)
        parsed = json.loads(decoded)
        if isinstance(parsed, dict):
            return parsed
    return {}


def sdk_login(
    email: str,
    password: str,
    device_id: Optional[str] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """Authenticate with ONEMT passport HTTPS API and return userId + sessionId."""
    clean_email = email.strip()
    if not clean_email or not password:
        return {"success": False, "error_code": "INVALID_INPUT", "error_msg": "Email and password are required"}

    resolved_device_id = device_id or build_device_id(clean_email)

    reqdata = json.dumps(
        {
            "name": clean_email,
            "password": hash_sdk_password(password),
            "identifytype": "email",
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )

    body_map = {
        "platform": config.SDK_PLATFORM,
        "appid": config.APP_ID,
        "timestamp": str(int(time.time())),
        "packagename": config.PACKAGE_NAME,
        "lang": config.SDK_LANG,
        "sdid": "",
        "channel": config.SDK_CHANNEL,
        "rstatus": "0",
        "clientversion": config.SDK_CLIENT_VERSION,
        "sessionid": "",
        "originalid": "",
        "deviceid": resolved_device_id,
        "reqdata": urllib.parse.quote(reqdata, safe=""),
        "securemode": "MD5",
    }

    payload_json = sign_sdk_payload(body_map)
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "appid": config.APP_ID,
        "User-Agent": config.SDK_USER_AGENT,
    }

    try:
        response = requests.post(
            config.SDK_LOGIN_URL,
            data=payload_json,
            headers=headers,
            timeout=timeout,
        )
        data = response.json()
    except requests.RequestException as exc:
        return {"success": False, "error_code": "NETWORK_ERROR", "error_msg": str(exc)}
    except ValueError as exc:
        return {"success": False, "error_code": "INVALID_JSON", "error_msg": str(exc)}

    rtncode = data.get("rtncode", "")
    if rtncode not in ("0", "00000", "SUCCESS", 0):
        return {
            "success": False,
            "error_code": str(rtncode),
            "error_msg": data.get("rtnmsg", "Login failed"),
        }

    try:
        rspdata = _parse_rspdata(data.get("rspdata"))
    except ValueError as exc:
        return {"success": False, "error_code": "INVALID_RSPDATA", "error_msg": str(exc)}

    user_id = rspdata.get("userid") or rspdata.get("userId")
    session_id = rspdata.get("sessionid") or rspdata.get("sessionId")
    if not user_id or not session_id:
        return {
            "success": False,
            "error_code": "MISSING_TOKENS",
            "error_msg": "Server returned success without userId/sessionId",
        }

    return {
        "success": True,
        "rtncode": str(rtncode),
        "userId": str(user_id),
        "sessionId": str(session_id),
    }

