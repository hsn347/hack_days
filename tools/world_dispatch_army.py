# -*- coding: utf-8 -*-
"""
world_dispatch_army.py
محاكاة مباشرة 1:1 لمنظومة إرسال وتشكيل الجيش والأبطال والحيوانات الأليفة
المستخرجة من سورس كود اللعبة الأصلي (Lua Source):
- worldDispatchArmyView_dec.lua (WorldDispatchArmyView)
- expeditionTypeltCtrl.lua & expedition_sort.lua (expeditionTypeltCtrl)
- newPetCtrl_dec.lua (newPetCtrl)
- artifactCtrl_dec.lua (artifactCtrl)
- buildLogic_dec.lua (buildLogic)
- mapDef_dec.lua (gMapDispatchArmyType & gMapExpeditionType)
- armyinfo_dec.lua (UNIT_FREE_WEIGHTS & UNIT_SPEEDS)
"""

from typing import Dict, List, Tuple, Any, Optional, Set
import math


# ════════════════════════════════════════════════════════════════════
# 1. ثوابت اللعبة وأنواع الخريطة (Game Constants & Definitions)
# ════════════════════════════════════════════════════════════════════

class gMapObjTypeDef:
    """معرفات أنواع الأهداف على الخريطة (mapDef_dec.lua:7)."""
    mapTypeNone = 0
    mapTypePlain = 1
    mapTypeRivers = 2
    mapTypeStone = 3
    mapObjTypePlayer = 4          # قلاع اللاعبين (Castle)
    mapObjTypeResource = 5        # حقول الموارد (Resource Tile)
    mapObjTypeNpc = 6             # الغزاة / الوحوش (Invaders / Monsters)
    mapObjTypeRelics = 7          # الآثار القديمة (Relics)
    mapObjTypeCampsite = 8        # المعسكرات (Campsite)
    mapObjTypeCastale = 9         # المعاقل الكبرى (Castale)
    mapObjTypeBattery = 10        # البطاريات / الأبراج (Battery)
    mapTypeRef = 11
    mapObjTypeTreasure = 12
    mapObjTypeChest = 13
    mapObjTypeSuperResource = 14  # الموارد الكبرى (Super Resource)
    mapObjTypeBoss = 15           # الزعماء (Boss)
    mapObjTypeEscort = 16
    mapObjTypeBattlefieldSite = 17
    mapObjTypeFortress = 18       # الحصون (Fortress)
    mapObjTypeAllianceBuild = 19  # مباني التحالف (Alliance Building)
    mapTypeTreasureBowl = 20
    mapObjTypeKingdomLevelBuild = 21
    mapObjTypeLegendLord = 22
    mapTypeHeroBattleBoss1 = 23
    mapTypeHeroBattleBoss2 = 24
    mapTypeGodBeast = 25          # الوحش الإلهي (God Beast)
    mapTypeStronghold = 26        # المعاقل (Stronghold)
    mapTypePve = 27
    mapObjTypeRemainsWar = 28
    mapObjNewTrialCity = 29
    mapObjTypeTory = 30
    mapTypeSeaMonsterInvade = 31
    mapTypeRomeAncientRuins = 32
    mapTypeWorshipBull = 33
    mapTypeFamousCity = 34
    mapTypeWildCattleRider = 35
    mapTypeCloudPeakWarBuilding = 36
    mapTypeDragon = 37
    mapTypeLargeResource = 38
    mapTypeNeutralBuild = 39
    mapTypeRadarNpc = 1000
    mapTypeRadarCommon = 1001


class gMapExpeditionType:
    """أنواع الحملات العسكرية في محرك اللعبة (mapDef_dec.lua:686)."""
    all = 1
    formation = 2
    garrison = 3
    plain = 10
    npc = 11                      # هجوم على الوحوش والغزاة
    relics = 12
    castle = 13                   # هجوم على قلعة لاعب
    campsite = 14
    battery = 15
    fortress = 16
    kingdom_build = 17
    boss = 18                     # هجوم على زعيم
    beast = 19                    # هجوم على وحش إلهي
    escort = 20
    plunder_escort = 21
    alliance_build = 22
    help = 23                     # نجدة / إعانة
    collect_wood = 24             # جمع خشب
    collect_food = 25             # جمع قمح
    collect_iron = 26             # جمع حديد
    collect_mithril = 27          # جمع ميثريل
    collect_gold = 28             # جمع ذهب
    stronghold = 29               # هجوم على معقل
    alliance_super_build = 30
    dry_running = 31
    carriage_escort = 32
    new_treasure_escort = 33


class worldMapDefine:
    """أنواع أزرار الخريطة في اللعبة (worldMapDefine_dec.lua)."""
    worldMapTipButtonType_zhanLing = 1
    worldMapTipButtonType_gongJi = 2
    worldMapTipButtonType_zhenCha = 3
    worldMapTipButtonType_xuanZhan = 4
    worldMapTipButtonType_caiji = 5
    worldMapTipButtonType_shibingYuabzhu = 6
    worldMapTipButtonType_ziyuanYuanzhu = 7
    worldMapTipButtonType_xiefang = 8
    worldMapTipButtonType_fanji = 9


# نوع الفرز التلقائي الافتراضي لكل هدف على الخريطة (mapDef_dec.lua:656)
# 1 = الفرز بالرتبة والمستوى (sortArmyListByLv)
# 2 = الفرز بالسرعة (sortArmyListBySpeed)
# 3 = الفرز بالحمولة الحرة (sortArmyListByWeight)
gMapDispatchArmyType: Dict[int, int] = {
    1: 2,   # Plain
    4: 1,   # Castle -> فرز بالمستوى (أعلى رتبة أولاً)
    5: 3,   # Resource -> فرز بالحمولة
    6: 2,   # Monster / NPC -> فرز بالسرعة (الفرسان أولاً)
    7: 2,   # Relics -> فرز بالسرعة
    8: 1,   # Campsite
    9: 1,   # Castale
    10: 1,  # Battery
    12: 2,  # Treasure
    13: 2,  # Chest
}


