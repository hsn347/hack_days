# 📋 جميع أوامر اللعبة (Empire: Four Kingdoms)

> مستخرج من ملف `cmdDef_dec.lua` — مرجع كامل لجميع أوامر البروتوكول

---

## 🏰 الأوامر الأساسية (Core Modules)

### CMD_LOGIN_DATA_INIT = `1000`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_LOGIN_DATA_INIT | تهيئة بيانات تسجيل الدخول |

### CMD_CITY_MODULE = `1001`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_CITYDATA | تهيئة بيانات المدينة |
| `2` | REQ_BUILD_BUILDING | بناء مبنى جديد |
| `3` | REQ_BUILD_UPGRADE | ترقية مبنى |
| `4` | REQ_BUILD_DEMOLISH | هدم مبنى |
| `5` | REQ_BUILD_EXCHANGE | تبديل مبنى |
| `6` | REQ_OPEN_GROUND | فتح أرض |
| `7` | REQ_OPEN_CHARGE_QUEUE | فتح طابور مدفوع |
| `8` | REQ_COLLECT_RES | جمع الموارد |
| `9` | REQ_SPEED_UP_RES | تسريع إنتاج الموارد |
| `10` | REQ_LEFT_CAN_GET_RES | الموارد المتبقية |
| `11` | REQ_UNLOCK_BUILDING | فتح مبنى مقفل |
| `12` | REQ_BUILD_HONOR_UPGRADE | ترقية شرف المبنى |

### CMD_LORD_MODULE = `1002`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_LORDDATA | تهيئة بيانات اللورد |
| `2` | REQ_CHANGE_NICKNAME | تغيير الاسم |
| `3` | REQ_CHANGE_IMAGEID | تغيير الصورة |
| `4` | REQ_SET_SKILL | تعيين مهارة |
| `6` | REQ_RESET_SKILL | إعادة تعيين المهارات |
| `7` | REQ_LORD_INFO_UID | معلومات لاعب بالـ UID |
| `9` | REQ_LORD_VALUE_UID | قيم اللورد |
| `10` | REQ_LORD_BATTLE_INFO | معلومات قتال اللورد |
| `11` | REQ_SEARCH_LORD_IN_KINGDOM | بحث عن لاعب في المملكة |
| `12` | REQ_SEARCH_LORD_ALL_WORLD | بحث عن لاعب في كل العوالم |
| `25` | REQ_CHANGE_SYS_AVATAR | تغيير الصورة الرمزية |
| `26` | REQ_CHANGE_SIGNATURE | تغيير التوقيع |
| `28` | REQ_LORD_POWER_RANK | ترتيب القوة |
| `34` | **REQ_SEAL_ACCOUNT_LIST** | **قائمة الحسابات المحظورة** ✅ تم التحقق |

### CMD_QUEUE_MODULE = `1003`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_QUEUEDATA | بيانات الطوابير |
| `2` | REQ_SPEED_UP_QUEUE | تسريع طابور |
| `3` | REQ_CANCEL_QUEUE | إلغاء طابور |

### CMD_BACKPACK_MODULE = `1004`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_BACKPACKDATA | بيانات الحقيبة |
| `2` | REQ_USE_ITEM | استخدام أداة |
| `3` | REQ_MERGE_ITEM | دمج أدوات |
| `7` | REQ_USE_ALL_SAFE_RES | استخدام كل الموارد الآمنة |
| `8` | REQ_SPLIT_ITEM | تقسيم أداة |

### CMD_ARMY_MODULE = `1005`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_ARMYDATA | بيانات الجيش |
| `2` | **REQ_TRAIN_ARMY** | **تدريب جيش** 🔥 |
| `3` | REQ_FIRE_ARMY | تسريح جيش |
| `4` | **REQ_CURE_WOUNDED_ARMY** | **علاج جيش جريح** 🔥 |
| `5` | REQ_GET_ARMY | جلب بيانات الجيش |
| `6` | REQ_SET_COMPILE | تعيين تشكيل |
| `7` | REQ_GET_COMPILE | جلب تشكيل |

---

## 🗺️ أوامر الخريطة والحركة

### CMD_KINGDOM_MAP_MODULE = `1006`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_KINGDOM_MAP | خريطة المملكة |
| `15` | REQ_KINGDOM_MAP_OBJ_INFO | معلومات كائن على الخريطة |
| `17` | REQ_KINGDOM_MAP_MOVE_CITY | نقل المدينة |
| `21` | REQ_GET_ALLIANCE_MEMBER | أعضاء التحالف على الخريطة |
| `22` | REQ_GET_COLLECTING_INFO | معلومات الجمع |
| `33` | REQ_GET_SCOUT_FOOD | معلومات استكشاف الطعام |
| `42` | REQ_KINGDOM_MAP_GET_INIT_DATA | تهيئة بيانات الخريطة |
| `47` | REQ_SWITCH_WORLD_MAP | تبديل خريطة العالم |
| `55` | REQ_GET_KING | معلومات الملك |
| `56` | REQ_GET_OTHER_KINGDOM_INFO | معلومات مملكة أخرى |
| `1000` | REQ_KINGDOM_MAP_SYNC | مزامنة الخريطة |

