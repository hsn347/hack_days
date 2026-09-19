import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getAdminStats, getAdminUsers, updateAdminSubscription,
  banAdminUser, deleteAdminUser, approveCastleAdmin, rejectCastleAdmin,
  updateUserProfileApi
} from '../lib/botApi'
import type { User, Subscription } from '../types'

// ─── All users (admin only) ────────────────────────────────
export function useAllUsers() {
  return useQuery({
    queryKey: ['admin_users'],
    queryFn: async () => {
      return await getAdminUsers()
    },
    staleTime: 30_000,
  })
}

// ─── Admin stats ───────────────────────────────────────────
export function useAdminStats() {
  return useQuery({
    queryKey: ['admin_stats'],
    queryFn: async () => {
      return await getAdminStats()
    },
    staleTime: 60_000,
  })
}

// ─── Update user ───────────────────────────────────────────
export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, data }: { uid: string; data: Partial<User> }) => {
      if (data.username || data.phone) {
        await updateUserProfileApi({ username: data.username, phone: data.phone })
      }
      if (data.is_banned !== undefined) {
        await banAdminUser(uid, { is_banned: data.is_banned, reason: data.banned_reason || '' })
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin_users'] }),
  })
}

// ─── Update subscription ───────────────────────────────────
export function useUpdateSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, sub }: { uid: string; sub: Partial<Subscription> }) => {
      await updateAdminSubscription(uid, {
        plan_id:             sub.plan_id || 'custom',
        plan_name:           sub.plan_name || 'باقة مخصصة',
        subscription_status: sub.status || 'active',
        expires_at:          sub.expires_at || new Date(Date.now() + 30 * 86400000).toISOString(),
        max_castles_allowed: sub.max_castles_allowed ?? 1,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}

// ─── Ban/unban user ────────────────────────────────────────
export function useBanUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, ban, reason }: { uid: string; ban: boolean; reason?: string }) => {
      await banAdminUser(uid, { is_banned: ban, reason: reason || '' })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}

// ─── Delete user ───────────────────────────────────────────
export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (uid: string) => {
      await deleteAdminUser(uid)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
    },
  })
}

// ─── Approve pending castle (admin only) ───────────────────
export function useApproveCastle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, castleId }: { userId: string; castleId: string }) => {
      await approveCastleAdmin(castleId)
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles', vars.userId] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}

// ─── Reject pending castle (admin only) ────────────────────
export function useRejectCastle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, castleId, reason }: { userId: string; castleId: string; reason?: string }) => {
      await rejectCastleAdmin(castleId, reason)
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles', vars.userId] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}