class gMapMoveLineType:
    """معرفات أنواع خطوط سير الجيوش والمسيرات (mapDef_dec.lua:207)."""
    moveLineTypeAttackLord = 1        # هجوم فردي على قلعة أو وحش
    moveLineTypeScout = 2             # استطلاع
    moveLineTypecapture = 3           # احتلال حقل مورد أو مبنى
    moveLineTypeRelicsExplore = 4     # استكشاف آثار
    moveLineTypeResourceHelp = 5      # مساعدة موارد
    moveLineTypeArmyHelp = 6          # تعزيز جيش حليف
    moveLineTypeMass = 7              # هجوم حشد تحالف (Rally)
    moveLineTypeReturn = 8            # عودة الجيش للقلعة
    moveLineTypeRomanSoul = 9
    moveLineTypeSuperRes = 10         # مورد خارق
    moveLineTypeEscort = 11           # قافلة
    moveLineTypeEscortRob = 12        # نهب قافلة
    moveLineTypeEscortHelp = 13       # مساعدة قافلة
    moveLineTypeDuel = 14             # مبارزة
    moveLineTypeRoseGarden = 18
    moveLineTypeVisit = 19
    moveLineTypeDisinsect = 20
    moveLineTypeAllianceWar = 21
    moveLineTypeSingleTwoCityCamp = 26
    moveLineTypeRadarNpc = 27         # مهام الرادار


class gMapMoveLineMatrixType:
    """مصفوفات تشكيل حركة الفيلق (mapDef_dec.lua:239)."""
    moveLineMatrixTypeTroop = 1       # قوات عسكرية
    moveLineMatrixTypeDetection = 2   # كشافة
    moveLineMatrixTypeCollection = 3  # جمع موارد
    moveLineMatrixTypeTrade = 4       # تجارة / نقل
    moveLineMatrixTypeRomanSoul = 5
    moveLineMatrixTypeChest = 6       # صناديق
    moveLineMatrixTypeEscort = 7
    moveLineMatrixTypeEscortRob = 8
    moveLineMatrixTypeEscortHelp = 9
    moveLineMatrixTypeNewTrial = 11
    moveLineMatrixTypeVisit = 12
    moveLineMatrixTypeDisinsect = 13
    moveLineMatrixTypeWinterWarChest = 14


class gCmdDef:
    """أوامر بروتوكول حزم الخريطة والبحث والهجوم (cmdDef_dec.lua)."""
    CMD_KINGDOM_MAP_MODULE = "1006"
    REQ_KINGDOM_MAP_OBJ_INFO = "15"
    REQ_KINGDOM_MAP_SYNC = "1000"

    CMD_KINGDOM_QUEUE_MODULE = "1007"
    ADD_KINGDOM_QUEUE = "2"
    REQ_BACK_QUEUE = "3"
    REQ_KINGDOM_QUEUE_SPEED_QUEUE = "4"

    CMD_FIND_MONSTER_MODULE = "2011"
    REQ_SEARCH_MAP = "3"
    REQ_FIND_UP_MAX_LV = "4"
    REQ_JUST_DO_FIND_BATTLE_BOSS = "5"



# ════════════════════════════════════════════════════════════════════
# 2. جداول بيانات الوحدات الأصلية (Unit Weights & Speeds from armyinfo_dec.lua)
# ════════════════════════════════════════════════════════════════════

UNIT_FREE_WEIGHTS: Dict[int, int] = {
    # عربات الإمداد (armyType 8)
    701: 20, 703: 21, 705: 22, 707: 27, 709: 28, 711: 30,
    # المنجنيق وعربات الهجوم (armyType 7)
    702: 13, 704: 14, 706: 15, 708: 16, 710: 17, 712: 18,
    # المشاة (Infantry 401..412)
    401: 8, 402: 8, 403: 9, 404: 9, 405: 10, 406: 10,
    407: 11, 408: 11, 409: 12, 410: 12, 411: 13, 412: 13,
    # الفرسان (Cavalry 501..512)
    501: 6, 502: 6, 503: 7, 504: 7, 505: 8, 506: 8,
    507: 9, 508: 9, 509: 10, 510: 10, 511: 11, 512: 11,
    # الرماة (Archers 601..612)
    601: 7, 602: 8, 603: 8, 604: 9, 605: 9, 606: 10,
    607: 10, 608: 11, 609: 11, 610: 12, 611: 12, 612: 13,
}

UNIT_SPEEDS: Dict[int, float] = {
    # المشاة
    401: 9.0, 402: 8.0, 403: 9.0, 404: 8.0, 405: 9.0, 406: 8.0,
    407: 9.0, 408: 8.0, 409: 9.0, 410: 8.0, 411: 9.0, 412: 8.0,
    # الفرسان (الأسرع في اللعبة دائماً)
    501: 13.0, 502: 14.0, 503: 13.0, 504: 14.0, 505: 13.0, 506: 14.0,
    507: 13.0, 508: 14.0, 509: 13.0, 510: 14.0, 511: 13.0, 512: 14.0,
    # الرماة
    601: 8.0, 602: 8.0, 603: 8.0, 604: 8.0, 605: 8.0, 606: 8.0,
    607: 8.0, 608: 8.0, 609: 8.0, 610: 8.0, 611: 8.0, 612: 8.0,
    # الورشة والمنجنيق (الأبطأ في اللعبة)
    701: 5.0, 702: 7.0, 703: 5.0, 704: 7.0, 705: 5.0, 706: 7.0,
    707: 5.0, 708: 7.0, 709: 5.0, 710: 7.0, 711: 5.0, 712: 7.0,
}

