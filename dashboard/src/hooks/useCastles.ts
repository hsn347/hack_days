import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchCastles, fetchCastle, createCastle, updateCastle,
  updateCastleCredentials, toggleCastleActive, deleteCastle,
  startBot, stopBot, stopUserBots, getWsBaseUrl, getAdminLiveProcesses
} from '../lib/botApi'
import {
  useUserBotStatuses,
  useMultiplexedBotStatus,
  purgeAllUserStatusSockets,
  type RealStatus
} from './useUserBotStatuses'
import type { Castle, BotState, CastleConfig } from '../types'
import { DEFAULT_CASTLE_CONFIG } from '../types'

export { useUserBotStatuses, useMultiplexedBotStatus, purgeAllUserStatusSockets }
export type { RealStatus }


// ─── Deep merge castle config with defaults ────────────────
export function mergeCastleConfig(fcConfig: Record<string, unknown>): CastleConfig {
  const def = DEFAULT_CASTLE_CONFIG
  const fc = fcConfig || {}

  const mergeMM = (fmm: Record<string, unknown>) => {
    const rawRuins = ((fmm?.ruins as Record<string, unknown>) || {})
    const VALID_EXPLORE_TIMES = [900, 3600, 14400, 28800]
    const rawTime = Number(rawRuins.explore_time)
    let cleanTime = def.march_manager.ruins.explore_time
    if (VALID_EXPLORE_TIMES.includes(rawTime)) {
      cleanTime = rawTime
    } else if (!isNaN(rawTime) && rawTime > 0) {
      cleanTime = VALID_EXPLORE_TIMES.reduce((prev, curr) =>
        Math.abs(curr - rawTime) < Math.abs(prev - rawTime) ? curr : prev
      )
    }

    const cleanFmm = { ...(fmm || {}) }
    delete (cleanFmm as any).elf
    return {
      ...def.march_manager,
      ...cleanFmm,
      transport:   { ...def.march_manager.transport,   ...((fmm?.transport   as Record<string, unknown>) || {}) },
      ruins:       { ...def.march_manager.ruins,       ...rawRuins, explore_time: cleanTime },
      combat:      { ...def.march_manager.combat,      ...((fmm?.combat      as Record<string, unknown>) || {}) },
      invaders:    { ...def.march_manager.invaders,    ...((fmm?.invaders    as Record<string, unknown>) || {}) },
      rebels:      { ...def.march_manager.rebels,      ...((fmm?.rebels      as Record<string, unknown>) || {}) },
      stronghold:  { ...def.march_manager.stronghold,  ...((fmm?.stronghold  as Record<string, unknown>) || {}) },
      gold_gather: { ...def.march_manager.gold_gather, ...((fmm?.gold_gather as Record<string, unknown>) || {}) },
      gather:      { ...def.march_manager.gather,      ...((fmm?.gather      as Record<string, unknown>) || {}) },
    }
}

  const mergeTrain = (ft: Record<string, unknown>) => ({
    ...def.train,
    ...(ft || {}),
    levels: { ...def.train.levels, ...((ft?.levels as Record<string, unknown>) || {}) },
  })

  const mergePrestige = (fp: Record<string, unknown>) => {
    const rawSub = (fp?.subtasks as Record<string, unknown>) || {}
    const trainVal = typeof rawSub.train === 'boolean' ? rawSub.train : def.prestige.subtasks.train
    return {
      ...def.prestige,
      ...(fp || {}),
      subtasks: {
        ...def.prestige.subtasks,
        ...rawSub,
        fortress: trainVal,
      },
    }
  }

  return {
    ...def,
    ...(fc as Partial<CastleConfig>),
    city_harvest:       { ...def.city_harvest,       ...((fc.city_harvest       as Record<string, unknown>) || {}) },
    research:           { ...def.research,           ...((fc.research           as Record<string, unknown>) || {}) },
    alliance:           { ...def.alliance,           ...((fc.alliance           as Record<string, unknown>) || {}) },
    port:               { ...def.port,               ...((fc.port               as Record<string, unknown>) || {}) },
    train:              mergeTrain((fc.train          as Record<string, unknown>) || {}),
    pet_patrol:         { ...def.pet_patrol,         ...((fc.pet_patrol         as Record<string, unknown>) || {}) },
    territory_expansion:{ ...def.territory_expansion,...((fc.territory_expansion as Record<string, unknown>) || {}) },
    torch_chest:        { ...(def.torch_chest || { enabled: false }), ...((fc.torch_chest as Record<string, unknown>) || {}) },
    open_torch_chest:   { ...(def.open_torch_chest || { enabled: false }), ...((fc.open_torch_chest as Record<string, unknown>) || {}) },
    hero_consign:       { ...(def.hero_consign || { enabled: false }), ...((fc.hero_consign as Record<string, unknown>) || {}) },
    shield:             { ...def.shield,             ...((fc.shield             as Record<string, unknown>) || {}) },
    stamina:            { ...def.stamina,            ...((fc.stamina            as Record<string, unknown>) || {}) },
    skills:             { ...def.skills,             ...((fc.skills             as Record<string, unknown>) || {}), target_skills: (fc.skills as Record<string, unknown>)?.target_skills as string[] || def.skills.target_skills },
    hero_draw:          { ...def.hero_draw,          ...((fc.hero_draw          as Record<string, unknown>) || {}) },
    treasure_pavilion:  { ...def.treasure_pavilion,  ...((fc.treasure_pavilion  as Record<string, unknown>) || {}) },
    blacksmith_forge:   { ...def.blacksmith_forge,   ...((fc.blacksmith_forge   as Record<string, unknown>) || {}) },
    imperial_mausoleum: { ...def.imperial_mausoleum, ...((fc.imperial_mausoleum as Record<string, unknown>) || {}) },
    alliance_treasure:  { ...def.alliance_treasure,  ...((fc.alliance_treasure  as Record<string, unknown>) || {}) },
    daily_luxury_gift:  { ...def.daily_luxury_gift,  ...((fc.daily_luxury_gift  as Record<string, unknown>) || {}) },
    vip_gift:           { ...def.vip_gift,           ...((fc.vip_gift           as Record<string, unknown>) || {}) },
    tactics_hall:       { ...def.tactics_hall,       ...((fc.tactics_hall       as Record<string, unknown>) || {}) },
    watermill:          { ...def.watermill,          ...((fc.watermill          as Record<string, unknown>) || {}) },
    fountain:           { ...def.fountain,           ...((fc.fountain           as Record<string, unknown>) || {}), resources: (fc.fountain as Record<string, unknown>)?.resources as string[] || def.fountain.resources },
    material_workshop:  { ...def.material_workshop,  ...((fc.material_workshop  as Record<string, unknown>) || {}), materials: (fc.material_workshop as Record<string, unknown>)?.materials as string[] || def.material_workshop.materials },
    caravan:            { ...def.caravan,            ...((fc.caravan            as Record<string, unknown>) || {}) },
    port_delegate:      { ...def.port_delegate,      ...((fc.port_delegate      as Record<string, unknown>) || {}) },
    savings_bank:       { ...def.savings_bank,       ...((fc.savings_bank       as Record<string, unknown>) || {}), days: [1, 7, 15, 30].includes((fc.savings_bank as { days?: number })?.days as number) ? ((fc.savings_bank as { days?: number }).days as number) : 7, deposit: Math.min(6000, Math.max(100, Number((fc.savings_bank as { deposit?: number })?.deposit) || 2000)) },
    warrior_exchange:   { ...(def.warrior_exchange || { enabled: false, count: 15 }), ...((fc.warrior_exchange as Record<string, unknown>) || {}), count: Math.min(15, Math.max(1, Number((fc.warrior_exchange as { count?: number })?.count) || 15)) },
    gather_boost:       { ...(def.gather_boost || { enabled: false }), ...((fc.gather_boost as Record<string, unknown>) || {}) },
    elf:                { ...(def.elf || { enabled: false, formation_id: 1 }), ...((fc.elf as Record<string, unknown>) || {}) },
    building:           { ...def.building,           ...((fc.building           as Record<string, unknown>) || {}) },
    prestige:           mergePrestige((fc.prestige    as Record<string, unknown>) || {}),
    troy_treasure:      { ...(def.troy_treasure || { enabled: false }), ...((fc.troy_treasure as Record<string, unknown>) || {}) },
    march_manager:      mergeMM((fc.march_manager     as Record<string, unknown>) || {}),

  } as CastleConfig
}

