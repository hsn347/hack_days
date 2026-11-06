import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import ar from '../locales/ar.json'
import en from '../locales/en.json'
import tr from '../locales/tr.json'
import { getInitialLanguage } from '../config/tenants'

/**
 * تهيئة i18next بناءً على لغة النطاق والخيارات اليدوية للمستخدم:
 * - دومين نورجان (nurjanbot.online): اللغة الافتراضية التركية ('tr').
 * - دومين إبراهيم الرئيسي (ibraabot.online): اللغة الافتراضية العربية ('ar').
 * - تم إلغاء استخدام navigator detector لمنع لغة متصفح الزائر من تجاوز لغة النطاق الافتراضية.
 */
const initialLang = getInitialLanguage()

i18n
  .use(initReactI18next)
  .init({
    resources: {
      ar: { translation: ar },
      en: { translation: en },
      tr: { translation: tr },
    },
    lng: initialLang,
    fallbackLng: initialLang,
    interpolation: { escapeValue: false },
  })

export { getInitialLanguage }
export default i18n
