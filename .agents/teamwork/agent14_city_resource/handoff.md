# QA Verification & Adversarial Review Report: NOTIFY_CITY Mutations
**Agent**: Agent 14 (City & Resource Delta QA Agent)  
**Roles**: Reviewer, Adversarial Critic  
**Working Directory**: `e:\osmanli\.agents\teamwork\agent14_city_resource\`  
**Date**: 2026-11-09T13:53:00Z  

---

## 1. Executive Summary & Review Verdict

- **Review Verdict**: **REQUEST_CHANGES**
- **Integrity Violation Check**: **CLEAN (PASS)**
  - No hardcoded test responses or magic fixtures found in `core/live_memory.py`.
  - Pure algorithmic implementation adhering to project conventions.
- **Core Requirement Verification**: **PASS (4 / 4 Verified in `LiveMemoryEngine`)**
  - Resource delta summation & clamp-to-zero safety: **PASSED**
  - Absolute replacements (`reslist`, `saferes`, `dayMaxRes`): **PASSED**
  - Uncollected resource updates (`updateUnCollectRes`): **PASSED**
  - Second charge queue activation (`openChargeQueue`): **PASSED**
- **Adversarial / Integration Findings**:
  - **Critical Finding 1**: Double-Dispatch bug in `game_client.py:688` causes all `res` deltas, uncollected increments, queue finishes, and backpack counts to be applied **TWICE**.
  - **Major Finding 2**: Omission of client-side `starttime` defaulting in `openChargeQueue` (`core/live_memory.py:643`) breaks `tasks/building.py:716` builder slot evaluation.
  - **Minor Finding 3**: `openChargeQueue` does not insert into `queueCtrl` if `queueCtrl` was initialized as a `list` (from login `retdata`).

---

## 2. 5-Component Handoff Report

### 2.1 Observation

1. **`core/live_memory.py:586-651` (`_handle_notify_city`)**:
   - `res` calculation:
     ```python
     old_val = int(reslist.get(k, 0) or 0)
     new_val = max(0, old_val + int(count))
     reslist[k] = str(new_val) if isinstance(reslist.get(k), str) else new_val
     ```
   - `reslist` replacement:
     ```python
     city_ctrl["reslist"] = copy.deepcopy(delta["reslist"])
     ```
   - `updateUnCollectRes`:
     ```python
     old_cur = int(target_dict.get("curres", 0) or 0)
     new_cur = max(0, old_cur + int(count))
     target_dict["curres"] = str(new_cur) if isinstance(target_dict.get("curres"), str) else new_cur
     ```
   - `openChargeQueue`:
     ```python
     charge_info = copy.deepcopy(delta["openChargeQueue"])
     city_ctrl.setdefault("queue", {})["1201"] = charge_info
     charge_info_q = copy.deepcopy(charge_info)
     charge_info_q["qtype"] = "1201"
     queue_ctrl = self.init_data.setdefault("queueCtrl", {})
     if isinstance(queue_ctrl, dict):
         queue_ctrl["1201"] = charge_info_q
     ```

2. **`game_client.py:674-691` (`_dispatch`)**:
   - Line 676:
     ```python
     if isinstance(c, dict):
         try:
             self.memory_engine.ingest_packet(c)
         except Exception as _e:
             log.debug(f"[LiveMemory] ingest error: {_e}")
     ```
   - Line 681-690:
     ```python
     if cmd == '1009' and isinstance(c, dict):
         data_obj = c.get('data', {})
         if isinstance(data_obj, dict):
             notify_id = str(data_obj.get('notifyID', ''))
             notify_data = data_obj.get('notifyData', [])
             if notify_id:
                 try:
                     self.memory_engine.handle_notify(notify_id, notify_data)
                 except Exception as _e:
                     log.debug(f"[LiveMemory] notify error ({notify_id}): {_e}")
     ```

3. **`core/live_memory.py:510-526` (`ingest_packet`)**:
   - Lines 520-526:
     ```python
     elif str(packet.get("cmd")) == "1009" and isinstance(packet.get("data"), dict):
         notify_id = packet["data"].get("notifyID")
         notify_data = packet["data"].get("notifyData")

     if notify_id is not None and notify_data is not None:
         self.handle_notify(notify_id, notify_data)
     ```

4. **Empirical Reproduction Command & Output**:
   Command:
   ```powershell
   python -c "from core.live_memory import LiveMemoryEngine; e = LiveMemoryEngine({'cityCtrl': {'reslist': {'1001': 1000}}}); c = {'cmd': '1009', 'data': {'notifyID': '9', 'notifyData': [{'res': {'1001': 500}}]}}; e.ingest_packet(c); print('After ingest_packet:', e.init_data['cityCtrl']['reslist']['1001']); e.handle_notify('9', c['data']['notifyData']); print('After handle_notify (step 3):', e.init_data['cityCtrl']['reslist']['1001'])"
   ```
   Verbatim output:
   ```
   After ingest_packet: 1500
   After handle_notify (step 3): 2000
   ```

5. **`game file/lua_src/cityCtrl_dec.lua:1041-1048`**:
   ```lua
   local openChargeQueue = v.openChargeQueue
   if openChargeQueue then
     local starttime = serviceFunctions.systemTime()
     local totaltime = openChargeQueue.totaltime
     local lefttime = openChargeQueue.lefttime
     local curcity = self:getCurCity()
     if curcity then
       curcity:addBuildChargeQueue(gQueueTypeDef.charge_build_queue, starttime, totaltime, lefttime)
   ```

6. **`tasks/building.py:716-720`**:
   ```python
   st = float(q1201.get("starttime", 0))
   tt = float(q1201.get("totaltime", 0))
   if (st + tt) > time.time():
       self.max_build_slots = 2
       return 2
   ```

### 2.2 Logic Chain

1. **Observation 1** establishes that `LiveMemoryEngine._handle_notify_city` implements the mathematical addition and clamp-to-zero logic for `res`, full dictionary assignment for `reslist`, incremental additions to `curres` for `updateUnCollectRes`, and dictionary insertions for `openChargeQueue`.
2. **Observation 3** proves that `LiveMemoryEngine.ingest_packet` explicitly detects `cmd == '1009'` and calls `self.handle_notify(notify_id, notify_data)`.
3. **Observation 2** proves that immediately after line 676 calls `self.memory_engine.ingest_packet(c)`, line 688 calls `self.memory_engine.handle_notify(notify_id, notify_data)` again for the exact same packet.
4. **Observation 4** empirically verifies that a resource delta of +500 results in +1000 in `init_data` when both statements execute.
5. Therefore, any notification containing additive operations (`res` addition or subtraction, `updateUnCollectRes`, queue level upgrades, backpack increments) is mutated twice when arriving over the network stream.
6. **Observation 5** proves that the game server push notification for `openChargeQueue` delivers only `totaltime` and `lefttime`, and Lua client code explicitly synthesizes `starttime = serviceFunctions.systemTime()`.
7. **Observation 1** demonstrates that `core/live_memory.py` copies `delta["openChargeQueue"]` directly without setting `starttime` when absent.
8. **Observation 6** demonstrates that `tasks/building.py` computes `st + tt > time.time()`. When `st` is `0`, `0 + 172800 < time.time()`, causing `tasks/building.py` to mistakenly determine that the second build slot has expired.

### 2.3 Caveats

1. The core logic inside `LiveMemoryEngine._handle_notify_city` is mathematically sound and 100% compliant with Lua specifications when called once. The double-mutation flaw resides in the caller routing (`game_client.py:681-691`).
2. Server login payload (`retdata.cityCtrl.queue['1201']`) does contain `starttime`, so login initialization is unaffected; only asynchronous push notifications via `CMD 1009` are impacted by the missing `starttime` default.

### 2.4 Conclusion

- The implementation of `_handle_notify_city` in `core/live_memory.py` is accurate, robust against clamp-to-zero, and properly isolates mutated dictionaries via deep copy.
- However, the overall task must be marked **REQUEST_CHANGES** due to two actionable defects:
  1. **Critical**: Double dispatch in `game_client.py:681-691` must be removed or guarded to prevent double mutation.
  2. **Major**: `core/live_memory.py:643` should default `starttime = int(time.time())` if omitted in `openChargeQueue` payload, preserving compatibility with `tasks/building.py`.

### 2.5 Verification Method

1. **Unit & Adversarial Test Suite**:
   ```powershell
   python -m unittest tests/test_agent14_city_resource_qa.py
   ```
   Verifies all 20 test cases including resource summation, zero clamp, replacement, uncollected resources, second queue, and the adversarial double-call proof.
2. **Invalidation Condition**:
   If `python -c "from core.live_memory import LiveMemoryEngine; e = LiveMemoryEngine({'cityCtrl': {'reslist': {'1001': 1000}}}); c = {'cmd': '1009', 'data': {'notifyID': '9', 'notifyData': [{'res': {'1001': 500}}]}}; e.ingest_packet(c); e.handle_notify('9', c['data']['notifyData']); print(e.init_data['cityCtrl']['reslist']['1001'])"` produces `1500` instead of `2000`, the double-dispatch issue is resolved.

---

## 3. Adversarial Review Dimension Breakdown

### Challenge 1: Double-Dispatch on Network Ingress (CRITICAL)
- **Challenged Assumption**: "Calling `ingest_packet(c)` and then `handle_notify(notify_id, notify_data)` in `_dispatch` provides redundant safety."
- **Attack Scenario**: Server sends `NOTIFY_CITY` with `res: {"1001": -50000}` (e.g. training troops). The bot subtracts 100,000 food instead of 50,000.
- **Blast Radius**: High. Causes desynchronization of resources, building levels, and inventory counts.
- **Mitigation**: Remove lines 680-691 in `game_client.py`, OR remove notify handling from `ingest_packet`.

### Challenge 2: Missing `starttime` in `openChargeQueue` (MAJOR)
- **Challenged Assumption**: "The server always delivers `starttime` inside `openChargeQueue` push notifications."
- **Attack Scenario**: Player hires a 2nd builder. Server pushes `{"openChargeQueue": {"totaltime": 172800, "lefttime": 86400}}`. `st` defaults to `0`. `tasks/building.py` calculates `(0 + 172800) > 1762700000` -> `False`. Bot fails to utilize the 2nd build queue.
- **Blast Radius**: Medium-High. Bot wastes rented builder time.
- **Mitigation**: Add `charge_info.setdefault("starttime", int(time.time()))` in `core/live_memory.py:644`.

### Challenge 3: `queueCtrl` List Container Typing (MINOR)
- **Challenged Assumption**: "`queueCtrl` is always a `dict`."
- **Attack Scenario**: If `retdata.queueCtrl` was ingested as a `list` of queue dictionaries, `openChargeQueue` does not append `1201` to `queueCtrl`.
- **Mitigation**: In `_handle_notify_city`, append `charge_info_q` to `queue_ctrl` if `isinstance(queue_ctrl, list)`.