// ─── Persistent Local Storage Cache for Castles (Instant 0ms App Launch) ──
export const CASTLES_CACHE_PREFIX = 'empire_castles_cache_'
export const LEGACY_CASTLES_CACHE_PREFIX = 'ibra_castles_cache_'
export const ACTIVE_CASTLE_PREFIX = 'empire_active_castle_'
export const LEGACY_ACTIVE_CASTLE_PREFIX = 'ibra_active_castle_'

export function getCachedCastles(userId: string) {
  if (typeof window === 'undefined' || !userId) return undefined
  try {
    let raw = localStorage.getItem(`${CASTLES_CACHE_PREFIX}${userId}`)
    if (!raw) {
      raw = localStorage.getItem(`${LEGACY_CASTLES_CACHE_PREFIX}${userId}`)
    }
    if (!raw) return undefined
    const parsed = JSON.parse(raw)
    if (parsed && Array.isArray(parsed.items) && parsed.items.length > 0) {
      return {
        pages: [{ items: parsed.items as Castle[] }],
        pageParams: [null],
      }
    }
  } catch {
    // ignore
  }
  return undefined
}

export function getCachedCastlesTimestamp(userId: string): number | undefined {
  if (typeof window === 'undefined' || !userId) return undefined
  try {
    let raw = localStorage.getItem(`${CASTLES_CACHE_PREFIX}${userId}`)
    if (!raw) {
      raw = localStorage.getItem(`${LEGACY_CASTLES_CACHE_PREFIX}${userId}`)
    }
    if (!raw) return undefined
    const parsed = JSON.parse(raw)
    return typeof parsed.timestamp === 'number' ? parsed.timestamp : undefined
  } catch {
    return undefined
  }
}

