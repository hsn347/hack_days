# Lua Protocol & Notification Specification Reference
**Document Version**: 1.0.0  
**Author**: Agent 1 (Lua Protocol & Notify Analyst)  
**Primary Sources**:
- `game file/lua_src/cmdDef_dec.lua`
- `game file/lua_src/notifyIDDef_dec.lua`
- `game file/lua_src/notifyCtrl_dec.lua`
- `game file/lua_src/cityCtrl_dec.lua`, `cityCell_dec.lua`, `buildCell_dec.lua`
- `game file/lua_src/queueCtrl_dec.lua`, `queueTypeDef_dec.lua`
- `game file/lua_src/kingdomMapCtrl_dec.lua`, `mapDef_dec.lua`
- `game file/lua_src/armyCtrl_dec.lua`
- `game file/lua_src/heroCtrl_dec.lua`, `heroMgr_dec.lua`
- `game file/lua_src/lordInfoCtrl_dec.lua`, `lordAuxiliary_dec.lua`
- `game file/lua_src/buffCtrl_dec.lua`
- `game file/lua_src/backpackCtrl_dec.lua`
- `game file/lua_src/meritCtrl_dec.lua`
- `game file/lua_src/timeRewardCtrl_dec.lua`
- `game file/lua_src/loginDataInitCtrl_dec.lua`

---

## 1. Executive Protocol & Notification Architecture

### 1.1 Server-to-Client Notification Channel (CMD 1009)
The game server delivers all asynchronous real-time events and state delta pushes via command **`1009`** (`gCmd.CMD_NOTIFY_MODULE`).
When a packet with `cmd = "1009"` is received from the TCP stream:
- `content.err`: Error code (`0` indicates success / valid push).
- `content.data.notifyID`: String or numeric identifier corresponding to `gNotifyID`.
- `content.data.notifyData`: Payload object containing the event-specific data table.

### 1.2 Dispatching Engine (`notifyCtrl.lua`)
In Lua, `notifyCtrl` registers handlers on `(cmd = 1009, subcmd)` for every configured notification:
```lua
local function notifyRsp(self, content)
  if content.err == gErrDef.Err_None then
    local notifyID = tostring(content.data.notifyID)
    self:dispatchEvent({
      name = notifyID,
      data = content.data.notifyData
    })
  end
end
```
Each functional controller (such as `cityCtrl`, `queueCtrl`, `armyCtrl`, `buffCtrl`, `backpackCtrl`) registers a listener callback to `notifyCtrl:register(gNotifyID.<EVENT>, handler(self, self.<Callback>))`.

---

## 2. Comprehensive Enumeration of All Notification IDs (`gNotifyID`)

All notifications defined in `notifyIDDef_dec.lua`, mapped through `notifyMsgConfig` in `notifyCtrl_dec.lua` to subcommands of `CMD_NOTIFY_MODULE` (`1009`):

