# Forensic Audit Report: Frontend & State Architecture
**Project**: Osmanli Empire Bot Dashboard (React 18, Vite, TypeScript, Tailwind CSS)  
**Inspector**: Explorer 1 (Frontend & State Architect Explorer / Frontend Network & Performance Auditor)  
**Date**: 2026-11-02  
**Target Directory**: `dashboard/`  
**Governing Documents**: `ORIGINAL_REQUEST.md`, `AGENTS_CONSTITUTION.md`

---

## 1. Executive Summary & Root Cause Matrix

A forensic investigation of the frontend architecture reveals that while modern libraries are integrated (`@tanstack/react-query` v5, `zustand` v5, `framer-motion`, `react-router-dom` v7), the codebase suffers from severe architectural fragmentation:
1. **State Overlap & Divergent Truths**: Castle state is duplicated across 5 disconnected layers (Server DB, TanStack Query cache, LocalStorage cache, Component local state, and direct WebSockets), with tangled reconciliation code that freezes or corrupts UI status.
2. **Silent Mutation Desync**: On component unmount (`TaskTabContent.tsx`), changes are dispatched via unmanaged direct API calls that bypass TanStack Query and LocalStorage, creating an illusion of lost settings when navigating back.
3. **Network Inefficiency & Missing Cancellation**: None of the 45+ API calls in `botApi.ts` implement `AbortController`. In-flight requests cannot be aborted during page transitions. Furthermore, each castle card establishes its own dedicated WebSocket connection instead of using the existing multiplexed user WebSocket hook.
4. **Admin Dashboard Scalability Bottlenecks**: `Admin.tsx` mounts both full desktop table rows AND mobile card subtrees simultaneously for all users without server-side or client-side pagination or virtualization. Keystrokes in search immediately trigger unthrottled re-filtering and massive re-render cascades.
5. **Security & Cleanup Failures**: Plaintext user passwords for fast-switching accounts are stored in `localStorage` using reversible XOR scrambling. LocalStorage castles caches are never cleared on logout or account switching.

### Severity & Impact Matrix

| ID | Issue Description | Severity | Area | Affected Files & Lines |
|---|---|---|---|---|
| **FE-01** | Multiple Conflicting Sources of Truth for Castle State & Tangled Status Logic | **CRITICAL** | State / Truth | `CastleCard.tsx:64-140`, `useCastles.ts:150-173` |
| **FE-02** | Silent Unmount Mutation Desynchronization bypassing Query Cache & LocalStorage | **CRITICAL** | State / Mutations | `TaskTabContent.tsx:731-743` |
| **FE-03** | LocalStorage Cache Leak Across Logouts & Account Switches | **CRITICAL** | Cache / Privacy | `useAuth.ts:359-363, 462-468`, `useCastles.ts:104-147` |
| **FE-04** | Complete Absence of `AbortController` in all 45+ REST API Client Calls | **HIGH** | Network / Lifecycle | `botApi.ts:1-819`, `useCastles.ts`, `useUsers.ts` |
| **FE-05** | WebSocket Flooding (1 Connection Per Card instead of Multiplexed Socket) | **HIGH** | Network / WebSocket | `CastleCard.tsx:93-118`, `useCastles.ts:209-315` |
| **FE-06** | Admin Dashboard DOM Explosion & Missing Pagination / Virtualization | **HIGH** | Scalability / Performance | `Admin.tsx:619, 652-671, 898-1050`, `useUsers.ts:10-18` |
| **FE-07** | N+1 Sequential HTTP Flooding on Batch Settings Update | **HIGH** | Network / Mutations | `useCastles.ts:508-524`, `Accounts.tsx:181-240` |
| **FE-08** | Insecure Reversible XOR Password Storage in `localStorage` | **HIGH** | Security / Storage | `savedAccounts.ts:29-53, 105-141` |
| **FE-09** | Missing Search Input Debouncing / Throttling across all Pages | **MEDIUM** | Performance / INP | `Accounts.tsx:24, 563`, `Admin.tsx:610, 836`, `AdminUsersCastles.tsx:19` |
| **FE-10** | Unmemoized Heavy Components & Context Re-render Cascades | **MEDIUM** | Performance / Renders | `CastleCard.tsx:31`, `useAuth.ts:37-60, 500-515` |
| **FE-11** | Blocking Browser `window.confirm()` Dialogs in Admin Operations | **MEDIUM** | UX / Thread Blocking | `Admin.tsx:674, 689, 706`, `AdminLiveProcesses.tsx:69` |
| **FE-12** | Hardcoded Arabic UI Text Bypassing Trilingual Localization | **MEDIUM** | Localization / i18n | `AdminLayout.tsx:189, 217, 309`, `AdminLiveProcesses.tsx:168-230` |
| **FE-13** | Dark/Light Mode Contrast Inversion (Hardcoded Black/White Opacity) | **MEDIUM** | Theme / CSS | `TaskTabContent.tsx:101-135`, `CastleCard.tsx:543` |
| **FE-14** | Object URL Memory Leak in Dynamic PWA Manifest Generation | **LOW** | Memory Leak | `TenantContext.tsx:238-245` |
| **FE-15** | Unmanaged Mutation Timers in Query Settled Hooks | **LOW** | Timers / Lifecycle | `useCastles.ts:417-420, 462-465` |