# مصفوفة مهارات فرز الأبطال التخصصية لكل نوع حملة (expedition_sort.lua)
EXPEDITION_SORT_CONFIG: Dict[int, Dict[str, Any]] = {
    # 11: هجوم على الوحوش والغزاة (NPC)
    gMapExpeditionType.npc: {
        "sortBuffType": 5900001,
        "sortAtt": 1,  # HERO_WAR
        "sortSkill": [5660001, 5630006, 5660005, 5630008],  # مهارات ضرر وسرعة قتال الوحوش
    },
    # 13: هجوم على قلعة لاعب (Castle)
    gMapExpeditionType.castle: {
        "sortBuffType": 5900001,
        "sortAtt": 1,  # HERO_WAR
        "sortSkill": [],
    },
    # 18: هجوم على زعيم (Boss)
    gMapExpeditionType.boss: {
        "sortBuffType": 5900001,
        "sortAtt": 1,  # HERO_WAR
        "sortSkill": [],
    },
    # 19: هجوم على وحش إلهي (Beast)
    gMapExpeditionType.beast: {
        "sortBuffType": 5900001,
        "sortAtt": 1,  # HERO_WAR
        "sortSkill": [],
    },
    # 24: جمع خشب
    gMapExpeditionType.collect_wood: {
        "sortBuffType": 5900058,
        "sortAtt": 2,  # HERO_DEVELOP
        "sortSkill": [5650007, 5650002, 5650004, 5620002, 5620004, 5620009],
    },
    # 25: جمع قمح
    gMapExpeditionType.collect_food: {
        "sortBuffType": 5900061,
        "sortAtt": 2,  # HERO_DEVELOP
        "sortSkill": [5650007, 5650002, 5650004, 5620002, 5620004, 5620012],
    },
    # 26: جمع حديد
    gMapExpeditionType.collect_iron: {
        "sortBuffType": 5900059,
        "sortAtt": 2,  # HERO_DEVELOP
        "sortSkill": [5650007, 5650002, 5650004, 5620002, 5620004, 5620010],
    },
    # 27: جمع ميثريل
    gMapExpeditionType.collect_mithril: {
        "sortBuffType": 5900060,
        "sortAtt": 2,  # HERO_DEVELOP
        "sortSkill": [5650007, 5650002, 5650004, 5620002, 5620004, 5620011],
    },
    # 28: جمع ذهب
    gMapExpeditionType.collect_gold: {
        "sortBuffType": 5900049,
        "sortAtt": 2,  # HERO_DEVELOP
        "sortSkill": [5650007, 5650002, 5650004, 5620002, 5620004, 5620003],
    },
    # 29: هجوم على معقل (Stronghold)
    gMapExpeditionType.stronghold: {
        "sortBuffType": 5900001,
        "sortAtt": 1,  # HERO_WAR
        "sortSkill": [],
    },
}


# ════════════════════════════════════════════════════════════════════
# 3. دوال فرز وتشكيل القوات (Troop Sorting & Selection from WorldDispatchArmyView)
# ════════════════════════════════════════════════════════════════════

def sortArmyListByLv(armyIDList: List[int]) -> List[int]:
    """
    الفرز حسب المستوى/الرتبة تنازلياً (WorldDispatchArmyView:sortArmyListByLv):
    - الأولوية للمستوى الأعلى (T12 ثم T11 ثم T10..).
    - عند تساوي المستوى: مشاة (4xx) ثم فرسان (5xx) ثم رماة (6xx) ثم ورشة (7xx).
    """
    def _lv_sort_key(army1: int):
        armyID1 = army1 % 1000
        armyLv1 = armyID1 % 100
        return (-armyLv1, armyID1)

    return sorted(armyIDList, key=_lv_sort_key)


def sortArmyListBySpeed(armyIDList: List[int], speeds: Optional[Dict[int, float]] = None) -> List[int]:
    """
    الفرز حسب السرعة تنازلياً (WorldDispatchArmyView:sortArmyListBySpeed):
    - الأولوية للسرعة الأعلى (الفرسان أولاً دائماً).
    - عند تساوي السرعة: المستوى الأعلى أولاً، ثم المعرف تصاعدياً.
    """
    speed_map = speeds or UNIT_SPEEDS

    def _speed_sort_key(army1: int):
        speed1 = speed_map.get(army1, 8.0)
        armyID1 = army1 % 1000
        armyLv1 = armyID1 % 100
        return (-speed1, -armyLv1, armyID1)

    return sorted(armyIDList, key=_speed_sort_key)


def sortArmyListByWeight(armyIDList: List[int], weights: Optional[Dict[int, int]] = None) -> List[int]:
    """
    الفرز حسب سعة الحمولة الحرة (WorldDispatchArmyView:sortArmyListByWeight):
    - الأولوية المطلقة لعربة المستوى 1 (701) أولاً دائماً.
    - ثم باقي الوحدات تنازلياً حسب الحمولة الحرة (freeWeight).
    - عند تساوي الحمولة: المستوى الأعلى أولاً، ثم المعرف تصاعدياً.
    """
    weight_map = weights or UNIT_FREE_WEIGHTS

    def _weight_sort_key(army1: int):
        if army1 == 701:
            return (0, 0, 0, 0)
        weight1 = weight_map.get(army1, 0)
        armyID1 = army1 % 1000
        armyLv1 = armyID1 % 100
        return (1, -weight1, -armyLv1, armyID1)

    return sorted(armyIDList, key=_weight_sort_key)


def getArmyListBySelectedType(
    selectType: int,
    armyIDList: List[int],
    speeds: Optional[Dict[int, float]] = None,
    weights: Optional[Dict[int, int]] = None
) -> List[int]:
    """
    توجيه فرز القوات حسب خيار الفرز المحدد (WorldDispatchArmyView:getArmyListBySelectedType):
    1 = الرتبة/المستوى (sortArmyListByLv)
    2 = السرعة (sortArmyListBySpeed)
    3 = سعة الحمولة (sortArmyListByWeight)
    """
    if selectType == 1:
        return sortArmyListByLv(armyIDList)
    elif selectType == 2:
        return sortArmyListBySpeed(armyIDList, speeds=speeds)
    elif selectType == 3:
        return sortArmyListByWeight(armyIDList, weights=weights)
    return armyIDList


def setCurValByArmyid(
    tableArmyData: Dict[int, Dict[str, Any]],
    cur_state: Dict[str, int],
    allCount: int,
    armyid: int,
    curCount: int
) -> int:
    """
    تعيين عدد القوات لوحدة معينة مع كبح السقف الإجمالي (WorldDispatchArmyView:setCurValByArmyid).
    """
    armyData = tableArmyData.get(armyid)
    if not armyData:
        return 0

    max_avail = int(armyData.get("armycount", 0))
    if curCount > max_avail:
        return 0

    curArmyCount = cur_state.get("curCount", 0)
    existing_cur = int(armyData.get("curCount", 0))
    if existing_cur > 0:
        curArmyCount -= existing_cur
        if curArmyCount < 0:
            return 0

    # كبح العدد بسقف سعة المسيرة القصوى (allCount)
    if (curArmyCount + curCount > allCount) and (curCount > 0):
        curCount = allCount - curArmyCount

    armyData["curCount"] = curCount
    cur_state["curCount"] = curArmyCount + curCount
    return curCount


def setCurValMax(
    tableArmyData: Dict[int, Dict[str, Any]],
    cur_state: Dict[str, int],
    allCount: int,
    armyid: int
) -> int:
    """
    ملء الوحدة بالحد الأقصى المتاح حتى اكتمال السعة (WorldDispatchArmyView:setCurValMax).
    """
    armyData = tableArmyData.get(armyid, {})
    armyMax = int(armyData.get("armycount", 0))
    return setCurValByArmyid(tableArmyData, cur_state, allCount, armyid, armyMax)


