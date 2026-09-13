import { useState, useEffect } from 'react'
import {
  collection, doc, onSnapshot, query, orderBy, limit,
  startAfter, getDocs, getDoc, setDoc, updateDoc, deleteDoc, writeBatch, type QueryDocumentSnapshot,
} from 'firebase/firestore'
import { useQuery, useMutation, useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { db } from '../lib/firebase'
import type { Castle, BotState, CastleConfig } from '../types'
import { DEFAULT_CASTLE_CONFIG } from '../types'

const PAGE_SIZE = 100

// ─── Deep merge castle config with defaults ────────────────
// يضمن وجود جميع حقول الـ config حتى للقلاع القديمة في Firebase
function mergeCastleConfig(firebaseConfig: Record<string, unknown>): CastleConfig {
  const def = DEFAULT_CASTLE_CONFIG
  const fc = firebaseConfig || {}

  const mergeMM = (fmm: Record<string, unknown>) => ({
    ...def.march_manager,
    ...(fmm || {}),
    transport:   { ...def.march_manager.transport,   ...((fmm?.transport   as Record<string, unknown>) || {}) },
    ruins:       { ...def.march_manager.ruins,       ...((fmm?.ruins       as Record<string, unknown>) || {}) },
    combat:      { ...def.march_manager.combat,      ...((fmm?.combat      as Record<string, unknown>) || {}) },
    elf:         { ...def.march_manager.elf,         ...((fmm?.elf         as Record<string, unknown>) || {}) },
    invaders:    { ...def.march_manager.invaders,    ...((fmm?.invaders    as Record<string, unknown>) || {}) },
    rebels:      { ...def.march_manager.rebels,      ...((fmm?.rebels      as Record<string, unknown>) || {}) },
    stronghold:  { ...def.march_manager.stronghold,  ...((fmm?.stronghold  as Record<string, unknown>) || {}) },
    gather:      { ...def.march_manager.gather,      ...((fmm?.gather      as Record<string, unknown>) || {}) },
    priority_order: (fmm?.priority_order as string[]) || def.march_manager.priority_order,
  })

  const mergeTrain = (ft: Record<string, unknown>) => ({
    ...def.train,
    ...(ft || {}),
    levels: { ...def.train.levels, ...((ft?.levels as Record<string, unknown>) || {}) },
  })

  const mergePrestige = (fp: Record<string, unknown>) => ({
    ...def.prestige,
    ...(fp || {}),
    subtasks: { ...def.prestige.subtasks, ...((fp?.subtasks as Record<string, unknown>) || {}) },
  })

  return {
    city_harvest:       { ...def.city_harvest,       ...((fc.city_harvest       as Record<string, unknown>) || {}) },
    research:           { ...def.research,           ...((fc.research           as Record<string, unknown>) || {}) },
    alliance:           { ...def.alliance,           ...((fc.alliance           as Record<string, unknown>) || {}) },
    port:               { ...def.port,               ...((fc.port               as Record<string, unknown>) || {}) },
    train:              mergeTrain((fc.train          as Record<string, unknown>) || {}),
    pet_patrol:         { ...def.pet_patrol,         ...((fc.pet_patrol         as Record<string, unknown>) || {}) },
    territory_expansion:{ ...def.territory_expansion,...((fc.territory_expansion as Record<string, unknown>) || {}) },
    shield:             { ...def.shield,             ...((fc.shield             as Record<string, unknown>) || {}) },
    stamina:            { ...def.stamina,            ...((fc.stamina            as Record<string, unknown>) || {}) },
    skills:             { ...def.skills,             ...((fc.skills             as Record<string, unknown>) || {}), target_skills: (fc.skills as Record<string, unknown>)?.target_skills as string[] || def.skills.target_skills },
    hero_draw:          { ...def.hero_draw,          ...((fc.hero_draw          as Record<string, unknown>) || {}) },
    tactics_hall:       { ...def.tactics_hall,       ...((fc.tactics_hall       as Record<string, unknown>) || {}) },
    watermill:          { ...def.watermill,          ...((fc.watermill          as Record<string, unknown>) || {}) },
    fountain:           { ...def.fountain,           ...((fc.fountain           as Record<string, unknown>) || {}), resources: (fc.fountain as Record<string, unknown>)?.resources as string[] || def.fountain.resources },
    material_workshop:  { ...def.material_workshop,  ...((fc.material_workshop  as Record<string, unknown>) || {}), materials: (fc.material_workshop as Record<string, unknown>)?.materials as string[] || def.material_workshop.materials },
    caravan:            { ...def.caravan,            ...((fc.caravan            as Record<string, unknown>) || {}) },
    port_delegate:      { ...def.port_delegate,      ...((fc.port_delegate      as Record<string, unknown>) || {}) },
    savings_bank:       { ...def.savings_bank,       ...((fc.savings_bank       as Record<string, unknown>) || {}) },
    building:           { ...def.building,           ...((fc.building           as Record<string, unknown>) || {}) },
    prestige:           mergePrestige((fc.prestige    as Record<string, unknown>) || {}),
    march_manager:      mergeMM((fc.march_manager     as Record<string, unknown>) || {}),
    gold_gather:        fc.gold_gather ? { ...(def.gold_gather || { enabled: false, locations: [] }), ...(fc.gold_gather as Record<string, unknown>) } : def.gold_gather,
  } as CastleConfig
}

// ─── Castles real-time list (paginated) ────────────────────
export function useCastles(userId: string) {
  return useInfiniteQuery({
    queryKey: ['castles', userId],
    initialPageParam: null as QueryDocumentSnapshot | null,
    queryFn: async ({ pageParam }) => {
      const ref = collection(db, 'users', userId, 'castles')
      let q = query(ref, orderBy('created_at', 'desc'), limit(PAGE_SIZE))
      if (pageParam) q = query(ref, orderBy('created_at', 'desc'), startAfter(pageParam), limit(PAGE_SIZE))
      const snap = await getDocs(q)
      return {
        items: snap.docs.map(d => {
          const data = d.data() as Record<string, unknown>
          return {
            id: d.id,
            ...data,
            config: mergeCastleConfig((data.config as Record<string, unknown>) || {}),
          } as Castle
        }),
        lastDoc: snap.docs[snap.docs.length - 1] ?? null,
      }
    },
    getNextPageParam: (lastPage) => lastPage.lastDoc,
    staleTime: 60_000,
    enabled: !!userId,
  })
}

// ─── Single castle (static) ────────────────────────────────
export function useCastle(userId: string, castleId: string) {
  return useQuery({
    queryKey: ['castle', userId, castleId],
    queryFn: async () => {
      const snap = await getDocs(collection(db, 'users', userId, 'castles'))
      const d = snap.docs.find(doc => doc.id === castleId)
      if (!d) throw new Error('Castle not found')
      const data = d.data() as Record<string, unknown>
      return {
        id: d.id,
        ...data,
        config: mergeCastleConfig((data.config as Record<string, unknown>) || {}),
      } as Castle
    },
    staleTime: 30_000,
    enabled: !!userId && !!castleId,
  })
}

// ─── Bot status real-time (lightweight) ───────────────────
export function useBotStatusLive(
  userId: string,
  castleId: string,
  onUpdate: (state: string) => void
) {
  const ref = doc(db, 'users', userId, 'castles', castleId)
  return {
    subscribe: () => onSnapshot(ref, (snap) => {
      const data = snap.data()
      if (data?.bot_status?.state) onUpdate(data.bot_status.state)
    })
  }
}

// ─── Real process status via WebSocket ────────────────────
// اتصال WebSocket دائم بـ api_server.py — لا polling، لا استهلاك موارد.
// الخادم يُرسل الحالة فور الاتصال ثم فقط عند التغيير.
// إذا انقطع الاتصال → يُعيد الاتصال تلقائياً بعد 3 ثوانٍ.

type RealStatus = 'running' | 'starting' | 'idle' | 'disconnected' | 'reconnecting' | 'offline'


export function useRealBotStatus(castleId: string, enabled: boolean = true): {
  status: RealStatus
} {
  const [status, setStatus] = useState<RealStatus>('offline')

  useEffect(() => {
    if (!enabled || !castleId) return

    const WS_BASE = (import.meta.env.VITE_BOT_API_URL ?? 'http://localhost:8000')
      .replace(/^http/, 'ws')
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let destroyed = false

    function connect() {
      if (destroyed) return
      try {
        ws = new WebSocket(`${WS_BASE}/ws/status/${castleId}`)

        ws.onopen = () => {
          // الاتصال ناجح — الخادم سيُرسل الحالة الأولية فوراً
        }

        ws.onmessage = (e) => {
          const s = e.data?.trim() as RealStatus
          if (s) setStatus(s)
        }

        ws.onclose = () => {
          if (!destroyed) {
            // الخادم غير متاح أو انقطع → نُبلّغ بـ offline وننتظر 3 ثوانٍ للإعادة
            setStatus('offline')
            reconnectTimer = setTimeout(connect, 3000)
          }
        }

        ws.onerror = () => {
          ws?.close()
        }
      } catch {
        setStatus('offline')
        if (!destroyed) reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      destroyed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [castleId, enabled])

  return { status }
}

// ─── Update bot state (via API server + Firebase fallback) ─────────
export function useUpdateBotState(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, state }: { castleId: string; state: BotState }) => {
      // دائماً حدّث Firebase أولاً (للمزامنة)
      await updateDoc(
        doc(db, 'users', userId, 'castles', castleId),
        { 'bot_status.state': state }
      )
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['castles', userId] }),
  })
}

