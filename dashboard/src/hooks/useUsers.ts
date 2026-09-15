import {
  collection, getDocs, getDoc, doc, updateDoc, deleteDoc, query, orderBy, where,
} from 'firebase/firestore'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { db } from '../lib/firebase'
import { stopBot, stopUserBots } from '../lib/botApi'
import type { User, Subscription } from '../types'

// ─── All users (admin only) ────────────────────────────────
export function useAllUsers() {
  return useQuery({
    queryKey: ['admin_users'],
    queryFn: async () => {
      const snap = await getDocs(query(collection(db, 'users'), orderBy('created_at', 'desc')))
      const users = await Promise.all(
        snap.docs.map(async (d) => {
          const userData = d.data() as Omit<User, 'uid'>
          const uid = d.id

          try {
            const castlesSnap = await getDocs(collection(db, 'users', uid, 'castles'))
            const castles = castlesSnap.docs.map(cd => cd.data() as Record<string, unknown>)
            const activeCount = castles.filter(c => (c.bot_status as Record<string, unknown> | undefined)?.state !== 'pending' && c.is_active !== false).length
            const pendingCount = castles.filter(c => (c.bot_status as Record<string, unknown> | undefined)?.state === 'pending').length
            const totalActualCount = castlesSnap.size

            const storedCount = userData.subscription?.current_castles_count
            const storedPending = userData.subscription?.pending_castles_count

            // Auto-heal / sync Firestore doc if count is missing or desynced
            if (storedCount !== activeCount || storedPending !== pendingCount) {
              updateDoc(doc(db, 'users', uid), {
                'subscription.current_castles_count': activeCount,
                'subscription.pending_castles_count': pendingCount,
              }).catch(() => {})
            }

            return {
              ...userData,
              uid,
              subscription: {
                ...(userData.subscription || {}),
                current_castles_count: activeCount,
                pending_castles_count: pendingCount,
                total_castles_count: totalActualCount,
              },
            } as User
          } catch (err) {
            console.error(`Failed to load castles for user ${uid}:`, err)
            return { ...userData, uid } as User
          }
        })
      )
      return users
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
      const users = usersSnap.docs.map(d => ({ uid: d.id, ...d.data() } as Partial<User> & { uid: string }))

      await Promise.all(
        users.map(async (u) => {
          const email = (u.email || '').toLowerCase().trim()
          if (u.role === 'admin' || email === 'ibraboths@gmail.com') return

          totalUsers++
          if (u.subscription?.status === 'active') activeSubscriptions++

          try {
            const castlesSnap = await getDocs(collection(db, 'users', u.uid, 'castles'))
            const castles = castlesSnap.docs.map(cd => cd.data())
            const activeCount = castles.filter(c => (c.bot_status as Record<string, unknown> | undefined)?.state !== 'pending' && c.is_active !== false).length
            totalCastles += activeCount
          } catch {
            totalCastles += u.subscription?.current_castles_count ?? 0
          }
        })
      )
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
      const userRef = doc(db, 'users', uid)
      const userSnap = await getDoc(userRef)
      const currentSub = userSnap.data()?.subscription || {}
      const newSub = { ...currentSub, ...sub }
      await updateDoc(userRef, { subscription: newSub })

      // إذا انتهت صلاحية الاشتراك، نوقف جميع قلاع المستخدم وعملياته في السيرفر فوراً
      const isExpired = newSub.status === 'expired' || 
        (newSub.expires_at && new Date(newSub.expires_at).getTime() < Date.now())

      if (isExpired) {
        try {
          const castlesSnap = await getDocs(collection(db, 'users', uid, 'castles'))
          await Promise.all(
            castlesSnap.docs.map(async (cDoc) => {
              const castleId = cDoc.id
              const cData = cDoc.data()
              if (cData.bot_status?.state === 'running' || cData.bot_status?.conn_state === 'connected') {
                await updateDoc(doc(db, 'users', uid, 'castles', castleId), {
                  'bot_status.state': 'idle',
                  'bot_status.conn_state': 'idle',
                  'bot_status.last_run_message': 'تم إيقاف البوت فوراً: انتهت صلاحية الاشتراك',
                })
              }
              stopBot(castleId).catch(() => {})
            })
          )
          stopUserBots(uid).catch(() => {})
        } catch (err) {
          console.warn('Failed to stop castles on subscription expiration:', err)
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}

// ─── Ban/unban user ────────────────────────────────────────
export function useBanUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ uid, ban }: { uid: string; ban: boolean }) => {
      await updateDoc(doc(db, 'users', uid), { is_banned: ban })

      if (ban) {
        // إيقاف جميع قلاع المستخدم وعمليات البوت في السيرفر فوراً لتحرير موارد النظام
        try {
          const castlesSnap = await getDocs(collection(db, 'users', uid, 'castles'))
          await Promise.all(
            castlesSnap.docs.map(async (cDoc) => {
              const castleId = cDoc.id
              const cData = cDoc.data()
              if (cData.bot_status?.state === 'running' || cData.bot_status?.conn_state === 'connected') {
                await updateDoc(doc(db, 'users', uid, 'castles', castleId), {
                  'bot_status.state': 'idle',
                  'bot_status.conn_state': 'idle',
                  'bot_status.last_run_message': 'تم إيقاف البوت فوراً: تم حظر الحساب من قبل الإدارة',
                })
              }
              stopBot(castleId).catch(() => {})
            })
          )
          stopUserBots(uid).catch(() => {})
        } catch (err) {
          console.warn('Failed to stop castles on ban:', err)
        }
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['castles'] })
    },
  })
}

// ─── Delete user ───────────────────────────────────────────
export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (uid: string) => {
      // إيقاف العمليات في السيرفر قبل الحذف
      stopUserBots(uid).catch(() => {})
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
      const castlesSnap = await getDocs(collection(db, 'users', userId, 'castles'))
      const allCastles = castlesSnap.docs.map(cd => ({ id: cd.id, ...cd.data() })) as Array<{ id: string; bot_status?: { state: string }; is_active?: boolean }>
      const activeCount = allCastles.filter(c => c.id === castleId || (c.bot_status?.state !== 'pending' && c.is_active !== false)).length
      const pendingCount = allCastles.filter(c => c.id !== castleId && c.bot_status?.state === 'pending').length

      const userSnap = await getDoc(userRef)
      const userData = userSnap.data()
      const maxAllowed = Number(userData?.subscription?.max_castles_allowed ?? 1)

      const updates: Record<string, unknown> = {
        'subscription.current_castles_count': activeCount,
        'subscription.pending_castles_count': pendingCount,
      }
      if (activeCount > maxAllowed) {
        updates['subscription.max_castles_allowed'] = activeCount
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
      const castlesSnap = await getDocs(collection(db, 'users', userId, 'castles'))
      const remaining = castlesSnap.docs.map(cd => cd.data()) as Array<{ bot_status?: { state: string }; is_active?: boolean }>
      const activeCount = remaining.filter(c => c.bot_status?.state !== 'pending' && c.is_active !== false).length
      const pendingCount = remaining.filter(c => c.bot_status?.state === 'pending').length

      const userRef = doc(db, 'users', userId)
      await updateDoc(userRef, {
        'subscription.current_castles_count': activeCount,
        'subscription.pending_castles_count': pendingCount,
      })
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['castles', vars.userId] })
      qc.invalidateQueries({ queryKey: ['user', vars.userId] })
    },
  })
}