def quickChoose(
    isFull: bool,
    instanceType: int,
    dispatchType: int,
    otherData: Dict[str, Any],
    tableArmy: List[int],
    tableArmyData: Dict[int, Dict[str, Any]],
    allCount: int,
    addWeight: float = 1.0
) -> Tuple[List[Dict[str, int]], int]:
    """
    دالة الاختيار السريع والتعبئة التلقائية (WorldDispatchArmyView:quickChoose):
    - للهجوم (قلاع، وحوش، معاقل، حصون): تملأ المقاعد تنازلياً حتى اكتمال سعة المسيرة (allCount).
    - لجمع الموارد: تحسب مضاعف المورد وتأخذ العدد المطلوب بدقة السقف (math.ceil).
    """
    cur_state = {"curCount": 0}

    # إعادة تصفير القوات
    for v in tableArmyData.values():
        v["curCount"] = 0

    if not isFull:
        return [], 0

    # 🌾 1. فرع جمع الموارد
    if (dispatchType == worldMapDefine.worldMapTipButtonType_zhanLing and
            instanceType == gMapObjTypeDef.mapObjTypeResource):
        res_type = int(otherData.get("resourceType", 1002))
        multiple = 1000.0 if res_type in (1001, 1006) else (6.0 if res_type == 1004 else (24.0 if res_type == 1005 else 1.0))
        curResCount = float(otherData.get("currentSourceNum", 0)) * multiple

        for armyid in tableArmy:
            data = tableArmyData.get(armyid)
            if data and curResCount > 0:
                armyWeight = float(data.get("weight", 10)) * addWeight
                armyCount = min(data["armycount"], math.ceil(curResCount / armyWeight))
                actual_added = setCurValByArmyid(tableArmyData, cur_state, allCount, armyid, armyCount)
                curResCount = max(0.0, curResCount - actual_added * armyWeight)
                if cur_state["curCount"] >= allCount:
                    break
    else:
        # ⚔️ 2. فرع الهجوم العام على أي هدف حربي في الخريطة
        for armyid in tableArmy:
            setCurValMax(tableArmyData, cur_state, allCount, armyid)
            if cur_state["curCount"] >= allCount:
                break

    dispatch_list = [
        {"id": v["armyid"], "num": v["curCount"]}
        for v in tableArmyData.values()
        if v.get("curCount", 0) > 0
    ]
    return dispatch_list, cur_state["curCount"]


# ════════════════════════════════════════════════════════════════════
# 4. دوال فرز واختيار الأبطال (Hero Selection from expeditionTypeltCtrl & WorldDispatchArmyView)
# ════════════════════════════════════════════════════════════════════

def initExpType(
    instanceType: int,
    dispatchType: int = 2,
    otherData: Optional[dict] = None,
    massInstanceType: Optional[int] = None
) -> int:
    """
    تحديد نوع الحملة العسكرية بناءً على الهدف (WorldDispatchArmyView:initExpType / lines 1070-1118).
    """
    otherData = otherData or {}
    if dispatchType in (worldMapDefine.worldMapTipButtonType_xiefang, worldMapDefine.worldMapTipButtonType_shibingYuabzhu):
        return gMapExpeditionType.help

    if massInstanceType in (gMapObjTypeDef.mapObjTypeBoss, gMapObjTypeDef.mapTypeHeroBattleBoss1, gMapObjTypeDef.mapTypeHeroBattleBoss2):
        return gMapExpeditionType.boss

    if massInstanceType == gMapObjTypeDef.mapTypeGodBeast or instanceType == gMapObjTypeDef.mapTypeGodBeast:
        return gMapExpeditionType.beast

    if instanceType in (gMapObjTypeDef.mapObjTypeNpc, gMapObjTypeDef.mapTypeRadarNpc):
        return gMapExpeditionType.npc

    if dispatchType == worldMapDefine.worldMapTipButtonType_caiji or instanceType == gMapObjTypeDef.mapObjTypeResource:
        rtype = otherData.get("resourceType")
        if rtype == 1003: return gMapExpeditionType.collect_wood
        elif rtype == 1002: return gMapExpeditionType.collect_food
        elif rtype == 1004: return gMapExpeditionType.collect_iron
        elif rtype == 1005: return gMapExpeditionType.collect_mithril
        elif rtype in (1001, 1006): return gMapExpeditionType.collect_gold
        return gMapExpeditionType.collect_wood

    if instanceType == gMapObjTypeDef.mapObjTypePlayer:
        return gMapExpeditionType.castle

    if instanceType in (gMapObjTypeDef.mapTypeStronghold, gMapObjTypeDef.mapTypePve):
        return gMapExpeditionType.stronghold

    if instanceType == gMapObjTypeDef.mapObjTypeFortress:
        return gMapExpeditionType.fortress

    if instanceType == gMapObjTypeDef.mapObjTypeBattery:
        return gMapExpeditionType.battery

    return gMapExpeditionType.plain


def _specialSkillWeights(expType: int, hero: dict) -> int:
    """حساب عدد مهارات البطل المتطابقة مع مصفوفة فرز الحملة (expeditionTypeltCtrl.specialSkillWeights)."""
    cfg = EXPEDITION_SORT_CONFIG.get(expType, {})
    special_skills = set(cfg.get("sortSkill", []))
    if not special_skills:
        return 0

    skills = hero.get("skillList", {})
    sids = []
    if isinstance(skills, dict):
        for s in skills.values():
            if isinstance(s, dict) and s.get("id"):
                try: sids.append(int(s["id"]))
                except Exception: pass
    elif isinstance(skills, list):
        for s in skills:
            if isinstance(s, dict) and s.get("id"):
                try: sids.append(int(s["id"]))
                except Exception: pass

    return sum(1 for sid in sids if sid in special_skills)


def _attrAdditionWeights(expType: int, hero: dict) -> int:
    """حساب مستوى مهارة المورد أو الهدف التخصصية (expeditionTypeltCtrl.attrAdditionWeights)."""
    cfg = EXPEDITION_SORT_CONFIG.get(expType, {})
    special_skills = cfg.get("sortSkill", [])
    if not special_skills:
        return 0
    target_skill = special_skills[-1]

    skills = hero.get("skillList", {})
    if isinstance(skills, dict):
        for s in skills.values():
            if isinstance(s, dict) and s.get("id") == target_skill:
                try: return int(s.get("lv", 1))
                except Exception: pass
    return 0