// ─── Bot Control (يُشغّل/يوقف البوت عبر API + يحدّث Firebase) ─────
export function useBotControl(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      castle,
      state,
    }: {
      castle: Castle
      state: 'running' | 'idle'
    }) => {
      const { startBot, stopBot, checkApiAvailable } = await import('../lib/botApi')

      const apiAvailable = await checkApiAvailable()

      if (state === 'running') {
        if (apiAvailable) {
          // ✅ استدعاء API مباشرة لتشغيل البوت
          await startBot({
            castle_id:    castle.id,
            user_id:      userId,
            email:        castle.email,
            password:     (castle as Castle & { password?: string }).password,
            config:       castle.config as unknown as Record<string, unknown>,
            loop_interval: 90,
          })
        } else {
          // ⚠️ API غير متاح — حدّث Firebase فقط (Fallback)
          console.warn('⚠️ api_server.py غير متاح — تحديث Firebase فقط')
          await updateDoc(
            doc(db, 'users', userId, 'castles', castle.id),
            {
              'bot_status.state':            'running',
              'bot_status.conn_state':       'connected',
              'bot_status.conn_message':     'في انتظار خادم البوت...',
              'bot_status.last_run_message': 'في انتظار خادم البوت...',
              'bot_status.conn_updated':     new Date().toISOString(),
            }
          )
          return
        }
      } else {
        if (apiAvailable) {
          // ✅ إيقاف عبر API
          await stopBot(castle.id)
        }
      }

      // تحديث Firebase دائماً (لمزامنة الحالة في لوحة التحكم)
      await updateDoc(
        doc(db, 'users', userId, 'castles', castle.id),
        {
          'bot_status.state':            state,
          'bot_status.conn_state':       state === 'running' ? 'connected' : 'idle',
          'bot_status.conn_message':     state === 'running' ? 'البوت متصل ويعمل الآن...' : 'تم إيقاف البوت بواسطة المستخدم',
          'bot_status.last_run_message': state === 'running' ? 'البوت يعمل الآن...' : 'تم الإيقاف',
          'bot_status.conn_updated':     new Date().toISOString(),
        }
      )
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['castles', userId] }),
  })
}