| # | Symbolic Name (`gNotifyID`) | Subcommand (`gCmd`) | Subcmd ID | Target Controller / Module | Event Description |
|---|-----------------------------|---------------------|-----------|----------------------------|-------------------|
| 1 | `BACKPACK` | `NOTIFY_BACKPACK_UPDATE` | "1" | `backpackCtrl` | Backpack items delta (`add`, `use`, `invalidtimeTable`) |
| 2 | `WORLD` | `NOTIFY_WORLD_UPDATE` | "2" | `kingdomMapCtrl` | World map object updates / player tile changes |
| 3 | `ALLIANCE` | `NOTIFY_ALLIANCE_UPDATE` | "3" | `allianceCtrl` | Alliance state, members, permissions, tech |
| 4 | `CHAT` | `NOTIFY_CHAT_UPDATE` | "4" | `chatCtrl` | Real-time chat messages |
| 5 | `MAIL` | `NOTIFY_MAIL_UPDATE` | "5" | `mailCtrl` | Mailbox updates / reports |
| 6 | `SETTLE` | `NOTIFY_SETTLE_FINISH` | "6" | `settleCtrl` | Settlement/season settlement completion |
| 7 | `BUFF` | `NOTIFY_BUFF_UPDATE` | "7" | `buffCtrl` | Buff activations, expiries, source closures |
| 8 | `LORD` | `NOTIFY_LORD_UPDATE` | "8" | `lordInfoCtrl` | Lord stats, stamina, exp, official title, spar |
| 9 | `CITY` | `NOTIFY_CITY_UPDATE` | "9" | `cityCtrl` | Resource deltas/totals, safe res, uncollected res, 2nd queue |
| 10 | `WATCHTOWER` | `NOTIFY_WATCHTOWER_UPDATE` | "10" | `watchTowerCtrl` | Incoming scouts/marches against player city |
| 11 | `WALLS` | `NOTIFY_WALLS_UPDATE` | "11" | `wallsCtrl` | Wall defense, fire burning queue, garrison |
| 12 | `QUEST` | `NOTIFY_QUEST_UPDATE` | "12" | `questCtrl` | Main/growth quest progress updates |
| 13 | `TREVIFOUNTAIN` | `NOTIFY_TREVIFOUNTAIN_UPDATE` | "13" | `treviFountainCtrl` | Wishing well / fountain free rolls & rewards |
| 14 | `QUEUE` | `NOTIFY_QUEUE_UPDATE` | "14" | `queueCtrl` | Global queue timer dispatch & completion |
| 15 | `ARMY` | `NOTIFY_ARMY_UPDATE` | "15" | `armyCtrl` | Castle army totals, wounded, training troops |
| 16 | `REWARD` | `NOTIFY_TIME_REWARD` | "16" | `timeRewardCtrl` | Harbor ship ready to collect (`isReceive = 2`) |
| 17 | `RECHARGE` | `NOTIFY_RECHARGE` | "17" | `rechargeCtrl` | Payment / top-up completion |
| 18 | `DAILYLOGIN_REWARD` | `NOTIFY_DAILYLOGIN_REWARD` | "18" | `loginRewardCtrl` | Daily login rewards status |
| 19 | `TIME` | `NOTIFY_SERVER_TIME` | "19" | `timeCtrl` | Server wall-clock timestamp synchronization |
| 20 | `TIME_REWARD` | `NOTIFY_RESET_TIME_REWARD` | "20" | `timeRewardCtrl` | Daily harbor ship cycle reset |
| 21 | `GUIDE` | `NOTIFY_GUIDE` | "21" | `guideCtrl` | Tutorial / guide state steps |
| 22 | `RECHARGE_ACTIVITY` | `NOTIFY_RECHARGE_ACTIVITY` | "22" | `rechargeActivityCtrl` | Recharge event tiers & rewards |
| 23 | `SHOP` | `NOTIFY_SHOP` | "23" | `shopCtrl` | Shop limits, item purchase counters |
| 24 | `WEATHER` | `NOTIFY_WEATHER_CHANGE` | "24" | `kingdomWeatherCtrl` | Kingdom weather state (rain, snow, sandstorm) |
| 25 | `CHAT_STATUS` | `NOTIFY_CHAT_STATUS` | "25" | `chatCtrl` | Mute status / chat room availability |
| 26 | `CUMUACTIVE` | `NOTIFY_CUMU_ACTIVE` | "26" | `cumuActiveCtrl` | Cumulative activity points and claims |
| 27 | `PYRAMID` | `NOTIFY_PYRAMID` | "27" | `pyramidCtrl` | Pyramid event state / battleground info |
| 28 | `LUCKYGIFT` | `NOTIFY_LUCKYGIFT` | "28" | `luckyGiftCtrl` | Lucky gift drop / red packet trigger |
| 29 | `EQUIPMENT` | `NOTIFY_EQUIPMENT` | "29" | `equipmentCtrl` | Lord equipment forging & inventory |
| 30 | `KINGDOM_LIST` | `NOTIFY_KINGDOM_LIST` | "30" | `kingdomCtrl` | Server/kingdom list status |
| 31 | `ROME_ACTIVITY` | `NOTIFY_ROME_ACTIVITY` | "31" | `romeActivityCtrl` | Rome ruins event phase & score |
| 32 | `ACCOUNT_EXTINFO` | `NOTIFY_ACCOUNT_EXTINFO` | "32" | `accountExtCtrl` | External account / binding info |
| 33 | `TREASUREMAP` | `NOTIFY_TREASUREMAP` | "35" | `treasureMapCtrl` | Treasure map fragments & excavations |
| 34 | `ACTIVITY_SHOW_CHANGE_TIME`| `NOTIFY_ACTIVITY_SHOW_CHANGE_TIME`| "36"| `activityShowCtrl` | Activity center calendar/time change |
| 35 | `HERO_TRIAL` | `NOTIFY_HERO_TRIAL` | "37" | `heroTrialCtrl` | Hero trial battle progress & rewards |
| 36 | `RAMADAN_REWARD` | `NOTIFY_RAMADAN_REWARD` | "38" | `ramadanRewardCtrl` | Holiday / Ramadan reward claims |
| 37 | `GROUPBUY` | `NOTIFY_GROUPBUY` | "39" | `groupBuyCtrl` | Group buy purchase tiers & unlocks |
| 38 | `RAMADAN_RANK_LIST` | `NOTIFY_RAMADAN_RANK_LIST` | "40" | `ramadanRankCtrl` | Event leaderboard updates |
| 39 | `BADGE_EXCHANGE` | `NOTIFY_BADGE_EXCHANGE` | "41" | `badgeExchangeCtrl` | Honor badge shop exchange |
| 40 | `CHATROOM` | `NOTIFY_CHATROOM_UPDATE` | "42" | `chatroomCtrl` | Voice/custom chatroom status |
| 41 | `CONQUESTWAR` | `NOTIFY_CONQUESTWAR` | "43" | `conquestWarCtrl` | Kingdom conquest war battlefield data |
| 42 | `CONTINUE_RECHARGE` | `NOTIFY_CONTINUE_RECHARGE`| "44" | `continueRechargeCtrl` | Consecutive daily top-up streaks |
| 43 | `FACEBOOK_TREASURE` | `NOTIFY_FACEBOOK_TREASURE`| "45" | `facebookTreasureCtrl` | Social share gift claims |
| 44 | `DRESS` | `NOTIFY_DRESS` | "46" | `dressCtrl` | Castle skins, march skins, nameframes |
| 45 | `PROP` | `NOTIFY_PROP` | "47" | `propCtrl` | Specialized props / temporary boosters |
| 46 | `SCOUT_RECORD` | `NOTIFY_SCOUT_RECORD` | "48" | `scoutRecordCtrl` | Scout incoming/outgoing logs |
| 47 | `ESCORT` | `NOTIFY_ESCORT` | "49" | `escortCtrl` | Carriage escort mission state |
| 48 | `ESCORT_CART` | `NOTIFY_ESCORT_CART` | "50" | `escortCartCtrl` | Escort cart position & durability |
| 49 | `ESCORT_ASSIST` | `NOTIFY_ESCORT_ASSIST` | "51" | `escortAssistCtrl` | Ally escort assistance invites |
| 50 | `ESCORT_INTEL` | `NOTIFY_ESCORT_INTEL` | "52" | `escortIntelCtrl` | Escort intel / plunder targets |
| 51 | `RESURRECTION` | `NOTIFY_RESURRECTION` | "53" | `resurrectionCtrl` | Resurrection hall soul recovery |
| 52 | `SNATCH` | `NOTIFY_SNATCH` | "54" | `snatchCtrl` | Relic snatch / grab event |
| 53 | `EVERYDAY_TASK` | `NOTIFY_EVERYDAY_TASK` | "55" | `everydayTaskCtrl` | Daily quest progression & chests |
| 54 | `LUCKYDAY_ACTIVITY` | `NOTIFY_LUCKYDAY_ACTIVITY`| "56" | `luckyDayActivityCtrl` | Lucky day bonus multipliers |
| 55 | `ACTIVITY_CENTER_UI` | `NOTIFY_ACTIVITY_CENTER_UI`| "57"| `activityCenterUICtrl` | Event banner / badge updates |
| 56 | `NEW_ACTIVITY` | `NOTIFY_NEW_ACTIVITY` | "58" | `newActivityCtrl` | Newly opened event banners |
| 57 | `SALESROOM` | `NOTIFY_SALESROOM` | "59" | `salesRoomAgCtrl` | Auction house / black market items |
| 58 | `NOVICE_GIFT` | `NOTIFY_NOVICE_GIFT` | "60" | `noviceGiftCtrl` | Starter pack / newbie progression gift |
| 59 | `COMMON` | `NOTIFY_COMMON` | "61" | `notifyCtrl` | System broadcast messages & notices |
| 60 | `BACK_GOLD_ACTIVITY` | `NOTIFY_BACK_GOLD_ACTIVITY`| "62"| `backGoldActivityCtrl`| Gold cashback rebate event |
| 61 | `SIGN_REWARD_ACTIVITY` | `NOTIFY_SIGN_REWARD_ACTIVITY`|"63"| `signRewardCtrl` | 30-day attendance check-in |
| 62 | `ALLIANCE_RELATION` | `NOTIFY_ALLIANCE_RELATION`| "64" | `allianceRelationCtrl` | Alliance diplomatic pacts (friendly/hostile) |
| 63 | `PET` | `NOTIFY_PET` | "65" | `newPetCtrl` | Pet system, skills, feeding |
| 64 | `MONSTERPALACE_ACTIVITY`| `NOTIFY_MONSTERPALACE_ACTIVITY`|"66"| `monsterpalaceCtrl` | Monster palace boss challenge |
| 65 | `KING_RETURN_ACTIVITY` | `NOTIFY_KING_RETURN_ACTIVITY`|"67"| `kingReturnCtrl` | Veteran recall / return event |
| 66 | `ELITE_PALACE` | `NOTIFY_ELITE_PALACE` | "68" | `elitePalaceCtrl` | Elite palace trial rooms |
| 67 | `PYRAMIDWAR` | `NOTIFY_PYRAMIDWAR` | "69" | `pyramidWarCtrl` | Pyramid cross-server faction war |
| 68 | `KING_GROUP_BUY` | `NOTIFY_KING_GROUP_BUY` | "70" | `kingGroupBuyAgCtrl` | Kingdom group-buy collective goal |
| 69 | `LIFE_WATER` | `NOTIFY_LIFE_WATER` | "71" | `lifeWaterCtrl` | Fountain of life revival spring |
| 70 | `COLLCET_WORDS` | `NOTIFY_COLLCET_WORDS` | "72" | `collectWordsAgCtrl` | Letter/word collecting festival |
| 71 | `ALLIANCE_MOBILIZATION` | `NOTIFY_ALLIANCE_MOBILIZATION`|"73"| `playerMobilizationCtrl`| Alliance festival quest board |
| 72 | `TREASURE_BOWL` | `NOTIFY_TREASURE_BOWL` | "74" | `kingdomMapCtrl` | Map cornucopia / treasure bowl gifts |
| 73 | `LORD_ACTIVITY` | `NOTIFY_LORD_ACTIVITY` | "75" | `lordActivityCtrl` | Lord tournament / combat leaderboards |
| 74 | `NEW_PLAYRE_TASK` | `NOTIFY_NEW_PLAYRE_TASK` | "76" | `newPlayerTaskCtrl` | Beginner 7-day milestones |
| 75 | `SETTING` | `NOTIFY_SETTING` | "77" | `settingCtrl` | Player settings & push notifications |
| 76 | `ICE_BREAK` | `NOTIFY_ICE_BREAK` | "78" | `iceBreakCtrl` | Winter ice breaker mini-game |
| 77 | `PREMIUM_STORE` | `NOTIFY_PREMIUM_STORE` | "79" | `premiumStoreCtrl` | VIP privilege exchange store |
| 78 | `START_WORK_ACTIVITY` | `NOTIFY_START_WORK_ACTIVITY`| "80"| `startWorkActivityCtrl`| Labor Day / start-work event |
| 79 | `NEW_KING_RISES` | `NOTIFY_NEW_KING_RISES` | "81" | `newKingRisesCtrl` | Rise of King milestone challenges |
| 80 | `NOTIFY_PET_EXCHANGE` | `NOTIFY_PET_EXCHANGE` | "82" | `newPetCtrl` | Pet fragment exchange market |
| 81 | `DAILY_GOALS_ACTIVITY` | `NOTIFY_DAILY_GOALS_ACTIVITY`|"83"| `dailyGoalsActivityCtrl`| Daily goal target chest points |
| 82 | `RECHARGE_GIFT` | `NOTIFY_RECHARGE_GIFT` | "84" | `rechargeGiftCtrl` | Cumulative purchase gift chests |
| 83 | `RECHARGE_ACTIVIT_GIFT`| `RECHARGE_ACTIVIT_GIFT` | "85" | `rechargeGiftCtrl` | Event purchase packs |
| 84 | `KINGDOM_LEVEL` | `NOTIFY_KINGDOM_LEVEL` | "86" | `kingdomLevelCtrl` | Kingdom world level buffs |
| 85 | `PRIVILEGE_GIFT` | `NOTIFY_PRIVILEGE_GIFT` | "87" | `privilegeGiftCtrl` | Monthly subscription privilege chests |
| 86 | `RED_PACKAGE_ACTIVITY` | `NOTIFY_RED_PACKAGE_ACTIVITY`|"88"| `redPackageActivityCtrl`| Alliance red packets / gold gifts |
| 87 | `WAR_GEM` | `NOTIFY_WAR_GEM` | "89" | `warGemCtrl` | War gem socketing & polishing |
| 88 | `LLW` | `NOTIFY_LEGEND_LORD_WAR` | "90" | `legendLordWarCtrl` | Legendary lord tournament |
| 89 | `LEGEND_LORD` | `NOTIFY_LEGEND_LORD` | "92" | `legendLordCtrl` | Legendary lord titles & stats |
| 90 | `EXCHANGE_MALL` | `NOTIFY_EXCHANGE_MALL` | "93" | `exchangeMallCtrl` | Token exchange store |
| 91 | `ACTIVITY_ORDER_SORT` | `NOTIFY_ACTIVITY_ORDER_SORT`| "94"| `activityShowCtrl` | Custom ordering of active tabs |
| 92 | `VIP` | `NOTIFY_VIP` | "95" | `vipCtrl` | VIP points, VIP level, daily chests |
| 93 | `ALLIANCE_TREASURE` | `NOTIFY_ALLIANCE_TREASURE` | "96" | `allianceTreasureCtrl`| Alliance gift chests & mine digs |
| 94 | `CUMU_SIGNIN` | `NOTIFY_CUMU_SIGNIN` | "97" | `eightDaysRewardActivityCtrl`| 8-day sign-in reward streak |
| 95 | `WEEK_RECHARGE_FEEDBACK`| `NOTIFY_WEEK_RECHARGE_FEEDBACK`|"98"| `weeklyRechargeActivityCtrl`| Weekly rebate gift |
| 96 | `NPCTIP_REWARD_COUNT` | `NOTIFY_NPCTIP_REWARD_COUNT`|"99"| `npcTipCtrl` | Castle NPC speech reward counts |
| 97 | `SERVER_STATUS` | `NOTIFY_SERVER_STATUS` | "100" | `serverStatusCtrl` | Server maintenance / status warnings |
| 98 | `TURNTABLE_ACTIVITY` | `NOTIFY_TURNTABLE_ACTIVITY`| "101"| `turntableActivityCtrl`| Lucky wheel spins |
| 99 | `TIME_LIMIT_TASK` | `NOTIFY_TIME_LIMIT_TASK` | "102" | `timeLimitTaskCtrl` | Flash time-limited mission |
| 100| `GOD_BEAST` | `NOTIFY_GOD_BEAST` | "103" | `godBeastCtrl` | Ancient divine beast awakening |
| 101| `HERO` | `NOTIFY_HERO` | "104" | `heroCtrl` | Hero collection, star, level, appoint, garrison |
| 102| `ATTRIBUTE_CHANGE` | `NOTIFY_ATTRIBUTE_CHANGE` | "105" | `boeAttributeCtrl` | Real-time combat power/attribute updates |
| 103| `SEVEN_DAY_ACTIVITY` | `NOTIFY_SEVEN_DAY_ACTIVITY`| "106"| `sevenDayTaskCtrl` | Carnival 7-day festival |
| 104| `CROSS_MISSION` | `NOTIFY_CROSS_MISSION` | "107" | `crossDecryptionCtrl` | Cross-server puzzle exploration |
| 105| `MIRCALE_BOX` | `NOTIFY_MIRCALE_BOX` | "108" | `mircaleBoxCtrl` | Miracle box keys and chest tiers |
| 106| `MAPDATA` | `NOTIFY_MAP_DATA` | "200" | `kingdomMapCtrl` | Full map chunk tile grid data |
| 107| `MAP_SYNC` | `NOTIFY_MAP_SYNC` | "201" | `kingdomMapCtrl` | Real-time map tile deltas / relocations |
| 108| `LOCAL_QUEUE_SYNC` | `NOTIFY_LOCAL_QUEUE_SYNC` | "202" | `kingdomMapCtrl` | March lines: ADD(1), REMOVE(2), UPDATE(3), ADD_ALL(4), REMOVE_ALL(5) |
| 109| `KW` | `NOTIFY_KW_UPDATE` | "300" | `KWKingdomCtrl` | Throne / Kingdom War state |
| 110| `AW` | `NOTIFY_AW_UPDATE` | "301" | `allianceWarCtrl` | Alliance War battlefield state |
| 111| `ACHIEVEMENT_INFO` | `NOTIFY_ACHIEVEMENT_UPDATE`| "400"| `achievementctrl` | Player achievement unlocks |
| 112| `REDENVELOPES_SEND_INFO`| `NOTIFY_REDENVELOPES_SEND_INFO`|"401"| `redPackageActivityCtrl`| Sent red packet claimed status |
| 113| `ACHIEVEMENT_BUFF_INFO`| `NOTIFY_ACHIEVEMENT_BUFF_CHANGE`|"402"| `achievementctrl` | Permanent achievement attribute buffs |
| 114| `RUINS_WAR_STATE_INFO`| `NOTIFY_RUINS_WAR_STATE_INFO`|"414"| `remainsWarCtrl` | Ancient ruins battle status |
| 115| `RW` | `NOTIFY_RUINS_WAR` | "415" | `remainsWarCtrl` | Ruins war phase transitions |
| 116| `VOICE_ROOM` | `NOTIFY_VOICE_ROOM` | "416" | `chatroomCtrl` | Voice channel participants |
| 117| `TEAM_UPDATE` | `NOTIFY_DVWAR_TEAM_UPDATE` | "423" | `devilValleyCtrl` | Devil valley faction war teams |
| 118| `DVW` | `NOTIFY_DEVIL_VALLEY_WAR` | "427" | `devilValleyCtrl` | Devil valley battlefield state |
| 119| `NOTIFY_TEAM` | `NOTIFY_TEAM` | "441" | `teamCtrl` | Rally team formation updates |
| 120| `NOTIFY_CHAT_CHANNEL` | `NOTIFY_CHAT_CHANNEL` | "444" | `chatCtrl` | Active chat channel subscribe |
| 121| `NOTIFY_KINGDOMGUARD` | `NOTIFY_KINGDOMGUARD` | "445" | `kingdomGuardianCtrl`| Kingdom guard fortress status |
| 122| `CLICKPRAISE_INFO` | `NOTIFY_CLICKPRAISE_INFO` | "1000"| `clickPraiseCtrl` | Social likes received |
| 123| `EVALUATION_OF_STARS` | `NOTIFY_EVALUATION_OF_STARS`|"1001"| `evaluationCtrl` | App store star ratings reward |
| 124| `STUFFWORKSHOP_REFINERY`| `NOTIFY_STUFFWORKSHOP_REFINERY`|"1002"| `stuffWorkshopCtrl` | Material workshop refining queue |
| 125| `MILITARY_RANK_DATA_CHANGE`| `NOTIFY_MILITARYRANK_DATA_CHANGE`|"1003"| `militaryRankCtrl` | Military rank promotions & badges |
| 126| `FLOWER_SYS_DATA_CHANGE`| `NOTIFY_FLOWER_SYS_DATA_CHANGE`|"1004"| `flowerSysCtrl` | Flower charm & gifting rank |
| 127| `SIEGECOMBAT` | `NOTIFY_SIEGECOMBAT` | "1006"| `siegeCombatCtrl` | City siege defense combat state |
| 128| `OPENEXCHANGESTORE` | `NOTIFY_OPENEXCHANGESTORE` | "1007"| `exchangeStoreAgCtrl`| Exchange market opened notice |
| 129| `EXCHANGESTORE_REDPOT`| `NOTIFY_EXCHANGESTORE_REDPOT`|"1008"| `exchangeStoreAgCtrl`| Market red dot refresh |
| 130| `CLOSE_EXCHANGESTORE`| `NOTIFY_CLOSE_EXCHANGESTORE`|"1009"| `exchangeStoreAgCtrl`| Exchange market closed notice |
| 131| `UPDATE_HERODRAWTIMES`| `NOTIFY_UPDATE_HERODRAWTIMES`|"1010"| `heroEnlistCtrl` | Daily free hero recruit counts |
| 132| `HERO_AUTOPACK_SKILL`| `NOTIFY_HERO_AUTOPACK_SKILL`|"1012"| `heroCtrl` | Auto-learn hero skills |
| 133| `KILLMONSTER` | `NOTIFY_KILLMONSTER_NUM` | "1013"| `killMonsterCtrl` | Daily monster kill counter |
| 134| `BUYPHYSICAL` | `NOTIFY_BUYSTAMINA_NUM` | "1014"| `buyStaminaCtrl` | Daily stamina purchases counter |
| 135| `DAILY_DISCOUNT_GIFT` | `NOTIFY_DAILY_DISCOUNT` | "1015"| `dailyDiscountGiftCtrl`| Daily special discount bundles |
| 136| `LUCKY_BLESS_INFO` | `NOTIFY_LUCKY_BLESS_INFO` | "1016"| `luckyBlessCtrl` | Lucky prayer blessing attributes |
| 137| `NOTIFY_AYT_SIGN` | `NOTIFY_AYT_SIGN` | "1017"| `CumulativeCheckinCtrl`| Festival check-in sign updates |
| 138| `NOTIFY_KING_LV_ATY` | `NOTIFY_KING_LV_ATY` | "1018"| `kingSecretCtrl` | King Level milestone competition |
| 139| `NOTIFY_POWERATY_ADDPOWER`| `NOTIFY_POWERATY_ADDPOWER`|"1019"| `outstandingCtrl` | Power sprint competition deltas |
| 140| `NOTIFY_PRINCESS` | `NOTIFY_PRINCESS` | "1020"| `beautyCtrl` | Beauty / Princess affection & favor |
| 141| `NOTIFY_PSN_TURNTABLE_ATY`| `NOTIFY_PSN_TURNTABLE_ATY`|"1021"| `personalTurntableCtrl`| Personal lucky wheel spins |
| 142| `NOTIFY_EMPEROR_ATY` | `NOTIFY_EMPEROR_ATY` | "1022"| `imperialTreasureCtrl`| Emperor coronation event |
| 143| `NOTIFY_LORD_SKILL_UPGRADE`| `NOTIFY_LORD_SKILL_UPGRADE`|"1023"| `lordSkillCtrl` | Lord talent / skill upgrades |
| 144| `NOTIFY_GENERAL_ATY` | `NOTIFY_GENERAL_ATY` | "1024"| `activityCommonTaskCtrl`| General activity points |
| 145| `UNIVERSAL_TASK` | `NOTIFY_UNIVERSAL_TASK` | "1025"| `universalTaskCtrl` | Common tasks progression |
| 146| `NOTIFY_CASTARMOR` | `NOTIFY_CASTARMOR` | "1026"| `castArmorCtrl` | Cast armor forging & set bonuses |
| 147| `NOTIFY_PVE_BATTLE` | `NOTIFY_PVE_BATTLE` | "1027"| `islandCtrl` | PVE expedition stage progress |
| 148| `NOTIFY_RUNE` | `NOTIFY_RUNE` | "1028"| `forgingCtrl` | Rune slots & rune inscriptions |
| 149| `NOTIFY_BOE_DYNAMIC_BAG`| `NOTIFY_BOE_DYNAMIC_BAG` | "1029"| `boeBagCtrl` | Dynamic items (timed/expiring items) |
| 150| `NOTIFY_APRILFOOL_DAY`| `NOTIFY_APRILFOOL_DAY` | "1030"| `aprilFoolCtrl` | April fools festival events |
| 151| `NOTIFY_BOE_LUCKY_PACKAGE`| `NOTIFY_BOE_LUCKY_PACKAGE`|"1031"| `boeBagCtrl` | Surprise mystery parcels |
| 152| `NOTIFY_LORD_SKILL` | `NOTIFY_LORD_SKILL` | "1032"| `lordSkillCtrl` | Active skill cooldowns & timers |
| 153| `NOTIFY_VOW_STAR_LAMPS`| `NOTIFY_VOW_STAR_LAMPS` | "1033"| `wishningLightCtrl` | Star lantern wishing rewards |
| 154| `SURPRISE_RECHARGE_DOUBLE`| `NOTIFY_SURPRISE_RECHARGE_DOUBLE`|"1034"| `surpriseGiftCtrl` | Double diamond recharge promo |
| 155| `NOTIFY_BIRTHDAY_CAKE`| `NOTIFY_BIRTHDAY_CAKE` | "1035"| `birthdayCelebrationCtrl`| Birthday cake making progress |
| 156| `NOTIFY_DRAW_CARD` | `NOTIFY_DRAW_CARD` | "1036"| `drawCardCtrl` | Tarot / card flip rewards |
| 157| `NOTIFY_DYNAMIC_AD` | `NOTIFY_DYNAMIC_AD` | "1037"| `dynamicAdCtrl` | In-game dynamic announcements |
| 158| `NOTIFY_KING_GROUP_ATY`| `NOTIFY_KING_GROUP_ATY` | "1038"| `kingGroupBuyAgCtrl` | Kingdom group purchase progress |
| 159| `NOTIFY_MUTI_TURN_ATY`| `NOTIFY_MUTI_TURN_ATY` | "1039"| `treasureTableCtrl` | Multi-tier turntable wheel |
| 160| `NOTIFY_CUSTOM_ATY` | `NOTIFY_CUSTOM_ATY` | "1040"| `activityCustomCtrl` | Custom server-driven event |
| 161| `PYRAMID_POINT` | `NOTIFY_PYRAMID_POINT` | "1041"| `pyramidCtrl` | Pyramid personal score deltas |
| 162| `NOTIFY_DAILY_UNLOCK_ATY`| `NOTIFY_DAILY_UNLOCK_ATY`|"1042"| `newSeventDayTaskCtrl` | Daily unlock mission stages |
| 163| `NOTIFY_UPDATE_HERO_LEGEND_ENLIST`| `NOTIFY_UPDATE_HERO_LEGEND_ENLIST`|"1043"| `heroEnlistCtrl` | Legendary hero tavern recruit |
| 164| `NOTIFY_NEW_KING_LV` | `NOTIFY_NEW_KING_LV` | "1044"| `newKingSecretCtrl` | New king level ranking score |
| 165| `NOTIFY_ATY_WEELLY` | `NOTIFY_ATY_WEELLY` | "1045"| `weeklyCalendarCtrl` | Weekly event calendar cycle |
| 166| `NOTIFY_DAILY_RECHARGE_ATY`| `NOTIFY_DAILY_RECHARGE_ATY`|"1046"| `multiPositionRechargeCtrl`| Multi-slot recharge tiers |
| 167| `NOTIFY_WAR_GEM_HALL_INFO`| `NOTIFY_WAR_GEM_HALL_INFO`|"1047"| `warGemCtrl` | War gem hall masteries |
| 168| `NOTIFY_WAR_GEM_HALL_UNLOCK_POS`| `NOTIFY_WAR_GEM_HALL_UNLOCK_POS`|"1048"| `warGemCtrl` | War gem socket unlock states |
| 169| `NOTIFY_TROY_TREASURE`| `NOTIFY_TROY_TREASURE` | "1049"| `troyTreasureCtrl` | Troy treasure vault explores |
| 170| `NOTIFY_ROME_RUINS_LEFT_LIFE`| `NOTIFY_ROME_RUINS_LEFT_LIFE`|"1050"| `romeActivityCtrl` | Rome ruins boss health / life |
| 171| `NOTIFY_PLAYER_QUEUE_CHANGE`| `NOTIFY_PLAYER_QUEUE_CHANGE`|"1051"| `queueCtrl` | Immediate player queue delta (`time_reward`, `workshop`) |
| 172| `NOTIFY_DUNGEON` | `NOTIFY_DUNGEON` | "1053"| `cryptAdventureCtrl` | Crypt adventure floor & keys |
| 173| `NOTIFY_DOMINATION` | `NOTIFY_DOMINATION` | "1054"| `kingdomDominateCtrl` | Kingdom domination points |
| 174| `NOTIFY_GOLDENSHIP` | `NOTIFY_GOLDENSHIP` | "1055"| `goldenShipCtrl` | Golden treasure ship arrival |
| 175| `NOTIFY_CUMULATE_REWARD`| `NOTIFY_CUMULATE_REWARD`| "1057"| `dailyGoodGiftCtrl` | Cumulative purchase reward tier |
| 176| `NOTIFY_RESET_CELEBRATION_FREE`| `NOTIFY_RESET_CELEBRATION_FREE`|"1058"| `qingDianMianDanCtrl`| Celebration free-order reset |
| 177| `NOTIFY_THANKS_FEEDBACK`| `NOTIFY_THANKS_FEEDBACK`|"1059"| `thanksgivingCtrl` | Thanksgiving feedback rewards |
| 178| `NOTIFY_CIRCUS` | `NOTIFY_CIRCUS` | "1060"| `circusTroupeCtrl` | Circus troupe stage performance |
| 179| `NOTIFY_WORSHIPBULL` | `NOTIFY_WORSHIPBULL` | "1061"| `bullSacrificeCtrl` | Bull sacrifice altar tributes |
| 180| `NOTIFY_ANTIQUE` | `NOTIFY_ANTIQUE` | "1062"| `antiqueAppreciationCtrl`| Antique appraisal & valuation |
| 181| `NOTIFY_FAMOUS_CITY_DATA`| `NOTIFY_FAMOUS_CITY_DATA`|"1066"| `famousCityCtrl` | Famous historical cities ownership |
| 182| `NOTIFY_SULEIMAN_TREASURE`| `NOTIFY_SULEIMAN_TREASURE`|"1067"| `suleimanCtrl` | Suleiman treasure expeditions |
| 183| `NOTIFY_DRILL_BATTLE` | `NOTIFY_DRILL_BATTLE` | "1068"| `dryRunningCtrl` | Military drill / exercise battle |
| 184| `NOTIFY_SERVER_QUEST` | `NOTIFY_SERVER_QUEST` | "1069"| `wangtubayeCtrl` | Kingdom chronicles / server quests |
| 185| `NOTIFY_MERITORIOUS_TASK`| `NOTIFY_MERITORIOUS_TASK`|"1070"| `meritCtrl` (`meritoriousTaskCtrl`)| Meritorious quest updates (core, side, daily) |
| 186| `NOTIFY_FIELD_SHOP` | `NOTIFY_FIELD_SHOP` | "1075"| `fieldShopCtrl` | Wilderness wanderer merchant shop |
| 187| `NOTIFY_LUCKY_DICE` | `NOTIFY_LUCKY_DICE` | "1076"| `luckyDiceCtrl` | Board game lucky dice rolls |
| 188| `NOTIFY_GENGTING_WAR_SEASON_DATA`| `NOTIFY_GENGTING_WAR_SEASON_DATA`|"1077"| `gengtingWarCtrl`| Gengting war season stats |
| 189| `NOTIFY_CLOUD_PEAK` | `NOTIFY_CLOUD_PEAK` | "1078"| `cloudPeakWarCtrl` | Cloud peak duel battlefield |
| 190| `NOTIFY_RACE_TIME` | `NOTIFY_RACE_TIME` | "1079"| `numRaceCtrl` | Time race competition countdown |
| 191| `NOTIFY_SNOWMAN_EXCHANGE`| `NOTIFY_SNOWMAN_EXCHANGE`|"1080"| `makeSnowmanCtrl` | Snowman decoration item trade |
| 192| `NOTIFY_IMAGE_SEAL` | `NOTIFY_IMAGE_SEAL` | "1081"| `emojiSealCtrl` | Custom emoji seal stamp unlocks |
| 193| `NOTIFY_EASTER_EGGS` | `NOTIFY_EASTER_EGGS` | "1082"| `easterEggsCtrl` | Easter egg discovery rewards |
| 194| `NOTIFY_CARRIAGE_ESCORT`| `NOTIFY_CARRIAGE_ESCORT`|"1083"| `carriageEscortCtrl` | High-value royal carriage status |
| 195| `NOTIFY_ROSE_ROAD` | `NOTIFY_ROSE_ROAD` | "1084"| `roseRoadCtrl` | Rose road garden milestones |
| 196| `NOTIFY_ROSE_GARDEN` | `NOTIFY_ROSE_GARDEN` | "1085"| `allianceRoseGardenCtrl`| Alliance shared rose garden |
| 197| `NOTIFY_GUEST_VISIT` | `NOTIFY_GUEST_VISIT` | "1086"| `guestVisitCtrl` | Castle noble visitor dialogs |
| 198| `NOTIFY_RUNE_SMELT` | `NOTIFY_RUNE_SMELT` | "1087"| `runeSmeltCtrl` | Rune smelting & essence values |
| 199| `NOTIFY_FIREWORK_CELEBRATION`| `NOTIFY_FIREWORK_CELEBRATION`|"1088"| `fireworkCelebrationCtrl`| Firework party launch rounds |
| 200| `NOTIFY_PULL_PIN_PUZZLE`| `NOTIFY_PULL_PIN_PUZZLE`|"1089"| `pullPinCtrl` | Pull-the-pin mini game floors |
| 201| `NOTIFY_COMPOSITE_ACTIVITY`| `NOTIFY_COMPOSITE_ACTIVITY`|"1091"| `beefLambMakeCtrl`| Cooking & item merging recipes |
| 202| `NOTIFY_MIGRATION` | `NOTIFY_MIGRATION` | "1092"| `kingdomTransferCtrl` | Kingdom immigration travel permits |
| 203| `NOTIFY_RAPID_DEVELOPMENT`| `NOTIFY_RAPID_DEVELOPMENT`|"1094"| `rapidDevCtrl` | Rapid growth speed boosters |
| 204| `NOTIFY_VIDEO_AD` | `NOTIFY_VIDEO_AD` | "1095"| `adCtrl` | Video reward ad counters |
| 205| `NOTIFY_TICKET_ATY` | `NOTIFY_TICKET_ATY` | "1096"| `caipiaoMilingCtrl` | Secret lottery tickets |
| 206| `NOTIFY_FIREWORK_PARTY`| `NOTIFY_FIREWORK_PARTY` | "1097"| `fireworkPartyCtrl` | Evening firework banquet gifts |
| 207| `NOTIFY_PIZZA_CHALLENGE`| `NOTIFY_PIZZA_CHALLENGE`|"1098"| `pizzaChallengeCtrl` | Pizza challenge stage score |
| 208| `NOTIFY_HERO_BOX_ATY` | `NOTIFY_HERO_BOX_ATY` | "1099"| `heroBoxCtrl` | Hero treasure chest points |
| 209| `NOTIFY_SPAR_BOX_ATY` | `NOTIFY_SPAR_BOX_ATY` | "1100"| `gemsTreasureCtrl` | Crystal spar chest points |
| 210| `NOTIFY_CAKE_PUZZLE_INFO`| `NOTIFY_CAKE_PUZZLE_INFO`|"1101"| `cakePuzzleCtrl` | Cake puzzle jigsaw pieces |
| 211| `NOTIFY_CORBAN_CELEBRATION_ATY`| `NOTIFY_CORBAN_CELEBRATION_ATY`|"1102"| `corbanCelebrationCtrl`| Feast celebration missions |
| 212| `NOTIFY_SPEED_PIONEER_INFO`| `NOTIFY_SPEED_PIONEER_INFO`|"1103"| `speedPioneerCtrl` | Speed pioneer rush ranking |
| 213| `NOTIFY_LOTTERY_ATY` | `NOTIFY_LOTTERY_ATY` | "1104"| `lotteryAtyCtrl` | Golden raffle tickets |
| 214| `NOTITY_ANA_STAR` | `NOTITY_ANA_STAR` | "1105"| `anaStarCtrl` | Ana star celestial blessings |
| 215| `NOTIFY_ANA_STAR_WAR` | `NOTIFY_ANA_STAR_WAR` | "1106"| `anaStarWarCtrl` | Celestial star faction war |
| 216| `NOTIFY_MAZE_ATY` | `NOTIFY_MAZE_ATY` | "1107"| `mazeActivityCtrl` | Labyrinth exploration stages |
| 217| `NOTIFY_EMPIRE_SHOP` | `NOTIFY_EMPIRE_SHOP` | "1108"| `empireShopCtrl` | Empire seasonal mall items |
| 218| `NOTIFY_HERO_TACTICAL_HALL`| `NOTIFY_HERO_TACTICAL_HALL`|"1109"| `heroTacticalHallCtrl`| Tactical hall queue & skills |
| 219| `NOTIFY_SUPER_LOTTERY_ATY`| `NOTIFY_SUPER_LOTTERY_ATY`|"1110"| `superLotteryCtrl` | Super jackpot draw numbers |
| 220| `NOTIFY_NEW_ESCORT` | `NOTIFY_NEW_ESCORT` | "1111"| `newEscortCtrl` | Overhauled escort transport |
| 221| `NOTITY_AREAN` | `NOTITY_AREAN` | "1112"| `aresArenaCtrl` | Ares arena PVP ranking & matches |
| 222| `NOTIFY_SNOW_JOURNEY` | `NOTIFY_SNOW_JOURNEY` | "1113"| `snowJourneyCtrl` | Winter snow trail expedition |
| 223| `NOTIFY_OTHERRACEINTRUSION`| `NOTIFY_OTHER_RACE_INTRUSION`|"1114"| `otherRaceIntrusionCtrl`| Alien horde siege attack waves |
| 224| `NOTIFY_HERO_BATTLE_BOSS`| `NOTIFY_HERO_BATTLE_BOSS`|"1115"| `heroBattleBossCtrl` | Hero solo boss challenge |
| 225| `NOTIFY_GOLDEN_MINER` | `NOTIFY_GOLDEN_MINER` | "1116"| `goldenMinerCtrl` | Gold miner claw game stages |
| 226| `NOTIFY_NUGGETS_ATY` | `NOTIFY_NUGGETS_ATY` | "1117"| `nuggetsAtyCtrl` | Gold rush panning deltas |
| 227| `NOTIFY_IMPERIAL_TREASURE`| `NOTIFY_IMPERIAL_TREASURE`|"1118"| `imperialTreasureCtrl`| Royal treasury key openings |
| 228| `NOTIFY_MAP_BUFF_CHANGE`| `NOTIFY_MAP_BUFF_CHANGE`|"1119"| `mapBuffCtrl` | Territory & world zone buffs |
| 229| `NOTIFY_LORD_TREASURE` | `NOTIFY_LORD_TREASURE` | "1120"| `lordTreasureAgCtrl` | Lord legendary relic power |
| 230| `NOTIFY_RESCUE_HERO_ATY`| `NOTIFY_RESCUE_HERO_ATY`|"1121"| `rescueHeroCtrl` | Captive hero rescue mission |
| 231| `NOTIFY_CHRISTMAS_SHOW`| `NOTIFY_CHRISTMAS_SHOW` | "1122"| `christmasShowCtrl` | Holiday celebration display |
| 232| `NOTIFY_TWO_CITY_WAR` | `NOTIFY_TWO_CITY_WAR` | "1123"| `twoCityCtrl` | Twin cities clash battlefield |
| 233| `NOTIFY_BEFORE_TWO_CITY`| `NOTIFY_BEFORE_TWO_CITY`|"1124"| `beforeTwoCityWarCtrl`| Twin cities prep-phase score |
| 234| `NOTIFY_TWO_CITY_LEADER`| `NOTIFY_TWO_CITY_LEADER`|"1125"| `twoCityLeaderAgCtrl` | Twin cities commander orders |
| 235| `NOTIFY_TWO_CITY_STORM` | `NOTIFY_TWO_CITY_STORM` | "1126"| `twoCityStormAgCtrl` | Twin cities storm assault phase |
| 236| `NOTIFY_CHISEL_LAND` | `NOTIFY_CHISEL_LAND` | "1127"| `chiselLandCtrl` | Land excavation grid digging |
| 237| `NOTIFY_MYSTERIOUSNOTES_ATY`| `NOTIFY_MYSTERIOUSNOTES_ATY`|"1128"| `mysteriousNotesCtrl`| Mysterious archaeologist notes |
| 238| `NOTIFY_GEM_ROAD` | `NOTIFY_GEM_ROAD` | "1129"| `gemRoadCtrl` | Gem advancement trail progress |
| 239| `NOTIFY_NUM_RACE` | `NOTIFY_NUM_RACE` | "1130"| `numRaceCtrl` | Numerical rush event rankings |
| 240| `NOTIFY_RICHER_MAN` | `NOTIFY_RICHER_MAN` | "1131"| `richerManCtrl` | Monopoly board movement |
| 241| `NOTIFY_WINTER_WAR_MAP`| `NOTIFY_WINTER_WAR_MAP` | "1132"| `winterWarMapCtrl` | Winter battlefield map zones |
| 242| `NOTIFY_ORDER_ATY` | `NOTIFY_ORDER_ATY` | "1133"| `orderAtyCtrl` | Order dispatch task shipments |
| 243| `NOTIFY_STONE_MINE` | `NOTIFY_STONE_MINE` | "1000201"| `stoneMineCtrl` | Stone quarry mining rate |
| 244| `NOTIFY_COMPASS_SLOT` | `NOTIFY_COMPASS_SLOT` | "1000202"| `compassSlotCtrl` | Nautical compass needle slots |
| 245| `NOTIFY_TURKEY_GIFT` | `NOTIFY_TURKEY_GIFT` | "1000203"| `turkeyGiftCtrl` | Feast roasted turkey gifts |
| 246| `NOTIFY_FOUR_SQUARE_GIFT`| `NOTIFY_FOUR_SQUARE_GIFT`|"1000204"| `fourSquareGiftCtrl`| Four-square lottery grid |
| 247| `NOTIFY_LANTERN` | `NOTIFY_LANTERN` | "1000205"| `lanternCtrl` | Lantern festival riddle gifts |
| 248| `NOTIFY_BAR_DARTS` | `NOTIFY_BAR_DARTS` | "1000206"| `barDartsCtrl` | Tavern dart throwing targets |
| 249| `NOTIFY_DECORATION_COLLECT`| `NOTIFY_DECORATION_COLLECT`|"1000208"| `decorationCollectCtrl`| Castle decor collection sets |
| 250| `NOTIFY_HERO_VOYAGE` | `NOTIFY_HERO_VOYAGE` | "1000209"| `heroVoyageAgCtrl` | Hero sea voyage consign tasks |
| 251| `NOTIFY_HERO_FORMATION`| `NOTIFY_HERO_FORMATION`|"1000210"| `heroFormationCtrl` | Hero preset formations |
| 252| `NOTIFY_LIGHT_JOURNEY` | `NOTIFY_LIGHT_JOURNEY` | "1000211"| `lightJourneyCtrl` | Journey of light pass rewards |
| 253| `NOTIFY_PERSONAL_ACTIVITY`| `NOTIFY_PERSONAL_ACTIVITY`|"1000213"| `personFreeBuffCtrl`| Solo challenge milestones |
| 254| `NOTIFY_WINTER_WAR` | `NOTIFY_WINTER_WAR` | "1000214"| `winterWarCtrl` | Winter faction war rounds |
| 255| `NOTIFY_RADAR_ATY` | `NOTIFY_RADAR_ATY` | "1000215"| `radarAtyCtrl` | Radar target tracking & sweeps |
| 256| `NOTIFY_MASS_ITEM_SPEED`| `NOTIFY_MASS_ITEM_SPEED`|"1000040"| `kingdomMapCtrl` | Mass march speed-up items |

