import React from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowLeft } from 'lucide-react'
import { Layout } from '../components/layout/Layout'
import { TaskTabContent } from '../components/accounts/TaskTabContent'
import { ResourceBar } from '../components/accounts/ResourceBar'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useCastle } from '../hooks/useCastles'
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

  const isRTL = language === 'ar'

  if (isLoading) return (
    <Layout><div className="py-32 text-gray-500 text-center">{t('common.loading')}</div></Layout>
  )
  if (!castle) return (
    <Layout><div className="py-32 text-gray-500 text-center">{t('common.error')}</div></Layout>
  )

  const info = castle.castle_info
  const bot  = castle.bot_status

  return (
    <Layout title={info.lord_name}>
      <div className="space-y-5 w-full">
        {/* Back button */}
        <button
          onClick={() => navigate('/accounts')}
          className="flex items-center gap-2 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors cursor-pointer"
        >
          {isRTL ? <ArrowRight size={16} /> : <ArrowLeft size={16} />}
          {t('common.back')}
        </button>

        {/* Castle header */}
        <div className="p-5 glass-card">
          <div className="flex flex-wrap justify-between items-start gap-4">
            <div className="flex items-start gap-4">
              <div className="flex flex-shrink-0 justify-center items-center bg-primary-900/60 dark:bg-primary-900/60 border border-primary-700/40 rounded-2xl w-14 h-14 font-bold text-primary-400 text-xl">
                {info.castle_level}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="font-bold text-gray-900 dark:text-white text-xl">{info.lord_name}</h1>
                  <span className="badge badge-blue">{info.castle_name}</span>
                  <StatusBadge state={bot.state} label={t(`status.${bot.state}`)} />
                </div>
                <div className="mt-1 text-gray-500 dark:text-gray-400 text-sm">{castle.email}</div>
                <div className="flex items-center gap-4 mt-2 text-gray-600 dark:text-gray-400 text-sm">
                  <span>⚡ {(info.lord_power / 1_000_000).toFixed(1)}M قوة</span>
                  <span>🌍 سيرفر #{info.server_id}</span>
                  <span>📍 {info.coordinates.x}, {info.coordinates.y}</span>
                  <span>⭐ VIP {info.vip_level}</span>
                </div>
                {info.alliance_name && (
                  <div className="mt-1 text-gray-600 dark:text-gray-400 text-sm">🤝 {info.alliance_name}</div>
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
                      : 'bg-black/5 dark:bg-white/4 border-gray-300 dark:border-white/10 text-gray-500 dark:text-gray-600'
                  }`}
                >
                  {i < bot.active_marches ? '⚔' : '·'}
                </div>
              ))}
              <span className="ms-1 text-gray-500 dark:text-gray-400 text-xs">{bot.active_marches}/{bot.max_marches}</span>
            </div>
          </div>

          {/* Resources */}
          <div className="mt-4 pt-4 border-gray-200 dark:border-white/8 border-t">
            <ResourceBar resources={castle.resources} />
          </div>

          {/* Bot status message */}
          {bot.last_run_message && (
            <div className="bg-black/5 dark:bg-white/3 mt-3 px-3 py-2 rounded-lg text-gray-600 dark:text-gray-400 text-xs">
              💬 {bot.last_run_message}
            </div>
          )}
        </div>

        {/* Task settings */}
        <div className="space-y-5 p-4 md:p-6 w-full glass-card">
          <div className="flex justify-between items-center">
            <h2 className="font-semibold text-gray-900 dark:text-white text-base">إعدادات المهام</h2>
          </div>
          <div className="w-full">
            <TaskTabContent castle={castle} userId={uid} />
          </div>
        </div>
      </div>
    </Layout>
  )
}