// ─── Update castle config ──────────────────────────────────
export function useUpdateCastleConfig(userId: string, castleId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (config: Partial<CastleConfig>) => {
      const updates: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(config)) {
        updates[`config.${k}`] = v
      }
      await updateDoc(doc(db, 'users', userId, 'castles', castleId), updates)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['castle', userId, castleId] })
      qc.invalidateQueries({ queryKey: ['castles', userId] })
    },
  })
}

// ─── Batch update castle configs ────────────────────────────
export function useBatchUpdateCastleConfigs(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleIds, config }: { castleIds: string[]; config: Partial<CastleConfig> }) => {
      if (!castleIds || castleIds.length === 0) return
      const updates: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(config)) {
        updates[`config.${k}`] = v
      }
      // Chunk by 400 to respect Firestore writeBatch limit (max 500 per batch)
      for (let i = 0; i < castleIds.length; i += 400) {
        const chunk = castleIds.slice(i, i + 400)
        const batch = writeBatch(db)
        for (const id of chunk) {
          batch.update(doc(db, 'users', userId, 'castles', id), updates)
        }
        await batch.commit()
      }
    },
    onSuccess: (_, { castleIds }) => {
      castleIds.forEach(id => {
        qc.invalidateQueries({ queryKey: ['castle', userId, id] })
      })
      qc.invalidateQueries({ queryKey: ['castles', userId] })
    },
  })
}