export function saveCachedCastles(userId: string, items: Castle[]) {
  if (typeof window === 'undefined' || !userId || !items) return
  try {
    const payload = JSON.stringify({ items, timestamp: Date.now() })
    localStorage.setItem(`${CASTLES_CACHE_PREFIX}${userId}`, payload)
    localStorage.setItem(`${LEGACY_CASTLES_CACHE_PREFIX}${userId}`, payload)
  } catch {
    // ignore
  }
}

export function getActiveCastleId(userId: string): string | null {
  if (typeof window === 'undefined' || !userId) return null
  try {
    return localStorage.getItem(`${ACTIVE_CASTLE_PREFIX}${userId}`) ||
           localStorage.getItem(`${LEGACY_ACTIVE_CASTLE_PREFIX}${userId}`)
  } catch {
    return null
  }
}

export function saveActiveCastleId(userId: string, castleId: string) {
  if (typeof window === 'undefined' || !userId) return
  try {
    localStorage.setItem(`${ACTIVE_CASTLE_PREFIX}${userId}`, castleId)
    localStorage.setItem(`${LEGACY_ACTIVE_CASTLE_PREFIX}${userId}`, castleId)
  } catch {
    // ignore
  }
}

export function clearActiveCastleId(userId: string) {
  if (typeof window === 'undefined' || !userId) return
  try {
    localStorage.removeItem(`${ACTIVE_CASTLE_PREFIX}${userId}`)
    localStorage.removeItem(`${LEGACY_ACTIVE_CASTLE_PREFIX}${userId}`)
  } catch {
    // ignore
  }
}