def _attrValueWeights(expType: int, hero: dict) -> int:
    """
    جلب القوة الأساسية للبطل حسب نوع الحملة (expeditionTypeltCtrl.attrValueWeights):
    - للحرب (sortAtt == 1): يعتمد على قوة الحرب الأساسية (المستوى والنجوم والرتبة).
    - للتنمية (sortAtt == 2): يعتمد على قوة التنمية الأساسية.
    """
    lv = int(hero.get("level") or hero.get("lv") or 1)
    star = int(hero.get("star") or 0)
    stage = int(hero.get("stage") or 0)
    return lv * 1000 + star * 100 + stage


def sortHeros(expType: int, heroList: List[dict]) -> List[int]:
    """
    الفرز الهرمي الصارم للأبطال بمعادلة الأوزان الدقيقة (expeditionTypeltCtrl.sortHeros):
    va = p0 * specialWeights + p1 * additionWeights + p2 * valueWeights + (6000000 - aId)
    """
    maxHeroId = 6000000

    def _hero_sort_key(hero: dict):
        try: hid = int(hero.get("id", 0))
        except Exception: hid = 0

        sp_w = _specialSkillWeights(expType, hero)
        add_w = _attrAdditionWeights(expType, hero)
        val_w = _attrValueWeights(expType, hero)
        tie_breaker = maxHeroId - hid
        return (sp_w, add_w, val_w, tie_breaker)

    sorted_heroes = sorted(heroList, key=_hero_sort_key, reverse=True)
    return [int(h["id"]) for h in sorted_heroes if "id" in h]


def initHeroData(allHeros: List[dict], expType: int) -> Tuple[List[int], List[int]]:
    """
    تصفية أبطال المعارك، وفرز الأبطال، وعزل أبطال الحامية للذيل (WorldDispatchArmyView:initHeroData).
    """
    curHeroList = []
    for h in allHeros:
        # استبعاد أبطال المعارك الحية (state == 1 / battle)
        state = h.get("status", {}).get("state", 0) if isinstance(h.get("status"), dict) else 0
        if state != 1:
            curHeroList.append(h)

    # فرز الأبطال حسب معايير نوع الحملة
    curHeroIdList = sortHeros(expType, curHeroList)

    # عزل أبطال الحامية (state == 2 / garrison)
    hero_map = {int(h["id"]): h for h in curHeroList if "id" in h}
    non_garrison: List[int] = []
    garrison: List[int] = []

    for hid in curHeroIdList:
        hero = hero_map.get(hid, {})
        state = hero.get("status", {}).get("state", 0) if isinstance(hero.get("status"), dict) else 0
        if state == 2:
            garrison.append(hid)
        else:
            non_garrison.append(hid)

    # تجميع القائمة بحيث يأتي أبطال الحامية في نهاية القائمة
    full_ordered = non_garrison + garrison
    return full_ordered, garrison


def autoSelectHeros(curHeroIdList: List[int], garrisonHeroList: List[int], max_heroes: int = 2) -> List[int]:
    """
    الاختيار التلقائي النهائي لأفضل بطلين متاحين خارج الحامية (WorldDispatchArmyView:autoSelectHeros).
    """
    garrison_set = set(garrisonHeroList)
    selected = []
    for hid in curHeroIdList[:max_heroes]:
        if hid not in garrison_set:
            selected.append(hid)
    return selected


# ════════════════════════════════════════════════════════════════════
# 5. دوال الحيوان الأليف والتميمة (Pet & Artifact Selection)
# ════════════════════════════════════════════════════════════════════

def getBestPetId(pets_data: Dict[str, Any]) -> Optional[int]:
    """
    اختيار الحيوان الأليف الأقوى والأعلى معرفاً (newPetCtrl:getBestPetId):
    table.sort(petList, function(a, b) return a.id > b.id end)
    """
    if not pets_data:
        return None

    pet_ids = []
    for pid_str in pets_data.keys():
        try:
            pet_ids.append(int(pid_str))
        except Exception:
            continue

    if not pet_ids:
        return None

    # فرز تنازلي حسب المعرف (الأعلى معرفاً هو الأحدث والأقوى)
    pet_ids.sort(reverse=True)
    return pet_ids[0]


def getPageIndexHasMaxPower(artifact_data: Dict[str, Any]) -> int:
    """
    اختيار صفحة التميمة/الرون ذات القوة الأعلى (artifactCtrl:getPageIndexHasMaxPower).
    """
    if not artifact_data or not isinstance(artifact_data, dict):
        return 1
    # افتراضي الصفحة 1 أو الصفحة النشطة
    return int(artifact_data.get("curPageIndex", artifact_data.get("activePage", 1)))


# ════════════════════════════════════════════════════════════════════
# 6. الدالة الموحدة الشاملة لمحاكاة الواجهة (Unified Dispatch Simulation)
# ════════════════════════════════════════════════════════════════════