### CMD_KINGDOM_QUEUE_MODULE = `1007`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `2` | ADD_KINGDOM_QUEUE | إضافة طابور مملكة |
| `6` | REQ_BACK_QUEUE | إرجاع طابور |
| `7` | REQ_SPEED_QUEUE | تسريع طابور |
| `8` | REQ_RECALL_QUEUE | استدعاء طابور |
| `16` | REQ_ALL_QUEUE | كل الطوابير |
| `78` | REQ_BACK_ALL_QUEUE | إرجاع كل الطوابير |
| `1000` | REQ_KINGDOM_LOCAL_QUEUE_SYNC | مزامنة الطوابير المحلية |

---

## ⚔️ التحالف (CMD_ALLIANCE_MODULE = `1010`) — الأهم!

| subcmd | الاسم | الوصف | حالة |
|--------|-------|-------|------|
| `1` | REQ_INIT_ALLIANCEDATA | تهيئة بيانات التحالف | |
| `2` | REQ_ALLIANCE_GET_INFO_BY_ID | معلومات تحالف بالـ ID | |
| `5` | REQ_ALLIANCE_GET_MEMBER_INFO | معلومات عضو | |
| `6` | REQ_ALLIANCE_GET_MEMBER_LIST | قائمة الأعضاء | |
| `7` | REQ_ALLIANCE_GET_APPLY_LIST | قائمة طلبات الانضمام | |
| `20` | REQ_ALLIANCE_CREATE | إنشاء تحالف | |
| `22` | REQ_ALLIANCE_JOIN | الانضمام لتحالف | |
| `23` | REQ_ALLIANCE_QUIT | مغادرة التحالف | |
| `24` | REQ_ALLIANCE_EXPEL_MEMBER | طرد عضو | |
| `25` | REQ_ALLIANCE_APPLY_JOIN | طلب انضمام | |
| `27` | REQ_ALLIANCE_AGREE_APPLY | قبول طلب انضمام | |
| `29` | REQ_ALLIANCE_INVITE_JOIN | دعوة للانضمام | |
| `34` | REQ_ALLIANCE_DEMISE | نقل القيادة | |
| `36` | REQ_ALLIANCE_PROMOTE_MEMBER | ترقية عضو | |
| `37` | REQ_ALLIANCE_DEMOTE_MEMBER | تنزيل رتبة عضو | |
| **`39`** | **REQ_ALLIANCE_STORE_DATA** | **📦 جلب بيانات متجر التحالف** | ✅ |
| **`40`** | **REQ_ALLIANCE_STORE_BUY** | **🛒 شراء من متجر التحالف** | ✅ |
| `41` | REQ_ALLIANCE_ITEMSHOP_BUY | شراء من متجر الأدوات | |
| `42` | REQ_ALLIANCE_LIST | قائمة التحالفات | |
| **`43`** | **REQ_ALLIANCE_LOG** | **📜 سجل أحداث التحالف** | ✅ |
| `44` | REQ_ALLIANCE_INIT_HELP | تهيئة المساعدة | |
| `45` | REQ_ALLIANCE_REQ_HELP | طلب مساعدة | |
| `46` | REQ_ALLIANCE_HELP_MEMBER | مساعدة عضو | |
| `47` | REQ_ALLIANCE_HELP_ALL | مساعدة الكل | |
| **`48`** | **REQ_ALLIANCE_DONATE_SCI** | **💰 تبرع لأبحاث التحالف** | ✅ |
| `49` | REQ_ALLIANCE_RESEARCH_SCI | بحث في أبحاث التحالف | |
| `50` | REQ_ALLIANCE_CLEAN_DONATE_SCI_CD | إزالة وقت انتظار التبرع | |
| `51` | REQ_ALLIANCE_DONATE_RANK | ترتيب التبرعات | |
| `52` | REQ_ALLIANCE_SEND_ALL_MAIL | إرسال بريد لجميع الأعضاء | |
| **`56`** | **REQ_ALLIANCE_MESSAGE_SHIELD_LIST** | **قائمة الدروع** | ✅ |
| **`58`** | **REQ_ALLIANCE_GET_BWIDLIST** | **القائمة السوداء/البيضاء** | ✅ |
| `62` | REQ_ALLIANCE_GET_STORE_RECORD | سجل مشتريات المتجر | |
| `63` | REQ_ALLIANCE_SET_BUILDING | بناء مبنى تحالف | |
| **`71`** | **REQ_ALLIANCE_TERRITORY_INIT_DATA** | **بيانات أراضي التحالف (الأعلام)** | ✅ |
| `75` | REQ_ALLIANCE_ALLIANCE_SCIENCE | بيانات أبحاث التحالف | |
| **`81`** | **REQ_ALLIANCE_DONATE_SYN_DATA** | **بيانات التبرع المتزامنة** | ✅ |
| `82` | REQ_ALLIANCE_RECOMMENT_SCIENCE | البحث الموصى به | |
| **`83`** | **REQ_ALLIANCE_REQ_ALLIANCE_STRIKE_BACK** | **بيانات الضربة المرتدة** | ✅ |
| `85` | REQ_ALLIANCE_CANNON_INFO | معلومات المدفع | |
| `86` | REQ_ALLIANCE_USE_CANNON | استخدام المدفع | |
| `89` | REQ_ALLIANCE_LARGE_RES | موارد التحالف الكبيرة | |