export function purgeCastlesCache(userId?: string) {
  if (typeof window === 'undefined') return
  try {
    purgeAllUserStatusSockets()
    if (userId) {
      localStorage.removeItem(`${CASTLES_CACHE_PREFIX}${userId}`)
      localStorage.removeItem(`${LEGACY_CASTLES_CACHE_PREFIX}${userId}`)
      localStorage.removeItem(`${ACTIVE_CASTLE_PREFIX}${userId}`)
      localStorage.removeItem(`${LEGACY_ACTIVE_CASTLE_PREFIX}${userId}`)
    }
    const keysToRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && (
        key.startsWith(CASTLES_CACHE_PREFIX) ||
        key.startsWith(LEGACY_CASTLES_CACHE_PREFIX) ||
        key.startsWith(ACTIVE_CASTLE_PREFIX) ||
        key.startsWith(LEGACY_ACTIVE_CASTLE_PREFIX)
      )) {
        keysToRemove.push(key)
      }
    }
    for (const key of keysToRemove) {
      localStorage.removeItem(key)
    }
  } catch {
    // ignore
  }
}

// ─── Castles list (SQLite REST API مع التخزين المحلي الفوري والتحديث اللحظي) ──
export function useCastles(userId: string) {
  return useQuery({
    queryKey: ['castles', userId],
    queryFn: async ({ signal }) => {
      const items = await fetchCastles(userId, { signal })
      const formatted = items.map(c => ({
        ...c,
        config: mergeCastleConfig((c.config as unknown as Record<string, unknown>) || {}),
      }))
      saveCachedCastles(userId, formatted)
      return {
        pages: [{ items: formatted }],
        pageParams: [null],
      }
    },
    initialData: () => getCachedCastles(userId),
    initialDataUpdatedAt: () => getCachedCastlesTimestamp(userId),
    staleTime: 60_000,
    gcTime: 600_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
    enabled: !!userId,
  })
}

// ─── Single castle (static) ────────────────────────────────
export function useCastle(userId: string, castleId: string) {
  return useQuery({
    queryKey: ['castle', userId, castleId],
    queryFn: async ({ signal }) => {
      const c = await fetchCastle(castleId, { signal })
      return {
        ...c,
        config: mergeCastleConfig((c.config as unknown as Record<string, unknown>) || {}),
      }
    },
    initialData: () => {
      const cached = getCachedCastles(userId)
      const found = cached?.pages?.[0]?.items?.find((c: Castle) => c.id === castleId)
      return found ? found : undefined
    },
    staleTime: 30_000,
    gcTime: 300_000,
    refetchOnWindowFocus: false,
    enabled: !!userId && !!castleId,
  })
}

// ─── Live Bot Stats Query (TanStack Query) ──────────────────
export function useLiveBotStats(enabled: boolean = true) {
  return useQuery({
    queryKey: ['live_bot_stats'],
    queryFn: async ({ signal }) => {
      return await getAdminLiveProcesses({ signal })
    },
    staleTime: 10_000,
    gcTime: 60_000,
    refetchInterval: 10_000,
    refetchOnWindowFocus: false,
    enabled,
  })
}

// ─── Bot status real-time (stub compatibility) ─────────────
export function useBotStatusLive(
  _userId: string,
  _castleId: string,
  _onUpdate: (state: string) => void
) {
  return {
    subscribe: () => () => {},
  }
}

// ─── Real process status via Multiplexed WebSocket ─────────
export function useRealBotStatus(castleId: string, enabled: boolean = true, userId?: string): {
  status: RealStatus
} {
  return useMultiplexedBotStatus(castleId, userId, 'offline', enabled)
}

// ─── Update bot state ──────────────────────────────────────
export function useUpdateBotState(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, state }: { castleId: string; state: BotState }) => {
      if (state === 'idle') {
        await stopBot(castleId)
      }
    },
    onMutate: async ({ castleId, state }) => {
      await qc.cancelQueries({ queryKey: ['castles', userId] })
      const prevData = qc.getQueryData<any>(['castles', userId])
      if (prevData?.pages) {
        qc.setQueryData(['castles', userId], {
          ...prevData,
          pages: prevData.pages.map((page: any) => ({
            ...page,
            items: (page.items || []).map((c: Castle) =>
              c.id === castleId
                ? {
                    ...c,
                    bot_status: {
                      ...c.bot_status,
                      state: state === 'idle' ? 'idle' : state,
                      conn_state: state === 'idle' ? 'idle' : c.bot_status?.conn_state,
                      conn_message: state === 'idle' ? 'تم إيقاف البوت' : c.bot_status?.conn_message,
                    }
                  }
                : c
            )
          }))
        })
      }
      return { prevData }
    },
    onError: (_err, _vars, context) => {
      if (context?.prevData) {
        qc.setQueryData(['castles', userId], context.prevData)
      }
    },
    onSettled: (_data, _err, vars) => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      if (vars?.castleId) {
        qc.invalidateQueries({ queryKey: ['castle', userId, vars.castleId] })
      }
      qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
    },
  })
}

