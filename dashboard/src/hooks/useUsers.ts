import {
  collection, getDocs, doc, updateDoc, deleteDoc, query, orderBy, where,
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