---

## 3. Deep Analysis of Key Controllers & Notification Payloads

### 3.1 `cityCtrl` (City, Buildings & Resources)
#### 3.1.1 Initial Login Payload Structure (`retdata.cityCtrl`)
Delivered in `loginDataInitCtrl:getLoginDataInitRsp`:
```python
{
    "cinfo": { "cid": "123456", "name": "CastleName", ... },
    "blist": [
        {
            "binfo": {
                "bid": "101",          # Building Definition ID (e.g., 101 = Castle)
                "iid": "1",            # Instance ID
                "index": "1",          # Grid slot index (Unique primary key in city)
                "lv": "25",            # Regular level
                "state": "0",          # Building State (0 = NORMAL, 2 = UPGRADEING, ...)
                "curres": "0",         # Uncollected resource accumulation
                "curres_safe": "0",    # Safe uncollected resource accumulation
                "honorLv": "0",        # War/Honor level (Glory level, e.g., 1..30)
                "hlv": "0"             # Alias for honorLv
            }
        },
        ...
    ],
    "reslist": {
        "1001": "5423000",             # Food
        "1002": "4210000",             # Wood
        "1003": "1200000",             # Iron
        "1004": "850000",              # Mithril
        "1005": "35000"                # Gold
    },
    "saferes": { "1001": "1000000", "1002": "1000000", ... },
    "dayMaxRes": { "1001": "20000000", ... },
    "arealist": ["1", "2", "3", "4"],
    "newPlayerFlag": 0,
    "queue": {
        "1201": {                      # Charge builder queue (if active)
            "starttime": 1700000000,
            "totaltime": 172800,
            "lefttime": 85000
        }
    }
}
```

