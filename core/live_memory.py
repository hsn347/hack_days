# -*- coding: utf-8 -*-
r"""
core/live_memory.py — Production-Grade Live State Memory Engine for Empire Game Bot
══════════════════════════════════════════════════════════════════════════════════
Author: Core Live Memory Engineer (Agent 8 Implementation)
Workspace: e:\osmanli

Key Responsibilities:
  1. Ingress Controller Whitelisting: Strips any non-whitelisted controller from
     incoming server packets (retdata / data / notifyData) to eliminate memory leaks.
  2. Smart Deep Merge Engine: Recursively merges nested dictionaries and applies
     Copy-on-Write (CoW) entity-keyed updates to lists without wipes or duplicates.
  3. Real-Time Notification Synchronizers: Handles push notifications (NOTIFY_CITY,
     NOTIFY_QUEUE, NOTIFY_BACKPACK, NOTIFY_ARMY, NOTIFY_HERO, NOTIFY_LORD, NOTIFY_BUFF,
     NOTIFY_LOCAL_QUEUE_SYNC) reflecting state transitions directly into memory.
  4. Strict Memory Readiness Gate: Validates structural integrity of critical
     startup controllers before allowing bot execution.
  5. Concurrency & Thread-Safety: Dual-lock protection via threading.RLock and asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger("LiveMemory")

# ══════════════════════════════════════════════════════════════════════════════
# 1. Controller Whitelists & Startup Readiness Definitions
# ══════════════════════════════════════════════════════════════════════════════

# Authoritative frozenset of exactly 43 controllers required by bot tasks & systems
ALLOWED_CONTROLLERS: FrozenSet[str] = frozenset({
    # --- Critical Startup Core (6) ---
    "cityCtrl",
    "lordInfoCtrl",
    "queueCtrl",
    "armyCtrl",
    "heroCtrl",
    "backpackCtrl",

    # --- Core Subsystems & Progression (11) ---
    "allianceCtrl",
    "technologyCtrl",
    "vipCtrl",
    "meritoriousTaskCtrl",
    "timeRewardCtrl",
    "lordSkillCtrl",
    "boeAttributeCtrl",
    "buffCtrl",
    "petCtrl",
    "kingdomMapCtrl",
    "buyStaminaCtrl",

    # --- Feature & Activity Tasks (22) ---
    "salesRoomAgCtrl",
    "pyramidCtrl",
    "heroVoyageAgCtrl",
    "heroEnlistCtrl",
    "heroTacticalHallAgCtrl",
    "heroTacticalHallCtrl",
    "heroEquipAgCtrl",
    "runeForgeAgCtrl",
    "allianceTreasureCtrl",
    "cumulateRewardData",
    "fieldShopCtrl",
    "PveBattleCtrl",
    "badgeExchangeCtrl",
    "savingsBankAgCtrl",
    "troyTreasureAgCtrl",
    "exchangeStoreAgCtrl",
    "generalAtyMgr",
    "activityShowCtrl",
    "godBeastCtrl",
    "equipmentCtrl",
    "playerCtrl",
    "itemShop",
    "shopItemBuyTimesMgr",

    # --- Aliases & Internal State Keys (4) ---
    "lord",
    "loginDataInitCtrl",
    "item_sign",
    "local_queues",
})

# The exact 6 controllers required before allowing any bot task to execute
CRITICAL_STARTUP_CONTROLLERS: FrozenSet[str] = frozenset({
    "cityCtrl",
    "lordInfoCtrl",
    "queueCtrl",
    "armyCtrl",
    "heroCtrl",
    "backpackCtrl",
})

# Fallback queries mapping critical controller -> (cmd, subcmd, payload)
FALLBACK_QUERIES: Dict[str, Tuple[int, int, Dict[str, Any]]] = {
    "cityCtrl": (1001, 1, {}),
    "lordInfoCtrl": (1002, 7, {"uid": 0}),
    "queueCtrl": (1003, 1, {}),
    "armyCtrl": (1005, 1, {}),
    "backpackCtrl": (1004, 1, {}),
    "local_queues": (1007, 1000, {}),
}


def get_fallback_query(controller: str, uid: Any = 0) -> Optional[Tuple[int, int, Dict[str, Any]]]:
    """
    Returns the (cmd, subcmd, payload) tuple for querying missing controller data.
    Populates uid dynamically if provided.
    """
    if controller not in FALLBACK_QUERIES:
        return None
    cmd, subcmd, payload = FALLBACK_QUERIES[controller]
    payload_copy = copy.deepcopy(payload)
    if controller == "lordInfoCtrl" and uid:
        payload_copy["uid"] = uid
    return cmd, subcmd, payload_copy


# ══════════════════════════════════════════════════════════════════════════════
# 2. Domain Constants & Building Lifecycle Definitions
# ══════════════════════════════════════════════════════════════════════════════

class BUILD_STATE:
    NORMAL = "0"
    BUILDING = "1"
    UPGRADING = "2"
    DEMOLISHING = "3"
    LOCK = "8"


class BUILD_OPERATE_TYPE:
    BUILD = 0
    DEMOLISH = 1
    UPGRADE = 2
    CANCEL = 11


# ══════════════════════════════════════════════════════════════════════════════
# 3. Smart Deep-Merge Engine (CoW & Keyed Lists)
# ══════════════════════════════════════════════════════════════════════════════

KeySpec = Union[
    str,
    Sequence[Union[str, Tuple[str, ...]]],
    Callable[[Dict[str, Any]], Optional[str]],
]

DEFAULT_KEY_MAPS: Dict[str, KeySpec] = {
    # City buildings: match by 'index' (including binfo.index); fallback to (bid, iid)
    "cityCtrl.blist": ("index", ("bid", "iid")),
    "blist": ("index", ("bid", "iid")),

    # Heroes: match by id or heroId or cId
    "heroCtrl.heroes": ("id", "heroId", "cId"),
    "heroCtrl": ("id", "heroId", "cId"),
    "heroes": ("id", "heroId", "cId"),

    # Buffs: match by id or buffId
    "buffCtrl": ("id", "buffId"),
    "buffCtrl.list": ("id", "buffId"),
    "buffCtrl.buffList": ("id", "buffId"),

    # Queues: match by qtype, queuetype, queueId, or id
    "queueCtrl": ("qtype", "queuetype", "queueId", "id"),
    "local_queues": ("id",),

    # Consign tasks: match by index or id
    "heroVoyageAgCtrl.consignTasks": ("index", "id"),
    "consignTasks": ("index", "id"),

    # Backpack items if represented as list
    "backpackCtrl.items": ("id", "itemId"),
    "backpackCtrl": ("id", "itemId"),

    # Meritorious tasks
    "meritoriousTaskCtrl.tasks": ("id", "taskId", "dynamicId"),
    "meritoriousTaskCtrl.taskData": ("id", "taskId", "dynamicId"),

    # Alliance help list
    "allianceCtrl.helplist": ("id", "helpId"),
}

GENERIC_CANDIDATE_KEYS = (
    "index", "id", "bid", "qtype", "queuetype", "queueId",
    "heroId", "buffId", "taskId", "helpId", "itemId", "uid", "key"
)


def _extract_field_value(item: Any, field_name: str) -> Optional[Any]:
    """Extracts a field from item directly or from item['binfo']."""
    if not isinstance(item, dict):
        return None
    if field_name in item and item[field_name] is not None:
        return item[field_name]
    binfo = item.get("binfo")
    if isinstance(binfo, dict) and field_name in binfo and binfo[field_name] is not None:
        return binfo[field_name]
    return None


def extract_entity_key(item: Any, key_spec: Optional[KeySpec] = None) -> Optional[str]:
    """
    Extracts a normalized, hashable string identity from a dictionary entity.
    Supports single keys, composite keys (e.g. ('bid', 'iid')), custom extractors,
    and automatic fallback to generic identifiers.
    """
    if not isinstance(item, dict):
        return None

    # 1. Custom callable extractor
    if callable(key_spec):
        res = key_spec(item)
        return str(res).strip() if res is not None else None

    # 2. Explicit key_spec supplied
    if key_spec is not None:
        candidates = [key_spec] if isinstance(key_spec, str) else list(key_spec)

        for candidate in candidates:
            # Composite key: e.g. ("bid", "iid")
            if isinstance(candidate, (tuple, list)):
                parts = []
                all_found = True
                for sub_field in candidate:
                    val = _extract_field_value(item, str(sub_field))
                    if val is None:
                        all_found = False
                        break
                    parts.append(f"{sub_field}:{str(val).strip()}")
                if all_found:
                    return "|".join(parts)
            else:
                # Single candidate field
                val = _extract_field_value(item, str(candidate))
                if val is not None:
                    return f"{candidate}:{str(val).strip()}"

    # 3. Generic heuristic candidate search
    for candidate in GENERIC_CANDIDATE_KEYS:
        val = _extract_field_value(item, candidate)
        if val is not None:
            return f"{candidate}:{str(val).strip()}"

    # 4. Composite fallback for buildings: bid + iid
    bid = _extract_field_value(item, "bid")
    iid = _extract_field_value(item, "iid")
    if bid is not None and iid is not None:
        return f"bid:{str(bid).strip()}|iid:{str(iid).strip()}"

    return None


def _merge_keyed_lists(
    target_list: List[Any],
    update_list: List[Any],
    key_spec: Optional[KeySpec],
    sub_path: Tuple[str, ...],
    key_maps: Mapping[str, KeySpec],
    delete_marker: str = "_delete"
) -> List[Any]:
    """
    Merges update_list into target_list using Copy-on-Write (CoW).
    Replaces the list container reference to preserve iterator integrity
    in concurrent reader coroutines.
    """
    # 1. Build index map of existing target items: key -> (index, dict)
    existing_map: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for idx, item in enumerate(target_list):
        if isinstance(item, dict):
            k = extract_entity_key(item, key_spec)
            if k:
                existing_map[k] = (idx, item)

    # Work on a shallow copy of target_list to guarantee Copy-on-Write
    result_list: List[Any] = list(target_list)
    keys_to_delete: Set[str] = set()

    # 2. Iterate through update_list
    for update_item in update_list:
        if not isinstance(update_item, dict):
            # Non-dict in update list: append if not already present
            if update_item not in result_list:
                result_list.append(copy.deepcopy(update_item))
            continue

        # Check for deletion marker
        is_delete = (
            update_item.get(delete_marker) is True
            or str(update_item.get("notifyType", "")).lower() in ("del", "remove", "cancel", "finish")
            or str(update_item.get("state", "")).lower() in ("del", "demolish_done")
        )

        item_key = extract_entity_key(update_item, key_spec)

        if item_key and item_key in existing_map:
            orig_idx, existing_item = existing_map[item_key]
            if is_delete:
                keys_to_delete.add(item_key)
            else:
                # Merge update_item into existing_item
                smart_deep_merge(
                    target=existing_item,
                    update=update_item,
                    key_maps=key_maps,
                    path=sub_path + (item_key,),
                    in_place=True,
                    delete_marker=delete_marker
                )
        else:
            if not is_delete:
                new_copy = copy.deepcopy(update_item)
                new_copy.pop(delete_marker, None)
                result_list.append(new_copy)
                if item_key:
                    existing_map[item_key] = (len(result_list) - 1, new_copy)

    # 3. Apply deletions cleanly if any
    if keys_to_delete:
        result_list = [
            item for item in result_list
            if not (isinstance(item, dict) and extract_entity_key(item, key_spec) in keys_to_delete)
        ]

    return result_list


def smart_deep_merge(
    target: MutableMapping[str, Any],
    update: Mapping[str, Any],
    key_maps: Optional[Mapping[str, KeySpec]] = None,
    path: Tuple[str, ...] = (),
    in_place: bool = True,
    delete_marker: str = "_delete"
) -> MutableMapping[str, Any]:
    """
    Recursively and atomically merges `update` into `target`.

    Guarantees:
      1. Keyed lists of dictionaries merge elements by identity (no wipes, no duplicates).
      2. Missing entities in keyed lists are appended.
      3. Entities marked for deletion are safely pruned.
      4. Primitive lists are replaced with deep copies of the update list.
      5. Nested dictionaries are deeply traversed and merged.
      6. Untouched target fields are strictly preserved.
      7. Modifying lists swaps the list container reference (Copy-on-Write)
         preventing iterator invalidation in concurrent reader coroutines.
    """
    if not isinstance(target, MutableMapping) or not isinstance(update, Mapping):
        raise TypeError(f"smart_deep_merge requires mappings, got target={type(target)}, update={type(update)}")

    effective_key_maps = DEFAULT_KEY_MAPS if key_maps is None else {**DEFAULT_KEY_MAPS, **key_maps}
    dest = target if in_place else copy.deepcopy(target)

    for key, update_val in update.items():
        current_path = path + (str(key),)
        path_str = ".".join(current_path)

        # Explicit deletion marker at mapping level
        if isinstance(update_val, Mapping) and update_val.get(delete_marker) is True:
            dest.pop(key, None)
            continue

        # 1. Key not in target: insert deep copy
        if key not in dest:
            dest[key] = copy.deepcopy(update_val)
            continue

        target_val = dest[key]

        # 2. Both values are Mappings: recursive deep merge
        if isinstance(target_val, MutableMapping) and isinstance(update_val, Mapping):
            smart_deep_merge(
                target=target_val,
                update=update_val,
                key_maps=effective_key_maps,
                path=current_path,
                in_place=True,
                delete_marker=delete_marker
            )

        # 3. Both values are Lists: smart keyed or primitive list merge
        elif isinstance(target_val, list) and isinstance(update_val, list):
            has_dicts = any(isinstance(x, dict) for x in update_val) or any(isinstance(x, dict) for x in target_val)

            if has_dicts:
                # Resolve key_spec for path
                key_spec = None
                for candidate_path in (path_str, str(key)):
                    if candidate_path in effective_key_maps:
                        key_spec = effective_key_maps[candidate_path]
                        break

                # Apply Copy-on-Write container replacement
                dest[key] = _merge_keyed_lists(
                    target_list=target_val,
                    update_list=update_val,
                    key_spec=key_spec,
                    sub_path=current_path,
                    key_maps=effective_key_maps,
                    delete_marker=delete_marker
                )
            else:
                # Primitive list: replace with deep copy
                dest[key] = copy.deepcopy(update_val)

        # 4. Scalar value, primitive, or mismatched types: replace
        else:
            dest[key] = copy.deepcopy(update_val)

    return dest


# ══════════════════════════════════════════════════════════════════════════════
# 4. Live Memory Engine Class
# ══════════════════════════════════════════════════════════════════════════════

class LiveMemoryEngine:
    """
    Central in-memory state engine for the Empire game bot.

    Maintains `init_data`, enforces ingress whitelisting, routes push
    notifications, tracks local march queues, and provides thread-safe access.
    """

    def __init__(self, init_data: Optional[Dict[str, Any]] = None):
        self.init_data: Dict[str, Any] = init_data if init_data is not None else {}
        self.local_queues_map: Dict[str, Any] = {}
        self._thread_lock = threading.RLock()
        self._async_lock: Optional[asyncio.Lock] = None

    @property
    def async_lock(self) -> asyncio.Lock:
        """Lazily initialize asyncio.Lock inside running event loop."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    # ──────────────────────────────────────────────────────────────────────────
    # Whitelist & Ingress Filtering
    # ──────────────────────────────────────────────────────────────────────────

    def filter_whitelisted(self, packet_data: Any) -> Dict[str, Any]:
        """
        Filters any controller dictionary to retain ONLY keys present in ALLOWED_CONTROLLERS.
        Strips all high-frequency chat, red points, and unused activity garbage.
        """
        if not isinstance(packet_data, dict):
            return {}
        return {k: v for k, v in packet_data.items() if k in ALLOWED_CONTROLLERS}

    def extract_controllers(self, packet: Any) -> Dict[str, Any]:
        """
        Inspects an incoming network packet or data envelope, discovers controller
        payloads (in retdata, data, or packet root), and returns a whitelisted dict.
        """
        if not isinstance(packet, dict):
            return {}

        candidates: List[Dict[str, Any]] = []

        data = packet.get("data")
        if isinstance(data, dict):
            if "retdata" in data and isinstance(data["retdata"], dict):
                candidates.append(data["retdata"])
            candidates.append(data)

        retdata = packet.get("retdata")
        if isinstance(retdata, dict):
            candidates.append(retdata)

        candidates.append(packet)

        for candidate in candidates:
            filtered = self.filter_whitelisted(candidate)
            if filtered:
                return filtered

        return {}

    def ingest_packet(self, packet: Any) -> Dict[str, Any]:
        """
        Ingests an incoming server packet:
          1. Detects push notification payloads (notifyID/notifyData) and routes them.
          2. Extracts controller state updates, filters by whitelist, and applies smart_deep_merge.
        Returns the updated init_data mapping.
        """
        if not isinstance(packet, dict):
            return self.init_data

        with self._thread_lock:
            # 1. Check for Push Notifications
            notify_id = None
            notify_data = None

            if "notifyID" in packet:
                notify_id = packet.get("notifyID")
                notify_data = packet.get("notifyData")
            elif isinstance(packet.get("data"), dict) and "notifyID" in packet["data"]:
                notify_id = packet["data"].get("notifyID")
                notify_data = packet["data"].get("notifyData")
            elif str(packet.get("cmd")) == "1009" and isinstance(packet.get("data"), dict):
                notify_id = packet["data"].get("notifyID")
                notify_data = packet["data"].get("notifyData")

            if notify_id is not None and notify_data is not None:
                self.handle_notify(notify_id, notify_data)

            # 2. Extract and merge whitelisted controller state
            controllers = self.extract_controllers(packet)
            if controllers:
                smart_deep_merge(self.init_data, controllers, in_place=True)

        return self.init_data

    # ──────────────────────────────────────────────────────────────────────────
    # Notification Handlers (Lua Model Synchronization)
    # ──────────────────────────────────────────────────────────────────────────

    def handle_notify(self, notify_id: Union[int, str], notify_data: Any) -> None:
        """
        Dispatches server push notifications to their respective controller synchronizers.
        """
        with self._thread_lock:
            str_id = str(notify_id).strip().upper()

            # NOTIFY_CITY (9)
            if str_id in ("9", "CITY", "NOTIFY_CITY", "NOTIFY_CITY_UPDATE"):
                self._handle_notify_city(notify_data)

            # NOTIFY_QUEUE (14) or NOTIFY_PLAYER_QUEUE_CHANGE (1051)
            elif str_id in ("14", "QUEUE", "NOTIFY_QUEUE", "NOTIFY_QUEUE_UPDATE",
                            "1051", "PLAYER_QUEUE_CHANGE", "NOTIFY_PLAYER_QUEUE_CHANGE"):
                self._handle_notify_queue(notify_data)

            # NOTIFY_BACKPACK (1)
            elif str_id in ("1", "BACKPACK", "NOTIFY_BACKPACK", "NOTIFY_BACKPACK_UPDATE"):
                self._handle_notify_backpack(notify_data)

            # NOTIFY_ARMY (15)
            elif str_id in ("15", "ARMY", "NOTIFY_ARMY", "NOTIFY_ARMY_UPDATE"):
                self._handle_notify_army(notify_data)

            # NOTIFY_HERO (104)
            elif str_id in ("104", "HERO", "NOTIFY_HERO"):
                self._handle_notify_hero(notify_data)

            # NOTIFY_LORD (8)
            elif str_id in ("8", "LORD", "NOTIFY_LORD", "NOTIFY_LORD_UPDATE"):
                self._handle_notify_lord(notify_data)

            # NOTIFY_BUFF (7)
            elif str_id in ("7", "BUFF", "NOTIFY_BUFF", "NOTIFY_BUFF_UPDATE"):
                self._handle_notify_buff(notify_data)

            # NOTIFY_LOCAL_QUEUE_SYNC (202)
            elif str_id in ("202", "LOCAL_QUEUE_SYNC", "NOTIFY_LOCAL_QUEUE_SYNC"):
                self._handle_notify_local_queue(notify_data)

            # NOTIFY_TIME_REWARD (16, 20)
            elif str_id in ("16", "20", "TIME_REWARD", "NOTIFY_TIME_REWARD", "NOTIFY_RESET_TIME_REWARD"):
                self._handle_notify_time_reward(notify_data, str_id)

            # NOTIFY_MERITORIOUS_TASK (1070)
            elif str_id in ("1070", "MERITORIOUS_TASK", "NOTIFY_MERITORIOUS_TASK"):
                self._handle_notify_meritorious(notify_data)

    def _handle_notify_city(self, notify_data: Any) -> None:
        """
        Synchronizes NOTIFY_CITY (Subcmd 9):
          - res: Relative delta addition (clamped to 0).
          - reslist: Full resource map replacement.
          - saferes: Safe resource map replacement/merge.
          - dayMaxRes: Daily gathering cap replacement.
          - updateUnCollectRes: Increments curres on corresponding building by index.
          - openChargeQueue: Activates charge builder queue (1201).
        """
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        city_ctrl = self.init_data.setdefault("cityCtrl", {})

        for delta in items:
            if not isinstance(delta, dict):
                continue

            # 1. Delta resource consumption or additions
            if "res" in delta and isinstance(delta["res"], dict):
                reslist = city_ctrl.setdefault("reslist", {})
                for resid, count in delta["res"].items():
                    k = str(resid)
                    old_val = int(float(reslist.get(k, 0) or 0))
                    new_val = max(0, old_val + int(float(count)))
                    # Preserve original string or int type
                    reslist[k] = str(new_val) if isinstance(reslist.get(k), str) else new_val

            # 2. Full resource list replacement
            if "reslist" in delta and isinstance(delta["reslist"], dict):
                city_ctrl["reslist"] = copy.deepcopy(delta["reslist"])

            # 3. Safe resource replacement / update
            if "saferes" in delta and isinstance(delta["saferes"], dict):
                city_ctrl["saferes"] = copy.deepcopy(delta["saferes"])

            # 4. Daily maximum resources
            if "dayMaxRes" in delta and isinstance(delta["dayMaxRes"], dict):
                city_ctrl["dayMaxRes"] = copy.deepcopy(delta["dayMaxRes"])

            # 5. Uncollected production accumulated in resource buildings
            if "updateUnCollectRes" in delta and isinstance(delta["updateUnCollectRes"], dict):
                blist = city_ctrl.get("blist", [])
                if isinstance(blist, list):
                    for idx_key, count in delta["updateUnCollectRes"].items():
                        target_idx = str(idx_key)
                        for b_item in blist:
                            if not isinstance(b_item, dict):
                                continue
                            b_idx = str(_extract_field_value(b_item, "index") or "")
                            if b_idx == target_idx:
                                target_dict = b_item.get("binfo") if isinstance(b_item.get("binfo"), dict) else b_item
                                old_cur = int(float(target_dict.get("curres", 0) or 0))
                                new_cur = max(0, old_cur + int(float(count)))
                                target_dict["curres"] = str(new_cur) if isinstance(target_dict.get("curres"), str) else new_cur
                                break

            # 6. Second (charge) build queue
            if "openChargeQueue" in delta and isinstance(delta["openChargeQueue"], dict):
                raw_charge = delta["openChargeQueue"]
                charge_info = copy.deepcopy(raw_charge)
                if "starttime" in raw_charge and raw_charge["starttime"] is not None:
                    try:
                        charge_info["starttime"] = int(float(raw_charge["starttime"]))
                    except (ValueError, TypeError):
                        pass
                elif "starttime" in charge_info:
                    del charge_info["starttime"]

                city_ctrl.setdefault("queue", {})["1201"] = charge_info
                charge_info_q = copy.deepcopy(charge_info)
                charge_info_q["qtype"] = "1201"
                queue_ctrl = self.init_data.setdefault("queueCtrl", {})
                if isinstance(queue_ctrl, dict):
                    queue_ctrl["1201"] = charge_info_q

    def _handle_notify_queue(self, notify_data: Any) -> None:
        """
        Synchronizes NOTIFY_QUEUE (14) and NOTIFY_PLAYER_QUEUE_CHANGE (1051):
          - Updates active queue tracking in queueCtrl.
          - On completion or cancellation, matches cityCtrl.blist and updates building state:
            * Regular upgrade: increments lv, sets state = "0" (BUILD_STATE.NORMAL).
            * Honor upgrade: increments honorLv and hlv, sets state = "0".
            * Cancel: sets state = "0" without level change.
        """
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        city_ctrl = self.init_data.setdefault("cityCtrl", {})
        queue_ctrl = self.init_data.setdefault("queueCtrl", {})

        for item in items:
            if not isinstance(item, dict):
                continue

            event = item.get("dispatchQueueEvent") if isinstance(item.get("dispatchQueueEvent"), dict) else item
            data_ctx = event.get("data") if isinstance(event.get("data"), dict) else {}

            qtype = str(event.get("queuetype") or event.get("qtype") or item.get("queuetype") or item.get("qtype") or "")
            notify_type = str(event.get("notifyType") or item.get("notifyType") or "").lower()
            optype = event.get("optype") or data_ctx.get("optype") or item.get("optype")
            optype_str = str(optype) if optype is not None else ""

            # Check if this is a completion, deletion, or cancellation event
            is_finish = notify_type in ("finish", "del", "remove", "cancel") or optype_str == "11"
            is_cancel = notify_type == "cancel" or optype_str == "11"

            # 1. Remove or update in queueCtrl
            if qtype:
                if is_finish:
                    if isinstance(queue_ctrl, dict):
                        queue_ctrl.pop(qtype, None)
                    elif isinstance(queue_ctrl, list):
                        self.init_data["queueCtrl"] = [
                            q for q in queue_ctrl
                            if isinstance(q, dict) and str(q.get("qtype") or q.get("queuetype") or "") != qtype
                        ]
                else:
                    if isinstance(queue_ctrl, dict):
                        queue_ctrl[qtype] = copy.deepcopy(event)

            # 2. Reflect on building in cityCtrl if related to building queues (1200 / 1201) or contains building keys
            bid = event.get("bid") or data_ctx.get("bid") or item.get("bid")
            iid = event.get("iid") or data_ctx.get("iid") or item.get("iid")
            b_index = event.get("index") or data_ctx.get("index") or item.get("index")

            if is_finish and (qtype in ("1200", "1201") or bid is not None or b_index is not None):
                blist = city_ctrl.get("blist", [])
                if isinstance(blist, list):
                    target_b = None
                    for b in blist:
                        if not isinstance(b, dict):
                            continue
                        if b_index is not None and str(_extract_field_value(b, "index")) == str(b_index):
                            target_b = b
                            break
                        if bid is not None and iid is not None:
                            b_bid = str(_extract_field_value(b, "bid"))
                            b_iid = str(_extract_field_value(b, "iid"))
                            if b_bid == str(bid) and b_iid == str(iid):
                                target_b = b
                                break

                    if target_b is not None:
                        binfo = target_b.get("binfo") if isinstance(target_b.get("binfo"), dict) else target_b

                        if is_cancel:
                            # Canceled upgrade: revert state to NORMAL without level increment
                            binfo["state"] = BUILD_STATE.NORMAL
                        else:
                            # Determine if this was an honor upgrade or normal upgrade
                            is_honor = bool(
                                event.get("honorUpgradeWaitRsp")
                                or data_ctx.get("honorUpgradeWaitRsp")
                                or event.get("isHonor")
                                or data_ctx.get("isHonor")
                                or event.get("honor")
                                or str(optype_str).lower() == "honor"
                            )

                            if is_honor:
                                current_hlv = int(binfo.get("honorLv") or binfo.get("hlv") or 0)
                                new_hlv = current_hlv + 1
                                binfo["honorLv"] = str(new_hlv) if isinstance(binfo.get("honorLv"), str) else new_hlv
                                binfo["hlv"] = str(new_hlv) if isinstance(binfo.get("hlv"), str) else new_hlv
                                binfo["state"] = BUILD_STATE.NORMAL
                            elif optype_str in ("2", ""):
                                # Normal building upgrade
                                current_lv = int(binfo.get("lv", 0) or 0)
                                new_lv = current_lv + 1
                                binfo["lv"] = str(new_lv) if isinstance(binfo.get("lv"), str) else new_lv
                                binfo["state"] = BUILD_STATE.NORMAL
                            elif optype_str == "0":
                                # New building construction completed
                                binfo["state"] = BUILD_STATE.NORMAL
                                if int(binfo.get("lv", 0) or 0) == 0:
                                    binfo["lv"] = "1"
                            elif optype_str == "1":
                                # Demolish: prune building from blist
                                self.init_data["cityCtrl"]["blist"] = [
                                    b for b in blist if b is not target_b
                                ]

    def _handle_notify_backpack(self, notify_data: Any) -> None:
        """
        Synchronizes NOTIFY_BACKPACK (Subcmd 1):
          - add: Increments item counts in backpackCtrl.
          - use: Decrements item counts (minimum 0).
        """
        data_block = notify_data[0] if (isinstance(notify_data, list) and notify_data) else notify_data
        if not isinstance(data_block, dict):
            return

        backpack = self.init_data.setdefault("backpackCtrl", {})

        # Handle additions
        add_items = data_block.get("add", {})
        if isinstance(add_items, dict):
            for item_id, count in add_items.items():
                k = str(item_id)
                delta = int(count)
                if isinstance(backpack, dict):
                    if k in backpack:
                        if isinstance(backpack[k], dict):
                            old = int(backpack[k].get("count", 0))
                            backpack[k]["count"] = str(old + delta)
                        else:
                            backpack[k] = max(0, int(backpack[k]) + delta)
                    else:
                        backpack[k] = {"id": k, "count": str(delta)}
                elif isinstance(backpack, list):
                    found = False
                    for entry in backpack:
                        if isinstance(entry, dict) and str(entry.get("id")) == k:
                            entry["count"] = str(int(entry.get("count", 0)) + delta)
                            found = True
                            break
                    if not found:
                        backpack.append({"id": k, "count": str(delta)})

        # Handle consumptions / usage
        use_items = data_block.get("use", {})
        if isinstance(use_items, dict):
            for item_id, count in use_items.items():
                k = str(item_id)
                delta = int(count)
                if isinstance(backpack, dict):
                    if k in backpack:
                        if isinstance(backpack[k], dict):
                            old = int(backpack[k].get("count", 0))
                            backpack[k]["count"] = str(max(0, old - delta))
                        else:
                            backpack[k] = max(0, int(backpack[k]) - delta)
                elif isinstance(backpack, list):
                    for entry in backpack:
                        if isinstance(entry, dict) and str(entry.get("id")) == k:
                            old = int(entry.get("count", 0))
                            entry["count"] = str(max(0, old - delta))
                            break

    def _handle_notify_army(self, notify_data: Any) -> None:
        """Synchronizes NOTIFY_ARMY (15)."""
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        army_ctrl = self.init_data.setdefault("armyCtrl", {})
        for item in items:
            if not isinstance(item, dict):
                continue
            army_info = item.get("armyInfo")
            if isinstance(army_info, dict):
                if "woundedArmy" in army_info:
                    army_ctrl["woundedArmy"] = copy.deepcopy(army_info["woundedArmy"])
                if "trainArmy" in army_info:
                    army_ctrl["trainArmy"] = copy.deepcopy(army_info["trainArmy"])
                smart_deep_merge(army_ctrl, army_info, in_place=True)
            else:
                if "woundedArmy" in item:
                    army_ctrl["woundedArmy"] = copy.deepcopy(item["woundedArmy"])
                if "trainArmy" in item:
                    army_ctrl["trainArmy"] = copy.deepcopy(item["trainArmy"])
                smart_deep_merge(army_ctrl, item, in_place=True)

    def _handle_notify_hero(self, notify_data: Any) -> None:
        """Synchronizes NOTIFY_HERO (104)."""
        heroes_to_merge = []
        if isinstance(notify_data, dict):
            raw_data = notify_data.get("data")
            if isinstance(raw_data, list):
                for sub in raw_data:
                    if isinstance(sub, list):
                        heroes_to_merge.extend(sub)
                    elif isinstance(sub, dict):
                        heroes_to_merge.append(sub)
            else:
                heroes_to_merge.append(notify_data)
        elif isinstance(notify_data, list):
            heroes_to_merge.extend(notify_data)

        if heroes_to_merge:
            hero_ctrl = self.init_data.get("heroCtrl")
            if isinstance(hero_ctrl, list):
                self.init_data["heroCtrl"] = _merge_keyed_lists(
                    target_list=hero_ctrl,
                    update_list=heroes_to_merge,
                    key_spec=("id", "heroId", "cId"),
                    sub_path=("heroCtrl",),
                    key_maps=DEFAULT_KEY_MAPS
                )
            elif isinstance(hero_ctrl, dict) and "heroes" in hero_ctrl and isinstance(hero_ctrl["heroes"], list):
                hero_ctrl["heroes"] = _merge_keyed_lists(
                    target_list=hero_ctrl["heroes"],
                    update_list=heroes_to_merge,
                    key_spec=("id", "heroId", "cId"),
                    sub_path=("heroCtrl", "heroes"),
                    key_maps=DEFAULT_KEY_MAPS
                )
            else:
                self.init_data["heroCtrl"] = heroes_to_merge

    def _handle_notify_lord(self, notify_data: Any) -> None:
        """Synchronizes NOTIFY_LORD (8)."""
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        lord_info = self.init_data.setdefault("lordInfoCtrl", {})

        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key and isinstance(key, str):
                sub_dict = {k: v for k, v in item.items() if k != "key"}
                target_sub = lord_info.setdefault(key, {})
                if isinstance(target_sub, dict):
                    smart_deep_merge(target_sub, sub_dict, in_place=True)
                else:
                    lord_info[key] = copy.deepcopy(sub_dict)
            else:
                smart_deep_merge(lord_info, item, in_place=True)

    def _handle_notify_buff(self, notify_data: Any) -> None:
        """Synchronizes NOTIFY_BUFF (7)."""
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        buff_ctrl = self.init_data.setdefault("buffCtrl", [])

        # Normalize buff_ctrl as list container
        target_list: List[Any]
        if isinstance(buff_ctrl, list):
            target_list = buff_ctrl
        elif isinstance(buff_ctrl, dict) and "buffList" in buff_ctrl and isinstance(buff_ctrl["buffList"], list):
            target_list = buff_ctrl["buffList"]
        else:
            target_list = []
            self.init_data["buffCtrl"] = target_list

        for item in items:
            if not isinstance(item, dict):
                continue
            sync_type = str(item.get("syncType", ""))

            if sync_type == "openBuff":
                buffs = item.get("list", [])
                if isinstance(buffs, list):
                    target_list = _merge_keyed_lists(
                        target_list=target_list,
                        update_list=buffs,
                        key_spec=("id", "buffId"),
                        sub_path=("buffCtrl",),
                        key_maps=DEFAULT_KEY_MAPS
                    )
            elif sync_type in ("closeBuff", "buffFinish"):
                effect_ids = item.get("list") if sync_type == "closeBuff" else [item.get("id")]
                if isinstance(effect_ids, (list, tuple)):
                    to_remove = {str(x) for x in effect_ids if x is not None}
                    target_list = [
                        b for b in target_list
                        if not (isinstance(b, dict) and (str(b.get("id")) in to_remove or str(b.get("effectType")) in to_remove))
                    ]
            elif sync_type == "closeSource":
                src = str(item.get("source", ""))
                if src:
                    target_list = [
                        b for b in target_list
                        if not (isinstance(b, dict) and str(b.get("source")) == src)
                    ]
            else:
                # Direct merge
                if isinstance(item, dict):
                    target_list = _merge_keyed_lists(
                        target_list=target_list,
                        update_list=[item],
                        key_spec=("id", "buffId"),
                        sub_path=("buffCtrl",),
                        key_maps=DEFAULT_KEY_MAPS
                    )

        if isinstance(self.init_data.get("buffCtrl"), dict) and "buffList" in self.init_data["buffCtrl"]:
            self.init_data["buffCtrl"]["buffList"] = target_list
        else:
            self.init_data["buffCtrl"] = target_list

    def _handle_notify_local_queue(self, notify_data: Any) -> None:
        """
        Synchronizes NOTIFY_LOCAL_QUEUE_SYNC (202):
          - msgType 1 (ADD): Inserts new march line.
          - msgType 2 (REMOVE): Deletes completed/recalled march line.
          - msgType 3 (UPDATE): Updates active march line.
          - msgType 4 (ADD_ALL): Full replacement.
          - msgType 5 (REMOVE_ALL): Clears all marches.
        """
        items = notify_data if isinstance(notify_data, list) else [notify_data]
        for msg in items:
            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("msgType")
            data = msg.get("data")

            if msg_type == 1 and isinstance(data, dict):  # ADD
                qid = str(data.get("id", ""))
                if qid:
                    self.local_queues_map[qid] = data
            elif msg_type == 2 and isinstance(data, dict):  # REMOVE
                qid = str(data.get("id", ""))
                self.local_queues_map.pop(qid, None)
            elif msg_type == 3 and isinstance(data, dict):  # UPDATE
                qid = str(data.get("id", ""))
                if qid in self.local_queues_map:
                    smart_deep_merge(self.local_queues_map[qid], data, in_place=True)
                else:
                    self.local_queues_map[qid] = data
            elif msg_type == 4 and isinstance(data, list):  # ADD_ALL
                new_map = {str(m.get("id")): m for m in data if isinstance(m, dict) and m.get("id")}
                self.local_queues_map.clear()
                self.local_queues_map.update(new_map)
            elif msg_type == 5:  # REMOVE_ALL
                self.local_queues_map.clear()

        # Mirror in init_data["local_queues"]
        self.init_data["local_queues"] = list(self.local_queues_map.values())

    def _handle_notify_time_reward(self, notify_data: Any, notify_id: str) -> None:
        """Synchronizes NOTIFY_TIME_REWARD (16) and NOTIFY_RESET_TIME_REWARD (20)."""
        time_reward = self.init_data.setdefault("timeRewardCtrl", {})
        if notify_id in ("16", "TIME_REWARD", "NOTIFY_TIME_REWARD"):
            time_reward["isReceive"] = 2
        elif notify_id in ("20", "NOTIFY_RESET_TIME_REWARD"):
            time_reward["isReceive"] = 1
            time_reward["sequence"] = 1
            time_reward["isAllReceive"] = 0

    def _handle_notify_meritorious(self, notify_data: Any) -> None:
        """Synchronizes NOTIFY_MERITORIOUS_TASK (1070)."""
        data_block = notify_data[0] if (isinstance(notify_data, list) and notify_data) else notify_data
        if not isinstance(data_block, dict):
            return

        merit = self.init_data.setdefault("meritoriousTaskCtrl", {})
        flag = data_block.get("flag")
        payload = data_block.get("data", {})

        if flag == "base" and isinstance(payload, dict):
            smart_deep_merge(merit, payload, in_place=True)
        elif flag == "task" and isinstance(payload, dict):
            add_tasks = payload.get("add", {})
            if isinstance(add_tasks, dict):
                smart_deep_merge(merit, add_tasks, in_place=True)
            remove_tasks = payload.get("remove", {})
            if isinstance(remove_tasks, dict):
                for category, task_map in remove_tasks.items():
                    target_cat = merit.get(category)
                    if isinstance(target_cat, dict) and isinstance(task_map, dict):
                        for tid in task_map.keys():
                            target_cat.pop(str(tid), None)

    # ──────────────────────────────────────────────────────────────────────────
    # Memory Readiness Gate
    # ──────────────────────────────────────────────────────────────────────────

    def is_memory_ready(self) -> Tuple[bool, List[str]]:
        """
        Validates presence and structural validity of CRITICAL_STARTUP_CONTROLLERS:
          1. cityCtrl: dict with non-empty 'blist' list and 'reslist' dict.
          2. lordInfoCtrl: dict with 'base' containing valid 'uid'.
          3. queueCtrl: dict or list.
          4. armyCtrl: dict containing 'totalArmy', 'armyInfo', or 'woundedArmy'.
          5. heroCtrl: list or dict.
          6. backpackCtrl: dict or list.

        Returns (is_ready, missing_or_invalid_controllers).
        """
        with self._thread_lock:
            missing_or_invalid: List[str] = []

            # 1. cityCtrl
            city = self.init_data.get("cityCtrl")
            if not isinstance(city, dict):
                missing_or_invalid.append("cityCtrl")
            else:
                blist = city.get("blist")
                reslist = city.get("reslist")
                if not isinstance(blist, list) or len(blist) == 0:
                    missing_or_invalid.append("cityCtrl.blist")
                if not isinstance(reslist, dict) or len(reslist) == 0:
                    missing_or_invalid.append("cityCtrl.reslist")

            # 2. lordInfoCtrl
            lord = self.init_data.get("lordInfoCtrl")
            if not isinstance(lord, dict):
                missing_or_invalid.append("lordInfoCtrl")
            else:
                base = lord.get("base")
                if not isinstance(base, dict) or not base.get("uid"):
                    missing_or_invalid.append("lordInfoCtrl.base")

            # 3. queueCtrl
            queue = self.init_data.get("queueCtrl")
            if not isinstance(queue, (dict, list)):
                missing_or_invalid.append("queueCtrl")

            # 4. armyCtrl
            army = self.init_data.get("armyCtrl")
            if not isinstance(army, dict):
                missing_or_invalid.append("armyCtrl")
            else:
                has_army_data = (
                    "totalArmy" in army
                    or "armyInfo" in army
                    or "woundedArmy" in army
                )
                if not has_army_data:
                    missing_or_invalid.append("armyCtrl.data")

            # 5. heroCtrl
            heroes = self.init_data.get("heroCtrl")
            if not isinstance(heroes, (list, dict)):
                missing_or_invalid.append("heroCtrl")

            # 6. backpackCtrl
            backpack = self.init_data.get("backpackCtrl")
            if not isinstance(backpack, (dict, list)):
                missing_or_invalid.append("backpackCtrl")

            return (len(missing_or_invalid) == 0, missing_or_invalid)

    # ──────────────────────────────────────────────────────────────────────────
    # Thread-Safe Inspection Snapshot
    # ──────────────────────────────────────────────────────────────────────────

    def get_snapshot(self, controller: Optional[str] = None) -> Any:
        """
        Returns a thread-safe deep copy snapshot of the live memory or a specific controller.
        Prevents 'RuntimeError: dictionary changed size during iteration' in web threads / CLI.
        """
        with self._thread_lock:
            if controller is None:
                return copy.deepcopy(self.init_data)
            val = self.init_data.get(controller)
            return copy.deepcopy(val) if val is not None else {}
