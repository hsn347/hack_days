import React, { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Play, Square, Plus, AlertTriangle, Clock, SlidersHorizontal } from 'lucide-react'
import { motion } from 'framer-motion'
import { Layout } from '../components/layout/Layout'
import { CastleCard } from '../components/accounts/CastleCard'
import { TaskTabs } from '../components/accounts/TaskTabs'
import { TaskTabContent } from '../components/accounts/TaskTabContent'
import { AddCastleModal } from '../components/accounts/AddCastleModal'
import { EditCastleModal } from '../components/accounts/EditCastleModal'
import { useAuth } from '../hooks/useAuth'
import { useCastles, useUpdateBotState, useBotControl, useDeleteCastle } from '../hooks/useCastles'
import type { TaskTab, Castle } from '../types'
import toast from 'react-hot-toast'

export function AccountsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const uid = user?.uid ?? ''

  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<TaskTab>('gather')
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editingCastle, setEditingCastle] = useState<Castle | null>(null)
  const [showBatchSettings, setShowBatchSettings] = useState(false)

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useCastles(uid)
  const updateBot    = useUpdateBotState(uid)  // للـ fallback وتحديث Firebase فقط
  const botControl   = useBotControl(uid)       // يشغّل/يوقف عبر api_server.py
  const deleteCastle = useDeleteCastle(uid)

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
    activeCastles.forEach(c =>
      botControl.mutate({ castle: c, state: 'idle' })
    )
    toast.success('تم إرسال أمر الإيقاف لجميع الحسابات')
  }

  const handleDelete = (id: string, wasActive?: boolean) => {
    if (!confirm(t('accounts.confirmDelete'))) return
    deleteCastle.mutate({ castleId: id, wasActive }, {
      onSuccess: () => toast.success('تم حذف الحساب بنجاح'),
      onError:   () => toast.error(t('common.error')),
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

        {/* Batch Settings Accordion Header (from reference Image 4) */}
        {activeCastles.length > 0 && (
          <div className="p-4 md:p-5 glass-card w-full">
            <button
              onClick={() => setShowBatchSettings(s => !s)}
              className="flex justify-between items-center w-full text-gray-400 hover:text-white text-xs transition-colors"
            >
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={14} className="text-primary-400" />
                <span className="font-medium text-white">إعدادات جماعية</span>
                <span className="text-gray-500">— تُطبّق على {activeCastles.length} حسابات</span>
              </div>
              <span>{showBatchSettings ? '▲' : '▼'}</span>
            </button>
            {showBatchSettings && (
              <div className="mt-4 pt-4 border-white/8 border-t w-full space-y-4">
                {/* Batch target: use first active castle as template */}
                {activeCastles.length > 0 && (
                  <div className="w-full space-y-4">
                    <TaskTabs active={activeTab} onChange={setActiveTab} />
                    <div className="mt-4 w-full">
                      <TaskTabContent
                        tab={activeTab}
                        castle={activeCastles[0]}
                        userId={uid}
                      />
                    </div>
                    <p className="mt-3 text-gray-500 text-xs text-center">
                      ⚠️ هذه الإعدادات تُعدّل حساب واحد فقط. لتطبيقها على الكل، سيُضاف هذا الخيار قريباً.
                    </p>
                  </div>
                )}
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

        {/* Load more */}
        {hasNextPage && (
          <div className="pt-2 text-center">
            <button
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
              className="text-sm btn-secondary"
            >
              {isFetchingNextPage ? t('common.loading') : 'تحميل المزيد'}
            </button>
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
    </Layout>
  )
}
