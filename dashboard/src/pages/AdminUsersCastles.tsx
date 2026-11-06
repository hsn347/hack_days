import React, { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Search, Users, ChevronDown, ChevronUp, AlertTriangle,
  X, RefreshCw, Zap, Shield, Trash2, Landmark, CheckCircle2, Lock, Swords,
  ChevronLeft, ChevronRight
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AdminLayout } from '../components/layout/AdminLayout'
import { CastleCard } from '../components/accounts/CastleCard'
import {
  fetchAdminUsersCastlesSummary,
  fetchAdminUserCastles,
  deleteCastle,
  disableElfForAllCastles,
  AdminUserSummary,
  AdminUsersCastlesPaginatedResponse,
} from '../lib/botApi'
import { useDebounce } from '../hooks/useDebounce'
import { Castle } from '../types'

// ─── Subcomponent: On-Demand Lazy Loaded Castle Details ────────
function UserCastlesDetail({
  user,
  onDeleteCastle,
}: {
  user: AdminUserSummary
  onDeleteCastle: (castle: Castle, user: AdminUserSummary) => void
}) {
  const { t } = useTranslation()
  const {
    data: castles = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin_user_castles', user.uid],
    queryFn: ({ signal }) => fetchAdminUserCastles(user.uid, { signal }),
    staleTime: 30_000,
    gcTime: 300_000,
    refetchOnWindowFocus: false,
  })

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2 text-slate-500 dark:text-slate-400">
        <div className="w-5 h-5 rounded-full border-2 border-emerald-500/30 border-t-emerald-500 animate-spin" />
        <span className="text-xs">{t('common.loading', 'جاري تحميل قلاع المستخدم...')}</span>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-between p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs">
        <span>{String((error as any)?.message || t('common.error', 'تعذر تحميل القلاع'))}</span>
        <button
          type="button"
          onClick={() => refetch()}
          className="px-2 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 font-semibold cursor-pointer"
        >
          {t('common.retry', 'إعادة المحاولة')}
        </button>
      </div>
    )
  }

  if (castles.length === 0) {
    return (
      <div className="text-center py-6 text-xs text-slate-500 dark:text-slate-400 font-medium">
        لا توجد أي قلاع مسجلة لهذا المستخدم حتى الآن.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {castles.map((castle, cIdx) => (
        <CastleCard
          key={castle.id}
          castle={castle}
          userId={user.uid}
          index={cIdx}
          onDelete={() => onDeleteCastle(castle, user)}
        />
      ))}
    </div>
  )
}