---

## 📬 الإشعارات (CMD_NOTIFY_MODULE = `1009`)

| subcmd | الاسم | الوصف | حالة |
|--------|-------|-------|------|
| `1` | NOTIFY_BACKPACK_UPDATE | تحديث الحقيبة | |
| **`2`** | **NOTIFY_WORLD_UPDATE** | **تحديث العالم (NPC، وحوش)** | ✅ |
| **`3`** | **NOTIFY_ALLIANCE_UPDATE** | **تحديث التحالف (أعضاء، أبحاث)** | ✅ |
| `4` | NOTIFY_CHAT_UPDATE | تحديث الدردشة | |
| `5` | NOTIFY_MAIL_UPDATE | تحديث البريد | |
| `7` | NOTIFY_BUFF_UPDATE | تحديث التعزيزات | |
| `8` | NOTIFY_LORD_UPDATE | تحديث اللورد | |
| **`9`** | **NOTIFY_CITY_UPDATE** | **تحديث المدينة (الموارد)** | ✅ |
| `14` | NOTIFY_QUEUE_UPDATE | تحديث الطابور | |
| `15` | NOTIFY_ARMY_UPDATE | تحديث الجيش | |
| **`19`** | **NOTIFY_SERVER_TIME** | **وقت السيرفر** | ✅ |
| `23` | NOTIFY_SHOP | إشعار المتجر | |
| **`30`** | **NOTIFY_KINGDOM_LIST** | **قائمة الممالك** | ✅ |
| **`36`** | **NOTIFY_ACTIVITY_SHOW_CHANGE_TIME** | **تغيير وقت الفعالية** | ✅ |
| **`96`** | **NOTIFY_ALLIANCE_TREASURE** | **كنوز التحالف** | ✅ |

---

## 💬 الدردشة والبريد

### CMD_CHAT_MODULE = `1011`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_NEWLY_CHATDATA | تهيئة الدردشة |
| `2` | REQ_SEND_MESSAGE | إرسال رسالة |
| `9` | REQ_INIT_SHIELD_DATA_AND_CHAT_STATUS | بيانات الحظر والحالة |
| `15` | REQ_GET_VOICE_ROOM_INVITE_INFO | دعوات غرف الصوت |

### CMD_MAIL_MODULE = `1015`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_MAILDATA | تهيئة البريد |
| `2` | REQ_MAIL_LIST | قائمة الرسائل |
| `3` | REQ_SEND_CHAT_MAIL | إرسال بريد |
| `4` | REQ_REMOVE_MAIL | حذف بريد |

---

## 🔬 الأبحاث والمتجر

### CMD_TECHNOLOGY_MODULE = `1017`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_TECHNOLOGY_DATA | بيانات الأبحاث |
| `2` | REQ_RESEARCH_TECHNOLOGY | بدء بحث |

### CMD_STORES_MODULE = `1024`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_INIT_STORESDATA | بيانات المتجر العام |

### CMD_PREMIUM_STORE_MODULE = `1068`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_PREMIUM_STORE_OPEN_PAGE | فتح المتجر المميز |
| `2` | REQ_PREMIUM_STORE_BUY | شراء من المتجر المميز |

---

## 🏆 المعارك والحروب

### CMD_COLLECTMAP_MODULE = `1022`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| **`1`** | **REQ_INIT_COLLECTMAPDATA** | **إحداثيات أعضاء التحالف** ✅ |

### CMD_CONQUESTWAR = `1070`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| **`1`** | **REQ_GET_CONQUESTWAR_INFO** | **معلومات حرب الغزو** ✅ |
| `2` | REQ_GET_CONQUESTWAR_RANK | ترتيب حرب الغزو |
| `4` | REQ_GET_CONQUESTWAR_STAGE_INFO | معلومات المرحلة |