// ─── Add new castle ───────────────────────────────────────
export function useAddCastle(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      // 1. Fetch user to check subscription limits
      const userRef = doc(db, 'users', userId)
      const userSnap = await getDoc(userRef)
      const userData = userSnap.data()
      const sub = userData?.subscription
      const maxAllowed = Number(sub?.max_castles_allowed ?? 1)
      const currentCount = Number(sub?.current_castles_count ?? 0)

      // Expiration & Active status check
      const now = new Date()
      const isExpired = sub?.expires_at ? new Date(sub.expires_at).getTime() <= now.getTime() : false
      const isSubActive = (sub?.status === 'active' || !sub?.status) && !isExpired

      // Rule:
      // If user is within allowed count AND subscription has not expired:
      // IMMEDIATELY ACCEPTED without waiting for admin!
      // Otherwise, if count >= maxAllowed or subscription is expired:
      // goes to pending approval queue.
      const isWithinQuota = currentCount < maxAllowed
      const isAutoApproved = isSubActive && isWithinQuota
      const isPending = !isAutoApproved

      let pendingReason = ''
      if (!isSubActive) {
        pendingReason = 'بانتظار موافقة المسؤول (انتهت فترة الاشتراك أو الحساب غير نشط)'
      } else if (!isWithinQuota) {
        pendingReason = 'بانتظار موافقة المسؤول (تم تجاوز عدد الحسابات المسموح بها)'
      }

      // 2. Create new castle document
      const castleColRef = collection(db, 'users', userId, 'castles')
      const newCastleRef = doc(castleColRef)

      const emailTrimmed = email.trim()
      const lordFallback = emailTrimmed.split('@')[0]

      const newCastle: Record<string, unknown> = {
        castle_id: newCastleRef.id,
        email: emailTrimmed,
        password: password,
        is_active: isAutoApproved,
        created_at: now.toISOString(),
        castle_info: {
          lord_name: lordFallback,
          castle_name: 'قلعة جديدة',
          server_id: 1,
          castle_level: 1,
          lord_power: 0,
          vip_level: 0,
          alliance_name: '',
          coordinates: { x: 0, y: 0 },
        },
        resources: {
          food: 0,
          wood: 0,
          iron: 0,
          diamond: 0,
          gold: 0,
          stamina: 100,
          last_updated: now.toISOString(),
        },
        bot_status: {
          state: isAutoApproved ? 'idle' : 'pending',
          last_run_time: null,
          next_run_time: null,
          last_run_message: isAutoApproved ? 'جاهز للتشغيل' : pendingReason,
          active_marches: 0,
          max_marches: 2,
          last_error: null,
        },
        config: DEFAULT_CASTLE_CONFIG,
      }

      await setDoc(newCastleRef, newCastle)

      // 3. Increment current active count or pending count
      if (isAutoApproved) {
        await updateDoc(userRef, {
          'subscription.current_castles_count': currentCount + 1,
        })
      } else {
        const pendingCount = Number(sub?.pending_castles_count ?? 0)
        await updateDoc(userRef, {
          'subscription.pending_castles_count': pendingCount + 1,
        })
      }

      return { id: newCastleRef.id, isPending }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
    },
  })
}

// ─── Update castle credentials ─────────────────────────────
export function useUpdateCastleCredentials(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, email, password }: { castleId: string; email: string; password?: string }) => {
      const castleRef = doc(db, 'users', userId, 'castles', castleId)
      const updates: Record<string, unknown> = {
        email: email.trim(),
      }
      if (password) {
        updates.password = password
      }
      await updateDoc(castleRef, updates)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
    },
  })
}

// ─── Delete castle ─────────────────────────────────────────
export function useDeleteCastle(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, wasActive }: { castleId: string; wasActive?: boolean }) => {
      await deleteDoc(doc(db, 'users', userId, 'castles', castleId))
      const userRef = doc(db, 'users', userId)
      const userSnap = await getDoc(userRef)
      const sub = userSnap.data()?.subscription
      if (wasActive) {
        const currentCount = Number(sub?.current_castles_count ?? 1)
        if (currentCount > 0) {
          await updateDoc(userRef, {
            'subscription.current_castles_count': currentCount - 1,
          })
        }
      } else {
        const pendingCount = Number(sub?.pending_castles_count ?? 1)
        if (pendingCount > 0) {
          await updateDoc(userRef, {
            'subscription.pending_castles_count': pendingCount - 1,
          })
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
    },
  })
}

