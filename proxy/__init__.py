# -*- coding: utf-8 -*-
"""
proxy — حزمة إدارة بروكسيات SOCKS5 المستقلة
"""
from .proxy_manager import (
    get_proxy_for_account,
    is_proxy_enabled,
    get_server_public_ip,
    proxy_status,
    test_single_proxy,
    get_network_mode,
    set_network_mode,
    get_proxy_ip_for_email,
    disable_proxy,
    enable_proxy,
    remove_castle_proxy,
    remove_user_proxy_bindings,
    get_castle_proxy,
    set_castle_proxy,
    reload_proxies,
)

__all__ = [
    "get_proxy_for_account",
    "is_proxy_enabled",
    "get_server_public_ip",
    "proxy_status",
    "test_single_proxy",
    "get_network_mode",
    "set_network_mode",
    "get_proxy_ip_for_email",
    "disable_proxy",
    "enable_proxy",
    "remove_castle_proxy",
    "remove_user_proxy_bindings",
    "get_castle_proxy",
    "set_castle_proxy",
    "reload_proxies",
]