---

## 2. Pillar 1: State Management & Single Source of Truth

### 2.1 Multi-Tier State Hierarchy & Data Flow Map

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Backend SQLite (`castles.db` via REST `api_server.py`)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP GET /api/castles
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. TanStack Query Cache (`['castles', userId]`)              │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌─────────────────────────────┐
│ 3. LocalStorage Snapshot     │ │ 4. `AccountsPage` State     │
│ (`ibra_castles_cache_{uid}`) │ │ (`allCastles`, `filtered`)  │
└──────────────────────────────┘ └─────────────┬───────────────┘
                                               │ Props: `castle`
                                               ▼
                                 ┌─────────────────────────────┐
                                 │ 5. `CastleCard` Local State │
                                 │ `liveCastle`, `liveState`   │
                                 └───────┬─────────────▲───────┘
                                         │             │ WS Message
                                         │             │
                                         │       ┌─────┴───────────────┐
                                         │       │ 6. WebSocket Stream │
                                         │       │ `/ws/status/{id}`   │
                                         │       └─────────────────────┘
                                         ▼ Props: `castle.config`
                                 ┌─────────────────────────────┐
                                 │ 7. `TaskTabContent` Draft   │
                                 │ `draftConfig`, `savedConfig`│
                                 └─────────────────────────────┘
