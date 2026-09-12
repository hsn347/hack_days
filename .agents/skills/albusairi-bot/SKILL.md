---
name: albusairi-bot
description: تحليل تطبيق البسيري موبايل (com.ebda3soft.EXC.albusairi). يحتوي على بروتوكول API، endpoints، مفتاح التشفير AES المستخرج، وهيكل الطلبات. فعّله عند العمل على أي بوت أو تحليل يخص تطبيق البسيري.
---

# البسيري موبايل - مرجع API والتشفير الكامل

## المراجع الرئيسية
- **CONTEXT.md**: `e:\osmanli\albusairi\CONTEXT.md`
- **Jadx Java Source**: `e:\osmanli\albusairi\jadx_out\sources\`
- **Apktool Smali & Res**: `e:\osmanli\albusairi\apktool_out\`
- **Native Library**: `e:\osmanli\albusairi\libnative-lib.so`

---

## 🔑 مفتاح التشفير AES (Plaintext Master Key)

```text
!Q6uGg384Ajupu1kl6U1vtCLRENs35VIcAf9LUZ@gK7gCHjnBfS30OhsVk7G93xP
```

- **الخوارزمية**: `AES-ECB-PKCS7` مع Base64 مخصص (`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_`)
- **المفتاح المشفر في Native SO**:
  `zRrVXeceB2gN3ai1uhZuVDmutEhYyAKftR-n7w6bPJF4oBW-EpXXwOfTaNOxL0AXRls9rzKPfsLoM4wwspzJLuY3puq3xx_E1bf-U4t7i1I=`

---

## 🌐 API Endpoints

- **Base URL**: `https://bosmobile.albusairiexch.com:6668/ExchangerService/`

| Endpoint | Method | الوصف |
|---|---|---|
| `login` | POST | تسجيل الدخول |
| `Logout_User/{SessionID}/{Phone}/{DeviceID}` | GET | تسجيل الخروج |
| `AddTransferRequest` | POST | إرسال حوالة جديدة |
| `GetTransfersListPost` | POST | كشف الحوالات |
| `GetListTransfersDelivering` | POST | حوالات قيد الاستلام |
| `GetCurrencyBalance` | POST | الاستعلام عن الرصيد |
| `GetListViewMain` | POST | بيانات الشاشة الرئيسية |
| `Window_OperationsAndroid` | POST | نافذة العمليات الرئيسية |
| `GETDataList` | POST | استعلامات القوائم |
| `GetListNotifications` | POST | الإشعارات |
| `Check_Security_Process` | POST | الفحص الأمني |
| `GetListSubscriberTopup` | POST | شحن رصيد وباقات |

---

## 📦 هيكل الـ BaseOperationModel

```json
{
  "AccessToken": "...",
  "SessionID": "...",
  "ClientType": "Android (مشفر AES)",
  "FormName": "EBS.Android.frmTransfersReceiving",
  "OpType": 0,
  "TransactionID": 0,
  "Method": null,
  "Condition": "",
  "TheRowJson": "[بيانات مشفرة AES كـ JSON array string]",
  "TheRow": null,
  "TheRowBytes": null,
  "CurrencyID": null,
  "ExtraInfo": null
}
```
