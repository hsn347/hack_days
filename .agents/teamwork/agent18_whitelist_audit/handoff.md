# Forensic Audit Report: Whitelist Ingress Filtering & Memory Footprint
**Document ID**: `AUDIT-AGENT18-WHITELIST-MEM-FINAL`  
**Agent**: Agent 18: Whitelist & Memory Footprint Auditor  
**Date**: 2026-11-09T13:56:00Z  
**Target Scope**: Ingress controller filtering, `ALLOWED_CONTROLLERS` enforcement, memory footprint reduction (RSS & JSON serialization), and memory leak / bounded growth validation in `core/live_memory.py` & `game_client.py`.

---

## 1. Observation

### 1.1 Live Game Session Dumps Ingress Audit
We inspected all 4 empirical server session dumps in `docs/`:
- `docs/burcudemr_live_memory.json` (744.0 KB JSON, 225 controllers)
- `docs/jzarco.all_live_memory.json` (660.7 KB JSON, 225 controllers)
- `docs/shook123_live_memory.json` (557.4 KB JSON, 225 controllers)
- `docs/shook124_live_memory.json` (559.2 KB JSON, 225 controllers)

Across these dumps, a total of **226 unique controllers** were observed:
- **39 controllers** belong to `ALLOWED_CONTROLLERS`.
- **187 controllers** are non-whitelisted background noise (chat rooms, video ads, red point beacons, client telemetry, retired seasonal events).

Execution of `python tests/audit_whitelist_memory.py` produced the following verbatim empirical results:
```
[PHASE 1: CATALOG VERIFICATION]
Total unique controllers observed: 226
Expected whitelisted controllers: 39
Expected non-whitelisted controllers to discard: 187
  Dump 'burcudemr_live_memory.json': 225 controllers -> 39 kept. Leaked: 0, Missing: 0, Corrupted: 0 => PASS
  Dump 'jzarco.all_live_memory.json': 225 controllers -> 39 kept. Leaked: 0, Missing: 0, Corrupted: 0 => PASS
  Dump 'shook123_live_memory.json': 225 controllers -> 39 kept. Leaked: 0, Missing: 0, Corrupted: 0 => PASS
  Dump 'shook124_live_memory.json': 225 controllers -> 39 kept. Leaked: 0, Missing: 0, Corrupted: 0 => PASS

  Super Payload (226 controllers wrapped in data.retdata):
    - Total controllers: 226
    - Whitelisted kept: 39 (100% of expected)
    - Non-whitelisted dropped: 187 (100% of non-whitelisted)
    - Leaked noise: 0
    - Famous noise verified absent: chatCtrl, chatroomCtrl, RedPointCtrl, videoAdCtrl, flowerSysCtrl, clientLogCtrl, voiceRoomCtrl, htMsgCtrl, dressCtrl, dressShop, rechargeCtrl, adCtrl
    - Subkey corruption: 0 corrupted fields across all whitelisted entities
```

### 1.2 Memory Footprint Reduction Metrics
Benchmarking JSON serialization size, deep in-memory object graph size (`sys.getsizeof` recursive traversal), and multi-account heap memory (`tracemalloc`) yielded:

| Target Payload | Raw JSON Size | Filtered JSON Size | JSON Reduction % | Raw Deep Graph | Filtered Deep Graph | Deep Graph Reduction % |
|---|---|---|---|---|---|---|
| `burcudemr_live_memory.json` | 744.0 KB | 276.1 KB | **62.89%** | 2,818.4 KB | 1,174.5 KB | **58.33%** |
| `jzarco.all_live_memory.json` | 660.7 KB | 257.4 KB | **61.04%** | 2,420.4 KB | 1,060.9 KB | **56.17%** |
| `shook123_live_memory.json` | 557.4 KB | 206.9 KB | **62.88%** | 1,939.2 KB | 826.4 KB | **57.38%** |
| `shook124_live_memory.json` | 559.2 KB | 208.4 KB | **62.73%** | 1,951.9 KB | 836.4 KB | **57.15%** |
| **226-Controller Super Dump** | **744.1 KB** | **276.1 KB** | **62.90%** | **2,819.3 KB** | **1,174.5 KB** | **58.34%** |

