import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowLeft } from 'lucide-react'
import { Layout } from '../components/layout/Layout'
import { TaskTabContent } from '../components/accounts/TaskTabContent'
import { ResourceBar } from '../components/accounts/ResourceBar'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useCastle, useCastleLogs } from '../hooks/useCastles'
import { useAuth } from '../hooks/useAuth'
import { useAppStore } from '../store/appStore'

export function CastleDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { language } = useAppStore()
  const uid = user?.uid ?? ''

  const { data: castle, isLoading } = useCastle(uid, id ?? '')
  const { data: logs } = useCastleLogs(uid, id ?? '')

  const isRTL = language === 'ar'

  if (isLoading) return (
    <Layout><div className="text-center py-32 text-gray-500">{t('common.loading')}</div></Layout>
  )
  if (!castle) return (
    <Layout><div className="text-center py-32 text-gray-500">{t('common.error')}</div></Layout>
  )

  const info = castle.castle_info
  const bot  = castle.bot_status

  return (
    <Layout title={info.lord_name}>
      <div className="space-y-5 w-full">
        {/* Back button */}
        <button
          onClick={() => navigate('/accounts')}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
        >
          {isRTL ? <ArrowRight size={16} /> : <ArrowLeft size={16} />}
          {t('common.back')}
        </button>

        {/* Castle header */}
        <div className="glass-card p-5">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-primary-900/60 border border-primary-700/40 flex items-center justify-center text-xl font-bold text-primary-400 flex-shrink-0">
                {info.castle_level}
              </div>
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-xl font-bold text-white">{info.lord_name}</h1>
                  <span className="badge badge-blue">{info.castle_name}</span>
                  <StatusBadge state={bot.state} label={t(`status.${bot.state}`)} />
                </div>
                <div className="text-sm text-gray-500 mt-1">{castle.email}</div>
                <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                  <span>⚡ {(info.lord_power / 1_000_000).toFixed(1)}M قوة</span>
                  <span>🌍 سيرفر #{info.server_id}</span>
                  <span>📍 {info.coordinates.x}, {info.coordinates.y}</span>
                  <span>⭐ VIP {info.vip_level}</span>
                </div>
                {info.alliance_name && (
                  <div className="text-sm text-gray-500 mt-1">🤝 {info.alliance_name}</div>
                )}
              </div>
            </div>

            {/* March slots */}
            <div className="flex items-center gap-1.5">
              {Array.from({ length: bot.max_marches }).map((_, i) => (
                <div
                  key={i}
                  className={`w-7 h-7 rounded-lg border flex items-center justify-center text-xs ${
                    i < bot.active_marches
                      ? 'bg-primary-700/60 border-primary-600/50 text-primary-300'
                      : 'bg-white/4 border-white/10 text-gray-600'
                  }`}
                >
                  {i < bot.active_marches ? '⚔' : '·'}
                </div>
              ))}
              <span className="text-xs text-gray-500 ms-1">{bot.active_marches}/{bot.max_marches}</span>
            </div>
          </div>

          {/* Resources */}
          <div className="mt-4 pt-4 border-t border-white/8">
            <ResourceBar resources={castle.resources} />
          </div>

          {/* Bot status message */}
          {bot.last_run_message && (
            <div className="mt-3 text-xs text-gray-500 bg-white/3 rounded-lg px-3 py-2">
              💬 {bot.last_run_message}
            </div>
          )}
        </div>

        {/* Task settings */}
        <div className="glass-card p-4 md:p-6 space-y-5 w-full">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white text-base">إعدادات المهام</h2>
          </div>
          <div className="w-full">
            <TaskTabContent castle={castle} userId={uid} />
          </div>
        </div>

        {/* Logs */}
        {logs && logs.length > 0 && (
          <div className="glass-card overflow-hidden">
            <div className="px-5 py-3 border-b border-white/8">
              <h2 className="text-sm font-semibold text-white">سجل العمليات</h2>
            </div>
            <div className="divide-y divide-white/6 max-h-80 overflow-y-auto">
              {logs.map(log => (
                <div key={log.id} className="px-5 py-3 flex items-start gap-3">
                  <span className={`badge mt-0.5 flex-shrink-0 ${
                    log.status === 'success' ? 'badge-green' :
                    log.status === 'error'   ? 'badge-red'   :
                    log.status === 'warning' ? 'badge-yellow' : 'badge-gray'
                  }`}>
                    {log.status}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm text-white font-medium">{log.title}</div>
                    <div className="text-xs text-gray-500">{log.message}</div>
                    <div className="text-xs text-gray-600 mt-0.5">
                      {new Date(log.timestamp).toLocaleString('ar')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