```

### 2.2 Deep Finding: 5 Competing State Layers & Broken Status Logic (FE-01)
- **Location**: `dashboard/src/components/accounts/CastleCard.tsx:64-140`
- **Observation**:
  `CastleCard` receives `castle` via props from `useCastles(userId)`. However, it immediately forks it into local component state:
  ```tsx
  // CastleCard.tsx:64-66
  const [liveCastle, setLiveCastle] = useState<Castle>(castle)
  const [liveState, setLiveState] = useState<string>(castle.bot_status.state)
  const [connState, setConnState] = useState<string>(castle.bot_status?.conn_state ?? '')
  ```
  It then opens an independent WebSocket stream (`useRealBotStatus(castle.id)`), which returns `realStatus`.
  To reconcile these diverging states, `CastleCard` implements 15 lines of tangled boolean checks:
  ```tsx
  // CastleCard.tsx:133-140
  const isDeploying    = connState === 'deploying' || liveState === 'deploying' || realStatus === 'deploying'
  const isStoppingActive = isStopping || connState === 'stopping' || liveState === 'stopping' || (realStatus as string) === 'stopping'
  const isError        = !isDeploying && !isStoppingActive && (liveState === 'error' || connState === 'error' || bot?.conn_state === 'error' || bot?.state === 'error' || realStatus === 'error')
  const isDisconnected = !isDeploying && !isStoppingActive && !isError && (connState === 'disconnected' || liveState === 'disconnected')
  const isReconnecting = !isDeploying && !isStoppingActive && !isError && (connState === 'reconnecting' || liveState === 'reconnecting')
  const isWaitingCycle = !isDeploying && !isStoppingActive && !isError && (connState === 'waiting' || liveState === 'waiting') && !isDisconnected && !isReconnecting
  const isRunningNow   = !isDeploying && !isStoppingActive && !isError && (connState === 'connected' || liveState === 'running') && !isDisconnected && !isReconnecting && !isWaitingCycle
  const isBotActive    = !isError && !isStoppingActive && (isRunningNow || isWaitingCycle || isDisconnected || isReconnecting || (!isDeploying && liveState === 'running'))
  ```
  Furthermore, lines 84-90 suppress incoming prop updates while stopping or starting:
  ```tsx
  useEffect(() => {
    setLiveCastle(castle)
    if (!isStopping && !isStarting) {
      setLiveState(castle.bot_status.state)
      setConnState(castle.bot_status?.conn_state ?? '')
    }
  }, [castle, isStopping, isStarting])
  ```
- **Consequence**: If an API error or network drop occurs while `isStopping` or `isStarting` is true, the card locks up in a frozen spinner state (`isStoppingActive` or `isStarting`), blocking the user from retrying or seeing the true server status.

### 2.3 Deep Finding: Silent Unmount Mutation Desynchronization (FE-02)
- **Location**: `dashboard/src/components/accounts/TaskTabContent.tsx:731-743`
- **Observation**:
  `TaskTabContent` debounces auto-saving changes (`scheduleSave(250)`). When a user toggles an option or edits an input and switches tabs or navigates back to `/dashboard` or `/accounts` within 250ms, the cleanup effect triggers:
  ```tsx
  // TaskTabContent.tsx:731-743
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
- **Root Cause & Flow Failure**:
  1. `updateCastle(...)` is invoked directly from `botApi.ts`, completely bypassing `useUpdateCastleConfig`.
  2. `qc.setQueryData(['castles', userId])` is NOT called.
  3. `saveCachedCastles(userId, ...)` is NOT called.
  4. The SQLite database receives the new config, but TanStack Query cache and `localStorage` retain the OLD config.
  5. Because `useCastles` has `staleTime: 60_000` (1 minute), when the user navigates back to the castle settings within 60 seconds, TanStack Query serves the stale in-memory cache and re-renders the old settings!
  6. To the user, their changes appear to have been discarded or reverted.

---

## 3. Pillar 2: Caching Policies & Invalidation Lifecycle

### 3.1 Global QueryClient Defaults
- **Location**: `dashboard/src/lib/queryClient.ts:3-13`
```ts
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            60_000,              // 1 minute
      gcTime:               1000 * 60 * 60 * 24, // 24 HOURS
      retry:                2,
      refetchOnWindowFocus: false,
      refetchOnReconnect:   'always',
    },
  },
})
```
- **Analysis**:
  - `gcTime: 24h` is excessively high for a single-page client session. Inactive queries and unmounted component caches remain in JavaScript heap memory indefinitely, preventing garbage collection.
  - `staleTime: 60s` combined with `refetchOnWindowFocus: false` means any mutations performed in another browser window, tab, or mobile device will not be visible for at least 60 seconds unless a manual refetch occurs.