// ─── Bot Control (تشغيل/إيقاف البوت عبر API السريع) ────────
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
      if (state === 'running') {
        await startBot({
          castle_id:    castle.id,
          user_id:      userId,
          email:        castle.email,
          password:     (castle as Castle & { password?: string }).password,
          loop_interval: castle.loop_interval || 40,
        })
      } else {
        await stopBot(castle.id)
      }
    },
    onMutate: async ({ castle, state }) => {
      await qc.cancelQueries({ queryKey: ['castles', userId] })
      const prevData = qc.getQueryData<any>(['castles', userId])
      if (prevData?.pages) {
        qc.setQueryData(['castles', userId], {
          ...prevData,
          pages: prevData.pages.map((page: any) => ({
            ...page,
            items: (page.items || []).map((c: Castle) =>
              c.id === castle.id
                ? {
                    ...c,
                    bot_status: {
                      ...c.bot_status,
                      state: state === 'running' ? 'starting' : 'idle',
                      conn_state: state === 'running' ? 'starting' : 'idle',
                      conn_message: state === 'running' ? 'جاري بدء التشغيل...' : 'تم إيقاف البوت',
                    }
                  }
                : c
            )
          }))
        })
      }
      return { prevData }
    },
    onError: (_err, _vars, context) => {
      if (context?.prevData) {
        qc.setQueryData(['castles', userId], context.prevData)
      }
    },
    onSettled: (_data, _err, vars) => {
      const invalidateAll = () => {
        qc.invalidateQueries({ queryKey: ['castles', userId] })
        if (vars?.castle?.id) {
          qc.invalidateQueries({ queryKey: ['castle', userId, vars.castle.id] })
        }
        qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
      }
      if (vars?.state === 'idle') {
        setTimeout(invalidateAll, 1500)
      } else {
        invalidateAll()
      }
    },
  })
}

// ─── Batch Stop All Bots (طلب موحد وسريع) ──────────────────
export function useStopUserBots(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await stopUserBots(userId)
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: ['castles', userId] })
      const prevData = qc.getQueryData<any>(['castles', userId])
      if (prevData?.pages) {
        qc.setQueryData(['castles', userId], {
          ...prevData,
          pages: prevData.pages.map((page: any) => ({
            ...page,
            items: (page.items || []).map((c: Castle) => ({
              ...c,
              bot_status: {
                ...c.bot_status,
                state: 'idle',
                conn_state: 'idle',
                conn_message: 'تم إيقاف البوت بواسطة المستخدم',
              },
            })),
          })),
        })
      }
      return { prevData }
    },
    onError: (_err, _vars, context) => {
      if (context?.prevData) {
        qc.setQueryData(['castles', userId], context.prevData)
      }
    },
    onSettled: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['castles', userId] })
        qc.invalidateQueries({ queryKey: ['castle', userId] })
        qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
      }, 1500)
    },
  })
}