#### 3.1.2 Push Notification Structure (`NOTIFY_CITY`, Subcommand "9")
Received via `notifyCtrl:register(gNotifyID.CITY, updateCityData)`:
The payload `event.data` is an array/table of delta objects `v`:
```python
[
    {
        # Delta resource consumption or additions
        "res": {
            "1001": -45000,            # Food subtracted
            "1002": 12000              # Wood added
        },
        # Safe resource cap full replacement (if present)
        "saferes": { "1001": "1200000", "1002": "1200000" },
        # Resource list full replacement (if present)
        "reslist": { "1001": "5378000", "1002": "4222000" },
        # Daily resource gathering limit full replacement
        "dayMaxRes": { "1001": "20000000", "1002": "20000000" },
        # Uncollected production accumulated in farm/sawmill buildings
        "updateUnCollectRes": {
            "15": 1200,                # Building at index 15 added 1200 res
            "18": 850                  # Building at index 18 added 850 res
        },
        # Second (hired) build queue state
        "openChargeQueue": {
            "totaltime": 172800,
            "lefttime": 86400
        },
        # Maximum resource limit notification (array of pairs: [mtype, resid, ...])
        "maxRes": [0, 1001, 1, 1002]
    }
]
```

#### 3.1.3 Handling Logic in `cityCtrl.lua`
1. **`res` (Delta Resources)**:
   ```lua
   for resid, count in pairs(costreslist) do
     local ret = tonumber(curcity.resList[tostring(resid)]) or 0
     ret = ret + tonumber(count)
     if ret <= 0 then ret = 0 end
     curcity.resList[tostring(resid)] = tostring(ret)
   end
   ```
