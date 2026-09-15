import React, { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Play, Square, Plus, Clock, SlidersHorizontal, Users, Lock, ShieldAlert, AlertTriangle, Copy, CheckCheck } from 'lucide-react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { Layout } from '../components/layout/Layout'
import { CastleCard } from '../components/accounts/CastleCard'
import { TaskTabContent } from '../components/accounts/TaskTabContent'
import { AddCastleModal } from '../components/accounts/AddCastleModal'
import { EditCastleModal } from '../components/accounts/EditCastleModal'
import { ConfirmStopModal } from '../components/accounts/ConfirmStopModal'
import { ConfirmDeleteCastleModal } from '../components/accounts/ConfirmDeleteCastleModal'
import { useAuth } from '../hooks/useAuth'
import { useCastles, useUpdateBotState, useBotControl, useDeleteCastle, useBatchUpdateCastleConfigs } from '../hooks/useCastles'
import type { Castle, CastleConfig } from '../types'
import toast from 'react-hot-toast'

export function AccountsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const uid = user?.uid ?? ''

  const [search, setSearch] = useState('')
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editingCastle, setEditingCastle] = useState<Castle | null>(null)
  const [deletingTarget, setDeletingTarget] = useState<{ id: string; wasActive?: boolean } | null>(null)
  const [showBatchSettings, setShowBatchSettings] = useState(false)
  const [showStopAllModal, setShowStopAllModal] = useState(false)

  const { data, isLoading } = useCastles(uid)
  const updateBot    = useUpdateBotState(uid)  // للـ fallback وتحديث Firebase فقط
  const botControl   = useBotControl(uid)       // يشغّل/يوقف عبر api_server.py
  const deleteCastle = useDeleteCastle(uid)
  const batchUpdate  = useBatchUpdateCastleConfigs(uid)

  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([])
  const [batchTemplateCastleId, setBatchTemplateCastleId] = useState<string>('')
  const [hasInitializedBatch, setHasInitializedBatch] = useState(false)

  const allCastles = data?.pages.flatMap(p => p.items) ?? []

  // Filter castles by search query
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return allCastles
    return allCastles.filter(c => {
      const emailPrefix = (c.email || '').split('@')[0].toLowerCase()
      return (
        c.castle_info.lord_name.toLowerCase().includes(q) ||
        emailPrefix.includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.castle_info.alliance_name?.toLowerCase().includes(q) ||
        c.castle_id.toLowerCase().includes(q)
      )
    })
  }, [allCastles, search])

  // Partition into pending vs active
  const pendingCastles = useMemo(() =>
    filtered.filter(c => !c.is_active || c.bot_status.state === 'pending'),
    [filtered]
  )

  const activeCastles = useMemo(() =>
    filtered.filter(c => c.is_active && c.bot_status.state !== 'pending'),
    [filtered]
  )

  // فحص هل الحساب يعمل بالفعل (سواء في جولة نشطة أو بانتظار الدورة التالية أو إعادة الاتصال)
  const isCastleRunning = (c: Castle): boolean => {
    const s = c.bot_status?.state
    const cs = c.bot_status?.conn_state
    return s === 'running' || s === 'waiting' || cs === 'connected' || cs === 'waiting' || cs === 'reconnecting'
  }

  const runningCastles = useMemo(() => activeCastles.filter(isCastleRunning), [activeCastles])
  const idleCastles = useMemo(() => activeCastles.filter(c => !isCastleRunning(c)), [activeCastles])

  const runningCount = runningCastles.length
  const idleCount = idleCastles.length
  const maxAllowed = user?.subscription?.max_castles_allowed ?? 1
  const currentCount = user?.subscription?.current_castles_count ?? activeCastles.length

  const isSuperAdmin = user?.role === 'admin' || user?.email?.trim().toLowerCase() === 'ibraboths@gmail.com'
  const isBanned = !isSuperAdmin && Boolean(user?.is_banned)
  const isExpired = !isSuperAdmin && (
    user?.subscription?.status === 'expired' ||
    (user?.subscription?.expires_at ? new Date(user.subscription.expires_at).getTime() < Date.now() : false)
  )
  const isRunBlocked = isBanned || isExpired

  const handleRunAll = () => {
    if (isBanned) {
      toast.error(t('accounts.bannedToast'))
      return
    }
    if (isExpired) {
      toast.error(t('accounts.expiredToast'))
      return
    }
    if (idleCastles.length === 0) {
      toast(t('accounts.allAlreadyRunning'), { icon: 'ℹ️' })
      return
    }
    // تشغيل الحسابات المتوقفة فقط دون المساس بالحسابات التي تعمل بالفعل
    idleCastles.forEach(c =>
      botControl.mutate({ castle: c, state: 'running' })
    )
    toast.success(t('accounts.commandSentRun', { count: idleCastles.length }))
  }

  const handleStopAll = () => {
    setShowStopAllModal(true)
  }

  const handleConfirmStopAll = () => {
    runningCastles.forEach(c =>
      botControl.mutate({ castle: c, state: 'idle' })
    )
    setShowStopAllModal(false)
    toast.success(t('accounts.commandSentStop'))
  }

  const handleDelete = (id: string, wasActive?: boolean) => {
    setDeletingTarget({ id, wasActive })
  }

  const handleConfirmDelete = () => {
    if (!deletingTarget) return
    deleteCastle.mutate({ castleId: deletingTarget.id, wasActive: deletingTarget.wasActive }, {
      onSuccess: () => {
        toast.success(t('accounts.deleteSuccess'))
        setDeletingTarget(null)
      },
      onError: () => {
        toast.error(t('common.error'))
        setDeletingTarget(null)
      },
    })
  }

  // مزامنة الحسابات النشطة وتعيين أول قلعة كقالب افتراضي تلقائياً مع أول تحميل
  useEffect(() => {
    if (!hasInitializedBatch && activeCastles.length > 0) {
      setSelectedBatchIds(activeCastles.map(c => c.id))
      setBatchTemplateCastleId(activeCastles[0].id)
      setHasInitializedBatch(true)
    }
  }, [activeCastles, hasInitializedBatch])

  // القلعة المعتمدة كقالب للإعدادات الجماعية
  const templateCastle = useMemo(() => {
    if (activeCastles.length === 0) return null
    return activeCastles.find(c => c.id === batchTemplateCastleId) || activeCastles[0]
  }, [activeCastles, batchTemplateCastleId])

  const handleSetAsBatchTemplate = (castleId: string) => {
    setBatchTemplateCastleId(castleId)
    setShowBatchSettings(true)
    const target = activeCastles.find(c => c.id === castleId)
    const name = (target?.castle_info?.lord_name && !['لورد الإمبراطورية', 'القلعة الملكية', 'قلعة جديدة', 'غير معروف', 'قلعة'].includes(target.castle_info.lord_name))
      ? target.castle_info.lord_name
      : (target?.email || '').split('@')[0] || 'القلعة'
    toast.success(t('accounts.templateLoadedToast', { name }))
  }

  const handleApplyAllTemplateSettings = async () => {
    if (!templateCastle) return
    if (selectedBatchIds.length === 0) {
      toast.error(t('accounts.selectAtLeastOneBatch'))
      return
    }
    try {
      await batchUpdate.mutateAsync({
        castleIds: selectedBatchIds,
        config: templateCastle.config,
      })
      toast.success(t('accounts.applyAllSuccess', { count: selectedBatchIds.length }))
    } catch {
      toast.error(t('common.error'))
    }
  }

  const handleSelectAllBatch = () => {
    if (selectedBatchIds.length === activeCastles.length) {
      setSelectedBatchIds([])
    } else {
      setSelectedBatchIds(activeCastles.map(c => c.id))
    }
  }

  const handleToggleBatchCastle = (castleId: string) => {
    setSelectedBatchIds(prev =>
      prev.includes(castleId) ? prev.filter(id => id !== castleId) : [...prev, castleId]
    )
  }

  const handleBatchSave = async (changedSections: Partial<CastleConfig>) => {
    if (selectedBatchIds.length === 0) {
      toast.error(t('accounts.selectAtLeastOneBatch'))
      throw new Error('No castles selected')
    }
    await batchUpdate.mutateAsync({
      castleIds: selectedBatchIds,
      config: changedSections,
    })
    // تبقى الحسابات المستهدفة هي جميع الحسابات النشطة بشكل افتراضي
    setSelectedBatchIds(activeCastles.map(c => c.id))
  }

  return (
    <Layout title={t('accounts.title')}>
      <div className="space-y-4">
        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center justify-between">
            <h1 className="font-bold text-white text-xl sm:text-2xl">{t('accounts.title')}</h1>
            {/* Quick status pill on mobile */}
            <div className="sm:hidden flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-xs">
              <span className={clsx('w-2 h-2 rounded-full', runningCount > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-gray-500')} />
              <span className="text-gray-300 font-medium">{activeCastles.length} {t('accounts.accountUnit')}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:flex items-center gap-2">
            <button
              onClick={() => setAddModalOpen(true)}
              className="col-span-2 sm:col-span-1 order-first sm:order-last flex items-center justify-center gap-2 py-2.5 sm:py-2 px-4 shadow-glow text-sm font-bold btn-primary rounded-xl active:scale-[0.98] transition-all"
              id="add-account-btn"
            >
              <Plus size={16} />
              <span>{t('accounts.addAccount')}</span>
            </button>
            <button
              onClick={handleRunAll}
              disabled={activeCastles.length === 0 || (!isRunBlocked && idleCastles.length === 0)}
              className={clsx(
                'flex items-center justify-center gap-1.5 py-2 px-3 text-xs sm:text-sm font-semibold rounded-xl active:scale-[0.98] transition-all',
                isRunBlocked
                  ? 'btn-run-all-locked bg-rose-500/15 border border-rose-500/40 text-rose-300 hover:bg-rose-500/25 cursor-pointer'
                  : 'btn-primary disabled:opacity-50'
              )}
              title={
                isBanned
                  ? t('accounts.bannedTooltip')
                  : isExpired
                  ? t('accounts.expiredTooltip')
                  : idleCastles.length === 0
                  ? t('accounts.allAlreadyRunning')
                  : undefined
              }
            >
              {isRunBlocked ? (
                <>
                  <Lock size={13} className="text-rose-400 btn-lock-icon" />
                  <span>{t('accounts.runAll')} ({isBanned ? t('accounts.lockedBanned') : t('accounts.lockedExpired')})</span>
                </>
              ) : (
                <>
                  <Play size={13} />
                  <span>{t('accounts.runAll')}</span>
                </>
              )}
            </button>
            <button
              onClick={handleStopAll}
              disabled={runningCount === 0}
              className="flex items-center justify-center gap-1.5 py-2 px-3 disabled:opacity-50 text-xs sm:text-sm font-semibold btn-secondary rounded-xl active:scale-[0.98] transition-all"
            >
              <Square size={13} />
              <span>{t('accounts.stopAll')}</span>
            </button>
          </div>
        </div>

        {/* Banner if banned or expired */}
        {isBanned && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="account-banner-banned flex items-center gap-3.5 p-3.5 sm:p-4 rounded-2xl bg-rose-500/15 border border-rose-500/40 text-rose-950 dark:text-rose-100 shadow-xs"
          >
            <div className="banner-icon-box w-9 h-9 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shrink-0 text-rose-400">
              <ShieldAlert size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="banner-title font-bold text-sm text-rose-950 dark:text-rose-100">{t('dashboard.bannedTitle')}</span>
                <span className="badge badge-red text-[10px] py-0.5">{t('dashboard.bannedBadge')}</span>
              </div>
              <p className="banner-desc text-xs text-rose-800 dark:text-rose-300/90 mt-0.5">{t('accounts.bannedBanner')}</p>
            </div>
          </motion.div>
        )}
        {!isBanned && isExpired && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="account-banner-expired flex items-center gap-3.5 p-3.5 sm:p-4 rounded-2xl bg-rose-500/15 border border-rose-500/35 text-rose-950 dark:text-rose-100 shadow-xs"
          >
            <div className="banner-icon-box w-9 h-9 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shrink-0 text-rose-400">
              <AlertTriangle size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="banner-title font-bold text-sm text-rose-950 dark:text-rose-100">{t('dashboard.expiredTitle')}</span>
                <span className="badge badge-red text-[10px] py-0.5">{t('status.expired')}</span>
              </div>
              <p className="banner-desc text-xs text-rose-800 dark:text-rose-300/90 mt-0.5">{t('accounts.expiredBanner')}</p>
            </div>
          </motion.div>
        )}

        {/* Batch Settings Accordion Header */}
        {activeCastles.length > 0 && (
          <div className="batch-settings-card bg-primary-950/20 shadow-lg border border-primary-500/25 rounded-2xl w-full overflow-hidden glass-card">
            {/* Clickable Header Bar: clicking anywhere on this header bar toggles the batch settings open/closed */}
            <div
              onClick={() => setShowBatchSettings(s => !s)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setShowBatchSettings(s => !s) } }}
              className={clsx(
                'batch-settings-header flex justify-between items-center py-2 px-3.5 sm:py-2.5 sm:px-5 w-full cursor-pointer select-none',
                showBatchSettings
                  ? 'bg-primary-900/30 border-b border-white/10'
                  : 'hover:bg-primary-900/25 active:bg-primary-900/40'
              )}
            >
              <div className="flex items-center gap-2.5 sm:gap-3">
                <div className="batch-icon-pod flex justify-center items-center bg-primary-500/20 shadow-sm border border-primary-500/30 rounded-lg w-7 h-7 sm:w-8 sm:h-8 text-primary-400 shrink-0">
                  <SlidersHorizontal size={15} />
                </div>
                <div className="text-start">
                  <span className="batch-title font-bold text-white text-xs sm:text-sm">{t('accounts.batchSettings')}</span>
                </div>
              </div>

              <div className="batch-toggle-pill flex items-center gap-1.5 sm:gap-2 bg-primary-500/15 hover:bg-primary-500/25 px-2.5 py-1 sm:px-3 sm:py-1.5 border border-primary-500/30 rounded-lg font-semibold text-primary-400 text-xs shrink-0">
                <span className="hidden sm:inline">{showBatchSettings ? t('accounts.closeSettings') : t('accounts.openTaskList')}</span>
                <span className="font-bold text-xs">{showBatchSettings ? '▲' : '▼'}</span>
              </div>
            </div>

            {showBatchSettings && (
              <div className="batch-settings-body space-y-5 bg-black/15 p-4 sm:p-5 w-full">
                {/* Account Selection Box */}
                <div className="batch-selection-box space-y-3 bg-white/[0.03] p-4 border border-white/8 rounded-xl">
                  <div className="flex flex-wrap justify-between items-center gap-2">
                    <div className="flex items-center gap-2">
                      <Users size={15} className="batch-users-icon text-primary-400" />
                      <span className="batch-box-title font-semibold text-white text-xs sm:text-sm">{t('accounts.targetAccounts')}</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleSelectAllBatch}
                      className="batch-select-all font-medium text-primary-400 hover:text-primary-300 text-xs underline transition-colors cursor-pointer"
                    >
                      {selectedBatchIds.length === activeCastles.length ? t('accounts.deselectAll') : t('accounts.selectAll')}
                    </button>
                  </div>

                  {/* Badges / Checkboxes for individual active castles */}
                  <div className="flex flex-wrap gap-2 pt-1 max-h-48 overflow-y-auto">
                    {activeCastles.map(c => {
                      const isSelected = selectedBatchIds.includes(c.id)
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => handleToggleBatchCastle(c.id)}
                          className={clsx(
                            'batch-castle-chip flex items-center gap-1.5 px-2.5 py-1 border rounded-lg font-medium text-[11px] transition-all duration-150 cursor-pointer',
                            isSelected
                              ? 'chip-selected bg-primary-600/25 border-primary-500/60 text-white shadow-sm'
                              : 'chip-unselected bg-white/[0.02] border-white/10 text-gray-400 hover:border-white/20 hover:text-gray-300'
                          )}
                        >
                          <span
                            className={clsx(
                              'chip-checkbox flex justify-center items-center border rounded w-3.5 h-3.5 font-bold text-[10px] transition-colors',
                              isSelected
                                ? 'bg-primary-500 border-primary-400 text-white'
                                : 'border-gray-600 bg-transparent text-transparent'
                            )}
                          >
                            ✓
                          </span>
                          <span className="chip-name font-semibold text-white">
                            {(() => {
                              const prefix = (c.email || '').split('@')[0] || 'قلعة'
                              return (c.castle_info?.lord_name && !['لورد الإمبراطورية', 'القلعة الملكية', 'قلعة جديدة', 'غير معروف', 'قلعة'].includes(c.castle_info.lord_name))
                                ? c.castle_info.lord_name
                                : prefix
                            })()}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Source Template Castle Box */}
                <div className="batch-template-box space-y-3 bg-white/[0.03] p-4 border border-white/8 rounded-xl">
                  <div className="flex flex-wrap justify-between items-center gap-2">
                    <div className="flex items-center gap-2">
                      <Copy size={15} className="text-primary-400 shrink-0" />
                      <span className="batch-box-title font-semibold text-white text-xs sm:text-sm">
                        {t('accounts.templateCastle')}
                      </span>
                    </div>

                    {templateCastle && (
                      <button
                        type="button"
                        onClick={handleApplyAllTemplateSettings}
                        disabled={batchUpdate.isPending || selectedBatchIds.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-primary-600 hover:bg-primary-500 active:scale-95 text-white disabled:opacity-50 transition-all cursor-pointer shadow-sm"
                        title={t('accounts.applyAllFromTemplate')}
                      >
                        <CheckCheck size={14} />
                        <span>{t('accounts.applyAllFromTemplate')}</span>
                      </button>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-1">
                    <label className="text-xs text-gray-400 shrink-0">
                      {t('accounts.copyFromCastle')}
                    </label>
                    <select
                      value={templateCastle?.id || ''}
                      onChange={(e) => setBatchTemplateCastleId(e.target.value)}
                      className="input-field !py-2 !px-3 text-xs sm:text-sm rounded-lg flex-1 cursor-pointer"
                    >
                      {activeCastles.map(c => {
                        const prefix = (c.email || '').split('@')[0] || 'قلعة'
                        const name = (c.castle_info?.lord_name && !['لورد الإمبراطورية', 'القلعة الملكية', 'قلعة جديدة', 'غير معروف', 'قلعة'].includes(c.castle_info.lord_name))
                          ? c.castle_info.lord_name
                          : prefix
                        return (
                          <option key={c.id} value={c.id}>
                            {name} — ({c.email})
                          </option>
                        )
                      })}
                    </select>
                  </div>
                </div>

                {/* Batch target: TaskTabContent */}
                {templateCastle && (
                  <div className="w-full">
                    <TaskTabContent
                      castle={templateCastle}
                      userId={uid}
                      isBatchMode={true}
                      batchTargetCount={selectedBatchIds.length}
                      onBatchSave={handleBatchSave}
                    />
                  </div>
                )}

              </div>
            )}
          </div>
        )}

        {/* Search input (matching reference UI Image 4 & 5) */}
        <div className="p-2.5 sm:p-3 glass-card">
          <div className="relative flex items-center">
            <Search size={16} className="pointer-events-none top-1/2 absolute text-gray-400 -translate-y-1/2 start-3.5 z-10" />
            <input
              id="castle-search"
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={t('accounts.searchPlaceholder')}
              className="w-full input-field !ps-10 text-sm sm:text-base"
              style={{ paddingInlineStart: '2.6rem' }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute end-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white text-xs px-2 py-1 rounded-md bg-white/10 hover:bg-white/15 transition-colors cursor-pointer"
                title={t('accounts.clearSearch')}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Castles list */}
        {isLoading ? (
          <div className="py-20 text-gray-500 text-center">{t('common.loading')}</div>
        ) : allCastles.length === 0 ? (
          <div className="space-y-4 p-8 py-16 text-center glass-card">
            <span className="text-5xl">🏰</span>
            <h2 className="font-bold text-white text-lg">{t('accounts.noAccounts')}</h2>
            <p className="mx-auto max-w-sm text-gray-500 text-sm">
              {t('accounts.noAccountsDesc')}
            </p>
            <button
              onClick={() => setAddModalOpen(true)}
              className="inline-flex gap-2 btn-primary"
            >
              <Plus size={16} />
              <span>{t('accounts.addFirstCastle')}</span>
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ─── Section 1: Registration Queue (طابور التسجيل) ─── */}
            {pendingCastles.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 font-semibold text-yellow-500 text-sm">
                  <Clock size={16} />
                  <span>{t('accounts.regQueue')} ({pendingCastles.length})</span>
                </div>
                <div className="space-y-3">
                  {pendingCastles.map((castle, idx) => (
                    <CastleCard
                      key={castle.id}
                      castle={castle}
                      userId={uid}
                      index={idx}
                      isPending
                      onDelete={() => handleDelete(castle.id, false)}
                      onEdit={() => setEditingCastle(castle)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ─── Section 2: Active Castles (نشط) ─── */}
            {activeCastles.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 font-semibold text-emerald-500 text-sm">
                  <span className="bg-emerald-500 shadow-glow rounded-full w-2.5 h-2.5" />
                  <span>{t('accounts.active')} ({activeCastles.length})</span>
                </div>
                <div className="space-y-3">
                  {activeCastles.map((castle, idx) => (
                    <CastleCard
                      key={castle.id}
                      castle={castle}
                      userId={uid}
                      index={idx}
                      onDelete={() => handleDelete(castle.id, true)}
                      onEdit={() => setEditingCastle(castle)}
                      onSetBatchTemplate={handleSetAsBatchTemplate}
                    />
                  ))}
                </div>
              </div>
            )}

            {filtered.length === 0 && search && (
              <div className="py-12 text-gray-500 text-center">
                {t('accounts.noMatchingAccounts', { query: search })}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Add Castle Modal */}
      <AddCastleModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        userId={uid}
      />

      {/* Edit Castle Credentials Modal */}
      <EditCastleModal
        isOpen={!!editingCastle}
        castle={editingCastle}
        onClose={() => setEditingCastle(null)}
        userId={uid}
      />

      {/* Confirm Stop All Modal */}
      <ConfirmStopModal
        isOpen={showStopAllModal}
        onClose={() => setShowStopAllModal(false)}
        onConfirm={handleConfirmStopAll}
        isAll={true}
        count={runningCount}
      />

      {/* Confirm Delete Castle Modal */}
      <ConfirmDeleteCastleModal
        isOpen={!!deletingTarget}
        onClose={() => setDeletingTarget(null)}
        onConfirm={handleConfirmDelete}
        isPending={deleteCastle.isPending}
      />
    </Layout>
  )
}