### 3.2 Deep Finding: LocalStorage Cache Leak Across Logouts & Account Switches (FE-03)
- **Location**: `dashboard/src/hooks/useAuth.ts:359-363, 462-468` vs `dashboard/src/hooks/useCastles.ts:104-147`
- **Observation**:
  `useCastles.ts` persists user castle data in `localStorage` under `ibra_castles_cache_${userId}` for "0ms instant launch":
  ```ts
  // useCastles.ts:137-147
  export function saveCachedCastles(userId: string, items: Castle[]) {
    localStorage.setItem(
      `${CASTLES_CACHE_PREFIX}${userId}`,
      JSON.stringify({ items, timestamp: Date.now() })
    )
  }
  ```
  However, examining the logout and switchAccount implementations in `useAuth.ts`:
  ```ts
  // useAuth.ts:462-468
  const logout = async () => {
    sessionStorage.removeItem('osmanli_admin_session_token')
    saveCachedUser(null)
    queryClient.clear()
    await signOut(auth)
    setUser(null)
  }
  ```
  And:
  ```ts
  // useAuth.ts:359-363
  queryClient.clear()
  sessionStorage.removeItem('osmanli_admin_session_token')
  saveCachedUser(null)
  ```
- **Consequence**:
  1. `localStorage.removeItem(`${CASTLES_CACHE_PREFIX}${userId}`)` is **NEVER** called.
  2. If user A logs out on a shared terminal, their castle IDs, lord names, alliance names, resource counts, coordinates, and full task configs remain unencrypted in `localStorage`.
  3. If user B logs in, or user A logs back in days later, the stale castle state is instantly served from `localStorage` before the server responds.

### 3.3 Cross-Query Invalidation Blind Spots
1. **Admin Castle Deletion Blind Spot**:
   - In `AdminUsersCastles.tsx:65-80`:
     ```ts
     qc.invalidateQueries({ queryKey: ['admin_users_castles'] })
     qc.invalidateQueries({ queryKey: ['admin_stats'] })
     qc.invalidateQueries({ queryKey: ['admin_users'] })
     ```
     `qc.invalidateQueries({ queryKey: ['castles', deletingCastle.userUid] })` is missing! If the admin or user views `AccountsPage` or `CastleDetailPage`, the deleted castle remains displayed from cache.
2. **Subscription Update Cache Invalidation**:
   - In `useUsers.ts:63`: `qc.invalidateQueries({ queryKey: ['castles'] })` invalidates query cache, but leaves `ibra_castles_cache_${userId}` untouched in `localStorage`.

---

## 4. Pillar 3: Network & API Optimization

### 4.1 Deep Finding: Total Absence of `AbortController` in REST Client (FE-04)
- **Location**: `dashboard/src/lib/botApi.ts:1-819`
- **Evidence**:
  A grep search for `signal` across the entire `dashboard/src/` directory matched ONLY lines 89 and 91 of `botApi.ts` (`AbortSignal.timeout(3000)` in health checks).
  None of the data-fetching or mutation methods accept an `AbortSignal`:
  - `fetchCastles(userId?: string): Promise<Castle[]>`
  - `fetchCastle(castleId: string): Promise<Castle>`
  - `getAdminUsers(): Promise<User[]>`
  - `getAdminStats(): Promise<...>`
  - `fetchAdminUsersCastles(): Promise<AdminUserWithCastles[]>`
  - `getAdminLiveProcesses(): Promise<LiveProcessesResponse>`
  - `getMerchantsOverview(): Promise<...>`
  - `getAdminProxies(): Promise<...>`
- **Impact**:
  - TanStack Query automatically provides a cancellation signal (`QueryFunctionContext.signal`), but none of the hooks pass it down.
  - When a user navigates from `/accounts` to `/dashboard` to `/admin`, previous HTTP queries cannot be aborted. In-flight requests consume client CPU, bandwidth, and server FastAPI worker threads.

### 4.2 Deep Finding: 1 WebSocket Connection Per Castle Card Anti-Pattern (FE-05)
- **Location**: `dashboard/src/components/accounts/CastleCard.tsx:93-118` vs `dashboard/src/hooks/useCastles.ts:263-315`
- **Evidence**:
  In `CastleCard.tsx:93`:
  ```tsx
  const { status: realStatus } = useRealBotStatus(castle.id)
  ```
  Which executes in `useCastles.ts:228`:
  ```tsx
  ws = new WebSocket(`${WS_BASE}/ws/status/${castleId}`)
  ```
  If a user manages 25 castles, 25 individual WebSockets are opened simultaneously.
  On disconnection, 25 timers trigger reconnection every 3000ms:
  ```tsx
  reconnectTimer = setTimeout(connect, 3000)
  ```
  **Critical Irony**: Lines 264-315 of `useCastles.ts` implement `useUserBotStatuses(userId)`:
  ```tsx
  // useCastles.ts:264
  export function useUserBotStatuses(userId: string, enabled: boolean = true) {
    ...
    ws = new WebSocket(`${WS_BASE}/ws/user-status/${userId}`)
  ```
  This hook sends real-time status updates for ALL user castles over a SINGLE multiplexed WebSocket.
  **Grep verification proves that `useUserBotStatuses` is 100% UNUSED anywhere in the frontend.**