2. **`reslist` (Full Resource Replacement)**:
   Directly replaces `curcity.resList = reslist`.
3. **`saferes`**:
   Directly replaces `curcity.saferes = saferes`.
4. **`dayMaxRes`**:
   Directly replaces `curcity.dayMaxRes = dayMaxRes`.
5. **`updateUnCollectRes`**:
   Iterates through `{ [index] = count }`, locates the building cell by index, and increments `bcell.info.curres = tostring(tonumber(bcell.info.curres) + count)`.
6. **`openChargeQueue`**:
   Calls `curcity:addBuildChargeQueue(1201, systemTime(), totaltime, lefttime)`.

#### 3.1.4 Building State Transitions & Level Progression
Building states in `buildDef_dec.lua`:
- `BUILD_STATE.NORMAL = 0`
- `BUILD_STATE.BUILDING = 1`
- `BUILD_STATE.UPGRADEING = 2`
- `BUILD_STATE.DEMOLISHING = 3`
- `BUILD_STATE.LOCK = 8`

Building operate types in `buildDef_dec.lua`:
- `BUILD_OPERATE_TYPE.BUILD = 0`
- `BUILD_OPERATE_TYPE.DEMOLISH = 1`
- `BUILD_OPERATE_TYPE.UPGRADE = 2`
- `QUEUE_OPERATE_TYPE.CANCLE = 11`