### CMD_KINGDOM_QUEUE_MODULE = `1030`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| **`6`** | **نتائج مراحل الحرب** | **نقاط التحالف والأفراد** ✅ |

---

## 🎮 أوامر أخرى مهمة

### CMD_RAMADAN_RANK_MODULE = `1065`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| **`1`** | **REQ_RAMADAN_RANK_GET_ID** | **بيانات الترتيب** ✅ |

### CMD_ALLIANCE_TREASURE_MODULE = `2015`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_ALLIANCE_TREASURE_INIT | تهيئة كنوز التحالف |
| `2` | REQ_ALLIANCE_TREASURE_MANUAL_REFRESH | تحديث يدوي |
| `3` | REQ_ALLIANCE_TREASURE_DIG | حفر كنز |
| `4` | REQ_ALLIANCE_TREASURE_REQUEST_HELP | طلب مساعدة |
| `5` | REQ_ALLIANCE_TREASURE_HELP_OTHER | مساعدة آخر |
| `6` | REQ_ALLIANCE_TREASURE_RECEIVE | استلام كنز |
| `7` | REQ_ALLIANCE_TREASURE_SPEED | تسريع الكنز |

### CMD_STUFF_WORKSHOP_MODULE = `2021`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_REFRESH | تحديث الورشة |
| `2` | REQ_REFINERY | تكرير |

### CMD_ALLIANCE_DONATE_MODULE = `2033`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| **`1`** | **طابور تبرعات التحالف** | **queue: {}** ✅ |

### CMD_FIND_MONSTER_MODULE = `2011`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_JUST_DO_FIND | البحث عن وحش |
| `3` | REQ_SEARCH_MAP | بحث في الخريطة |
| `5` | REQ_ALL_GOD_BEAST_INFO | كل بيانات الوحوش الأسطورية |

### CMD_HERO_MODULE = `2058`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_DRAW_CARD | سحب بطاقة بطل |
| `2` | REQ_UPGRADE_LV | ترقية مستوى البطل |
| `3` | REQ_UPGRADE_SRAR | ترقية نجوم البطل |
| `4` | REQ_EQUIP_SKILL | تجهيز مهارة |
| `15` | REQ_APPOINT_HERO | تعيين بطل |

### CMD_RUNE_MODULE = `2065`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | SUBCMD_RUNE_GET_DATA | بيانات الأحجار الرونية |
| `2` | SUBCMD_RUNE_FORGE | تشكيل حجر |
| `3` | SUBCMD_RUNE_EQUIP | تجهيز حجر |
| `6` | SUBCMD_RUNE_UPGRADE | ترقية حجر |

### CMD_TEAM_MODULE = `2089`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `1` | REQ_TEAM_INIT_DATA | بيانات الفريق |
| `2` | REQ_TEAM_CREATE | إنشاء فريق |

### CMD_DRILL_BATTLE = `3103`
| subcmd | الاسم | الوصف |
|--------|-------|-------|
| `5` | SUBCMD_DRILL_BATTLE_DATA | بيانات معركة التدريب |

---

## 📦 بيانات متجر التحالف (المُكتشفة)

الرد على `cmd=1010 subcmd=39`:
```json
{
  "retdata": {
    "selllist": {
      "300201": {"isinsell": true},
      "300701": {"isinsell": true},
      "301501": {"isinsell": true}
    },
    "itemlist": {
      "300103": 6,
      "400301": 30,
      "501301": 6,
      "300201": 283,
      "400401": 17,
      "300102": 3
    }
  }
}
```

### أمر الشراء `cmd=1010 subcmd=40`:
```json
// الطلب:
{"cmd":"1010", "subcmd":"40", "data":{"itemid":300201, "count":1}}

// الرد:
{"data":{"count":1, "itemid":300201}, "err":"0"}
```

---

## 💡 أوامر التبرع للأبحاث

### `cmd=1010 subcmd=48` (التبرع):
```json
// الطلب:
{"cmd":"1010", "subcmd":"48", "data":{"sciid":33012, "donatetype":2}}

// donatetype: 1=ذهب، 2=موارد
// الرد يحتوي: costres, scipoint, honor, score
```

### `cmd=1010 subcmd=81` (حالة التبرعات):
```json
// الرد:
{"donateCount":5, "donateGlodCount":0}
```

---

> ⚠️ **ملاحظة**: الأوامر المعلّمة بـ ✅ تم التحقق منها عبر التقاط حقيقي من الشبكة.
> الباقي مستخرج من الكود المصدري ولم يُختبر بعد.