### 4.3 Deep Finding: N+1 Sequential HTTP Flooding on Batch Settings Update (FE-07)
- **Location**: `dashboard/src/hooks/useCastles.ts:511-523`
- **Code**:
  ```tsx
  export function useBatchUpdateCastleConfigs(userId: string) {
    const qc = useQueryClient()
    return useMutation({
      mutationFn: async ({ castleIds, config }: { castleIds: string[]; config: Partial<CastleConfig> }) => {
        if (!castleIds || castleIds.length === 0) return
        await Promise.all(
          castleIds.map(id => updateCastle(id, { config: config as Record<string, unknown> }))
        )
      },
  ```
- **Impact**: If a user applies batch settings across 30 castles, the frontend dispatches 30 concurrent `PUT /api/castles/{id}` requests at the exact same millisecond. If one fails, `Promise.all` throws an error, leaving half the castles updated and half un-updated with zero rollback or idempotency.

### 4.4 Missing Debounce on Search Inputs (FE-09)
- **Accounts**: `Accounts.tsx:563` updates `search` state synchronously on every keystroke.
- **Admin Users**: `Admin.tsx:836` updates `search` state synchronously, filtering hundreds of users.
- **Admin Users Castles**: `AdminUsersCastles.tsx:19` runs a double-nested filter loop (users -> castles) on every keystroke.
- **Admin Live Processes**: `AdminLiveProcesses.tsx:23` runs synchronous filter on every keystroke.

---

## 5. Pillar 4: Performance & Re-render Cascades

### 5.1 Deep Finding: Admin Dashboard DOM Explosion & Missing Pagination (FE-06)
- **Location**: `dashboard/src/pages/Admin.tsx:619, 898-1050`
- **Evidence**:
  1. `useAllUsers()` fetches ALL users in one unpaginated payload: `GET /api/admin/users`.
  2. In `Admin.tsx:898-1025`, a desktop `<table>` renders `filtered.map(u => <tr key={u.uid} ...>)`.
  3. In `Admin.tsx:1028-1150`, a mobile container (`md:hidden`) renders `filtered.map(u => <div key={u.uid} className="... admin-user-card" ...>)`.
  4. React mounts BOTH the desktop table rows AND mobile cards in the virtual DOM simultaneously. For 200 users: 200 rows with 6 columns (1,200 table cells + action buttons) + 200 mobile cards = 400 complex card/row subtrees with dozens of svg icons.
  5. There is NO pagination, NO infinite scroll, and NO virtualization (`@tanstack/react-virtual`).
  6. Any state change (typing in the search input, toggling a filter chip) forces React to reconcile hundreds of DOM nodes.

### 5.2 Unmemoized Heavy Subtrees (`CastleCard.tsx`) (FE-10)
- **Location**: `dashboard/src/components/accounts/CastleCard.tsx:31`
- **Evidence**:
  `CastleCard` is 657 lines long, containing:
  - SVG icons, accordion sections, status badges
  - `ResourceBar` subcomponent
  - `TaskTabContent` (3,646 lines) when expanded
  - Modals: `ConfirmPresetModal`, `ConfirmStopModal`
  - Internal states: `liveCastle`, `liveState`, `connState`, `isStopping`, `isStarting`, etc.
  `export function CastleCard(...)` is NOT wrapped in `React.memo`.
  Every keystroke in `AccountsPage` search forces every single `CastleCard` on screen to re-render.
  Furthermore, event handlers in `Accounts.tsx` (`handleDelete`, `handleStopAll`, `handleBatchSave`, etc.) are inline functions recreated on every render.