**When queue ends or is canceled (`cityCtrl:buildQueueCallback`)**:
- **Normal Upgrade (`optype == 2`, regular)**:
  1. `bcell.info.lv = tostring(tonumber(bcell.info.lv) + 1)` (capped at `maxlv`)
  2. `bcell.info.state = tostring(BUILD_STATE.NORMAL)` (`"0"`)
- **Honor/War Level Upgrade (`optype == 2`, honor upgrade)**:
  1. `honorLv = (tonumber(bcell.info.honorLv) or tonumber(bcell.info.hlv) or 0) + 1` (capped at `maxHonorLv`)
  2. `bcell.info.honorLv = tostring(honorLv)`
  3. `bcell.info.hlv = tostring(honorLv)`
  4. `bcell.info.state = tostring(BUILD_STATE.NORMAL)` (`"0"`)
- **Build New (`optype == 0`)**:
  1. `bcell.info.state = tostring(BUILD_STATE.NORMAL)` (`"0"`)
- **Demolish (`optype == 1`)**:
  1. Removes building from `buildList` (`bcell = nil`)
- **Cancel Queue (`optype == 11`)**:
  1. Reverts building state back to `BUILD_STATE.NORMAL` (`"0"`). Level does NOT increment.

---

### 3.2 `queueCtrl` (Global Queues & Timers)
#### 3.2.1 Queue Types (`gQueueTypeDef`)
From `queueTypeDef_dec.lua`:
```lua
gQueueTypeDef = {
  free_build_queue               = 1200, # Primary free building queue
  charge_build_queue             = 1201, # Second / hired building queue
  hostpital_queue                = 1202, # Hospital healing queue
  chariot_plant_queue            = 1203, # Siege / chariot workshop training
  stables_queue                  = 1204, # Cavalry training queue
  range_queue                    = 1205, # Archer training queue
  barracks_queue                 = 1206, # Infantry training queue
  frotress_queue                 = 1207, # Trap building in fortress
  elite_queue                    = 1208, # Elite unit conversion
  technology_upgrade_queue       = 1212, # College / academy tech research
  skill_immediatelt_return       = 1213, # Lord immediate return skill CD
  skill_help                     = 1214, # Lord rescue skill CD
  skill_bumper                   = 1215, # Lord harvest bumper skill CD
  skill_resorrce_protection      = 1216, # Lord resource protection CD
  skill_alliance_march           = 1217, # Lord rally march speed CD
  skill_dap                      = 1218, # Lord defense boost CD
  vip_time                       = 1219, # VIP active timer
  moveline_embassy               = 1220, # Embassy reinforcement line
  moveline_map                   = 1221, # Map march line
  moveline_hall_or_war           = 1222, # War hall rally line
  moveline_wacth_tower           = 1223, # Watchtower scout line
  walls_burn                     = 1224, # Castle wall burning extinguish CD
  walls_defence                  = 1225, # Wall repair cooldown
  physical_recovery              = 1226, # Lord stamina full recovery countdown
  time_reward                    = 1227, # Harbor trade ship cooldown
  world_resource_cool            = 1228, # World gather node replenishment
  forge_equipment                = 1229, # Equipment forge queue
  change_resource_rate           = 1230, # Resource conversion rate CD
  trial_march                    = 1231, # Hero trial march line
  general_mibilization           = 1233, # Troop mobilization booster CD
  crazy_gather                   = 1234, # Fast gathering booster CD
  gather_protect                 = 1235, # Gather protection shield CD
  rapid_march                    = 1236, # Rapid march booster CD
  physical_abundant              = 1237, # Stamina surplus timer
  stuff_workshop                 = 1238, # Material workshop craft queue
  find_monster_free              = 1239, # Free monster search CD
  hero_meterial_workshop_produce = 1256, # Hero equipment material workshop
  hero_tactical_hall             = 1257  # Hero tactical hall study queue
}
```