export function AdminUsersCastlesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()

  // ─── Search & Filter State ─────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery, 300)
  const [filterType, setFilterType] = useState<'all' | 'with_castles' | 'no_castles' | 'running'>('all')

  // ─── Pagination State (Matches Admin.tsx) ──────────────────
  const [pageSize, setPageSize] = useState<number>(25)
  const [currentPage, setCurrentPage] = useState<number>(1)

  // Reset to page 1 whenever search, filter or page size changes
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchQuery, filterType, pageSize])

  // ─── Collapsed State: All user cards closed by default ─────
  const [expandedUsers, setExpandedUsers] = useState<Record<string, boolean>>({})

  // ─── Castle Delete Modal State ─────────────────────────────
  const [deletingCastle, setDeletingCastle] = useState<{
    castleId: string
    castleEmail?: string
    userUid: string
    userEmail: string
  } | null>(null)

  // ─── Disable Elf All Castles Modal State ────────────────────
  const [showDisableElfModal, setShowDisableElfModal] = useState(false)

  // ─── Query: Fetch Paginated Summary List (<60 KB) ───────────
  const {
    data: paginatedData,
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['admin_users_castles_summary', currentPage, pageSize, debouncedSearchQuery, filterType],
    queryFn: ({ signal }) =>
      fetchAdminUsersCastlesSummary(
        {
          page: currentPage,
          pageSize,
          search: debouncedSearchQuery,
          filterStatus: filterType,
        },
        { signal }
      ),
    placeholderData: (previousData) => previousData,
    staleTime: 45_000,
    refetchOnWindowFocus: false,
  })

  const users: AdminUserSummary[] = useMemo(() => {
    return paginatedData?.items || paginatedData?.users || []
  }, [paginatedData])

  const totalItems = paginatedData?.total ?? paginatedData?.total_count ?? users.length
  const totalPages = paginatedData?.total_pages ?? Math.max(1, Math.ceil(totalItems / pageSize))
  const validPage = Math.min(Math.max(1, currentPage), totalPages)
  const startIndex = totalItems === 0 ? 0 : (validPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, totalItems)
  const filteredUsers = users

  // ─── Toggle User Expand ────────────────────────────────────
  const toggleUser = (uid: string) => {
    setExpandedUsers(prev => ({
      ...prev,
      [uid]: !prev[uid]
    }))
  }

  // ─── Collapse / Expand All ─────────────────────────────────
  const collapseAll = () => setExpandedUsers({})

  // ─── Delete Castle Mutation ────────────────────────────────
  const deleteMutation = useMutation({
    mutationFn: async (castleId: string) => {
      await deleteCastle(castleId)
    },
    onSuccess: (_, castleId) => {
      toast.success(t('accounts.deletedSuccess', 'تم حذف القلعة بنجاح'))
      if (deletingCastle) {
        const uid = deletingCastle.userUid
        // 1. Scoped cache update and invalidation for this user's castle details query
        qc.setQueryData<Castle[]>(['admin_user_castles', uid], old => {
          if (!old) return []
          return old.filter(c => c.id !== castleId && (c as any).castle_id !== castleId)
        })
        qc.invalidateQueries({ queryKey: ['admin_user_castles', uid] })

        // 2. Optimistically update castle count in the current paginated summary cache without full reload
        const currentSummaryKey = ['admin_users_castles_summary', currentPage, pageSize, debouncedSearchQuery, filterType]
        qc.setQueryData<AdminUsersCastlesPaginatedResponse>(currentSummaryKey, old => {
          if (!old) return old
          const updatedUsers = (old.users || old.items || []).map(u => {
            if (u.uid === uid) {
              const newCount = Math.max(0, (u.castles_count || 1) - 1)
              return {
                ...u,
                castles_count: newCount,
                castle_count: newCount,
                castle_previews: (u.castle_previews || []).filter(cp => cp.id !== castleId && (cp as any).castle_id !== castleId),
              }
            }
            return u
          })
          return {
            ...old,
            items: updatedUsers,
            users: updatedUsers,
            summary_stats: old.summary_stats ? {
              ...old.summary_stats,
              total_castles: Math.max(0, old.summary_stats.total_castles - 1),
            } : undefined
          }
        })
      }
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      qc.invalidateQueries({ queryKey: ['admin_users'] })
      setDeletingCastle(null)
    },
    onError: (err: any) => {
      toast.error(err.message || t('accounts.deleteFailed', 'تعذر حذف القلعة'))
    }
  })

  // ─── Disable Elf for All Castles Mutation ─────────────────
  const disableElfMutation = useMutation({
    mutationFn: async () => {
      return await disableElfForAllCastles()
    },
    onSuccess: (data) => {
      toast.success(data.message || 'تم إيقاف مهمة العفريت لجميع القلاع بنجاح')
      qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })
      qc.invalidateQueries({ queryKey: ['admin_user_castles'] })
      qc.invalidateQueries({ queryKey: ['admin_stats'] })
      setShowDisableElfModal(false)
    },
    onError: (err: any) => {
      toast.error(err.message || 'تعذر إيقاف مهمة العفريت')
    }
  })

  const confirmDeleteCastle = () => {
    if (!deletingCastle) return
    deleteMutation.mutate(deletingCastle.castleId)
  }

  // ─── Overall Counts ────────────────────────────────────────
  const stats = useMemo(() => {
    if (paginatedData?.summary_stats) {
      return {
        totalUsers: paginatedData.summary_stats.total_users,
        totalCastles: paginatedData.summary_stats.total_castles,
        runningCastles: paginatedData.summary_stats.total_running,
      }
    }
    let totalCastles = 0
    let runningCastles = 0
    users.forEach(u => {
      totalCastles += u.castles_count || u.castle_count || 0
      runningCastles += u.running_count || u.active_count || 0
    })
    return {
      totalUsers: totalItems,
      totalCastles,
      runningCastles,
    }
  }, [paginatedData, users, totalItems])

  return (
    <AdminLayout title="قلاع المستخدمين">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">

        {/* ── Header & KPI Badges ── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-[#0c1410] p-4 sm:p-5 rounded-2xl border border-slate-200/80 dark:border-white/10 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <Landmark size={20} className="text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-black text-slate-900 dark:text-white leading-tight">
                قلاع المستخدمين
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                إدارة مركزية لجميع مستخدمي المنصة وقلاعهم مع التحكم الكامل
              </p>
            </div>
          </div>

          {/* Quick Metrics & Actions */}
          <div className="flex flex-wrap items-center gap-2 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100 dark:border-white/5">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 text-xs font-semibold text-slate-700 dark:text-slate-300">
              <Users size={12} className="text-emerald-500" />
              <span>{stats.totalUsers} مستخدم</span>
            </span>

            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/80 dark:border-emerald-500/25 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
              <Landmark size={12} />
              <span>{stats.totalCastles} قلعة</span>
            </span>

            {stats.runningCastles > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-teal-50 dark:bg-teal-500/15 border border-teal-200/80 dark:border-teal-500/30 text-xs font-bold text-teal-700 dark:text-teal-300 animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
                <span>{stats.runningCastles} يعمل الآن</span>
              </span>
            )}

            <button
              type="button"
              onClick={() => setShowDisableElfModal(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/25 text-xs font-bold transition-colors cursor-pointer"
              title="إيقاف مهمة الهجوم على العفريت لجميع القلاع في النظام"
            >
              <Swords size={12} className="text-amber-500" />
              <span>إيقاف العفريت للكل</span>
            </button>

            <button
              type="button"
              onClick={() => refetch()}
              disabled={isRefetching}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 transition-colors cursor-pointer"
              title="تحديث البيانات"
            >
              <RefreshCw size={13} className={isRefetching ? 'animate-spin text-emerald-500' : ''} />
            </button>
          </div>
        </div>

        {/* ── Search & Filter Controls ── */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          {/* Search Input */}
          <div className="relative flex-1 min-w-0">
            <Search size={15} className="absolute start-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="بحث بالاسم، بريد المستخدم، بريد القلعة، أو اسم اللورد..."
              className="w-full ps-9.5 pe-8 py-2 bg-white dark:bg-[#0c1410] border border-slate-200/80 dark:border-white/10 rounded-xl text-xs text-slate-900 dark:text-gray-100 placeholder-slate-400 focus:outline-hidden focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/25 transition-all shadow-xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 rounded cursor-pointer"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Quick Filter Badges */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 shrink-0 select-none">
            {(
              [
                { id: 'all', label: 'الكل' },
                { id: 'with_castles', label: 'لديهم قلاع' },
                { id: 'running', label: 'قيد التشغيل' },
                { id: 'no_castles', label: 'بدون قلاع' },
              ] as const
            ).map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilterType(f.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer border ${
                  filterType === f.id
                    ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                    : 'bg-white dark:bg-[#0c1410] text-slate-600 dark:text-slate-300 border-slate-200/80 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/5'
                }`}
              >
                {f.label}
              </button>
            ))}

            {Object.values(expandedUsers).some(Boolean) && (
              <button
                type="button"
                onClick={collapseAll}
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-500 dark:text-slate-400 bg-white dark:bg-white/5 border border-slate-200/80 dark:border-white/10 hover:text-slate-800 dark:hover:text-white transition-colors cursor-pointer"
                title="إغلاق كافة الكاردات"
              >
                طي الكل
              </button>
            )}
          </div>
        </div>

        {/* ── Users List ── */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 bg-white dark:bg-[#0c1410] rounded-2xl border border-slate-200/80 dark:border-white/10">
            <div className="w-8 h-8 rounded-full border-2 border-emerald-500/30 border-t-emerald-500 animate-spin" />
            <span className="text-xs text-slate-500 dark:text-slate-400">جاري تحميل المستخدمين وقلاعهم...</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center bg-white dark:bg-[#0c1410] rounded-2xl border border-slate-200/80 dark:border-white/10 p-6">
            <Users size={36} className="text-slate-300 dark:text-slate-600 mb-2" />
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">لا توجد نتائج مطابقة</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
              لم نعثر على أي مستخدم أو قلعة تطابق شروط البحث الحالية
            </p>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="mt-3 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 text-xs font-semibold hover:bg-emerald-500/20 transition-colors cursor-pointer"
              >
                مسح البحث
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredUsers.map(user => {
              const isExpanded = Boolean(expandedUsers[user.uid])

              return (
                <div
                  key={user.uid}
                  className="bg-white dark:bg-[#0c1410] rounded-2xl border border-slate-200/80 dark:border-white/10 shadow-xs overflow-hidden transition-all duration-200"
                >
                  {/* ── User Row / Header Card (Click to expand/collapse) ── */}
                  <div
                    onClick={() => toggleUser(user.uid)}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 sm:p-4 hover:bg-slate-50/60 dark:hover:bg-white/[0.02] cursor-pointer select-none transition-colors border-b border-transparent"
                  >
                    {/* Left: User Identity */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/10 border border-emerald-500/30 flex items-center justify-center font-bold text-sm text-emerald-600 dark:text-emerald-400 shrink-0">
                        {user.display_name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || 'U'}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-slate-900 dark:text-white truncate">
                            {user.display_name || user.email.split('@')[0]}
                          </span>

                          {user.is_banned ? (
                            <span className="px-1.5 py-0.2 rounded-md bg-rose-500/15 border border-rose-500/30 text-[10px] font-bold text-rose-500 dark:text-rose-400">
                              محظور
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.2 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                              {user.subscription?.plan_name || 'نشط'}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5 truncate">
                          <span>{user.email}</span>
                          {user.tenant_domain && (
                            <span className="text-[10px] px-1 py-0.2 rounded bg-slate-100 dark:bg-white/5 border border-slate-200/60 dark:border-white/10">
                              {user.tenant_domain}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: Badges & Chevron */}
                    <div className="flex items-center justify-between sm:justify-end gap-2 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100 dark:border-white/5">
                      {/* Castles Count */}
                      <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border ${
                        user.castles_count > 0
                          ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200/80 dark:border-emerald-500/25 text-emerald-700 dark:text-emerald-300'
                          : 'bg-slate-100 dark:bg-white/5 border-slate-200/80 dark:border-white/10 text-slate-500 dark:text-slate-400'
                      }`}>
                        <Landmark size={12} />
                        <span>{user.castles_count} {user.castles_count === 1 ? 'قلعة' : 'قلاع'}</span>
                      </span>

                      {/* Running Count if any */}
                      {user.running_count > 0 && (
                        <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-teal-50 dark:bg-teal-500/15 border border-teal-200/80 dark:border-teal-500/30 text-[11px] font-bold text-teal-700 dark:text-teal-300">
                          <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                          <span>{user.running_count} يعمل</span>
                        </span>
                      )}

                      {/* Expand/Collapse Chevron Indicator */}
                      <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200/60 dark:border-white/10 flex items-center justify-center text-slate-500 dark:text-slate-400 shrink-0">
                        {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                      </div>
                    </div>
                  </div>

                  {/* ── Dropdown / Collapsed Content: Lazy mounted on expand ── */}
                  {isExpanded && (
                    <div className="p-3 sm:p-4 bg-slate-50/70 dark:bg-[#070d0a]/60 border-t border-slate-200/80 dark:border-white/10 space-y-3">
                      <UserCastlesDetail
                        user={user}
                        onDeleteCastle={(castle, u) => {
                          setDeletingCastle({
                            castleId: castle.id,
                            castleEmail: castle.email,
                            userUid: u.uid,
                            userEmail: u.email,
                          })
                        }}
                      />
                    </div>
                  )}
                </div>
              )
            })}

            {/* ── Pagination Bar (Matches Admin.tsx) ── */}
            {totalItems > 0 && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-white dark:bg-[#0c1410] rounded-2xl border border-slate-200/80 dark:border-white/10 text-xs select-none shadow-xs mt-3">
                {/* Left: Range and total count */}
                <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-mono">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    {totalItems === 0 ? 0 : startIndex + 1}–{endIndex}
                  </span>
                  <span>/</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">
                    {totalItems}
                  </span>
                  <span>{t('admin.table.usersCount', 'مستخدم')}</span>
                </div>

                {/* Center: Prev / Next / Page Numbers */}
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    id="admin-castles-pagination-prev"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={validPage <= 1}
                    className="flex items-center justify-center w-8 h-8 rounded-lg border border-slate-200/80 dark:border-white/10 bg-white dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
                    title={t('common.prev', 'السابق')}
                  >
                    <ChevronRight size={15} className="rtl:rotate-0 rotate-180" />
                  </button>

                  <div className="flex items-center px-2 py-1 font-mono font-bold text-slate-700 dark:text-slate-300 text-xs">
                    <span>{validPage}</span>
                    <span className="mx-1 text-slate-400">/</span>
                    <span>{totalPages}</span>
                  </div>

                  <button
                    type="button"
                    id="admin-castles-pagination-next"
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={validPage >= totalPages}
                    className="flex items-center justify-center w-8 h-8 rounded-lg border border-slate-200/80 dark:border-white/10 bg-white dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
                    title={t('common.next', 'التالي')}
                  >
                    <ChevronLeft size={15} className="rtl:rotate-0 rotate-180" />
                  </button>
                </div>

                {/* Right: Page Size Selector */}
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-400 text-[11px] font-mono">{t('common.pageSize', 'عرض:')}</span>
                  {[10, 25, 50, 100].map(sz => (
                    <button
                      key={sz}
                      type="button"
                      onClick={() => setPageSize(sz)}
                      className={`px-2 py-1 rounded-md text-xs font-mono font-semibold transition cursor-pointer ${
                        pageSize === sz
                          ? 'bg-emerald-600 text-white shadow-xs'
                          : 'bg-white dark:bg-white/5 border border-slate-200/80 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/10'
                      }`}
                    >
                      {sz}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Delete Castle Confirmation Dialog ── */}
        {deletingCastle && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <div className="bg-white dark:bg-[#0c1410] border border-slate-200 dark:border-white/10 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-center justify-center text-rose-500 shrink-0">
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                    تأكيد حذف القلعة
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    حذف القلعة من حساب المستخدم نهائياً
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-white/5 rounded-xl border border-slate-200/60 dark:border-white/10 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">المستخدم:</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">{deletingCastle.userEmail}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">بريد القلعة:</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">{deletingCastle.castleEmail || deletingCastle.castleId}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={confirmDeleteCastle}
                  disabled={deleteMutation.isPending}
                  className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                >
                  {deleteMutation.isPending ? 'جاري الحذف...' : 'نعم، احذف القلعة'}
                </button>
                <button
                  type="button"
                  onClick={() => setDeletingCastle(null)}
                  disabled={deleteMutation.isPending}
                  className="py-2 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 text-xs font-semibold transition-colors cursor-pointer"
                >
                  إلغاء
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Disable Elf Confirmation Dialog ── */}
        {showDisableElfModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <div className="bg-white dark:bg-[#0c1410] border border-slate-200 dark:border-white/10 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-500 shrink-0">
                  <Swords size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                    إيقاف هجوم العفريت للجميع
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    تعطيل المهمة لكافة القلاع والدومينات
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-white/5 rounded-xl border border-slate-200/60 dark:border-white/10 text-xs space-y-2">
                <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                  هل أنت متأكد من رغبتك في إيقاف مهمة الهجوم على العفريت (ضبطها على <span className="font-mono text-amber-500 font-bold">False</span>) لجميع قلاع النظام عبر كافة الدومينات؟
                </p>
                <div className="flex items-center justify-between pt-1 border-t border-slate-200/40 dark:border-white/5 text-[11px] text-slate-500">
                  <span>إجمالي القلاع المتأثرة:</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">{stats.totalCastles} قلعة</span>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => disableElfMutation.mutate()}
                  disabled={disableElfMutation.isPending}
                  className="flex-1 py-2 px-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                >
                  {disableElfMutation.isPending ? (
                    <>
                      <RefreshCw size={13} className="animate-spin" />
                      <span>جاري الإيقاف...</span>
                    </>
                  ) : (
                    'تأكيد الإيقاف للكل'
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setShowDisableElfModal(false)}
                  disabled={disableElfMutation.isPending}
                  className="py-2 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 text-xs font-semibold transition-colors cursor-pointer"
                >
                  إلغاء
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </AdminLayout>
  )
}