// ─── Update castle config ──────────────────────────────────
export function useUpdateCastleConfig(userId: string, castleId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: Partial<CastleConfig> | { config: Partial<CastleConfig>; version?: number }) => {
      let cfg: Partial<CastleConfig>
      let version: number | undefined
      if (input && 'config' in input && typeof input.config === 'object') {
        cfg = input.config
        version = input.version
      } else {
        cfg = input as Partial<CastleConfig>
      }

      const res = await updateCastle(castleId, {
        config: cfg as Record<string, unknown>,
        version,
      })
      return res.castle
    },
    onSuccess: (updatedCastle) => {
      if (updatedCastle) {
        qc.setQueryData(['castle', userId, castleId], (old: any) =>
          old ? { ...old, ...updatedCastle, config: mergeCastleConfig((updatedCastle.config as unknown as Record<string, unknown>) || {}) } : old
        )
        qc.setQueryData(['castleConfig', castleId], updatedCastle.config)
        qc.setQueryData(['castles', userId], (old: any) => {
          if (!old) return old
          if (old.pages) {
            const nextPages = old.pages.map((page: any) => ({
              ...page,
              items: (page.items || []).map((c: Castle) =>
                c.id === castleId
                  ? { ...c, ...updatedCastle, config: mergeCastleConfig((updatedCastle.config as unknown as Record<string, unknown>) || {}) }
                  : c
              ),
            }))
            const flatItems = nextPages.flatMap((p: any) => p.items)
            saveCachedCastles(userId, flatItems)
            return {
              ...old,
              pages: nextPages,
            }
          }
          return old
        })
      }
    },
    onSettled: () => {
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
      await Promise.all(
        castleIds.map(id => updateCastle(id, { config: config as Record<string, unknown> }))
      )
    },
    onSuccess: (_, { castleIds }) => {
      castleIds.forEach(id => {
        qc.invalidateQueries({ queryKey: ['castle', userId, id] })
        qc.invalidateQueries({ queryKey: ['castleConfig', id] })
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
      const res = await createCastle({
        email: email.trim(),
        password: password.trim(),
        config: DEFAULT_CASTLE_CONFIG as unknown as Record<string, unknown>,
      })
      return { id: res.castle.id, isPending: !res.castle.is_active }
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      if (res?.id) {
        qc.invalidateQueries({ queryKey: ['castle', userId, res.id] })
      }
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
    },
  })
}

// ─── Update castle credentials ─────────────────────────────
export function useUpdateCastleCredentials(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, email, password }: { castleId: string; email: string; password?: string }) => {
      await updateCastleCredentials(castleId, {
        email: email.trim(),
        password: password?.trim(),
      })
    },
    onSuccess: (_, { castleId }) => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      qc.invalidateQueries({ queryKey: ['castle', userId, castleId] })
    },
  })
}

// ─── Toggle castle active ──────────────────────────────────
export function useToggleCastleActive(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId, isActive }: { castleId: string; isActive: boolean }) => {
      await toggleCastleActive(castleId, isActive)
    },
    onSuccess: (_, { castleId }) => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      qc.invalidateQueries({ queryKey: ['castle', userId, castleId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
    },
  })
}

// ─── Delete castle ─────────────────────────────────────────
export function useDeleteCastle(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ castleId }: { castleId: string; wasActive?: boolean }) => {
      await deleteCastle(castleId)
    },
    onSuccess: (_, { castleId }) => {
      qc.setQueryData(['castles', userId], (old: any) => {
        if (!old?.pages) return old
        const nextPages = old.pages.map((page: any) => ({
          ...page,
          items: (page.items || []).filter((c: Castle) => c.id !== castleId),
        }))
        const flatItems = nextPages.flatMap((p: any) => p.items)
        saveCachedCastles(userId, flatItems)
        return {
          ...old,
          pages: nextPages,
        }
      })
      qc.removeQueries({ queryKey: ['castle', userId, castleId] })
      qc.removeQueries({ queryKey: ['castleConfig', castleId] })
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
    },
  })
}

// ─── Import / Batch Add Castles ────────────────────────────
export function useImportCastles(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (castles: Array<{ email: string; password: string }>) => {
      const results = []
      for (const c of castles) {
        const res = await createCastle({
          email: c.email.trim(),
          password: c.password.trim(),
          config: DEFAULT_CASTLE_CONFIG as unknown as Record<string, unknown>,
        })
        results.push(res.castle)
      }
      return results
    },
    onSuccess: (results) => {
      qc.invalidateQueries({ queryKey: ['castles', userId] })
      if (Array.isArray(results)) {
        results.forEach(c => {
          if (c?.id) qc.invalidateQueries({ queryKey: ['castle', userId, c.id] })
        })
      }
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['live_bot_stats'] })
    },
  })
}