#### 3.2.2 Queue Data Schema in `retdata.queueCtrl`
Array of active queue objects:
```python
[
    {
        "qtype": "1200",               # Queue type ID (string or int)
        "starttime": 1700000000,        # UNIX start timestamp
        "totaltime": 3600,             # Total duration in seconds
        "lefttime": 1800,              # Remaining duration in seconds
        "data": {                      # Queue context payload
            "bid": "101",              # Building ID
            "iid": "1",                # Building instance ID
            "index": "1",              # Building slot index
            "optype": "2",             # 2 = UPGRADE, 0 = BUILD, 1 = DEMOLISH
            "costres": { ... },
            "honorUpgradeWaitRsp": 0
        }
    },
    ...
]
```

#### 3.2.3 Notifications: `NOTIFY_QUEUE` (14) & `NOTIFY_PLAYER_QUEUE_CHANGE` (1051)
1. **`NOTIFY_QUEUE` (`updatequeue`)**:
   Delivered when a queue event finishes or is pushed by server:
   ```python
   [
       {
           "dispatchQueueEvent": {
               "queuetype": 1200,
               "name": "1200",
               "bid": 101,
               "iid": 1,
               "optype": 2,
               "costres": { ... }
           }
       }
   ]
   ```
   Lua removes the queue from `self.queues[queuetype]` and dispatches the event, which invokes `cityCtrl:buildQueueCallback`.
2. **`NOTIFY_PLAYER_QUEUE_CHANGE` (`onNotifyEvent`)**:
   Carries dynamic queue updates for `time_reward` (1227) or `hero_meterial_workshop_produce` (1256):
   - For `time_reward`: updates `lefttime`.
   - For `workshop` with `notifyType == "new"`: adds new queue with `starttime`, `totaltime`, `lefttime`.

#### 3.2.4 Map March Queues (`NOTIFY_LOCAL_QUEUE_SYNC`, Subcommand "202")
Handled by `kingdomMapCtrl:onNotifyLocalQueueSyncData`:
Messages contain `msg.msgType` (from `gQueueSyncMsgType`):
- `ADD = 1`: Inserts new march queue `local_queues_map[msg.data.id] = msg.data`.
- `REMOVE = 2`: Deletes completed/recalled march queue `local_queues_map.pop(msg.data.id)`.
- `UPDATE = 3`: Updates existing march queue speed/target/line.
- `ADD_ALL = 4`: Full list synchronization of all active player marches.
- `REMOVE_ALL = 5`: Clears all active player marches.

---

### 3.3 `armyCtrl` (Armies, Formations & Troops)
#### 3.3.1 Initial Login Payload Structure (`retdata.armyCtrl`)
```python
{
    # Troops present in castle (available to defend or march)
    "totalArmy": {
        "10101": "5000",               # Level 1 Infantry: 5000 troops
        "10205": "3200",               # Level 5 Cavalry: 3200 troops
        "10308": "1500"                # Level 8 Archer: 1500 troops
    },
    # Wounded troops in hospital awaiting heal
    "woundedArmy": {
        "10101": "120",
        "10205": "45"
    },
    # Troops currently in training queues across military buildings
    "trainArmy": {
        "103": {                       # Barracks building index
            "10101": "200"             # Training 200 Level 1 Infantry
        }
    },
    "singleTrainAddInfo": { ... },     # Training capacity multipliers
    "compileLimit": 4                  # Maximum number of march formations unlocked
}
```

#### 3.3.2 Push Notification Structure (`NOTIFY_ARMY`, Subcommand "15")
Delivered to `armyCtrl:updatearmyinfo`:
```python
[
    {
        "armyInfo": {
            "totalArmy": { ... },
            "woundedArmy": { ... },
            "trainArmy": { ... },
            "singleTrainAddInfo": { ... },
            "compileLimit": 4
        },
        "filterQueueId": "987654",     # Filter march queue ID
        "notifyType": "complieLimit",  # Or "guide"
        "limit": 5
    }
]
```
- If `v.armyInfo` is present, it **completely replaces** `self.armyInfo`.
- Marching troops outside the castle are calculated dynamically in Lua via `kingdomMapCtrl.kingdomMapCell:getAllQueueLiveArmy()`. Total account army is:
  $$\text{Total Troops} = \text{totalArmy} + \text{woundedArmy} + \text{marcharmylist} + \text{woundedArmyInMarches}$$

---

### 3.4 `heroCtrl` (Hero Collection, Development & Appoint)
#### 3.4.1 Initial Login Payload Structure (`retdata.heroCtrl`)
Array of hero objects:
```python
[
    {
        "id": 5501001,                 # Hero ID (Primary Key)
        "star": 5,                     # Star rating
        "lv": 50,                      # Hero Level
        "exp": 125000,                 # Current EXP
        "quality": 4,                  # Quality tier (Orange/Purple/etc.)
        "skills": [                    # Learned hero skills
            { "id": 1001, "lv": 10 },
            { "id": 1002, "lv": 8 }
        ],
        "status": {
            "state": 1,                # 0 = Idle, 1 = Marching, 2 = Garrison
            "buildId": 0,
            "place": 0
        },
        "appointStatus": {
            "state": 1,                # 0 = Unassigned, 1 = On duty
            "buildId": 101,            # Assigned to Castle/Wall
            "place": 1
        }
    },
    ...
]
```

#### 3.4.2 Push Notification Structure (`NOTIFY_HERO`, Subcommand "104")
Delivered to `heroCtrl:onNotifyDataUpdate(content)`:
```python
{
    "data": [
        [
            {
                "id": 5501001,         # Hero ID
                "lv": 51,
                "exp": 2500,
                "status": { "state": 0 },
                ...
            }
        ]
    ]
}
```
**Merging Rule**:
- Indexed strictly by **`id`**.
- For each hero object `v` in `content.data[1]`:
  - If `v.id` exists in `heroMap`: merges/replaces the existing hero record with `v`.
  - If `v.id` is new: appends `v` to `heroMap` as a newly unlocked hero.
  - Updates official assignment (`appointStatus`) and wall defense garrison (`status`).

---

### 3.5 `lordInfoCtrl` (Lord Stats, Energy & Talents)
#### 3.5.1 Initial Login Payload Structure (`retdata.lordInfoCtrl`)
```python
{
    "base": {
        "uid": "12345678",
        "name": "LordPlayer",
        "level": 35,                   # Lord level
        "exp": 4500000,                # Lord experience points
        "health": 120,                 # Physical stamina
        "gold": 5000,                  # Premium diamonds / gold
        "spar": 1200,                  # Crystal spar
        "power": 45000000,             # Combat power
        "image": "1001",               # Avatar icon ID
        "signature": "My bio"
    },
    "fcInfo": {
        "power": 45000000,
        "armyPower": 30000000,
        "buildPower": 8000000,
        "techPower": 5000000,
        "heroPower": 2000000
    },
    "skill": {
        "skillPoints": 42,             # Unallocated talent points
        "battle": { "11001": 5 },
        "develop": { "12001": 10 },
        "auxiliary": { "13001": 5 }
    },
    "official": { ... },               # Kingdom official office
    "npc": { "killMaxLevel": 30 },     # Highest monster level defeated
    "onlineInfo": { "continueLoginDay": 15 }
}
```

#### 3.5.2 Push Notification Structure (`NOTIFY_LORD`, Subcommand "8")
Delivered to `lordInfoCtrl:notifyLordData`:
`event.data` is an array of updates with a `key` field indicating the sub-model:
```python
[
    {
        "key": "base",
        "level": 36,
        "exp": 2500,
        "health": 110,
        "gold": 5200
    },
    {
        "key": "fcInfo",
        "power": 46500000
    },
    {
        "key": "skill",
        "skillPoints": 45
    },
    {
        "key": "physical",
        "time": 300                    # Seconds remaining until next stamina recovery
    },
    {
        "key": "npc",
        "killMaxLevel": 31
    }
]
```
**Merging Rule**:
- If `key == "base"`: calls `lordAuxiliary:updateLordBaseInfo`, which loops over all fields in the payload and writes them into `self.lordInfo.base`.
- If `key == "fcInfo"`: merges combat power fields into `self.lordInfo.fcInfo`.
- If `key == "skill"`: sets `self.lordInfo.skill.skillPoints = var.skillPoints`.
- If `key == "physical"`: manages the `gQueueTypeDef.physical_recovery` (1226) queue.

---

### 3.6 `buffCtrl` (Active Buffs, Shields & Boosters)
#### 3.6.1 Initial Login Payload Structure (`retdata.buffCtrl`)
```python
{
    "buffList": [
        {
            "id": 1001,                # Buff definition ID
            "source": 1,               # Source (1 = Item, 2 = Skill, 3 = VIP, ...)
            "effectType": 101,         # Effect type (e.g., Peace Shield, March Speed)
            "effect": 50,              # Effect magnitude (e.g. 50% boost)
            "beginTime": 1700000000,   # Start timestamp
            "endTime": 1700028800      # Expiration timestamp
        },
        ...
    ]
}
```

#### 3.6.2 Push Notification Structure (`NOTIFY_BUFF`, Subcommand "7")
Delivered to `buffCtrl:updateDataRsp`:
`event.data` is an array of `notifyData` objects containing a `syncType`:
1. **`openBuff`**:
   ```python
   {
       "syncType": "openBuff",
       "list": [
           { "id": 1002, "beginTime": 1700010000, "extra": { ... } }
       ]
   }
   ```
   Inserts or activates the buff in `buffMgr`.
