import {
  collection, getDocs, getDoc, doc, updateDoc, deleteDoc, query, orderBy, where,
} from 'firebase/firestore'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { db } from '../lib/firebase'
import type { User, Subscription } from '../types'

// ─── All users (admin only) ────────────────────────────────
export function useAllUsers() {
  return useQuery({
    queryKey: ['admin_users'],
    queryFn: async () => {
      const snap = await getDocs(query(collection(db, 'users'), orderBy('created_at', 'desc')))
      return snap.docs.map(d => ({ uid: d.id, ...d.data() } as User))
    },
    staleTime: 30_000,
  })
}

// ─── Admin stats ───────────────────────────────────────────
export function useAdminStats() {
  return useQuery({
    queryKey: ['admin_stats'],
    queryFn: async () => {
      const usersSnap = await getDocs(collection(db, 'users'))
      let totalUsers = 0, activeSubscriptions = 0, totalCastles = 0
      const users = usersSnap.docs.map(d => d.data())
      for (const u of users) {
        totalUsers++
        if (u.subscription?.status === 'active') activeSubscriptions++
        totalCastles += u.subscription?.current_castles_count ?? 0
      }
      return { totalUsers, activeSubscriptions, totalCastles }
    },
    staleTime: 60_000,
  })
}

// ─── Update user ───────────────────────────────────────────
export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, data }: { uid: string; data: Partial<User> }) => {
      await updateDoc(doc(db, 'users', uid), data as Record<string, unknown>)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin_users'] }),
  })
}

// ─── Update subscription ───────────────────────────────────
export function useUpdateSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, sub }: { uid: string; sub: Partial<Subscription> }) => {
      await updateDoc(doc(db, 'users', uid), { subscription: sub })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin_users'] }),
  })
}

// ─── Ban/unban user ────────────────────────────────────────
export function useBanUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, ban }: { uid: string; ban: boolean }) => {
      await updateDoc(doc(db, 'users', uid), { is_banned: ban })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin_users'] }),
  })
}

// ─── Delete user ───────────────────────────────────────────
export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (uid: string) => {
      await deleteDoc(doc(db, 'users', uid))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin_users'] }),
  })
}

// ─── Approve pending castle (admin only) ───────────────────
export function useApproveCastle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, castleId }: { userId: string; castleId: string }) => {
      const castleRef = doc(db, 'users', userId, 'castles', castleId)
      await updateDoc(castleRef, {
        is_active: true,
        'bot_status.state': 'idle',
        'bot_status.last_run_message': 'جاهز للتشغيل (تمت الموافقة من الإدارة)',
      })

      const userRef = doc(db, 'users', userId)
      const userSnap = await getDoc(userRef)
      const userData = userSnap.data()
      const sub = userData?.subscription
      const currentCount = Number(sub?.current_castles_count ?? 0)
      const maxAllowed = Number(sub?.max_castles_allowed ?? 1)
      const pendingCount = Number(sub?.pending_castles_count ?? 1)

      const newCurrent = currentCount + 1
      const updates: Record<string, unknown> = {
        'subscription.current_castles_count': newCurrent,
        'subscription.pending_castles_count': Math.max(0, pendingCount - 1),
      }
      // If new current exceeds max allowed, automatically increase max allowed to accommodate
      if (newCurrent > maxAllowed) {
        updates['subscription.max_castles_allowed'] = newCurrent
      }
      await updateDoc(userRef, updates)
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles', vars.userId] })
      qc.invalidateQueries({ queryKey: ['user', vars.userId] })
    },
  })
}

// ─── Reject pending castle (admin only) ────────────────────
export function useRejectCastle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, castleId }: { userId: string; castleId: string }) => {
      await deleteDoc(doc(db, 'users', userId, 'castles', castleId))
      const userRef = doc(db, 'users', userId)
      const userSnap = await getDoc(userRef)
      const pendingCount = Number(userSnap.data()?.subscription?.pending_castles_count ?? 1)
      if (pendingCount > 0) {
        await updateDoc(userRef, {
          'subscription.pending_castles_count': pendingCount - 1,
        })
      }
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles', vars.userId] })
      qc.invalidateQueries({ queryKey: ['user', vars.userId] })
    },
  })
}
