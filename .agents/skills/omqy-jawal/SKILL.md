---
name: omqy-jawal
description: تحليل تطبيق العمقي جوال (omqy.jawal). يحتوي على بروتوكول API، endpoints، انواع العمليات المالية، وكيفية الاعتراض بـ Frida. فعّله عند العمل على اي بوت او تحليل يخص تطبيق العمقي.
---

# العمقي جوال - مرجع API الكامل

## كيفية الاستخدام
هذا الـ skill يحتوي على المعرفة المستخرجة من APK تطبيق العمقي جوال.
- **CONTEXT.md** (`e:\omqy_analysis\CONTEXT.md`): التوثيق الكامل للبروتوكول
- **jadx_out** (`e:\omqy_analysis\jadx_out\sources\omqy\`): الكود المفكك

## معلومات سريعة

### Base URL
```
https://omq.alomqy.com/OmqyJawal/v1/{Endpoint}
```

### Headers الاجبارية
| Header | القيمة |
|--------|--------|
| DeviceID | Android Device ID |
| AccessToken | من استجابة LogIn |
| TimeZone | timezone المستخدم |
| Locale | ar / en |
| Platform | 1 (Android) |
| IPAddress | IP من api.ipify.org |
| AppVersion | 6 |
| AppID | 1 |

### Endpoints الرئيسية
| Endpoint | الوصف |
|----------|-------|
| LogIn | تسجيل دخول |
| ActivateDevice | تفعيل جهاز |
| MoneyOperation | عملية مالية (جامعة) |
| GetServiceInfo | معلومات الخدمة |
| RequestAccountName | اسم صاحب الحساب |

### اهم OperationType في MoneyOperation
| رقم | العملية |
|-----|---------|
| 18 | SEND_TRANSFER - تحويل داخلي |
| 21 | SEND_INTERNATIONAL_TRANSFER - تحويل دولي |
| 23 | DISPLAY_BALANCE - عرض الرصيد |
| 24 | REPORT_ACCOUNT - تقرير الحساب |
| 25 | TRANSFER_QUERY - استعلام تحويل |
| 108 | CURRENCY_EXCHANGE - صرف عملات |

## الاعتراض بـ Frida
```bash
frida -U -n OmqyJawal -l intercept.js
```

## ملفات الكود المهمة
- `e:\omqy_analysis\jadx_out\sources\omqy\jawal\module\account\http\AccountHttpController.java` - منطق الطلبات
- `e:\omqy_analysis\jadx_out\sources\app\base\web\http\HttpConstant.java` - ثوابت الـ API
- `e:\omqy_analysis\jadx_out\sources\app\base\web\http\HttpController.java` - الـ headers
