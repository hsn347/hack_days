# Handoff Report: Frontend & State Architecture Forensic Survey

- **Agent ID**: Explorer 1 (`explorer_survey_1`)
- **Recipient**: Supreme Orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`)
- **Date**: 2026-11-02
- **Handoff Type**: Hard (Task Complete)
- **Detailed Findings Reference**: `e:\osmanli\.agents\teamwork\explorer_survey_1\report.md`

---

## 1. Observation

Direct observations with verbatim lines from `dashboard/src/`:

1. **State Desynchronization & Conflicting Truths**:
   - `dashboard/src/components/accounts/CastleCard.tsx:64-66`:
     ```tsx
     const [liveCastle, setLiveCastle] = useState<Castle>(castle)
     const [liveState, setLiveState] = useState<string>(castle.bot_status.state)
     const [connState, setConnState] = useState<string>(castle.bot_status?.conn_state ?? '')
     ```
   - `dashboard/src/components/accounts/CastleCard.tsx:133-140`:
     Complex boolean reconciliation resolving 4 distinct states (`connState`, `liveState`, `realStatus`, `bot?.state`).
   - `dashboard/src/components/accounts/TaskTabContent.tsx:731-743`:
     ```tsx
     useEffect(() => {
       return () => {
         if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
         if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
         if (
           !isBatchMode &&
           castle.id &&
           JSON.stringify(draftConfigRef.current) !== JSON.stringify(lastSavedConfigRef.current)
         ) {
           updateCastle(castle.id, { config: draftConfigRef.current as unknown as Record<string, unknown> }).catch(() => {})
         }
       }
     }, [castle.id, isBatchMode])
     ```
     `updateCastle` directly bypasses TanStack Query cache (`setQueryData`) and LocalStorage (`saveCachedCastles`).

2. **Caching & Invalidation Gaps**:
   - `dashboard/src/lib/queryClient.ts:7`:
     `gcTime: 1000 * 60 * 60 * 24` (24-hour garbage collection retention).
   - `dashboard/src/hooks/useAuth.ts:462-468` & `359-363`:
     `logout()` calls `queryClient.clear()` and `saveCachedUser(null)`, but NEVER calls `localStorage.removeItem('ibra_castles_cache_' + userId)`.
   - `dashboard/src/pages/AdminUsersCastles.tsx:76-78`:
     On castle delete, invalidates `admin_users_castles`, `admin_stats`, `admin_users`, but omits `['castles', userUid]`.

3. **Network Inefficiencies & WebSocket Anti-Pattern**:
   - `dashboard/src/lib/botApi.ts`: Zero occurrences of `signal?: AbortSignal` across all 45+ exported API methods.
   - `dashboard/src/components/accounts/CastleCard.tsx:93`:
     `const { status: realStatus } = useRealBotStatus(castle.id)` opens a separate `new WebSocket` per card.
   - `dashboard/src/hooks/useCastles.ts:264-315`:
     `useUserBotStatuses(userId)` provides a single multiplexed `/ws/user-status/${userId}` WebSocket, but is 100% UNUSED.
   - `dashboard/src/hooks/useCastles.ts:513-515`:
     Batch configuration updates execute `await Promise.all(castleIds.map(id => updateCastle(id, ...)))`, firing N parallel HTTP requests.
   - Search inputs in `Accounts.tsx:563`, `Admin.tsx:836`, `AdminUsersCastles.tsx:19`, and `AdminLiveProcesses.tsx:23` have zero debouncing.

4. **Performance & Scalability**:
   - `dashboard/src/pages/Admin.tsx:898-1050`:
     Simultaneously renders desktop table rows and mobile card subtrees for all filtered users without pagination or virtualization.
   - `dashboard/src/components/accounts/CastleCard.tsx:31`:
     657-line component is not wrapped in `React.memo`.
   - `dashboard/src/context/TenantContext.tsx:238`:
     `URL.createObjectURL(manifestBlob)` without `URL.revokeObjectURL()`.

5. **UX, Localization & Security**:
   - `dashboard/src/pages/Admin.tsx:674, 689, 710`: Native blocking `window.confirm()` used for user approvals and bans.
   - `dashboard/src/components/layout/AdminLayout.tsx:189, 217, 309`: Hardcoded Arabic strings for navigation tab titles.
   - `dashboard/src/components/accounts/CastleCard.tsx:543`: `bg-white/[0.04]` and `border-white/8` with zero contrast in light mode.
   - `dashboard/src/lib/savedAccounts.ts:29-53`: Passwords stored in `localStorage` via simple XOR with hardcoded salt `ibra_bot_salt_k9x_`.

---

## 2. Logic Chain

1. **State Divergence & Freezing**:
   - From Obs 1.1: Castle status is stored in 5 places: SQLite DB, TanStack Query cache, LocalStorage, `CastleCard` local state (`liveState`), and WebSocket message stream (`realStatus`).
   - When an action like "stop bot" is taken, `isStopping` is set to true. The prop synchronization effect (`useEffect` lines 84-90) explicitly suppresses server updates when `isStopping` is true. If the stop request fails or WebSocket drops, the component remains locked in `isStoppingActive`.
   - From Obs 1.3: When `TaskTabContent` unmounts, it issues a raw `fetch` via `updateCastle(...)` without calling `qc.setQueryData` or updating `localStorage`. Because TanStack Query caches the previous data with `staleTime: 60s`, re-navigating to the page serves the stale in-memory data, causing user changes to appear lost.

2. **Data Leakage & Stale Hydration**:
   - From Obs 2.2: Because `localStorage.removeItem('ibra_castles_cache_' + userId)` is never called on logout or account switch, castle data persists in the browser. When an account is re-selected, `getCachedCastles()` immediately feeds this stale snapshot into `useCastles` as `initialData`.

3. **Network Overload**:
   - From Obs 3.2 & 3.3: Opening 30 castle cards initiates 30 concurrent WebSocket connections to FastAPI. When the server restarts or network fluctuates, 30 simultaneous reconnect timers fire every 3 seconds.
   - Since `useUserBotStatuses` already exists to serve all castles over one socket, the 1-socket-per-card approach creates 30x unnecessary network connections.
   - From Obs 3.1: Because `botApi.ts` lacks `AbortSignal`, fast tab navigation leaves previous HTTP requests downloading in the background.

4. **Admin UI Lag (INP & LCP)**:
   - From Obs 4.1: Rendering both desktop `<tr>` rows and mobile `<div>` cards for all users mounts hundreds of DOM nodes. With un-debounced search inputs (Obs 3.5), typing "test" triggers 4 sequential full-table re-filtering and re-renders, causing high Input Delay (INP) and frame drops.

---

## 3. Caveats

- **Backend Coupling**: Addressing N+1 batch updates (Obs 3.4) ideally requires a dedicated bulk endpoint on the FastAPI backend (`PUT /api/castles/batch`), though client-side concurrency batching (e.g., p-limit) can mitigate it immediately.
- **WebSocket Backend Route**: Verifying whether `/ws/user-status/{userId}` is fully implemented and stable on the FastAPI backend is necessary before switching all `CastleCard` instances from `useRealBotStatus` to `useUserBotStatuses`.
- **Read-Only Scope**: In strict compliance with instructions, no source files were modified. All proposals are documented in `report.md`.

---

## 4. Conclusion

The frontend codebase has strong aesthetic and functional foundations, but requires architectural stabilization across 4 key fronts:
1. **Unify Truth & Fix Mutations**: Eliminate local state copies in `CastleCard`, ensure `TaskTabContent` unmount flushes to Query cache, and purge `localStorage` castles cache on logout.
2. **Optimize Network**: Add `AbortSignal` across `botApi.ts`, activate the single multiplexed `useUserBotStatuses` WebSocket hook, and debounce all search inputs.
3. **Scale Admin Table**: Implement pagination or virtualization in `Admin.tsx` and eliminate duplicate desktop+mobile DOM mounting.
4. **Clean UX & Security**: Replace `window.confirm()` with styled modals, translate hardcoded Arabic text in `AdminLayout.tsx` and child pages, fix light-mode contrast, and migrate password storage to secure tokens or Web Crypto.

---

## 5. Verification Method

To independently verify all observations:

1. **Verify Unmount Mutation Desync**:
   Inspect `dashboard/src/components/accounts/TaskTabContent.tsx` lines 731-743. Notice the call to raw `updateCastle` without `qc.setQueryData`.
2. **Verify Missing AbortSignal**:
   Run grep search for `signal` in `dashboard/src/lib/botApi.ts`. Confirm it only appears in `checkApiAvailable`.
3. **Verify WebSocket 1-per-card vs multiplexed**:
   Inspect `dashboard/src/components/accounts/CastleCard.tsx` line 93 (`useRealBotStatus`). Then check `dashboard/src/hooks/useCastles.ts` lines 264-315 (`useUserBotStatuses`) and verify with `grep_search` that it is unused.
4. **Verify LocalStorage Leak**:
   Inspect `dashboard/src/hooks/useAuth.ts` lines 462-468 (`logout`) and lines 359-363 (`switchAccount`). Confirm absence of `localStorage.removeItem('ibra_castles_cache_' + userId)`.
5. **Verify Hardcoded Arabic Strings in Admin**:
   Inspect `dashboard/src/components/layout/AdminLayout.tsx` lines 189, 217, 309 and `dashboard/src/pages/AdminLiveProcesses.tsx` lines 168-230.
