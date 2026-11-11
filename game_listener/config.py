"""Configuration constants for the Days of Empire listener."""

# Verified from game file/lua_src/src/src/app/svrconfig.lua (lines 6, 43, 94)
APP_ID = "100002001"
PACKAGE_NAME = "and.onemt.boe.tr"
LOGIN_SERVER_HOST = "119.8.212.255"
LOGIN_SERVER_PORT = 10000

# Android ONEMT native SDK parameters (documented in core/onemt_auth.py)
SDK_LOGIN_URL = "https://apiuc.menaapp.net/v5/passport/login"
SDK_APP_KEY = "d252596f076c9213dce69cdb39d488ea"
SDK_APP_SIGN_MD5 = "47965E93AD48A1D34F9EF116405AA6CF"
SDK_PWD_PREFIX = "gqY6DBt"
SDK_PWD_SUFFIX = "Oed76U0"
SDK_PLATFORM = "android"
SDK_CHANNEL = "googleplay"
SDK_CLIENT_VERSION = "5.33.0"
SDK_LANG = "ar"
SDK_USER_AGENT = "okhttp/3.14.9"

# Login Server client metadata (GAME_VERSION verified from live protocol in core/onemt_bot.py)
GAME_VERSION = "3.34.001"
DEFAULT_DEVICE_PLATFORM = "Android 14 SM-S918B Google and.onemt.boe.tr ar"
DEFAULT_DEVICE_MODEL = "SM-S918B"
DEFAULT_DEVICE_CARRIER = "STC"

# Gate protocol constants verified from gate_dec.lua (lines 19-21) & cmdDef_dec.lua (lines 2-3)
GATE_XOR_KEY = "OSxHP.!-wd?'lao5"
GATE_CMD_PREFIX = "onemt_"
GATE_MAX_REQUEST_SIZE = 65535
CMD_LOGIN_DATA_INIT = "1000"
REQ_LOGIN_DATA_INIT = "1"