2. **`closeBuff`**:
   ```python
   {
       "syncType": "closeBuff",
       "list": [101, 102]             # Effect types to remove
   }
   ```
3. **`closeSource`**:
   ```python
   {
       "syncType": "closeSource",
       "source": 1                    # Closes all buffs originating from this source
   }
   ```
4. **`buffFinish`**:
   ```python
   {
       "syncType": "buffFinish",
       "id": 1002,
       "source": 1,
       "effectType": 101
   }
   ```
   Closes the expired buff when its duration elapses.

---

### 3.7 `backpackCtrl` (Inventory, Items & Consumables)
#### 3.7.1 Initial Login Payload Structure (`retdata.backpackCtrl`)
```python
[
    {
        "id": "200101",                # Item ID (e.g., 5-minute speedup)
        "count": "150",                # Quantity
        "specialID": "0",
        "invalidtime": "0"             # Expiration timestamp (0 = permanent)
    },
    ...
]
```

#### 3.7.2 Push Notification Structure (`NOTIFY_BACKPACK`, Subcommand "1")
Delivered to `backpackCtrl:RSP:updateDataRsp`:
`event.data[1]` contains keyed synchronizer tables:
```python
{
    # Items added to inventory
    "add": {
        "200101": 10,                  # Added 10 of item 200101
        "300501": 2                    # Added 2 of item 300501
    },
    # Items consumed/used from inventory
    "use": {
        "200101": 5                    # Subtracted 5 of item 200101
    },
    # Error items (e.g., capacity reached)
    "err": [
        { "itemID": 200101, "err": 8001 }
    ],
    # Timed/expiring items invalidation timestamps
    "invalidtimeTabale": {
        "200101": 1700500000
    }
}
```
**Inventory Delta Merging Rule**:
- For each `(itemID, count)` in `add`:
  $$\text{inventory}[\text{itemID}] = \text{inventory.get}(\text{itemID}, 0) + \text{count}$$
- For each `(itemID, count)` in `use`:
  $$\text{inventory}[\text{itemID}] = \max(0, \text{inventory.get}(\text{itemID}, 0) - \text{count})$$
  If quantity reaches `0`, the item remains or is removed depending on display preference.

---

### 3.8 `meritoriousTaskCtrl` (`meritCtrl.lua`)
#### 3.8.1 Initial Login Payload Structure (`retdata.meritoriousTaskCtrl`)
```python
{
    "bOpen": True,                     # Feature unlocked boolean
    "meritLv": 5,                      # Meritorious military rank level
    "meritExp": 1200,                  # Current exp
    "dailyPoint": 80,                  # Today's activity points
    "main_task": {                     # Core/Main quests
        "1": 1001, "2": 1002
    },
    "branch_task": {                   # Side quests
        "1": 2001, "2": 2002
    },
    "daily_task": {                    # Daily recurring tasks
        "3001": 3, "3002": 1
    },
    "taskData": {                      # Detailed task states & progress
        "1001": { "id": 1001, "cur": 5, "max": 10, "state": 1 }
    },
    "meritorRwd": [1, 2, 3],           # Claimed rank level rewards
    "dailyBoxRwd": [1],                # Claimed daily chest tiers (e.g. 30, 60, 90 pts)
    "treasure": { ... },               # Meritorious shop items
    "nextDayTime": 1700035200          # Daily reset timestamp
}
```

#### 3.8.2 Push Notification Structure (`NOTIFY_MERITORIOUS_TASK`, Subcommand "1070")
Delivered to `meritCtrl:onNotified(event)`:
`event.data[1]` contains:
- If `flag == "base"`:
  ```python
  {
      "flag": "base",
      "data": {
          "meritLv": 6,
          "meritExp": 100,
          "dailyPoint": 100,
          ...
      }
  }
  ```
  Calls `updateData(data)` which overwrites all provided fields.
- If `flag == "task"`:
  ```python
  {
      "flag": "task",
      "data": {
          "add": {
              "main_task": { "3": 1003 },
              "branch_task": { "4": 2004 },
              "daily_task": { "3003": 1 },
              "taskData": { "1003": { ... } }
          },
          "remove": {
              "main_task": { "1": 1001 },
              "branch_task": { "1": 2001 },
              "daily_task": { "3001": 3 },
              "taskData": { "1001": { ... } }
          }
      }
  }
  ```
  Calls `updateIncrementData(data)`: adds tasks from `add` into their respective maps, and deletes tasks in `remove` from the maps.

---

### 3.9 `timeRewardCtrl` (Harbor Trade Ships / Matou)
#### 3.9.1 Initial Login Payload Structure (`retdata.timeRewardCtrl`)
```python
{
    "isReceive": 1,                    # 1 = Counting down, 2 = Ready to collect
    "sequence": 3,                     # Current ship index (1 through 10)
    "isAllReceive": 0,                 # 1 = All daily ships claimed
    "receiveTime": 1700001000,         # Timestamp when countdown started
    "reward": {                        # Contents of cargo
        "res": { "1001": 50000 },
        "item": { "200101": 1 }
    }
}
```

#### 3.9.2 Notifications
1. **`NOTIFY_TIME_REWARD` (Subcmd "16")**:
   Sets `self.timeRewardData.isReceive = 2`. The harbor ship has docked and can be claimed immediately!
2. **`NOTIFY_RESET_TIME_REWARD` (Subcmd "20")**:
   Daily midnight reset: sets `isReceive = 1`, `sequence = 1`, `isAllReceive = 0`, updates cargo, and restarts queue `1227` (`gQueueTypeDef.time_reward`).
3. **Claim Response (`gCmd.REQ_RECEIVE_TIME_REWARD`)**:
   Advances `sequence = sequence + 1`. If more ships remain, starts the next queue `1227` timer from config `timereward[sequence].time`. If `err == Err_ALL_RECEIVED_TODAY`, marks `isAllReceive = 1`.

---

## 4. Lua Controller Update & Model Merging Mechanics

### 4.1 Keyed List Deep-Merge Rules
In the reference Lua architecture, lists representing game entities are never blindly overwritten with partial arrays; they are indexed by distinct primary keys:

| Controller | Entity Collection | Primary Key | Lua Structure | Merge Algorithm |
|------------|-------------------|-------------|---------------|-----------------|
| `cityCtrl` | `blist` (Buildings) | `index` (Slot) or `bid`/`iid` | `self.buildList[index]` | Match building by `index` (or `bid`+`iid`). Deep merge fields (`lv`, `state`, `curres`, `honorLv`). Never wipe other buildings. |
| `heroCtrl` | `heroes` | `id` (Hero ID) | `self.heroMap[id]` | Match by `id`. Update attributes or append new hero. Never delete unmentioned heroes. |
| `buffCtrl` | `buffList` | `id` + `source` | `buffMgr.buffs` | Update matching buff instance or add. Remove on `closeBuff` / `closeSource` / `buffFinish`. |
| `queueCtrl`| `queues` | `qtype` (or `id`) | `self.queues[qtype]` | Unique per queue type. Replaced on start, popped on end/cancel. |
| `local_queues` | March lines | `id` (Queue ID) | `localQueueMap[id]` | Keyed by march queue ID. ADD inserts, UPDATE mutates, REMOVE pops. |
| `backpackCtrl` | Inventory items | `id` (Item ID) | `backpacks[type]` | Increments on `add`, decrements on `use`. |
| `meritCtrl`| Quests | Task Key / `id` | `questMap[id]` | Added via `add`, deleted via `remove`. |

### 4.2 Dict Replacement vs Recursive Mutation
- **Atomic Replacements**:
  Fields like `saferes`, `dayMaxRes`, `reslist` (when sent as full table), and `fcInfo` are atomically updated.
- **Delta Increments**:
  `res` in `NOTIFY_CITY`, and `add`/`use` in `NOTIFY_BACKPACK`, are algebraic deltas ($x \leftarrow \max(0, x + \Delta)$).
- **Callback-Triggered State Transformations**:
  Queue expirations in `queueCtrl` do not just delete the queue; they trigger callbacks back into dependent controllers (e.g. `cityCtrl:buildQueueCallback`), transitioning building state from `BUILD_STATE.UPGRADEING` (`2`) to `BUILD_STATE.NORMAL` (`0`) and incrementing building level (`lv` or `honorLv`).

---

## 5. Memory Readiness Verification Gate Criteria

To guarantee that bot tasks never execute against incomplete or corrupt state, the live memory must satisfy the following structural integrity conditions:

1. **`cityCtrl`**:
   - `blist` exists and contains at least Castle (`bid = 101`).
   - `reslist` exists and contains standard resources (`1001` through `1005`).
2. **`lordInfoCtrl`**:
   - `base` exists, contains valid `uid`, `level`, and `health`.
3. **`queueCtrl`**:
   - Initialized and ready to receive timer countdowns.
4. **`armyCtrl`**:
   - `totalArmy` dictionary exists.
5. **`backpackCtrl`**:
   - Item inventory map exists.

If any of these critical controllers are absent after initial login packet flow, the client must trigger an immediate **Fallback Sync Query** (e.g. `CMD_CITY_MODULE / REQ_INIT_CITYDATA`, `CMD_LORD_MODULE / REQ_INIT_LORDDATA`, `CMD_QUEUE_MODULE / REQ_INIT_QUEUEDATA`, `CMD_ARMY_MODULE / REQ_INIT_ARMYDATA`) before allowing any bot task to proceed.