### 5.3 Memory Leak: Unrevoked Object URLs (FE-14)
- **Location**: `dashboard/src/context/TenantContext.tsx:238-245`
- **Code**:
  ```ts
  const manifestBlob = new Blob([JSON.stringify(dynamicManifest)], { type: 'application/manifest+json' })
  const manifestBlobUrl = URL.createObjectURL(manifestBlob)
  ...
  manifestLink.href = manifestBlobUrl
  ```
- **Issue**: `URL.revokeObjectURL(manifestBlobUrl)` is never invoked in a cleanup effect. Every re-render of `TenantProvider` leaking blob references in memory.

---

## 6. Pillar 5: UX, Mutation Feedback & Security

### 6.1 Deep Finding: Insecure Reversible XOR Password Storage (FE-08)
- **Location**: `dashboard/src/lib/savedAccounts.ts:29-53, 105-141`
- **Evidence**:
  ```ts
  // savedAccounts.ts:29-53
  const CIPHER_KEY = 'ibra_bot_salt_k9x_'

  function encryptToken(plain: string): string {
    try {
      const chars = plain.split('').map((c, i) =>
        c.charCodeAt(0) ^ CIPHER_KEY.charCodeAt(i % CIPHER_KEY.length)
      )
      return btoa(String.fromCharCode(...chars))
    } catch {
      return btoa(plain)
    }
  }

  function decryptToken(cipher: string): string {
    try {
      const decoded = atob(cipher)
      const chars = decoded.split('').map((c, i) =>
        c.charCodeAt(0) ^ CIPHER_KEY.charCodeAt(i % CIPHER_KEY.length)
      )
      return String.fromCharCode(...chars)
    } catch {
      return ''
    }
  }
  ```
  `saveOrUpdateAccount` stores this `secretToken` directly in `localStorage` under `ibra_saved_accounts` and `ibra_saved_accounts_${tenantId}`.
- **Security Assessment**:
  This is trivial XOR obfuscation with a static hardcoded key in client code, NOT encryption. Anyone with temporary physical access to the device or any cross-site script running on the origin can decrypt all saved passwords in < 1 millisecond.
  This directly violates `AGENTS_CONSTITUTION.md` section 15.2: *"منع تخزين كلمات المرور، التوكنات السرية، أو مفاتيح الجلسات الحساسة في الـ localStorage أو الـ sessionStorage دون تشفير"*.

### 6.2 Blocking Browser `window.confirm()` Dialogs (FE-11)
- **Location**: `dashboard/src/pages/Admin.tsx:674, 689, 710`
- **Evidence**:
  ```ts
  // Admin.tsx:674
  if (!confirm(t('admin.quickApproveConfirm', { name: u.username || u.email }))) return
  // Admin.tsx:689
  if (!confirm(t('admin.approveAllConfirm', { count: pendingUsersCount }))) return
  // Admin.tsx:710
  if (!confirm(u.is_banned ? t('admin.unbanConfirm') : t('admin.banConfirm'))) return
  ```
  Native `confirm()` blocks the browser's JavaScript event loop, freezes UI animations, cannot be themed to dark mode, and produces inconsistent behavior in mobile PWA and iframe environments.