def simulate_world_dispatch(
    init_data: dict,
    instanceType: int,
    toPoint: Dict[str, int],
    dispatchType: int = 2,
    otherData: Optional[dict] = None,
    massInstanceType: Optional[int] = None,
    busy_heroes: Optional[Set[int]] = None,
    used_army: Optional[Dict[int, int]] = None,
    allCount: Optional[int] = None,
) -> Dict[str, Any]:
    """
    محاكاة متكاملة 100% لواجهة إرسال فيلق اللعبة (WorldDispatchArmyView:initData):
    تقوم بتوليد التشكيلة كاملة (جنود، أبطال، حيوان، تميمة، سعة) مباشرة من الذاكرة الحية (RAM) بصفر طلبات شبكة.
    """
    otherData = otherData or {}
    busy_heroes = busy_heroes or set()
    used_army = used_army or {}

    # 1. تحديد نوع الحملة ونوع الفرز
    expType = initExpType(instanceType, dispatchType=dispatchType, otherData=otherData, massInstanceType=massInstanceType)
    selectType = gMapDispatchArmyType.get(instanceType, 1)

    # 2. استخراج وفلترة الأبطال
    raw_heroes = init_data.get("heroCtrl") or {}
    heroes_list: List[dict] = []
    if isinstance(raw_heroes, dict):
        hlist = raw_heroes.get("heroList", raw_heroes.get("heroMap", {}))
        if isinstance(hlist, dict):
            heroes_list = list(hlist.values())
        elif isinstance(hlist, list):
            heroes_list = hlist
    elif isinstance(raw_heroes, list):
        heroes_list = raw_heroes

    # استبعاد المشغولين محلياً
    available_heroes = [h for h in heroes_list if isinstance(h, dict) and int(h.get("id", 0)) not in busy_heroes]
    ordered_hero_ids, garrison_ids = initHeroData(available_heroes, expType)
    chosen_heroes = autoSelectHeros(ordered_hero_ids, garrison_ids, max_heroes=2)

    # 3. اختيار الحيوان الأليف
    pet_ctrl = init_data.get("petCtrl") or {}
    pets_data = pet_ctrl.get("pets", {}) if isinstance(pet_ctrl, dict) else {}
    chosen_pet = getBestPetId(pets_data)

    # 4. اختيار التميمة
    art_data = init_data.get("artifactCtrl") or {}
    chosen_rune = getPageIndexHasMaxPower(art_data)

    # 5. حساب سعة المسيرة القصوى (allCount)
    if not allCount:
        try:
            from tasks.march_capacity import get_castle_march_capacity
            allCount = get_castle_march_capacity(init_data, chosen_heroes=chosen_heroes)
        except Exception:
            allCount = 50000

    # 6. جلب قوات القلعة المتاحة بعد خصم المستخدم
    army_ctrl = init_data.get("armyCtrl") or {}
    total_army = army_ctrl.get("totalArmy", {}) if isinstance(army_ctrl, dict) else {}
    available_troops: Dict[int, int] = {}
    if isinstance(total_army, dict):
        for k, v in total_army.items():
            try:
                tid = int(k)
                cnt = int(v)
                cnt -= used_army.get(tid, 0)
                if cnt > 0 and tid < 800:  # استبعاد الفخاخ
                    available_troops[tid] = cnt
            except Exception:
                pass

    # 7. فرز القوات حسب selectType
    armyIDList = list(available_troops.keys())
    sorted_army_ids = getArmyListBySelectedType(selectType, armyIDList)

    # 8. بناء مصفوفة tableArmyData
    tableArmyData: Dict[int, Dict[str, Any]] = {}
    for tid in sorted_army_ids:
        tableArmyData[tid] = {
            "armyid": tid,
            "armycount": available_troops[tid],
            "curCount": 0,
            "weight": UNIT_FREE_WEIGHTS.get(tid, 10),
            "speed": UNIT_SPEEDS.get(tid, 8.0)
        }

    # 9. تشغيل دالة التعبئة التلقائية (quickChoose)
    dispatch_army, total_selected = quickChoose(
        isFull=True,
        instanceType=instanceType,
        dispatchType=dispatchType,
        otherData=otherData,
        tableArmy=sorted_army_ids,
        tableArmyData=tableArmyData,
        allCount=allCount,
        addWeight=1.0
    )

    return {
        "expType": expType,
        "selectType": selectType,
        "allCount": allCount,
        "heros": chosen_heroes,
        "pets": [chosen_pet] if chosen_pet else [],
        "runePages": [chosen_rune] if chosen_rune else [],
        "armyList": dispatch_army,
        "total_troops": total_selected,
        "toPoint": toPoint,
    }


# ════════════════════════════════════════════════════════════════════
# 7. دوال المسافة وسرعة الفيلق وزمن السير (Distance & Travel Time)
# ════════════════════════════════════════════════════════════════════

def getTwoPointDistance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    حساب المسافة الإقليدية المستقيمة بين نقطتين على الخريطة (serviceFunctions.getTwoPointDistance).
    math.sqrt((x1 - x2)^2 + (y1 - y2)^2)
    """
    return math.sqrt((float(x1) - float(x2)) ** 2 + (float(y1) - float(y2)) ** 2)


def getMapDistance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    حساب مسافة المسار على خريطة اللعبة بالمربعات الموسعة (serviceFunctions.getMapDistance).
    getTwoPointDistance * 100
    """
    return getTwoPointDistance(x1, y1, x2, y2) * 100.0


def getArmyBaseMoveSpeed(
    lstArmy: List[Dict[str, int]],
    fromPoint: Dict[str, Any],
    toPoint: Dict[str, Any],
    mapObjType: int = 6,
    worldMapTipButtonType: int = 2,
    tipButtonType: Optional[int] = None,
    **kwargs
) -> float:
    """
    حساب السرعة الأساسية للفيلق مع تطبيق قاعدة الوحدة الأبطأ ومعامل تصحيح المسافة:
    (queueTimeUtil.getArmyBaseMoveSpeed / lines 298-319).
    """
    tip_type = worldMapTipButtonType if tipButtonType is None else tipButtonType
    speed = 0.0
    if tip_type == worldMapDefine.worldMapTipButtonType_zhenCha:
        speed = 20.0  # gScoutMoveSpeed
    elif tip_type == worldMapDefine.worldMapTipButtonType_ziyuanYuanzhu:
        speed = 10.0  # gResourceHelpMoveSpeed
    elif lstArmy:
        # قاعدة الوحدة الأبطأ: سرعة الجيش محكومة بأبطأ وحدة موجودة
        for item in lstArmy:
            aid = int(item.get("id", 0))
            army_speed = UNIT_SPEEDS.get(aid, 8.0)
            if speed == 0.0 or speed > army_speed:
                speed = army_speed

    if speed == 0.0:
        speed = 8.0

    # معامل تصحيح المسافة (y = (1100 + s) / 1100)
    s = getTwoPointDistance(fromPoint.get("x", 0), fromPoint.get("y", 0), toPoint.get("x", 0), toPoint.get("y", 0))
    y = (1100.0 + s) / 1100.0
    return speed * y


def getArmyMoveTime(
    lstArmy: List[Dict[str, int]],
    fromPoint: Dict[str, Any],
    toPoint: Dict[str, Any],
    mapObjType: int = 6,
    worldMapTipButtonType: int = 2,
    tipButtonType: Optional[int] = None,
    allPlus: float = 0.0,
    quickSkillPlus: float = 0.0,
    **kwargs
) -> int:
    """
    حساب زمن وصول المسيرة بالثواني بدقة سورس اللعبة (queueTimeUtil.getArmyBaseMoveTime).
    totalTime = math.ceil(moveDistance / speed)
    """
    tip_type = worldMapTipButtonType if tipButtonType is None else tipButtonType
    base_speed = getArmyBaseMoveSpeed(lstArmy, fromPoint, toPoint, mapObjType, tip_type, **kwargs)
    final_speed = base_speed * (1.0 + allPlus / 1000.0) * (1.0 + quickSkillPlus / 1000.0)
    if final_speed <= 0:
        final_speed = 8.0

    moveDistance = getMapDistance(fromPoint.get("x", 0), fromPoint.get("y", 0), toPoint.get("x", 0), toPoint.get("y", 0))
    totalTime = math.ceil(moveDistance / final_speed)
    return max(1, int(totalTime))