Multi-Account Process Heap Benchmark (100 concurrent accounts):
- Raw 100 Accounts Heap Delta: **201.29 MB**
- Filtered 100 Accounts Heap Delta: **83.89 MB**
- Heap Memory Allocation Reduction: **58.32%** (Savings: **117.40 MB** per 100 accounts)

### 1.3 Memory Leak & Unbounded Dictionary Growth Audit (10,000 Ingestion Cycles)
Simulating 10,000 successive ingress packets (alternating building deltas, chat/red-point noise floods, resource push notifications, and hero level increments) against `LiveMemoryEngine` produced:
```
[Cycle  1000] Controllers: 39 (Delta: 0), blist: 57, heroes: 44, cached: 4, leaks: 0
[Cycle  2500] Controllers: 39 (Delta: 0), blist: 57, heroes: 44, cached: 4, leaks: 0
[Cycle  5000] Controllers: 39 (Delta: 0), blist: 57, heroes: 44, cached: 4, leaks: 0
[Cycle  7500] Controllers: 39 (Delta: 0), blist: 57, heroes: 44, cached: 4, leaks: 0
[Cycle 10000] Controllers: 39 (Delta: 0), blist: 57, heroes: 44, cached: 4, leaks: 0

Leak Audit Verdict: PASS (Zero Unbounded Growth)
  - Controller Key Growth: 0 (bounded strictly at 39)
  - Keyed List (blist) Growth: 0 (bounded strictly at 57 buildings, zero duplicates)
  - Keyed List (heroes) Growth: 0 (bounded strictly at 44 heroes, zero duplicates)
  - Max Cached Packets Length: 4 (ceiling <= 64: True)
  - Net 10,000 Cycle Heap Expansion: 15.46 KB (Stable internal reference reuse)
```

### 1.4 Critical Implementation Vulnerabilities Discovered (Forensic Bug Findings)
During empirical stress-testing against real server data in `docs/burcudemr_live_memory.json`, two crash vectors were uncovered in `core/live_memory.py`:

1. **Vulnerability 1 (`core/live_memory.py:608`) — Fractional Resource Float String Crash**:
   - Code: `old_val = int(reslist.get(k, 0) or 0)`
   - Error: `ValueError: invalid literal for int() with base 10: '514089541.49461'`
   - Root Cause: Real game servers transmit resource amounts in `reslist` with decimals (e.g., `'1002': '514089541.49461'`, `'1003': '1755093362.3596'`). Calling `int('514089541.49461')` raises `ValueError`, crashing `_handle_notify_city`.
   - Recommended Fix: `int(float(reslist.get(k, 0) or 0))`

2. **Vulnerability 2 (`core/live_memory.py:637`) — Fractional Building curres Float String Crash**:
   - Code: `old_cur = int(target_dict.get("curres", 0) or 0)`
   - Error: `ValueError: invalid literal for int() with base 10: '0.0'`
   - Root Cause: Buildings in real session dumps have continuous resource accumulation stored as float strings (`"curres": "0.0"`, `"curres": 24947.94449524`). Calling `int('0.0')` crashes when `updateUnCollectRes` arrives.
   - Recommended Fix: `int(float(target_dict.get("curres", 0) or 0))`

---

## 2. Logic Chain

