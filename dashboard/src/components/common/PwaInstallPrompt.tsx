import React, { useState, useEffect } from 'react'
import { Download, Share2, PlusSquare, X, CheckCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useTenant } from '../../context/TenantContext'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function PwaInstallPrompt() {
  const { t } = useTranslation()
  const { brandName, tagline, logoUrl } = useTenant()
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isIOS, setIsIOS] = useState(false)
  const [isStandalone, setIsStandalone] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)

  useEffect(() => {
    // Check if already installed / running in standalone mode
    const isRunningStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as unknown as { standalone?: boolean }).standalone === true

    setIsStandalone(isRunningStandalone)
    if (isRunningStandalone) return

    // Detect iOS
    const userAgent = window.navigator.userAgent.toLowerCase()
    const isIosDevice = /iphone|ipad|ipod/.test(userAgent)
    setIsIOS(isIosDevice)

    // Capture Android/Chrome install event
    const handleBeforeInstall = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      const dismissed = localStorage.getItem('osmanli_pwa_dismissed')
      if (!dismissed) {
        setShowPrompt(true)
      }
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstall)

    // Check if iOS prompt was previously dismissed
    const dismissed = localStorage.getItem('osmanli_pwa_dismissed')
    if (isIosDevice && !dismissed) {
      // Delay prompt slightly for great UX
      const timer = setTimeout(() => setShowPrompt(true), 1800)
      return () => clearTimeout(timer)
    }

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall)
    }
  }, [])

  const handleInstallClick = async () => {
    if (deferredPrompt) {
      await deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice
      if (outcome === 'accepted') {
        setShowPrompt(false)
      }
      setDeferredPrompt(null)
    }
  }

  const handleDismiss = () => {
    setShowPrompt(false)
    localStorage.setItem('osmanli_pwa_dismissed', 'true')
  }

  if (isStandalone || !showPrompt) return null

  return (
    <aside
      aria-label="PWA Installation Helper"
      className="fixed bottom-16 md:bottom-6 inset-x-3 sm:inset-x-auto sm:end-6 sm:max-w-md z-50 p-4 rounded-2xl bg-gray-950/95 border border-primary-500/40 shadow-[0_10px_35px_rgba(0,0,0,0.8)] backdrop-blur-xl text-white animate-in fade-in slide-in-from-bottom-4 duration-300"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gray-900 border border-primary-500/30 flex items-center justify-center shrink-0 overflow-hidden shadow-sm">
            <img src={logoUrl || '/logo.png?v=2'} alt={brandName} className="w-full h-full object-cover" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
              {t('pwa.title', { brand: brandName })}
              {tagline ? (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary-500/20 text-primary-400 border border-primary-500/30">
                  {tagline}
                </span>
              ) : null}
            </h2>
            <p className="text-xs text-gray-300 mt-0.5">
              {t('pwa.desc')}
            </p>
          </div>
        </div>

        <button
          onClick={handleDismiss}
          className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
          title={t('pwa.close')}
        >
          <X size={16} />
        </button>
      </div>

      {isIOS ? (
        <div className="mt-3 pt-3 border-t border-white/10 space-y-2 text-xs text-gray-300">
          <p className="font-semibold text-primary-400 flex items-center gap-1.5">
            {t('pwa.iosGuideTitle')}
          </p>
          <ol className="space-y-1.5 ps-1 text-[11px] leading-relaxed">
            <li className="flex items-center gap-2">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white/10 text-white font-bold text-[10px] shrink-0">1</span>
              <span>
                {t('pwa.iosStep1')}{' '}
                <Share2 size={13} className="inline text-sky-400 mx-0.5" />{' '}
                {t('pwa.iosStep1Suffix')}
              </span>
            </li>
            <li className="flex items-center gap-2">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white/10 text-white font-bold text-[10px] shrink-0">2</span>
              <span>
                {t('pwa.iosStep2')}{' '}
                <strong className="text-white">{t('pwa.iosStep2Highlight')}</strong>{' '}
                <PlusSquare size={13} className="inline text-primary-400 mx-0.5" />.
              </span>
            </li>
            <li className="flex items-center gap-2">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white/10 text-white font-bold text-[10px] shrink-0">3</span>
              <span>
                {t('pwa.iosStep3')}{' '}
                <strong className="text-white">{t('pwa.iosStep3Highlight')}</strong>{' '}
                {t('pwa.iosStep3Suffix')}
              </span>
            </li>
          </ol>
          <button
            onClick={handleDismiss}
            className="w-full mt-2 py-1.5 px-3 rounded-xl bg-primary-600 hover:bg-primary-500 font-bold text-white text-xs transition-colors flex items-center justify-center gap-1.5 shadow-glow"
          >
            <CheckCircle size={14} />
            <span>{t('pwa.gotIt')}</span>
          </button>
        </div>
      ) : (
        <div className="mt-3 pt-3 border-t border-white/10 flex items-center gap-2">
          {deferredPrompt && (
            <button
              onClick={handleInstallClick}
              className="flex-1 py-2 px-3 rounded-xl bg-primary-600 hover:bg-primary-500 font-bold text-white text-xs transition-colors flex items-center justify-center gap-1.5 shadow-glow"
            >
              <Download size={14} />
              <span>{t('pwa.installNow')}</span>
            </button>
          )}
          <button
            onClick={handleDismiss}
            className="py-2 px-3 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-gray-300 transition-colors"
          >
            {t('pwa.later')}
          </button>
        </div>
      )}
    </aside>
  )
}
