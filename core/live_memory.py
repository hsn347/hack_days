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

    # Equipment items: match by eid (equipment ID)
    "equipmentCtrl.equipment_array": ("eid", "id"),
    "equipment_array": ("eid", "id"),
}

GENERIC_CANDIDATE_KEYS = (
    "index", "id", "eid", "bid", "qtype", "queuetype", "queueId",
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

def resolve_queue_owner_uid(queue_item: Any) -> Optional[str]:
    """
    Extracts owner UID from a local queue entry matching Lua kingdomQueueObjCell:getUid()
    (checks uid, playerID, from.uid, and explicit '<digits>-<seq>' id prefix).
    """
    if not isinstance(queue_item, dict):
        return None
    for key in ("uid", "playerID"):
        val = queue_item.get(key)
        if val not in (None, "", 0, "0"):
            return str(val).strip()
    from_obj = queue_item.get("from")
    if isinstance(from_obj, dict):
        val = from_obj.get("uid")
        if val not in (None, "", 0, "0"):
            return str(val).strip()
    qid = queue_item.get("id") if queue_item.get("id") not in (None, "") else queue_item.get("queueId")
    if qid is not None:
        parts = str(qid).strip().split("-", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[0] != "0":
            return parts[0]
    return None


def is_own_march_queue(queue_item: Any, my_uid: Any) -> bool:
    """
    Returns True if queue_item belongs to `my_uid` (or has no owner metadata, e.g. in unit-test mocks).
    Excludes other alliance/world players' marches when owner UID differs from `my_uid`.
    """
    if not isinstance(queue_item, dict):
        return False
    my_uid_s = str(my_uid).strip() if my_uid not in (None, "", 0, "0") else ""
    if not my_uid_s:
        return True
    owner_uid = resolve_queue_owner_uid(queue_item)
    if not owner_uid:
        return True
    return owner_uid == my_uid_s


class LiveMemoryEngine:
    """
    Central in-memory state engine for the Empire game bot.

    Maintains `init_data`, enforces ingress whitelisting, routes push
    notifications, tracks local march queues, and provides thread-safe access.
    """

    def __init__(self, init_data: Optional[Dict[str, Any]] = None, owner_uid: Any = None):
        self.init_data: Dict[str, Any] = init_data if init_data is not None else {}
        self.local_queues_map: Dict[str, Any] = {}
        self.local_queues_synced: bool = False
        self.owner_uid: str = str(owner_uid).strip() if owner_uid not in (None, "", 0, "0") else ""
        self._thread_lock = threading.RLock()
        self._async_lock: Optional[asyncio.Lock] = None
        self.last_ingest_report: Optional[Dict[str, Any]] = None

    def _resolve_owner_uid(self) -> str:
        if self.owner_uid:
            return self.owner_uid
        for ctrl_name in ("lordInfoCtrl", "loginDataInitCtrl"):
            ctrl = self.init_data.get(ctrl_name)
            if isinstance(ctrl, dict):
                base = ctrl.get("base")
                if isinstance(base, dict) and base.get("uid") not in (None, "", 0, "0"):
                    self.owner_uid = str(base["uid"]).strip()
                    return self.owner_uid
        return ""

    def get_local_queues_breakdown(self) -> Tuple[List[Any], List[Any]]:
        """Returns (own_queues, other_players_queues) from local_queues_map under lock."""
        with self._thread_lock:
            my_uid = self._resolve_owner_uid()
            own: List[Any] = []
            other: List[Any] = []
            for q in self.local_queues_map.values():
                if is_own_march_queue(q, my_uid):
                    own.append(q)
                else:
                    other.append(q)
            return own, other

    def get_own_local_queues(self) -> List[Any]:
        """Returns shallow list copy of active marches belonging strictly to this castle."""
        return self.get_local_queues_breakdown()[0]

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

    def _sync_local_queues_from_list(self, queues: List[Any]) -> None:
        """Synchronizes local_queues_map from a controller-extracted queue list."""
        new_map: Dict[str, Any] = {}
        for m in queues:
            if not isinstance(m, dict):
                continue
            raw_id = m.get("id") if m.get("id") not in (None, "") else m.get("queueId")
            if raw_id:
                new_map[str(raw_id)] = copy.deepcopy(m)
        if new_map or len(queues) == 0:
            self.local_queues_map.clear()
            self.local_queues_map.update(new_map)
        self.local_queues_synced = True
        self.init_data["local_queues"] = self.get_own_local_queues()

    @staticmethod
    def _extract_notification_envelope(packet: Dict[str, Any]) -> Tuple[Any, Any, bool]:
        """Extracts (notify_id, notify_data, is_1009_cmd) from a server packet."""
        is_1009 = str(packet.get("cmd", "")) == "1009"
        if "notifyID" in packet:
            return packet.get("notifyID"), packet.get("notifyData"), is_1009
        data = packet.get("data")
        if isinstance(data, dict) and "notifyID" in data:
            return data.get("notifyID"), data.get("notifyData"), is_1009
        if is_1009 and isinstance(data, dict):
            return data.get("notifyID"), data.get("notifyData"), True
        return None, None, is_1009

    # Mapping of normalized notifyID values -> (handler_method_name, base_targets, requires_data)
    _NOTIFY_ROUTE_TABLE: Dict[str, Tuple[str, Tuple[str, ...], bool]] = {
        "9": ("_handle_notify_city", ("cityCtrl",), True),
        "CITY": ("_handle_notify_city", ("cityCtrl",), True),
        "NOTIFY_CITY": ("_handle_notify_city", ("cityCtrl",), True),
        "NOTIFY_CITY_UPDATE": ("_handle_notify_city", ("cityCtrl",), True),
        "14": ("_handle_notify_queue", ("queueCtrl",), True),
        "QUEUE": ("_handle_notify_queue", ("queueCtrl",), True),
        "NOTIFY_QUEUE": ("_handle_notify_queue", ("queueCtrl",), True),
        "NOTIFY_QUEUE_UPDATE": ("_handle_notify_queue", ("queueCtrl",), True),
        "1051": ("_handle_notify_queue", ("queueCtrl",), True),
        "PLAYER_QUEUE_CHANGE": ("_handle_notify_queue", ("queueCtrl",), True),
        "NOTIFY_PLAYER_QUEUE_CHANGE": ("_handle_notify_queue", ("queueCtrl",), True),
        "1": ("_handle_notify_backpack", ("backpackCtrl",), True),
        "BACKPACK": ("_handle_notify_backpack", ("backpackCtrl",), True),
        "NOTIFY_BACKPACK": ("_handle_notify_backpack", ("backpackCtrl",), True),
        "NOTIFY_BACKPACK_UPDATE": ("_handle_notify_backpack", ("backpackCtrl",), True),
        "15": ("_handle_notify_army", ("armyCtrl",), True),
        "ARMY": ("_handle_notify_army", ("armyCtrl",), True),
        "NOTIFY_ARMY": ("_handle_notify_army", ("armyCtrl",), True),
        "NOTIFY_ARMY_UPDATE": ("_handle_notify_army", ("armyCtrl",), True),
        "104": ("_handle_notify_hero", ("heroCtrl",), True),
        "HERO": ("_handle_notify_hero", ("heroCtrl",), True),
        "NOTIFY_HERO": ("_handle_notify_hero", ("heroCtrl",), True),
        "8": ("_handle_notify_lord", ("lordInfoCtrl",), True),
        "LORD": ("_handle_notify_lord", ("lordInfoCtrl",), True),
        "NOTIFY_LORD": ("_handle_notify_lord", ("lordInfoCtrl",), True),
        "NOTIFY_LORD_UPDATE": ("_handle_notify_lord", ("lordInfoCtrl",), True),
        "7": ("_handle_notify_buff", ("buffCtrl",), True),
        "BUFF": ("_handle_notify_buff", ("buffCtrl",), True),
        "NOTIFY_BUFF": ("_handle_notify_buff", ("buffCtrl",), True),
        "NOTIFY_BUFF_UPDATE": ("_handle_notify_buff", ("buffCtrl",), True),
        "202": ("_handle_notify_local_queue", ("local_queues",), True),
        "LOCAL_QUEUE_SYNC": ("_handle_notify_local_queue", ("local_queues",), True),
        "NOTIFY_LOCAL_QUEUE_SYNC": ("_handle_notify_local_queue", ("local_queues",), True),
        "16": ("_handle_notify_time_reward", ("timeRewardCtrl",), False),
        "20": ("_handle_notify_time_reward", ("timeRewardCtrl",), False),
        "TIME_REWARD": ("_handle_notify_time_reward", ("timeRewardCtrl",), False),
        "NOTIFY_TIME_REWARD": ("_handle_notify_time_reward", ("timeRewardCtrl",), False),
        "NOTIFY_RESET_TIME_REWARD": ("_handle_notify_time_reward", ("timeRewardCtrl",), False),
        "1070": ("_handle_notify_meritorious", ("meritoriousTaskCtrl",), True),
        "MERITORIOUS_TASK": ("_handle_notify_meritorious", ("meritoriousTaskCtrl",), True),
        "NOTIFY_MERITORIOUS_TASK": ("_handle_notify_meritorious", ("meritoriousTaskCtrl",), True),
    }

    def ingest_packet_with_report(self, packet: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Ingests an incoming server packet and returns (init_data, report) where `report`
        describes notification arrival, merge outcome (merged/unhandled/failed/skipped),
        affected init_data controllers, and current live march queue snapshot.
        """
        if not isinstance(packet, dict):
            own_q, other_q = self.get_local_queues_breakdown()
            report = {
                "cmd": "",
                "subcmd": "",
                "is_notification": False,
                "notify_id": None,
                "notify_status": None,
                "notify_detail": None,
                "controller_status": None,
                "merged_controllers": [],
                "updated_keys": [],
                "updated_state": {},
                "local_queues_snapshot": copy.deepcopy(own_q),
                "local_queues_count": len(own_q),
                "all_local_queues_count": len(self.local_queues_map),
                "other_queues_count": len(other_q),
                "local_queues_synced": self.local_queues_synced,
                "overall_status": "ignored",
                "error": None,
                "should_log": False,
            }
            return self.init_data, report

        with self._thread_lock:
            cmd = str(packet.get("cmd", ""))
            subcmd = str(packet.get("subcmd", ""))
            notify_id, notify_data, is_1009 = self._extract_notification_envelope(packet)
            is_notification = bool(notify_id is not None or is_1009)

            notify_status: Optional[str] = None
            notify_detail: Any = None
            notify_targets: List[str] = []
            notify_summary: str = ""
            errors: List[str] = []

            # 1. Check and dispatch push notification payload
            if notify_id is not None:
                str_id = str(notify_id).strip().upper()
                spec = self._NOTIFY_ROUTE_TABLE.get(str_id)
                if spec is None:
                    notify_status = "unhandled_notify"
                    notify_detail = f"لا يوجد معالج للإشعار notifyID={notify_id}"
                elif notify_data is None and spec[2]:
                    notify_status = "empty_notify_data"
                    notify_targets = list(spec[1])
                    notify_detail = f"الإشعار notifyID={notify_id} وصل بدون notifyData"
                else:
                    n_res = self._dispatch_notify(notify_id, notify_data)
                    notify_status = n_res["status"]
                    notify_detail = n_res.get("detail")
                    notify_targets = n_res.get("targets", [])
                    notify_summary = n_res.get("summary", "") or ""
                    if n_res.get("error"):
                        errors.append(n_res["error"])
            elif is_1009:
                notify_status = "missing_notify_id"
                notify_detail = "وصلت حزمة cmd=1009 بدون حقل notifyID"

            # 2. Extract and merge whitelisted controller state
            controller_status: Optional[str] = None
            merged_controllers: List[str] = []
            try:
                controllers = self.extract_controllers(packet)
                if controllers:
                    merged_controllers = list(controllers.keys())
                    smart_deep_merge(self.init_data, controllers, in_place=True)
                    if "local_queues" in controllers and isinstance(self.init_data.get("local_queues"), list):
                        self._sync_local_queues_from_list(self.init_data["local_queues"])
                    elif (
                        ("lordInfoCtrl" in controllers or "loginDataInitCtrl" in controllers)
                        and "local_queues" in self.init_data
                    ):
                        self.init_data["local_queues"] = self.get_own_local_queues()
                    controller_status = "merged"
            except Exception as exc:
                controller_status = "failed"
                errors.append(f"controller_merge: {type(exc).__name__}: {exc}")

            # 3. Collect updated keys and resulting init_data state slice
            updated_keys: List[str] = []
            for k in list(notify_targets) + merged_controllers:
                if k not in updated_keys and k in self.init_data:
                    updated_keys.append(k)
            updated_state = {k: copy.deepcopy(self.init_data.get(k)) for k in updated_keys}

            if errors:
                overall_status = "failed"
            elif notify_status == "merged" or controller_status == "merged":
                overall_status = "merged"
            elif notify_status in ("unhandled_notify", "missing_notify_id", "empty_notify_data", "skipped_empty"):
                overall_status = notify_status
            else:
                overall_status = "ignored"

            is_march_sync_cmd = (cmd == "1007" and subcmd in ("1000", "16"))
            should_log = bool(is_notification or merged_controllers or errors or is_march_sync_cmd)

            own_q, other_q = self.get_local_queues_breakdown()
            queues_snapshot = copy.deepcopy(own_q)
            report = {
                "cmd": cmd,
                "subcmd": subcmd,
                "is_notification": is_notification,
                "notify_id": str(notify_id) if notify_id is not None else None,
                "notify_status": notify_status,
                "notify_detail": notify_detail,
                "notify_controllers": list(notify_targets),
                "new_value_summary": notify_summary,
                "controller_status": controller_status,
                "merged_controllers": merged_controllers,
                "updated_keys": updated_keys,
                "updated_state": updated_state,
                "local_queues_snapshot": queues_snapshot,
                "local_queues_count": len(own_q),
                "all_local_queues_count": len(self.local_queues_map),
                "other_queues_count": len(other_q),
                "local_queues_synced": self.local_queues_synced,
                "overall_status": overall_status,
                "error": " | ".join(errors) if errors else None,
                "should_log": should_log,
            }
            self.last_ingest_report = report

        return self.init_data, report

    def ingest_packet(self, packet: Any) -> Dict[str, Any]:
        """
        Ingests an incoming server packet:
          1. Detects push notification payloads (notifyID/notifyData) and routes them.
          2. Extracts controller state updates, filters by whitelist, and applies smart_deep_merge.
        Returns the updated init_data mapping.
        """
        return self.ingest_packet_with_report(packet)[0]

    # ──────────────────────────────────────────────────────────────────────────
    # Notification Handlers (Lua Model Synchronization)
    # ──────────────────────────────────────────────────────────────────────────

    def _infer_notify_targets(self, str_id: str, base_targets: Tuple[str, ...], notify_data: Any) -> List[str]:
        """Determines which top-level init_data controllers were touched by this notification."""
        targets = list(base_targets)
        items = notify_data if isinstance(notify_data, list) else ([notify_data] if isinstance(notify_data, dict) else [])
        if str_id in ("9", "CITY", "NOTIFY_CITY", "NOTIFY_CITY_UPDATE"):
            if any(isinstance(x, dict) and "openChargeQueue" in x for x in items):
                targets.append("queueCtrl")
        elif str_id in ("14", "QUEUE", "NOTIFY_QUEUE", "NOTIFY_QUEUE_UPDATE",
                        "1051", "PLAYER_QUEUE_CHANGE", "NOTIFY_PLAYER_QUEUE_CHANGE"):
            for item in items:
                if not isinstance(item, dict):
                    continue
                ev = item.get("dispatchQueueEvent") if isinstance(item.get("dispatchQueueEvent"), dict) else item
                qt = str(ev.get("queuetype") or ev.get("qtype") or item.get("queuetype") or item.get("qtype") or "")
                if qt in ("1200", "1201") or ev.get("bid") is not None or ev.get("index") is not None or item.get("bid") is not None:
                    targets.append("cityCtrl")
                    break
        return targets

    _RES_SHORT_NAMES: Dict[str, str] = {
        "1002": "قمح",
        "1003": "خشب",
        "1004": "حديد",
        "1005": "ألماس",
        "1006": "ذهب",
    }

    @staticmethod
    def _fmt_num(val: Any) -> str:
        try:
            f = float(val)
            return f"{int(f):,}" if f.is_integer() else f"{f:.1f}"
        except Exception:
            return str(val)

    def _summarize_notify_value(
        self, handler_name: str, notify_data: Any, detail: Any
    ) -> str:
        """Builds a short, human-readable summary of the updated live-memory value."""
        try:
            items = (
                notify_data
                if isinstance(notify_data, list)
                else ([notify_data] if isinstance(notify_data, dict) else [])
            )
            parts: List[str] = []

            if handler_name == "_handle_notify_local_queue" and isinstance(detail, dict):
                ops = detail.get("ops") or []
                q_cnt = detail.get("queues_count", 0)
                if ops:
                    shown = ", ".join(str(x) for x in ops[:3])
                    extra = f" (+{len(ops) - 3})" if len(ops) > 3 else ""
                    return f"{shown}{extra} | مسيراتي={q_cnt}"
                return f"مسيراتي={q_cnt}"

            if handler_name == "_handle_notify_city":
                city_ctrl = self.init_data.get("cityCtrl", {}) or {}
                reslist = city_ctrl.get("reslist", {}) or {}
                for d in items:
                    if not isinstance(d, dict):
                        continue
                    for rkey in ("res", "reslist"):
                        rmap = d.get(rkey)
                        if isinstance(rmap, dict):
                            for rid in list(rmap.keys())[:4]:
                                k = str(rid)
                                label = self._RES_SHORT_NAMES.get(k, k)
                                parts.append(f"{label}={self._fmt_num(reslist.get(k, rmap[rid]))}")
                    if isinstance(d.get("saferes"), dict):
                        smap = city_ctrl.get("saferes", {}) or {}
                        for rid in list(d["saferes"].keys())[:3]:
                            k = str(rid)
                            parts.append(f"آمن_{self._RES_SHORT_NAMES.get(k, k)}={self._fmt_num(smap.get(k, 0))}")
                    if isinstance(d.get("updateUnCollectRes"), dict):
                        u_map = d["updateUnCollectRes"]
                        blist = city_ctrl.get("blist", []) or []
                        for idx_k in list(u_map.keys())[:3]:
                            cur_v = None
                            for b in blist:
                                if isinstance(b, dict) and str(_extract_field_value(b, "index") or "") == str(idx_k):
                                    binfo = b.get("binfo") if isinstance(b.get("binfo"), dict) else b
                                    cur_v = binfo.get("curres")
                                    break
                            parts.append(f"مبنى#{idx_k}={self._fmt_num(cur_v if cur_v is not None else u_map[idx_k])}")
                        if len(u_map) > 3:
                            parts.append(f"(+{len(u_map) - 3})")
                    if isinstance(d.get("openChargeQueue"), dict):
                        parts.append("طابور_ثاني=مفتوح")

            elif handler_name == "_handle_notify_queue":
                queue_ctrl = self.init_data.get("queueCtrl", {}) or {}
                for it in items[:3]:
                    if not isinstance(it, dict):
                        continue
                    ev = it.get("dispatchQueueEvent") if isinstance(it.get("dispatchQueueEvent"), dict) else it
                    qt = str(ev.get("queuetype") or ev.get("qtype") or it.get("queuetype") or it.get("qtype") or "?")
                    nt = str(ev.get("notifyType") or it.get("notifyType") or "")
                    bid = ev.get("bid") or it.get("bid")
                    if nt.lower() in ("finish", "del", "remove", "cancel") or str(ev.get("optype", "")) == "11":
                        tag = "ملغى" if nt.lower() == "cancel" or str(ev.get("optype", "")) == "11" else "مكتمل"
                        parts.append(f"طابور {qt} ({tag}{f' مبنى#{bid}' if bid else ''})")
                    else:
                        q_obj = queue_ctrl.get(qt, ev) if isinstance(queue_ctrl, dict) else ev
                        tot = q_obj.get("totaltime") if isinstance(q_obj, dict) else None
                        parts.append(f"طابور {qt} (نشط{f' {tot}ث' if tot else ''})")

            elif handler_name == "_handle_notify_backpack":
                bp = self.init_data.get("backpackCtrl", {})
                blk = items[0] if items else {}
                if isinstance(blk, dict):
                    for mode in ("add", "use"):
                        mmap = blk.get(mode)
                        if isinstance(mmap, dict):
                            for item_id in list(mmap.keys())[:4]:
                                k = str(item_id)
                                new_cnt = None
                                if isinstance(bp, dict):
                                    entry = bp.get(k)
                                    new_cnt = entry.get("count") if isinstance(entry, dict) else entry
                                elif isinstance(bp, list):
                                    for entry in bp:
                                        if isinstance(entry, dict) and str(entry.get("id")) == k:
                                            new_cnt = entry.get("count")
                                            break
                                parts.append(f"#{k}={new_cnt if new_cnt is not None else mmap[item_id]}")

            elif handler_name == "_handle_notify_army":
                army_ctrl = self.init_data.get("armyCtrl", {}) or {}
                for it in items[:2]:
                    if not isinstance(it, dict):
                        continue
                    src = it.get("armyInfo") if isinstance(it.get("armyInfo"), dict) else it
                    for sec in ("freeArmy", "totalArmy", "woundedArmy", "trainArmy"):
                        if isinstance(src.get(sec), dict):
                            cur_sec = army_ctrl.get(sec, src[sec])
                            sample = [f"{k}:{self._fmt_num(cur_sec.get(k, v))}" for k, v in list(src[sec].items())[:3]]
                            parts.append(f"{sec}({','.join(sample)})")

            elif handler_name == "_handle_notify_hero":
                h_ctrl = self.init_data.get("heroCtrl")
                h_list = h_ctrl if isinstance(h_ctrl, list) else (h_ctrl.get("heroes", []) if isinstance(h_ctrl, dict) else [])
                h_by_id = {str(h.get("id") or h.get("heroId") or h.get("cId")): h for h in h_list if isinstance(h, dict)}
                seen: List[str] = []
                for it in items:
                    raw = it.get("data") if isinstance(it, dict) and isinstance(it.get("data"), list) else [it]
                    for entry in raw:
                        sub_entries = entry if isinstance(entry, list) else [entry]
                        for h in sub_entries:
                            if not isinstance(h, dict):
                                continue
                            hid = str(h.get("id") or h.get("heroId") or h.get("cId") or "")
                            if hid and hid not in seen:
                                seen.append(hid)
                for hid in seen[:3]:
                    cur = h_by_id.get(hid, {})
                    lv = cur.get("lv", "?")
                    st = (cur.get("status") or {}).get("state", "?") if isinstance(cur.get("status"), dict) else "?"
                    parts.append(f"بطل#{hid}(lv={lv},st={st})")

            elif handler_name == "_handle_notify_lord":
                lord = self.init_data.get("lordInfoCtrl", {}) or {}
                for it in items[:3]:
                    if not isinstance(it, dict):
                        continue
                    key = it.get("key")
                    if key and isinstance(key, str):
                        cur_sub = lord.get(key, {})
                        for fk in [k for k in it.keys() if k != "key"][:3]:
                            val = cur_sub.get(fk, it[fk]) if isinstance(cur_sub, dict) else it[fk]
                            parts.append(f"{key}.{fk}={self._fmt_num(val) if isinstance(val, (int, float)) else val}")
                    else:
                        for fk in list(it.keys())[:3]:
                            val = lord.get(fk, it[fk])
                            if not isinstance(val, (dict, list)):
                                parts.append(f"{fk}={val}")
                            else:
                                parts.append(f"{fk}=محدّث")

            elif handler_name == "_handle_notify_buff":
                for it in items[:3]:
                    if not isinstance(it, dict):
                        continue
                    st = it.get("syncType") or "update"
                    ids = it.get("list") if isinstance(it.get("list"), list) else ([it.get("id")] if it.get("id") else [])
                    id_strs = [str(x.get("id") if isinstance(x, dict) else x) for x in ids[:3] if x is not None]
                    parts.append(f"{st}({','.join(id_strs)})" if id_strs else str(st))

            elif handler_name == "_handle_notify_time_reward":
                tr = self.init_data.get("timeRewardCtrl", {}) or {}
                parts.append(f"isReceive={tr.get('isReceive')}, isAllReceive={tr.get('isAllReceive', 0)}")

            elif handler_name == "_handle_notify_meritorious":
                merit = self.init_data.get("meritoriousTaskCtrl", {}) or {}
                blk = items[0] if items else {}
                if isinstance(blk, dict):
                    flag = blk.get("flag")
                    payload = blk.get("data", {})
                    if flag == "base" and isinstance(payload, dict):
                        for k in list(payload.keys())[:3]:
                            parts.append(f"{k}={merit.get(k, payload[k])}")
                    elif flag == "task" and isinstance(payload, dict):
                        adds = payload.get("add", {})
                        if isinstance(adds, dict):
                            for cat, tmap in list(adds.items())[:2]:
                                if isinstance(tmap, dict):
                                    for tid in list(tmap.keys())[:2]:
                                        cur_t = (merit.get(cat) or {}).get(str(tid), tmap[tid])
                                        if isinstance(cur_t, dict) and ("cNum" in cur_t or "lNum" in cur_t):
                                            parts.append(f"#{tid}={cur_t.get('cNum', 0)}/{cur_t.get('lNum', 0)}")
                                        else:
                                            parts.append(f"{cat}.{tid}")

            summary = ", ".join(parts)
            if len(summary) > 120:
                summary = summary[:117] + "..."
            return summary
        except Exception:
            return ""

    def _dispatch_notify(self, notify_id: Union[int, str], notify_data: Any) -> Dict[str, Any]:
        """Routes a notification to its synchronizer and returns execution telemetry."""
        with self._thread_lock:
            str_id = str(notify_id).strip().upper()
            spec = self._NOTIFY_ROUTE_TABLE.get(str_id)
            if spec is None:
                return {
                    "matched": False,
                    "status": "unhandled_notify",
                    "targets": [],
                    "detail": f"لا يوجد معالج للإشعار notifyID={notify_id}",
                    "summary": "",
                    "error": None,
                }

            handler_name, base_targets, _requires_data = spec
            handler = getattr(self, handler_name)
            try:
                if handler_name == "_handle_notify_time_reward":
                    res = handler(notify_data, str_id)
                else:
                    res = handler(notify_data)
            except Exception as exc:
                logger.debug(f"[LiveMemory] handle_notify({notify_id}) failed: {exc}")
                return {
                    "matched": True,
                    "status": "failed",
                    "targets": list(base_targets),
                    "detail": f"فشل معالج {handler_name}",
                    "summary": "",
                    "error": f"{handler_name}: {type(exc).__name__}: {exc}",
                }

            targets = self._infer_notify_targets(str_id, base_targets, notify_data)
            summary = self._summarize_notify_value(handler_name, notify_data, res)
            if isinstance(res, dict) and handler_name == "_handle_notify_local_queue":
                if res.get("applied", 0) == 0:
                    return {
                        "matched": True,
                        "status": "skipped_empty",
                        "targets": targets,
                        "detail": res,
                        "summary": summary,
                        "error": None,
                    }
            return {
                "matched": True,
                "status": "merged",
                "targets": targets,
                "detail": res if res is not None else handler_name,
                "summary": summary,
                "error": None,
            }

    def handle_notify(self, notify_id: Union[int, str], notify_data: Any) -> None:
        """
        Dispatches server push notifications to their respective controller synchronizers.
        """
        self._dispatch_notify(notify_id, notify_data)

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
                if "totalArmy" in army_info:
                    army_ctrl["totalArmy"] = copy.deepcopy(army_info["totalArmy"])
                if "woundedArmy" in army_info:
                    army_ctrl["woundedArmy"] = copy.deepcopy(army_info["woundedArmy"])
                if "trainArmy" in army_info:
                    army_ctrl["trainArmy"] = copy.deepcopy(army_info["trainArmy"])
                smart_deep_merge(army_ctrl, army_info, in_place=True)
            else:
                if "totalArmy" in item:
                    army_ctrl["totalArmy"] = copy.deepcopy(item["totalArmy"])
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

    @staticmethod
    def _extract_queue_id(data: Dict[str, Any]) -> str:
        """Extracts string march/queue ID from 'id' or fallback 'queueId'."""
        raw_id = data.get("id") if data.get("id") is not None else data.get("queueId")
        if raw_id is None:
            return ""
        s_id = str(raw_id)
        return s_id if s_id != "" else ""

    _QUEUE_MSG_TYPE_ALIASES: Dict[str, int] = {
        "ADD": 1,
        "REMOVE": 2,
        "UPDATE": 3,
        "ADD_ALL": 4,
        "REMOVE_ALL": 5,
        "DEL_WATCH_POS": 11,
        "QUEUE_TARGET_STATUS": 21,
    }

    @classmethod
    def _normalize_queue_msg_type(cls, raw_type: Any) -> Optional[int]:
        if isinstance(raw_type, bool) or raw_type is None:
            return None
        if isinstance(raw_type, int):
            return raw_type
        s = str(raw_type).strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        return cls._QUEUE_MSG_TYPE_ALIASES.get(s.upper())

    def _handle_notify_local_queue(self, notify_data: Any) -> Dict[str, Any]:
        """
        Synchronizes NOTIFY_LOCAL_QUEUE_SYNC (202):
          - msgType 1 (ADD): Inserts new march line.
          - msgType 2 (REMOVE): Deletes completed/recalled march line.
          - msgType 3 (UPDATE): Updates active march line.
          - msgType 4 (ADD_ALL): Full replacement (list or keyed dict).
          - msgType 5 (REMOVE_ALL): Clears all marches.
          - msgType 11/21: Watch/target status acks defined in gQueueSyncMsgType.
        Returns summary dict of applied/skipped operations.
        """
        if isinstance(notify_data, list):
            items = notify_data
        elif isinstance(notify_data, dict):
            if "msgType" not in notify_data and any(
                isinstance(v, dict) and "msgType" in v for v in notify_data.values()
            ):
                items = list(notify_data.values())
            else:
                items = [notify_data]
        else:
            items = [] if notify_data is None else [notify_data]

        ops: List[str] = []
        applied = 0
        skipped = 0

        for msg in items:
            if not isinstance(msg, dict):
                skipped += 1
                ops.append("SKIP(non-dict)")
                continue

            raw_type = msg.get("msgType")
            msg_type = self._normalize_queue_msg_type(raw_type)
            data = msg.get("data")

            if msg_type == 1 and isinstance(data, dict):  # ADD
                qid = self._extract_queue_id(data)
                if qid:
                    self.local_queues_map[qid] = copy.deepcopy(data)
                    applied += 1
                    ops.append(f"ADD({qid})")
                else:
                    skipped += 1
                    ops.append("SKIP(ADD no-id)")
            elif msg_type == 2 and isinstance(data, dict):  # REMOVE
                qid = self._extract_queue_id(data)
                if qid:
                    existed = qid in self.local_queues_map
                    self.local_queues_map.pop(qid, None)
                    applied += 1
                    ops.append(f"REMOVE({qid}{' hit' if existed else ' miss'})")
                else:
                    skipped += 1
                    ops.append("SKIP(REMOVE no-id)")
            elif msg_type == 3 and isinstance(data, dict):  # UPDATE
                qid = self._extract_queue_id(data)
                if qid:
                    if qid in self.local_queues_map:
                        smart_deep_merge(self.local_queues_map[qid], data, in_place=True)
                    else:
                        self.local_queues_map[qid] = copy.deepcopy(data)
                    applied += 1
                    ops.append(f"UPDATE({qid})")
                else:
                    skipped += 1
                    ops.append("SKIP(UPDATE no-id)")
            elif msg_type == 4 and isinstance(data, (list, dict)):  # ADD_ALL
                new_map: Dict[str, Any] = {}
                entries = enumerate(data) if isinstance(data, list) else data.items()
                for k, m in entries:
                    if isinstance(m, dict):
                        qid = self._extract_queue_id(m)
                        if not qid and isinstance(data, dict) and str(k) not in ("", "0"):
                            qid = str(k)
                        if qid and qid != "0":
                            new_map[qid] = copy.deepcopy(m)
                self.local_queues_map.clear()
                self.local_queues_map.update(new_map)
                applied += 1
                ops.append(f"ADD_ALL({len(new_map)})")
            elif msg_type == 5:  # REMOVE_ALL
                self.local_queues_map.clear()
                applied += 1
                ops.append("REMOVE_ALL")
            elif msg_type in (11, 21):  # DEL_WATCH_POS / QUEUE_TARGET_STATUS
                applied += 1
                ops.append(f"ACK({msg_type})")
            else:
                skipped += 1
                ops.append(f"SKIP(msgType={raw_type})")

        if applied > 0:
            self.local_queues_synced = True

        own_q, other_q = self.get_local_queues_breakdown()
        # Mirror strictly own-castle marches in init_data["local_queues"]
        self.init_data["local_queues"] = own_q
        return {
            "ops": ops,
            "applied": applied,
            "skipped": skipped,
            "queues_count": len(own_q),
            "all_queues_count": len(self.local_queues_map),
            "other_queues_count": len(other_q),
        }

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
