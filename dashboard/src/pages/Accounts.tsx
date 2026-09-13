import React, { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Play, Square, Plus, AlertTriangle, Clock, SlidersHorizontal, Users } from 'lucide-react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { Layout } from '../components/layout/Layout'
import { CastleCard } from '../components/accounts/CastleCard'
import { TaskTabContent } from '../components/accounts/TaskTabContent'
import { AddCastleModal } from '../components/accounts/AddCastleModal'
import { EditCastleModal } from '../components/accounts/EditCastleModal'
import { ConfirmStopModal } from '../components/accounts/ConfirmStopModal'
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
  const [showBatchSettings, setShowBatchSettings] = useState(false)
  const [showStopAllModal, setShowStopAllModal] = useState(false)

  const { data, isLoading } = useCastles(uid)
  const updateBot    = useUpdateBotState(uid)  // للـ fallback وتحديث Firebase فقط
  const botControl   = useBotControl(uid)       // يشغّل/يوقف عبر api_server.py
  const deleteCastle = useDeleteCastle(uid)
  const batchUpdate  = useBatchUpdateCastleConfigs(uid)

  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([])
  const [hasInitializedBatch, setHasInitializedBatch] = useState(false)

  const allCastles = data?.pages.flatMap(p => p.items) ?? []

  // Filter castles by search query
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return allCastles
    return allCastles.filter(c =>
      c.castle_info.lord_name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.castle_info.alliance_name?.toLowerCase().includes(q) ||
      c.castle_id.toLowerCase().includes(q)
    )
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

  const runningCount = activeCastles.filter(c => c.bot_status.state === 'running').length
  const idleCount = activeCastles.length - runningCount
  const maxAllowed = user?.subscription?.max_castles_allowed ?? 1
  const currentCount = user?.subscription?.current_castles_count ?? activeCastles.length

  const handleRunAll = () => {
    activeCastles.forEach(c =>
      botControl.mutate({ castle: c, state: 'running' })
    )
    toast.success(`تم إرسال أمر التشغيل لـ ${activeCastles.length} حساب`)
  }

  const handleStopAll = () => {
    setShowStopAllModal(true)
  }

  const handleConfirmStopAll = () => {
    activeCastles.forEach(c =>
      botControl.mutate({ castle: c, state: 'idle' })
    )
    setShowStopAllModal(false)
    toast.success('تم إرسال أمر الإيقاف لجميع الحسابات بنجاح')
  }

  const handleDelete = (id: string, wasActive?: boolean) => {
    if (!confirm(t('accounts.confirmDelete'))) return
    deleteCastle.mutate({ castleId: id, wasActive }, {
      onSuccess: () => toast.success('تم حذف الحساب بنجاح'),
      onError:   () => toast.error(t('common.error')),
    })
  }

  // مزامنة الحسابات النشطة المختارة تلقائياً مع أول تحميل
  useEffect(() => {
    if (!hasInitializedBatch && activeCastles.length > 0) {
      setSelectedBatchIds(activeCastles.map(c => c.id))
      setHasInitializedBatch(true)
    }
  }, [activeCastles, hasInitializedBatch])

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
      toast.error('❌ يرجى تحديد حساب واحد على الأقل لتطبيق الإعدادات عليه!')
      throw new Error('No castles selected')
    }
    await batchUpdate.mutateAsync({
      castleIds: selectedBatchIds,
      config: changedSections,
    })
  }

  return (
    <Layout title={t('accounts.title')}>
      <div className="space-y-4">
        {/* Page header matching reference UI Image 4 & 6 */}
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div>
            <h1 className="font-bold text-white text-2xl">{t('accounts.title')}</h1>
            <p className="mt-0.5 text-gray-500 text-xs">
              نشط {runningCount} • {idleCount} غير نشط • الحد: {currentCount} / {maxAllowed}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleStopAll}
              disabled={runningCount === 0}
              className="flex items-center gap-1.5 disabled:opacity-50 text-sm btn-secondary"
            >
              <Square size={14} />
              {t('accounts.stopAll')}
            </button>
            <button
              onClick={handleRunAll}
              disabled={activeCastles.length === 0}
              className="flex items-center gap-1.5 disabled:opacity-50 text-sm btn-primary"
            >
              <Play size={14} />
              {t('accounts.runAll')}
            </button>
            <button
              onClick={() => setAddModalOpen(true)}
              className="flex items-center gap-1.5 shadow-glow text-sm btn-primary"
              id="add-account-btn"
            >
              <Plus size={14} />
              <span>حساب جديد </span>
            </button>
          </div>
        </div>

        {/* Banner (if running) */}
        {runningCount > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 bg-primary-900/30 p-3 border border-primary-700/30 rounded-xl"
          >
            <div className="flex flex-shrink-0 justify-center items-center bg-primary-700 rounded-lg w-7 h-7">
              <AlertTriangle size={14} className="text-primary-300" />
            </div>
            <p className="text-primary-300 text-sm">
              {t('accounts.banner', { count: runningCount })}
            </p>
            <span className="ms-auto badge badge-green">{runningCount} / {activeCastles.length}</span>
          </motion.div>
        )}

        {/* Batch Settings Accordion Header */}
        {activeCastles.length > 0 && (
          <div className="bg-primary-950/20 shadow-lg border border-primary-500/25 rounded-2xl w-full overflow-hidden transition-all duration-200 glass-card">
            {/* Clickable Header Bar: clicking anywhere on this header bar toggles the batch settings open/closed */}
            <div
              onClick={() => setShowBatchSettings(s => !s)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setShowBatchSettings(s => !s) } }}
              className={clsx(
                'flex justify-between items-center p-4 sm:p-5 w-full transition-all duration-200 cursor-pointer select-none',
                showBatchSettings
                  ? 'bg-primary-900/30 border-b border-white/10'
                  : 'hover:bg-primary-900/25 active:bg-primary-900/40'
              )}
            >
              <div className="flex items-center gap-3.5">
                <div className="flex justify-center items-center bg-primary-500/20 shadow-sm border border-primary-500/30 rounded-xl w-10 h-10 text-primary-400 shrink-0">
                  <SlidersHorizontal size={18} />
                </div>
                <div className="text-start">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-white text-sm sm:text-base">إعدادات جماعية</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 bg-primary-500/15 hover:bg-primary-500/25 px-3.5 py-2 border border-primary-500/30 rounded-xl font-semibold text-primary-400 text-xs transition-all shrink-0">
                <span className="hidden sm:inline">{showBatchSettings ? 'إغلاق الإعدادات' : 'فتح قائمة المهام'}</span>
                <span className="font-bold text-sm transition-transform duration-200">{showBatchSettings ? '▲' : '▼'}</span>
              </div>
            </div>

            {showBatchSettings && (
              <div className="space-y-5 bg-black/15 p-4 sm:p-5 w-full">
                {/* Account Selection Box */}
                <div className="space-y-3 bg-white/[0.03] p-4 border border-white/8 rounded-xl">
                  <div className="flex flex-wrap justify-between items-center gap-2">
                    <div className="flex items-center gap-2">
                      <Users size={15} className="text-primary-400" />
                      <span className="font-semibold text-white text-xs sm:text-sm">الحسابات المستهدفة</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleSelectAllBatch}
                      className="font-medium text-primary-400 hover:text-primary-300 text-xs underline transition-colors cursor-pointer"
                    >
                      {selectedBatchIds.length === activeCastles.length ? 'إلغاء تحديد الكل' : 'تحديد جميع الحسابات'}
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
                            'flex items-center gap-1.5 px-2.5 py-1 border rounded-lg font-medium text-[11px] transition-all duration-150 cursor-pointer',
                            isSelected
                              ? 'bg-primary-600/25 border-primary-500/60 text-white shadow-sm'
                              : 'bg-white/[0.02] border-white/10 text-gray-400 hover:border-white/20 hover:text-gray-300'
                          )}
                        >
                          <span
                            className={clsx(
                              'flex justify-center items-center border rounded w-3.5 h-3.5 font-bold text-[10px] transition-colors',
                              isSelected
                                ? 'bg-primary-500 border-primary-400 text-white'
                                : 'border-gray-600 bg-transparent text-transparent'
                            )}
                          >
                            ✓
                          </span>
                          <span className="font-semibold text-white">
                            {c.castle_info?.lord_name || 'قلعة'}
                          </span>

                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Batch target: TaskTabContent */}
                <div className="w-full">
                  <TaskTabContent
                    castle={activeCastles[0]}
                    userId={uid}
                    isBatchMode={true}
                    batchTargetCount={selectedBatchIds.length}
                    onBatchSave={handleBatchSave}
                  />
                </div>

              </div>
            )}
          </div>
        )}

        {/* Search input (matching reference UI Image 4 & 5) */}
        <div className="p-3 glass-card">
          <div className="relative">
            <Search size={15} className="top-1/2 absolute text-gray-500 -translate-y-1/2 start-3" />
            <input
              id="castle-search"
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="...البحث في البريد أو اسم القلعة"
              className="ps-9 input-field"
            />
          </div>
        </div>

        {/* Castles list */}
        {isLoading ? (
          <div className="py-20 text-gray-500 text-center">{t('common.loading')}</div>
        ) : allCastles.length === 0 ? (
          <div className="space-y-4 p-8 py-16 text-center glass-card">
            <span className="text-5xl">🏰</span>
            <h2 className="font-bold text-white text-lg">لا توجد حسابات مضافة بعد</h2>
            <p className="mx-auto max-w-sm text-gray-500 text-sm">
              أضف حساب قلعتك الأول لتبدأ بإدارة الموارد والمهام تلقائياً عبر البوت.
            </p>
            <button
              onClick={() => setAddModalOpen(true)}
              className="inline-flex gap-2 btn-primary"
            >
              <Plus size={16} />
              <span>إضافة حساب جديد</span>
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ─── Section 1: Registration Queue (طابور التسجيل) ─── */}
            {pendingCastles.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 font-semibold text-yellow-500 text-sm">
                  <Clock size={16} />
                  <span>طابور التسجيل ({pendingCastles.length})</span>
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
                  <span>نشط ({activeCastles.length})</span>
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
                    />
                  ))}
                </div>
              </div>
            )}

            {filtered.length === 0 && search && (
              <div className="py-12 text-gray-500 text-center">
                لم يتم العثور على أي حساب يطابق البحث "{search}"
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
    </Layout>
  )
}