# ════════════════════════════════════════════════════════════════════
# 8. منظومة البحث عن الأهداف في الخريطة (Target Search System)
# ════════════════════════════════════════════════════════════════════

def getPlayerMapQueueDPoint(init_data: dict) -> Dict[str, Any]:
    """
    استخراج معرفات وإحداثيات الأهداف المستهدفة حالياً من مسيرات اللاعب النشطة
    (worldMapMonsterSearch:getPlayerMapQueueDPoint / lines 715-725)
    لمنع تكرار الهجوم على نفس الوحش أو المورد.
    """
    exclude_ids = {}
    queues = init_data.get("local_queues", {})
    if isinstance(queues, dict):
        for qid, q in queues.items():
            if isinstance(q, dict):
                to_data = q.get("to") or {}
                target_id = to_data.get("id") or to_data.get("target_id")
                if target_id:
                    exclude_ids[str(target_id)] = True
    elif isinstance(queues, list):
        for q in queues:
            if isinstance(q, dict):
                to_data = q.get("to") or {}
                target_id = to_data.get("id") or to_data.get("target_id")
                if target_id:
                    exclude_ids[str(target_id)] = True
    return exclude_ids


def build_search_map_packet(
    x: int,
    y: int,
    mapType: int = gMapObjTypeDef.mapObjTypeNpc,
    minLv: int = 1,
    maxLv: int = 1,
    subType: int = 0,
    exclude: Optional[Dict[str, Any]] = None,
    range_val: int = 100,
    quickjump: bool = False
) -> Dict[str, Any]:
    """
    بناء حزمة البحث عن الأهداف في الخريطة (findMonsterCtrl:sendFind / lines 21-40):
    cmd = 2011, subcmd = 3 (REQ_SEARCH_MAP)
    """
    return {
        "cmd": gCmdDef.CMD_FIND_MONSTER_MODULE,
        "subcmd": gCmdDef.REQ_SEARCH_MAP,
        "data": {
            "x": int(x),
            "y": int(y),
            "mapType": int(mapType),
            "num": 1,
            "minLv": int(minLv),
            "maxLv": int(maxLv),
            "subType": int(subType),
            "exclude": exclude or {},
            "range": int(range_val),
            "quickjump": quickjump
        }
    }


async def search_world_map_target(
    conn: Any,
    x: int,
    y: int,
    mapType: int = gMapObjTypeDef.mapObjTypeNpc,
    minLv: int = 1,
    maxLv: int = 1,
    subType: int = 0,
    exclude: Optional[Dict[str, Any]] = None,
    range_val: int = 100
) -> Optional[Dict[str, Any]]:
    """
    إرسال طلب البحث عن هدف إلى سيرفر اللعبة واستقبال الإحداثيات والمعرف (findMonsterCtrl:getFindRsp).
    يعيد: {"x": point.x, "y": point.y, "id": point.id} أو None عند عدم توفر هدف.
    """
    if exclude is None and hasattr(conn, "init_data"):
        exclude = getPlayerMapQueueDPoint(conn.init_data)

    packet = build_search_map_packet(
        x=x, y=y, mapType=mapType, minLv=minLv, maxLv=maxLv,
        subType=subType, exclude=exclude, range_val=range_val
    )

    resp = await conn.query(packet["cmd"], packet["subcmd"], packet["data"])
    if not resp or resp.get("err", 0) != 0:
        return None

    result = resp.get("result", {})
    if isinstance(result, dict) and result:
        first_item = next(iter(result.values()))
        if isinstance(first_item, dict) and "x" in first_item and "y" in first_item:
            return {
                "x": int(first_item["x"]),
                "y": int(first_item["y"]),
                "id": first_item.get("id", f"{first_item['x']}-{first_item['y']}")
            }
    return None


# ════════════════════════════════════════════════════════════════════
# 9. فحص الهدف وبناء حزمة الهجوم (Target Inspection & March Dispatch)
# ════════════════════════════════════════════════════════════════════

def build_map_obj_info_packet(x: int, y: int, id_val: Any, kingdomId: int = 0) -> Dict[str, Any]:
    """
    بناء حزمة استعلام وفحص بيانات الهدف على الخريطة (kingdomMapCtrl:reqMapObjInfo):
    cmd = 1006, subcmd = 15 (REQ_KINGDOM_MAP_OBJ_INFO)
    """
    return {
        "cmd": gCmdDef.CMD_KINGDOM_MAP_MODULE,
        "subcmd": gCmdDef.REQ_KINGDOM_MAP_OBJ_INFO,
        "data": {
            "x": int(x),
            "y": int(y),
            "id": str(id_val),
            "kingdomId": int(kingdomId)
        }
    }


async def req_map_obj_info(conn: Any, x: int, y: int, id_val: Any, kingdomId: int = 0) -> Optional[Dict[str, Any]]:
    """
    إرسال استعلام فحص الهدف واستقبال تفاصيله (نسبة الصحة، الحماية، المكافآت).
    """
    if kingdomId == 0 and hasattr(conn, "kingdom_id"):
        kingdomId = getattr(conn, "kingdom_id", 0)

    packet = build_map_obj_info_packet(x, y, id_val, kingdomId)
    resp = await conn.query(packet["cmd"], packet["subcmd"], packet["data"])
    if resp and resp.get("err", 0) == 0:
        return resp.get("retData")
    return None