### 6.3 Hardcoded Arabic Text Bypassing Trilingual Localization (FE-12)
- **Location**:
  - `dashboard/src/components/layout/AdminLayout.tsx:189, 205, 218, 230, 243, 256, 264, 309, 326, 338, 351, 364`
    Hardcoded text in navigation tabs: `<span>المستخدمين</span>`, `<span>العمليات الحية</span>`, `<span>التجار</span>`, `<span>البروكسيات</span>`, `<span>قلاع المستخدمين</span>`, `<span>المظهر</span>`, `<span>خروج</span>`.
  - `dashboard/src/pages/AdminLiveProcesses.tsx:147, 168, 178, 196, 213, 230, 470`:
    `<span>العمليات الحية</span>`, `<span>تلقائي</span>`, `<span>تحديث</span>`, `<span>الكل</span>`, `<span>شغال</span>`, `<span>انتظار</span>`, `<div>المدة</div>`.
  - `dashboard/src/pages/AdminMerchants.tsx:52, 66, 75, 86, 97`:
    `<h1>التجار والنطاقات</h1>`, `<span>تحديث</span>`, `<span>التجار</span>`, `<span>المستخدمين</span>`, `<span>القلاع</span>`.
  - `dashboard/src/pages/AdminProxies.tsx:146, 174, 192`:
    `<span>بروكسيات</span>`, `<span>تحديث</span>`, `<div>المستخدمين</div>`.
- **Impact**: When a user selects English (`EN`) or Turkish (`TR`), these sections remain in Arabic, violating the trilingual requirement of R7 and Section 11 of the Constitution.

### 6.4 Dark/Light Mode Contrast Defects (FE-13)
- **Location**: `dashboard/src/components/accounts/CastleCard.tsx:543`, `dashboard/src/components/accounts/TaskTabContent.tsx:101-135`
- **Evidence**:
  ```tsx
  // CastleCard.tsx:543
  className="castle-icon-group flex items-center gap-0.5 bg-white/[0.04] p-1 sm:p-0.5 border border-white/8 rounded-xl sm:rounded-lg shrink-0"
  ```
  And:
  ```tsx
  // TaskTabContent.tsx:101
  'inline-flex items-center bg-black/60 shadow-sm border border-white/10 rounded-md h-6 ...'
  ```
- **Defect**: In Light mode (`document.body.style.backgroundColor = '#f1f5f2'`), `bg-white/[0.04]` and `border-white/8` are virtually invisible against the light slate background. In `TaskTabContent`, `bg-black/60` produces jarring solid black rectangles on light panels because it lacks the `dark:` prefix.

---

## 7. Recommended Architectural Target State

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PROPOSED TARGET ARCHITECTURE                     │
├────────────────────────────────┬───────────────────────────────────────┤
│ Pillar                         │ Target Architectural Solution          │
├────────────────────────────────┼───────────────────────────────────────┤
│ 1. State & Single Truth        │ • Single source of truth in React Query│
│                                │ • Deprecate `liveCastle/liveState` in  │
│                                │   `CastleCard`; derive status directly │
│                                │ • Ensure `TaskTabContent` unmount      │
│                                │   synchronizes with TanStack cache     │
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Caching Policies            │ • Normalize `gcTime` to 15-30 minutes  │
│                                │ • Full `localStorage` cache purge on   │
│                                │   logout/switch (`ibra_castles_cache_`)│
│                                │ • Complete cross-query invalidation    │
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. Network & API               │ • Add `signal?: AbortSignal` to all    │
│                                │   `botApi.ts` methods                  │
│                                │ • Switch `CastleCard` from 1-ws-per-   │
│                                │   card to single `useUserBotStatuses`  │
│                                │ • Backend batch PUT endpoint for batch │
│                                │ • 300ms debounce on all search inputs  │
├────────────────────────────────┼───────────────────────────────────────┤
│ 4. Performance & Re-renders    │ • Wrap `CastleCard` in `React.memo`    │
│                                │ • Add pagination (or virtualization)   │
│                                │   to `Admin.tsx` users table           │
│                                │ • Revoke Blob URLs on unmount          │
├────────────────────────────────┼───────────────────────────────────────┤
│ 5. UX, i18n & Security         │ • Replace `window.confirm` with custom │
│                                │   styled confirmation modals           │
│                                │ • Wrap all hardcoded strings in `t()`  │
│                                │ • Fix Light Mode CSS classes           │
│                                │ • Use Web Crypto API or secure tokens  │
└────────────────────────────────┴───────────────────────────────────────┘
```