1. **Premise 1**: The game server pushes packets containing up to 226 distinct controllers, the vast majority of which represent UI telemetry, chat logs, video ads, and unreferenced minigames.
2. **Observation 1**: In `docs/*live_memory.json`, exactly 226 unique controllers were observed. Exactly 39 of them are in `ALLOWED_CONTROLLERS`, and 187 are non-whitelisted.
3. **Observation 2**: When ingested into `LiveMemoryEngine`, `filter_whitelisted` and `extract_controllers` retained exactly 39 controllers across all 4 dumps and the 226-controller super dump. Exactly 187 non-whitelisted controllers were dropped (100% rejection rate). Leaked count was 0.
4. **Observation 3**: Subkey inspection demonstrated that all structures within whitelisted controllers (`cityCtrl.blist`, `cityCtrl.reslist`, `lordInfoCtrl.base`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`) were merged without key omission or structure corruption.
5. **Observation 4**: Filtering reduced JSON serialization size by **62.90%** (744.1 KB to 276.1 KB) and deep object graph size by **58.34%** (2,819.3 KB to 1,174.5 KB). In 100 concurrent accounts, heap memory consumption dropped from **201.29 MB** to **83.89 MB** (**58.32% reduction**).
6. **Observation 5**: Over 10,000 packet ingestion cycles with mixed updates, noise floods, and push notifications, dictionary growth was 0, keyed list duplicate count was 0, and `cached_packets` remained capped at <= 64.
7. **Observation 6**: Directly testing `_handle_notify_city` with live session float strings exposed `ValueError` at lines 608 and 637.
8. **Deduction**: The controller whitelisting, ingress filtering, and dictionary boundedness mechanisms perform with 100% functional integrity and deliver over 58-62% memory reduction. However, numeric parsing in `_handle_notify_city` must be updated to `int(float(...))` to handle live server float strings.

---

## 3. Caveats

1. **Audit Scope**: As an auditor under strict constraints, we did not modify `core/live_memory.py` to fix the two float string vulnerabilities. The findings are documented with reproduction code and exact line numbers for the Track 1 engineering team (`agent4_city_resource` / `agent9_memory_hygiene`) to resolve.
2. **Offline vs Live Socket**: The audit tested both real session payload dumps (`docs/*.json`) and synthetic 226-controller super payloads. Live socket crypto decoding was tested and confirmed via `onemt_bot` crypto modules.
3. **Allowed Controllers Catalog**: 39 out of the 42/43 controllers in `ALLOWED_CONTROLLERS` were present in the live dumps; the remaining 4 controllers (e.g. `lord`, `loginDataInitCtrl`, `item_sign`, `playerCtrl`) are fallback aliases or activity-specific keys that were verified in `tests/test_live_memory.py`.

---

## 4. Conclusion

- **Verdict on Whitelist Ingress Filtering**: **CLEAN / PASS**
  - 100% of 187 non-whitelisted controllers dropped at network ingress.
  - Zero leakage of chat, video ads, or red points.
  - 100% of whitelisted controllers preserved with zero key corruption.
- **Verdict on Memory Footprint Reduction**: **CLEAN / PASS**
  - JSON serialization size reduction: **62.90%**
  - In-memory deep object graph reduction: **58.34%**
  - 100-account heap allocation reduction: **58.32%** (117.4 MB RAM saved per 100 accounts)
- **Verdict on Memory Leak & Bounded Growth**: **CLEAN / PASS**
  - Zero unbounded dictionary growth over 10,000 cycles.
  - Zero duplicate items in keyed lists (`blist`, `heroes`).
  - Packet cache ceiling strictly enforced at <= 64 items.
- **Actionable Defect for Engineering**:
  - Update `core/live_memory.py:608` and `core/live_memory.py:637` to parse via `int(float(...))` to prevent crashes on live session decimal resource values.

---

## 5. Verification Method

To independently reproduce and verify this entire audit:

1. **Run the Forensic Audit Suite**:
   ```powershell
   python tests/audit_whitelist_memory.py
   ```
   *Expected Result*: All 4 dumps pass, super payload passes, memory reduction > 60%, 10,000-cycle leak audit passes with 0 growth, output JSON generated at `.agents/teamwork/agent18_whitelist_audit/audit_raw_results.json`.

2. **Run the Live Memory Unit Test Suite**:
   ```powershell
   python -m unittest tests/test_live_memory.py
   ```
   *Expected Result*: Ran 37 tests in ~0.7s — OK.

3. **Reproduce the Float String Vulnerability in `_handle_notify_city`**:
   ```powershell
   python -c "
   import json
   from core.live_memory import LiveMemoryEngine
   with open('docs/burcudemr_live_memory.json', 'r', encoding='utf-8') as f:
       d = json.load(f)
   e = LiveMemoryEngine()
   e.ingest_packet(d)
   e.handle_notify('9', [{'res': {'1002': 100}}])
   "
   ```
   *Expected Result*: Raises `ValueError: invalid literal for int() with base 10: '514089541.49461'`.