def worldMapFunction_gotoDispatch(
    dispatch_result: Dict[str, Any],
    instanceID: Optional[str] = None,
    dispatchType: int = 2,
    mapId: int = 0,
    otherData: Optional[dict] = None
) -> Dict[str, Any]:
    """
    بناء حزمة إرسال المسيرة الكاملة (worldMapFunction.gotoDispatch / lines 337-473):
    تحدد نوع خط السير (moveLineType) ونوع المصفوفة (matrixType) وهيكل الإرسال للسيرفر (1007/2).
    """
    toPoint = dispatch_result.get("toPoint", {"x": 0, "y": 0})
    otherData = otherData or {}

    # تحديد نوع خط السير وفق نوع الإرسال والهدف
    if dispatchType in (worldMapDefine.worldMapTipButtonType_gongJi, worldMapDefine.worldMapTipButtonType_fanji):
        moveLineType = gMapMoveLineType.moveLineTypeAttackLord
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeTroop
    elif dispatchType == worldMapDefine.worldMapTipButtonType_zhanLing:
        moveLineType = gMapMoveLineType.moveLineTypecapture
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeTroop
    elif dispatchType == worldMapDefine.worldMapTipButtonType_caiji:
        moveLineType = gMapMoveLineType.moveLineTypeSuperRes
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeCollection
    elif dispatchType == worldMapDefine.worldMapTipButtonType_zhenCha:
        moveLineType = gMapMoveLineType.moveLineTypeScout
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeDetection
    elif dispatchType in (worldMapDefine.worldMapTipButtonType_shibingYuabzhu, worldMapDefine.worldMapTipButtonType_xiefang):
        moveLineType = gMapMoveLineType.moveLineTypeArmyHelp
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeTroop
    elif dispatchType == worldMapDefine.worldMapTipButtonType_xuanZhan:
        moveLineType = gMapMoveLineType.moveLineTypeMass
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeTroop
    else:
        moveLineType = gMapMoveLineType.moveLineTypeAttackLord
        matrixType = gMapMoveLineMatrixType.moveLineMatrixTypeTroop

    moveLineData = {
        "moveLineType": moveLineType,
        "matrixType": matrixType,
        "data": {
            "to": {
                "x": int(toPoint["x"]),
                "y": int(toPoint["y"]),
                "id": str(instanceID or f"{toPoint['x']}-{toPoint['y']}")
            },
            "data": otherData,
            "army": dispatch_result.get("armyList", [])
        },
        "heros": dispatch_result.get("heros", []),
        "runePages": dispatch_result.get("runePages", [1]),
        "pets": dispatch_result.get("pets", []),
        "mapId": int(mapId)
    }

    return {
        "cmd": gCmdDef.CMD_KINGDOM_QUEUE_MODULE,
        "subcmd": gCmdDef.ADD_KINGDOM_QUEUE,
        "data": moveLineData
    }


async def req_march(conn: Any, march_packet: Dict[str, Any]) -> Dict[str, Any]:
    """
    إرسال حزمة الهجوم/المسيرة إلى سيرفر اللعبة (kingdomMapCtrl:reqMarch / ADD_KINGDOM_QUEUE 1007/2).
    """
    cmd = march_packet.get("cmd", gCmdDef.CMD_KINGDOM_QUEUE_MODULE)
    subcmd = march_packet.get("subcmd", gCmdDef.ADD_KINGDOM_QUEUE)
    data = march_packet.get("data", {})
    return await conn.query(cmd, subcmd, data)


# ════════════════════════════════════════════════════════════════════
# 10. دورة الهجوم المتكاملة (End-to-End Complete Attack Pipeline)
# ════════════════════════════════════════════════════════════════════

async def execute_full_attack_chain(
    conn: Any,
    instanceType: int = gMapObjTypeDef.mapObjTypeNpc,
    target_point: Optional[Dict[str, int]] = None,
    minLv: int = 1,
    maxLv: int = 1,
    send_march: bool = False
) -> Dict[str, Any]:
    """
    سلسلة الهجوم الكاملة من البداية حتى النهاية (End-to-End Complete Attack Pipeline):
    1. البحث عن الهدف الأقرب في الخريطة (Search Map 2011/3) إذا لم تُحدد إحداثيات صريحة.
    2. محاكاة تشكيل الفيلق الأنسب للهدف (simulate_world_dispatch 0ms).
    3. حساب المسافة وسرعة الفيلق وزمن السير (getArmyMoveTime).
    4. بناء حزمة خط السير الرسمية للعبة (worldMapFunction_gotoDispatch).
    5. إرسال حزمة الهجوم (1007/2) إذا طُلب ذلك (send_march=True).
    """
    init_data = conn.init_data if hasattr(conn, "init_data") else {}
    city_pos = getattr(conn, "castle_pos", {"x": 384, "y": 314})
    if hasattr(conn, "init_data") and "cityCtrl" in conn.init_data:
        city_ctrl = conn.init_data.get("cityCtrl", {})
        if isinstance(city_ctrl, dict):
            city_pos = {
                "x": city_ctrl.get("posX", city_pos.get("x", 384)),
                "y": city_ctrl.get("posY", city_pos.get("y", 314))
            }

    # 1. البحث عن الهدف إن لم يكن محدداً
    target = target_point
    if not target:
        found = await search_world_map_target(
            conn=conn,
            x=city_pos["x"],
            y=city_pos["y"],
            mapType=instanceType,
            minLv=minLv,
            maxLv=maxLv
        )
        if not found:
            return {"success": False, "error": "No target found on map"}
        target = {"x": found["x"], "y": found["y"]}
        instance_id = found.get("id")
    else:
        instance_id = f"{target['x']}-{target['y']}"

    # 2. محاكاة التشكيلة
    dispatch_res = simulate_world_dispatch(
        init_data=init_data,
        instanceType=instanceType,
        toPoint=target,
        dispatchType=2
    )

    # 3. حساب زمن المسيرة
    march_seconds = getArmyMoveTime(
        lstArmy=dispatch_res.get("armyList", []),
        fromPoint=city_pos,
        toPoint=target,
        mapObjType=instanceType,
        tipButtonType=2
    )
    dispatch_res["estimated_march_time"] = march_seconds

    # 4. بناء حزمة الهجوم
    map_id = getattr(conn, "kingdom_id", 0)
    march_packet = worldMapFunction_gotoDispatch(
        dispatch_result=dispatch_res,
        instanceID=instance_id,
        dispatchType=2,
        mapId=map_id
    )

    result = {
        "success": True,
        "target": target,
        "instance_id": instance_id,
        "formation": dispatch_res,
        "march_packet": march_packet,
        "march_time_seconds": march_seconds,
        "sent": False
    }

    # 5. إرسال الهجوم إن كان مطلوباً
    if send_march:
        march_rsp = await req_march(conn, march_packet)
        result["sent"] = True
        result["march_response"] = march_rsp

    return result

