local gametop = gModuleMgr.getObject("gametop")
local armyCtrl = gametop.playertop_:getModule("armyCtrl")
local buffCtrl = gametop.playertop_:getModule("buffCtrl")
local kingdomMapCtrl = gametop.playertop_:getModule("kingdomMapCtrl")
local lordInfoCtrl = gametop.playertop_:getModule("lordInfoCtrl")
local buildLogic = include("buildLogic")
local armyDesRead = include("armyDesRead")
local resDesRead = include("resDesRead")
local cityEffectInfoRead = include("cityEffectInfoRead")
local soundFileRead = include("soundFileRead")
local armyltCtrl = include("armyltCtrl")
local expeditionTypeltCtrl = include("expeditionTypeltCtrl")
local heroCtrl = gametop.playertop_:getModule("heroCtrl")
local heroMgr = heroCtrl:getHeroMgr()
local boeAttributeCtrl = gametop.playertop_:getModule("boeAttributeCtrl")
local heroAppointCtrl = gametop.playertop_:getModule("heroAppointCtrl")
local artifactCtrl = gametop.playertop_:getModule("artifactCtrl")
local heroSkillltCtrl = include("heroSkillltCtrl")
local constantRead = include("constantRead")
local equipmentCtrl = gametop.playertop_:getModule("equipmentCtrl")
local newPetCtrl = gametop.playertop_:getModule("newPetCtrl")
local petRead = include("petRead")
local skillDes = include("lordSkillDesRead")
local kingdomMapUtil = include("kingdomMapUtil")
local islandCtrl = gametop.playertop_:getModule("islandCtrl")
local battleShipltCtrl = include("battleShipltCtrl")
local battleShipCtrl = SoraDGetModule("battleShipCtrl")
local twoCityCtrl = SoraDGetModule("twoCityCtrl")
local lMapExpeditionDes = {
  [tostring(gMapExpeditionType.all)] = "1,\231\148\168\228\186\142\232\139\177\233\155\132\232\175\166\230\131\133\228\184\173\231\154\132\230\152\190\231\164\186\239\188\140\230\138\128\232\131\189\227\128\129\229\133\181\228\185\166\231\148\177\231\168\139\229\186\143\229\164\132\231\144\134\239\188\140\228\184\141\231\148\168\233\133\141\231\189\174",
  [tostring(gMapExpeditionType.formation)] = "2,\230\160\161\229\156\186\231\188\150\233\152\159",
  [tostring(gMapExpeditionType.plain)] = "10,\229\185\179\229\142\159",
  [tostring(gMapExpeditionType.npc)] = "11,\233\135\142\229\164\150\230\149\140\229\133\181",
  [tostring(gMapExpeditionType.relics)] = "12,\233\129\151\232\191\185",
  [tostring(gMapExpeditionType.castle)] = "13,\230\149\140\230\150\185\229\159\142\229\160\161",
  [tostring(gMapExpeditionType.campsite)] = "14,\232\144\165\229\156\176(\230\149\140\230\150\185)",
  [tostring(gMapExpeditionType.battery)] = "15,\231\130\174\229\143\176(\233\157\158\230\143\180\229\138\169)",
  [tostring(gMapExpeditionType.fortress)] = "16,\232\166\129\229\161\158(\233\157\158\230\143\180\229\138\169)",
  [tostring(gMapExpeditionType.kingdom_build)] = "17,\231\142\139\229\186\167(\233\157\158\230\143\180\229\138\169)",
  [tostring(gMapExpeditionType.boss)] = "18,\228\184\150\231\149\140boss(\229\140\133\230\139\172\232\139\177\233\155\132\228\185\139\230\136\152boss)",
  [tostring(gMapExpeditionType.beast)] = "19,\231\165\158\229\133\189",
  [tostring(gMapExpeditionType.escort)] = "20,\230\138\164\233\128\129\229\174\157\232\151\143(\230\138\188\232\191\144)",
  [tostring(gMapExpeditionType.plunder_escort)] = "21,\230\142\160\229\164\186\229\174\157\232\151\143(\230\138\188\232\191\144)",
  [tostring(gMapExpeditionType.alliance_build)] = "22,\232\129\148\231\155\159\229\187\186\231\173\145(\230\149\140\230\150\185)",
  [tostring(gMapExpeditionType.help)] = "23,\230\143\180\229\138\169\233\152\159\229\143\139",
  [tostring(gMapExpeditionType.collect_wood)] = "24,\229\135\186\229\190\129\233\135\135\233\155\134\230\156\168\230\157\144",
  [tostring(gMapExpeditionType.collect_food)] = "25,\229\135\186\229\190\129\233\135\135\233\155\134\231\178\174\233\163\159",
  [tostring(gMapExpeditionType.collect_iron)] = "26,\229\135\186\229\190\129\233\135\135\233\155\134\233\147\129\231\159\191",
  [tostring(gMapExpeditionType.collect_mithril)] = "27,\229\135\186\229\190\129\233\135\135\233\155\134\229\174\157\231\159\179",
  [tostring(gMapExpeditionType.collect_gold)] = "28,\229\135\186\229\190\129\233\135\135\233\155\134\233\135\145\231\159\191",
  [tostring(gMapExpeditionType.stronghold)] = "29,\230\141\174\231\130\185",
  [tostring(gMapExpeditionType.alliance_super_build)] = "30,\229\187\186\233\128\160\232\129\148\231\155\159\232\182\133\231\186\167\231\159\191"
}
local WorldDispatchArmyView = class("worldDispatchArmyView", function(target)
  if target == nil or target == "islandMode" then
    return SoraDCreateBasePanel("worldDispatchArmyView")
  end
  return target
end)

function WorldDispatchArmyView:initCfg()
  self._cfg = {}
  self._cfg.editboxColor = cc.c3b(175, 175, 175)
  self._cfg.colorGreen = cc.c3b(0, 190, 30)
  self._cfg.txtTotalColor1 = cc.c3b(255, 255, 255)
  self._cfg.allCombatColor1 = "#00BE1E"
  self._cfg.monsterTipColor1 = cc.c3b(250, 40, 0)
  self._cfg.monsterTipColor2 = cc.c3b(255, 255, 255)
  self._cfg.monsterTipColor3 = cc.c3b(0, 190, 30)
  self._cfg.scroll = {}
  self._cfg.scroll.originH = 356
  self._cfg.scroll.pveOffsetH = 50
  self._cfg.scroll.monsterOffsetH = 28
  self._cfg.scroll.troopOffsetH = 59
  self._cfg.heroCombatY = 571
  self._cfg.heroCombatY_island = 571
  self._cfg.pngAdd = "common_plus02.png"
  self._cfg.pngLingzhu = "linzhu_physical.png"
  self._cfg.pngSpeed = "icon_fight_speed_rank_01.png"
  self._cfg.singleH = 140
  self.useController = true
end

function WorldDispatchArmyView:ctor()
  self:initCfg()
  armyDesRead.loadSoldierPromotionRes()
  self.isHideCurrentSceneView = true
  include("worldMapDefine")
  include("worldMapFunction")
  self.toPoint = nil
  self.dispatchType = nil
  self.instanceID = nil
  self.instanceType = nil
  self.selectType = 1
  self.otherData = {}
  self.allSingles = {}
  self.tableArmySingle = {}
  self.tableSpare = {}
  self.tableArmy = {}
  self.tableArmyData = {}
  self.allCount = buildLogic.getExpArmyCount().total
  self.allowMaxCount = nil
  self.curCount = 0
  self.curWeight = 0
  self.isSelectFull = false
  self.leftTime = nil
  self.costTime = 0
  self.curTime = 0
  self.isIslandMode = false
  self.selectedHeroList = {}
  self.curHeroList = {}
  self.curHeroIdList = {}
  self.garrisonHeroList = {}
  self.recommendationHeroIdList = {}
  self.showHeroIdList = {}
  self.heroListData = {}
  self.recommendationHeroId = nil
  self.selectedOrder = 1
  self.tabHeros = {}
  self.isFirstIn = true
  self.selectedPetId = nil
  self.tabArmyTeamBtn = {}
  self.dropUpBox = SoraDGetExtendChildFromCCSByName(self, "CCS_worldDispatchDropUpBox_army")
  self.dropUpBox:setTroopTypeSelectedCallback(handler(self, self.troopTypeSelectedCallback))
  self.scroll = SoraDGetChildByName(self, "Top_Size_scrollviewGo")
  self.topNode = SoraDGetChildByName(self, "Top_node")
  self.bottomNode = SoraDGetChildByName(self, "Bottom_node")
  self.panelTopBg = SoraDGetChildByName(self, "panelTopBg")
  self.textTroops = SoraDGetChildByName(self, "textTroops")
  self.btnQuickChoose = SoraDGetChildByName(self.bottomNode, "btnQuick")
  self.nodeTitle = SoraDGetExtendChildFromCCSByName(self, "CCS_commonFramTitle_title")
  self.spriteChangeName = SoraDGetChildByName(self.nodeTitle, "spriteChangeName")
  self.labelNotice = SoraDGetChildByName(self, "Center_textNotice")
  self.btnConvene = SoraDGetChildByName(self, "Center_btnConvene")
  self.labTargetTip = SoraDGetChildByName(self.topNode, "Text_target_tip")
  self.labTroopPower = SoraDGetChildByName(self.topNode, "Text_troop_all_power")
  self.labelCount = SoraDGetChildByName(self.topNode, "textCount")
  self.txtTotal = SoraDGetChildByName(self.topNode, "textCountTotal")
  self.btnCountPlus = SoraDGetChildByName(self.topNode, "btnCountPlus")
  self.labelWeight = SoraDGetChildByName(self.topNode, "textWeight")
  self.btnPhysicalPlus = SoraDGetChildByName(self.topNode, "btnPhysicalPlus")
  self.imgWeight = SoraDGetChildByName(self.topNode, "imgWeight")
  self.imgCount = SoraDGetChildByName(self.topNode, "imgCount")
  self.Node_tip = SoraDGetChildByName(self.bottomNode, "Node_tip")
  self.Image_shadow = SoraDGetChildByName(self.bottomNode, "Image_shadow")
  self.btnGo = SoraDGetChildByName(self.bottomNode, "Button_go")
  self.labelTime = SoraDGetChildByName(self.btnGo, "textTime")
  self.labelGoTitle = SoraDGetChildByName(self.btnGo, "textBtnGoTitle")
  self.icon_hourglass_3 = SoraDGetChildByName(self.btnGo, "icon_hourglass_3")
  self.labelMonsterTip = SoraDGetChildByName(self.bottomNode, "Text_march_monster_tip")
  self.imgMonsterBg = SoraDGetChildByName(self.bottomNode, "Image_FLIP_monster_bg")
  self.imgMonsterBg2 = SoraDGetChildByName(self.bottomNode, "Image_monster_FLIP_bg_0")
  self.textTroops:setVisible(true)
  self.textTroops:setString(i18n("chuzheng_text_01"))
  self.btnQuickChoose:setTitleText(i18n("common_text_852"))
  self.btnQuickChoose:getTitleRenderer():setWidth(154)
  self.btnQuickChoose:getTitleRenderer():setHeight(30)
  self.btnQuickChoose:getTitleRenderer():setAlignment(cc.TEXT_ALIGNMENT_CENTER, cc.TEXT_ALIGNMENT_CENTER)
  self.spriteChangeName:setVisible(false)
  self.labelNotice:setString(i18n("common_text_858"))
  self.btnConvene:setTitleText(i18n("common_text_3616"))
  self.nodeTitle:setTitle(i18n("common_text_481"))
  self.labelTime:setString("00:00:00")
  self.labelWeight:setString("0")
  self.labelGoTitle:setString(i18n("common_text_481"))
  self.scroll:addEventListener(handler(self, self.scrollEventCallBack))
  self.btnQuickChoose:addTouchEventListener(handler(self, self.btnQuickClickCallBack))
  self.btnGo:addTouchEventListener(handler(self, self.btnGoClickCallBack))
  self.btnCountPlus:addTouchEventListener(handler(self, self.btnCountPlusClickCallBack))
  self.btnPhysicalPlus:addTouchEventListener(handler(self, self.btnPhysicalPlusClickCallBack))
  self.btnConvene:addTouchEventListener(handler(self, self.btnConveneClickCallBack))
  self.imgWeight:addTouchEventListener(handler(self, self.onTipShow))
  self.imgCount:addTouchEventListener(handler(self, self.onTipShow))
  self.btnGo:setButtonType(1)
  self.btnGo:setAutoGray(false)
  self.btnGo:setForcePressedActionEnable(true)
  self.selectArtifact = SoraDGetExtendChildFromCCSByName(self, "CCS_artifactRunePageSelectionButton")
  self.selectArtifact:setVisible(false)
  self.selectBattleShip = SoraDGetExtendChildFromCCSByName(self, "CCS_artifactRunePageSelectionButton_battleShip")
  self.selectBattleShip:setVisible(false)
  self.dropDownBox = SoraDGetExtendChildFromCCSByName(self, "CCS_worldDispatchDropDownBox_formation")
  self.dropDownBox:initData()
  self.dropDownBox:setOptionSelectedHandler(handler(self, self.onOptionSelected))
  self.hero1 = SoraDGetExtendChildFromCCSByName(self, "CCS_rewardHeroItem_1")
  self.hero2 = SoraDGetExtendChildFromCCSByName(self, "CCS_rewardHeroItem_2")
  self.Node_pet = SoraDGetExtendChildFromCCSByName(self, "CCS_petGuardNode")
  self.btnHeroDetail = SoraDGetChildByName(self, "Button_hero_detail")
  self.btnHeroDetail:addTouchEventListener(handler(self, self.btnHeroDetailCallback))
  self.hero1:setIsShowRemoveButtonMode(true)
  self.hero2:setIsShowRemoveButtonMode(true)
  self.hero1:initData({order = 1})
  self.hero2:initData({order = 2})
  self.hero1:setHandler(handler(self, self.onClickedHero))
  self.hero2:setHandler(handler(self, self.onClickedHero))
  self.hero1:setRemoveHandler(handler(self, self.onRemoveHero))
  self.hero2:setRemoveHandler(handler(self, self.onRemoveHero))
  self.hero1:setNameBestSize(cc.size(150, 65))
  self.hero2:setNameBestSize(cc.size(150, 65))
  table.insert(self.tabHeros, self.hero1)
  table.insert(self.tabHeros, self.hero2)
  self.Node_pet:getTextLabel():setPositionY(-92)
  self.selectArtifact:setNamePosY(-91.5)
  self.Node_pet:getDismissBtn():setScale(self.hero1:getScale() / self.Node_pet:getScale())
  self.Node_pet:getDismissBtn():setPosition(SoraDFSign(-39.5), 48)
  local canShow = self:canShowWargemPage()
  self.v.Button_wargem:setVisible(canShow)
  SoraDAddClickHandler(self.v.Button_wargem, function(target)
    SoraDPlaySound()
    SoraDCreatePanel("worldDispatchWargemView"):show()
  end)
  self:initTeamBtns()
  self:initPetNode()
  self:initArtifactButton()
  self:refreshGemPage()
end

function WorldDispatchArmyView:tabMain(...)
  return {
    s1 = function(c)
      if worldMapDefine.isInAnaStar() then
        c:call(self:tabGetAnaStarSpeedMovePlus(), "tabGetAnaStarSpeedMovePlus")
      end
    end
  }
end

function WorldDispatchArmyView:tabGetAnaStarSpeedMovePlus()
  return {
    s1 = function(c)
      c:call(boeAttributeCtrl:tabRequest(boeAttributeCtrl.reqGetWarSpecificAttribute), "s2", {"rsp", "err"}, gAttrCondDef.ALL_WAR, gAttrTargetDef.ALL_ARMY, gAttributeDef.MARCH_SPEED)
    end,
    s3 = function(c)
      c.v.speedPlus = c.v.rsp.data.rate
      self:updateMoveTime({
        isAnaStar = true,
        speedPlus = c.v.speedPlus
      })
      if self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss then
        c:call(boeAttributeCtrl:tabRequest(boeAttributeCtrl.reqGetWarSpecificAttribute), "s4", {"rsp", "err"}, gAttrCondDef.MONSTER_WAR, gAttrTargetDef.ALL_ARMY, gAttributeDef.MARCH_SPEED)
      end
    end,
    s5 = function(c)
      c.v.speedPlus = c.v.speedPlus + c.v.rsp.data.rate
      self:updateMoveTime({
        isAnaStar = true,
        speedPlus = c.v.speedPlus
      })
    end
  }
end

function WorldDispatchArmyView:canShowWargemPage()
  local holeDatas = include("warGemltCtrl"):getHolesByColor(gWarGemColor.WHITE)
  local canShow = false
  for i, v in ipairs(holeDatas) do
    local warLv = gGetBuildWarLv(BUILDID.CASTLE)
    if warLv >= v.castleLv then
      canShow = true
      break
    end
  end
  return canShow
end

function WorldDispatchArmyView:onArtifactNodeTouched()
  local panel = SoraDCreatePanel("artifactRunePageSwitchView")
  panel:setConfirmHandler(handler(self, self.onSuitPageIndexComfirmed))
  panel:initData(self.selectedArtifactIndex)
  panel:show()
end

function WorldDispatchArmyView:onBattleShipNodeTouched()
  local panel = SoraDCreatePanel("battleShipDetailSwitchView")
  local data = {
    name = self.curShipName,
    isBattleShip = true,
    shipType = self.curShipType
  }
  panel:initData(data)
  panel:show()
end

function WorldDispatchArmyView:onSuitPageIndexComfirmed(index)
  self.selectedArtifactIndex = index
  self:initArtifactButton()
end

function WorldDispatchArmyView:initArtifactButton()
  self.selectArtifact:setVisible(equipmentCtrl:isAnyEquipRefineMaxLv())
  self.selectBattleShip:setVisible(battleShipCtrl:isBattleShipUnLocked())
  self.Node_Center_Hero_Artifact = SoraDGetChildByName(self, "Node_Center_Hero_Artifact")
  local nodeArray = {}
  table.insert(nodeArray, self.hero1:getParent())
  table.insert(nodeArray, self.hero2:getParent())
  if self.selectArtifact:isVisible() then
    table.insert(nodeArray, self.selectArtifact)
  end
  if self.Node_pet:isVisible() then
    table.insert(nodeArray, self.Node_pet)
  end
  if self.selectBattleShip:isVisible() then
    table.insert(nodeArray, self.selectBattleShip)
  end
  local btnShowCount = table.nums(nodeArray)
  if 5 <= btnShowCount then
    for k, v in pairs(nodeArray) do
      v:setScale(0.8)
    end
  end
  local paddingArray = {
    137,
    125.5,
    120,
    120
  }
  local paddingArrayTemp = {}
  for i = 1, btnShowCount - 1 do
    table.insert(paddingArrayTemp, paddingArray[i])
  end
  SoraDAlignNodeArrayOnCenterX(5, nodeArray, SoraDFIsRA(), paddingArrayTemp)
  if not equipmentCtrl:isAnyEquipRefineMaxLv() then
    return
  end
  if not self.selectArtifactHasInit then
    self.selectedArtifactIndex = artifactCtrl:getPageIndexHasMaxPower()
    self.selectArtifact:setSelectedHandler(handler(self, self.onArtifactNodeTouched))
    self.selectArtifactHasInit = true
  end
  local artifactCtrl = gametop.playertop_:getModule("artifactCtrl")
  local curIndex = self.selectedArtifactIndex
  local name = artifactCtrl:getRunePageName(curIndex)
  local suitType = artifactCtrl:getCurActivedSuitEffectType(curIndex)
  local data = {pageName = name, suitType = suitType}
  self.selectArtifact:initData(data)
  self.selectArtifact:setNameColor(cc.c3b(255, 255, 255))
end

function WorldDispatchArmyView:initPetNode()
  local isLocked = SoraDIsPetBuildingLocked()
  local petList = newPetCtrl:getPetList()
  if isLocked or #petList <= 0 then
    self.Node_pet:setVisible(false)
    return
  end
  if self.selectedPetId == 0 then
    self.selectedPetId = nil
  else
    self.selectedPetId = self.selectedPetId or newPetCtrl:getBestPetId()
  end
  self.Node_pet:initData(isLocked, self.selectedPetId, nil, petList, true)
  self.Node_pet:getTextLabel():setTextColor(cc.c3b(255, 255, 255))
  self.Node_pet:setSelectHandle(function(target, petId)
    SoraDPlaySound()
    self.selectedPetId = petId or self.selectedPetId
    self.Node_pet:initData(isLocked, self.selectedPetId, nil, petList, true)
    self.Node_pet:getTextLabel():setTextColor(cc.c3b(255, 255, 255))
    if target and not tolua.isnull(target) and target.closePanel then
      target:closePanel()
    end
  end)
  self.Node_pet:setDismissHandle(function(target, petId)
    self.selectedPetId = nil
    self.Node_pet:initData(isLocked, self.selectedPetId, nil, petList, true)
    self.Node_pet:getTextLabel():setTextColor(cc.c3b(255, 255, 255))
  end)
end

function WorldDispatchArmyView:onTipShow(button, event)
  if event == ccui.TouchEventType.ended then
    SoraDPlaySound()
    if button == self.imgCount then
      SoraDShowMsgTip(i18n("common_text_4344"))
    elseif button == self.imgWeight then
      if self.instanceType == gMapObjTypeDef.mapObjTypeResource or self.dispatchType == worldMapDefine.worldMapTipButtonType_caiji then
        SoraDShowMsgTip(i18n("common_text_4345"))
      elseif self.instanceType == gMapObjTypeDef.mapObjTypeNpc or self.otherData.mainInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeCorbanSheep or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeCorbanBull or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull or self.instanceType == gMapObjTypeDef.mapTypeStronghold or self.instanceType == gMapObjTypeDef.mapTypePve or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWildCattleRider then
        SoraDShowMsgTip(i18n("common_text_4346"))
      else
        SoraDShowMsgTip(i18n("lordskill_name_11001"))
      end
    end
  end
end

function WorldDispatchArmyView:refreshTxtPosX()
end

function WorldDispatchArmyView:onMessageListener()
  SoraDAddMessage(self, "MESSAGE_ARMY_TEAMORGANIZE_BACKDATA", handler(self, self.adaptTeam))
  SoraDAddMessage(self, "MESSAGE_MAINCITYVIEW_CITYBUFF_ADD", function(target, data)
    if data and data.data and data.data.effectType == 19 then
      self:updateCountLabel()
    end
  end)
  SoraDAddMessage(self, "MESSAGE_ARMY_DISMISSAL", handler(self, self.refreshView))
  SoraDAddMessage(self, "MESSAGE_UI_WARGEM_PAGE_SWITCH", function()
    self:refreshGemPage()
    self:refreshView()
  end)
  SoraDAddMessage(self, "MESSAGE_SERVER_ARTIFACT_RUNE_PAGE_SELECT_RSP_GOTTON", handler(self, self.initArtifactButton))
  SoraDAddMessage(self, "MESSAGE_SERVER_PET_UNLOCK", handler(self, self.initPetNode))
  SoraDAddMessage(self, "MESSAGE_ARMY_COMPILE_LIMIT_UPDATE", handler(self, self.initTeamBtns))
  SoraDAddMessage(self, "MESSAGE_ADD_HERO", handler(self, self.initHeroData))
end

function WorldDispatchArmyView:refreshGemPage()
  local warGemCtrl = SoraDGetModule("warGemCtrl")
  local curSelectedPage = warGemCtrl:getCurSelectedPage()
  local pageName = warGemCtrl:getWarGemSuperPageName(curSelectedPage)
  self.v.Button_wargem:setTitleText(pageName)
  SoraDAutoSizeButtonTextScale(self.v.Button_wargem, 0.9, 0.8)
end

function WorldDispatchArmyView:refreshView()
  local armyIDList = armyCtrl:getArmyIDList()
  if self.isIslandMode then
    armyIDList = islandCtrl:getArmyIDList()
  end
  self:getArmyListBySelectedType(self.selectType, armyIDList)
  self:updateCountLabel()
  self.curCount = 0
  self:refreshTbArmyData(armyIDList)
  self.labelNotice:setVisible(0 >= #self.tableArmy)
  self.btnConvene:setVisible(0 >= #self.tableArmy)
  self:initScroll()
  self:quickChoose(true)
end

function WorldDispatchArmyView:updateColor(...)
  if self.curCount >= self.allCount then
  elseif buildLogic.getExpArmyCount(self.selectedHeroList).total > buildLogic.getExpArmyCount(self.selectedHeroList).unchangesize then
    self.txtTotal:setColor(cc.c3b(0, 190, 30))
  else
    self.txtTotal:setColor(cc.c3b(236, 236, 236))
  end
end

function WorldDispatchArmyView:updateCountLabel()
  if self.allowMaxCount then
    self.allCount = math.min(buildLogic.getExpArmyCount(self.selectedHeroList).total, self.allowMaxCount)
  else
    self.allCount = buildLogic.getExpArmyCount(self.selectedHeroList).total
  end
  self.labelCount:setTextDirectionMark(TextDirectionMark.None)
  self.labelCount:setString(string.formatnumberthousands(math.floor(self.curCount)) .. "/")
  self.txtTotal:setString(string.formatnumberthousands(math.floor(self.allCount)))
  self:refreshTxtPosX()
  self:updateColor()
end

function WorldDispatchArmyView:initTeamBtns()
  local troopCount = armyCtrl:getTroopCompileLimit()
  local showDrop = 4 < troopCount
  self.dropDownBox:setVisible(showDrop)
  self.dropDownBox:initData()
  local node = self.panelTopBg:getChildByName("Node_troop")
  for i = 1, 4 do
    local btn = self.tabArmyTeamBtn[i] or SoraDGetChildByName(node, "Button_troop" .. tostring(i))
    if not btn then
      btn = self.tabArmyTeamBtn[1]:clone()
      btn:addTo(node)
      btn:setName("Button_troop" .. tostring(i))
    end
    btn:getChildByName("selectedFlag"):setVisible(false)
    local tName = armyCtrl:getArmyCompileName(i)
    SoraDGetChildByName(btn, "Text_1"):setString(tName or i)
    self.tabArmyTeamBtn[i] = btn
    btn:setTag(i)
    btn:addTouchEventListener(handler(self, self.btnTeamClickCallBack))
  end
  SoraDSingleLineScale(self.textTroops, 75, true)
  SoraDAlignNodeArrayOnCenterX(0, node:getChildren(), SoraDFIsRA(), {
    13,
    8,
    8,
    8
  })
  if showDrop then
    local leftX = self.textTroops:getPositionX() + SoraDFSign(self.textTroops:getContentSize().width + 25)
    node:setPositionX(SoraDFPosX(640) - leftX)
  else
    node:setPositionX(320)
  end
end

function WorldDispatchArmyView:btnTeamClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    local btnTag = button:getTag()
    self:selectedTeamByTag(btnTag)
  end
end

function WorldDispatchArmyView:onOptionSelected(tag, isUnlockBtn)
  if isUnlockBtn then
    SoraDShowVipLvNotEnough(i18n("common_text_1147"))
  else
    self:selectedTeamByTag(tag)
  end
end

function WorldDispatchArmyView:selectedTeamByTag(tag)
  local btnTag = tag
  local dataArmy = armyCtrl:getArmyCompileData(btnTag)
  local dataHeros = armyCtrl:getHerosCompileData(btnTag)
  local bAutoHero = armyCtrl:getMapAutoHeros(btnTag)
  local runePageIndex = armyCtrl:getCompileRunePage(btnTag)
  local petId = armyCtrl:getCompilePets(btnTag)
  print("petId===selectedTeamByTag", petId, btnTag)
  if petId ~= nil then
    self.selectedPetId = petId
    self:initPetNode()
  else
    self.selectedPetId = 0
    self:initPetNode()
  end
  if runePageIndex ~= nil then
    self.selectedArtifactIndex = runePageIndex
    self:initArtifactButton()
  end
  dump(dataArmy, "WorldDispatchArmyView:btnTeamClickCallBack:dataArmy")
  dump(dataHeros, "WorldDispatchArmyView:btnTeamClickCallBack:dataHeros")
  if dataArmy then
    self:adaptTeam(nil, {
      type = btnTag,
      redata = dataArmy,
      reHeros = dataHeros,
      bAutoHero = bAutoHero
    })
    self:updateSelectedTeam()
  else
    armyCtrl:getArmyCompile(btnTag)
    SoraDCreatrNewLoading(self)
  end
end

function WorldDispatchArmyView:updateSelectedTeam()
  for k, v in pairs(self.tabArmyTeamBtn) do
    if v:getTag() == self.selectedArmyTeamTag then
      v:getChildByName("selectedFlag"):setVisible(true)
    else
      v:getChildByName("selectedFlag"):setVisible(false)
    end
  end
  self.dropDownBox:setTitleByArmyIndex(self.selectedArmyTeamTag)
end

function WorldDispatchArmyView:adaptTeam(target, redata)
  SoraDCloseLoading(self)
  if redata and redata.redata then
    local compile = redata.redata
    local notEnough = false
    local noneCompile = true
    if next(compile) ~= nil then
      for _, v in pairs(compile) do
        if 0 < v then
          noneCompile = false
          break
        end
      end
    end
    if noneCompile then
      SoraDShowMsgBox(i18n("common_text_1449"), i18n("common_text_204"))
      return
    else
      self.selectedArmyTeamTag = redata.type
      self:updateSelectedTeam()
    end
  end
  if redata and redata.redata then
    local autoHero = redata.bAutoHero
    local compileHeros = clone(redata.reHeros) or {}
    if SoraDRescueTaskQueueExist() then
      local fList = {}
      for k, v in pairs(compileHeros) do
        if not SoraDIsHeroine(v) then
          table.insert(fList, v)
        end
      end
      compileHeros = fList
    end
    for i = 1, 2 do
      local curHeroId = compileHeros[i]
      local otherHeroId = compileHeros[3 - i]
      if curHeroId then
        local hero = heroMgr:getHero(curHeroId)
        if hero:getHeroWorkState() == gHeroStatus.battle then
          compileHeros[i] = nil
          if autoHero then
            for _, v in ipairs(self.curHeroIdList) do
              if otherHeroId ~= v then
                compileHeros[i] = v
                break
              end
            end
          end
        end
      end
    end
    local tempHeros = {}
    for i, v in pairs(compileHeros) do
      table.insert(tempHeros, v)
    end
    compileHeros = tempHeros
    local delayRefresh = false
    for i = 1, 2 do
      local curHeroId = compileHeros[i]
      if curHeroId then
        local hero = heroMgr:getHero(curHeroId)
        if hero:getHeroWorkState() == gHeroStatus.garrison then
          delayRefresh = true
        end
      end
    end
    if delayRefresh == true and not self.isIslandMode then
      SoraDShowMsgBox(i18n("common_text_4485"), i18n("common_text_204"), i18n("common_text_185"), function(type)
        if type == MSGBOX_CALLBACK_YES then
          self.selectedHeroList = compileHeros
          self:updateCountLabel()
          self:refreshHeroView()
          self:adaptArmy(target, redata)
          self:updateView()
        end
      end)
    else
      self.selectedHeroList = compileHeros
      self:updateCountLabel()
      self:refreshHeroView()
      self:adaptArmy(target, redata)
      self:updateView()
    end
  end
end

function WorldDispatchArmyView:adaptArmy(target, redata)
  if redata and redata.redata then
    local compile = redata.redata
    local notEnough = false
    self:resetArmySelect()
    local recordCount = 0
    local scaleCount = 1
    local needAdd = self.allCount
    for _, v in pairs(compile) do
      recordCount = recordCount + v
    end
    if recordCount > self.allCount then
      scaleCount = self.allCount / recordCount
    end
    for k, v in pairs(compile) do
      if 0 < v then
        local notFind = true
        local armyid = tonumber(k)
        local data = self.tableArmyData[armyid]
        if data then
          if v > data.armycount then
            notEnough = true
            self:setCurValByArmyid(armyid, math.floor(data.armycount * scaleCount))
            needAdd = needAdd - math.floor(v * scaleCount)
          else
            self:setCurValByArmyid(armyid, math.floor(v * scaleCount))
            needAdd = needAdd - math.floor(v * scaleCount)
          end
          notFind = false
        end
        if notFind then
          notEnough = true
        end
      end
    end
    if scaleCount < 1 and 0 < needAdd then
      for k, v in pairs(compile) do
        if 0 < v then
          local armyid = tonumber(k)
          local data = self.tableArmyData[armyid]
          if data then
            local armycount = self:getArmyCount(armyid)
            self:setCurValByArmyid(armyid, armycount)
            needAdd = needAdd - (armycount - math.floor(v * scaleCount))
          end
        end
        if needAdd <= 0 then
          break
        end
      end
    end
    if scaleCount < 1 then
      if self.isIslandMode then
        SoraDShowMsgBox(i18n("island_des_23"), i18n("common_text_204"))
      else
        SoraDShowMsgBox(i18n("common_text_2025"), i18n("common_text_204"))
      end
    elseif notEnough then
      if self.isIslandMode then
        SoraDShowMsgBox(i18n("island_des_23"), i18n("common_text_204"))
      else
        SoraDShowMsgBox(i18n("common_text_1447"), i18n("common_text_204"))
      end
    end
  end
end

function WorldDispatchArmyView:sortArmyListByLv(armyIDList)
  self.tableArmy = {}
  table.sort(armyIDList, function(army1, army2)
    local armyID1 = army1 % 1000
    local armyID2 = army2 % 1000
    local armyLv1 = armyID1 % 100
    local armyLv2 = armyID2 % 100
    if armyLv1 == armyLv2 then
      return armyID1 < armyID2
    else
      return armyLv1 > armyLv2
    end
  end)
end

function WorldDispatchArmyView:sortArmyListBySpeed(armyIDList)
  self.tableArmy = {}
  table.sort(armyIDList, function(army1, army2)
    local speed1 = armyltCtrl.getArmyAttrAndSp(army1, ARMY_ATTR.SPEED)
    local speed2 = armyltCtrl.getArmyAttrAndSp(army2, ARMY_ATTR.SPEED)
    if speed1 == speed2 then
      local armyID1 = army1 % 1000
      local armyID2 = army2 % 1000
      local armyLv1 = armyID1 % 100
      local armyLv2 = armyID2 % 100
      if armyLv1 == armyLv2 then
        return armyID1 < armyID2
      else
        return armyLv1 > armyLv2
      end
    else
      return speed1 > speed2
    end
  end)
end

function WorldDispatchArmyView:sortArmyListByWeight(armyIDList)
  self.tableArmy = {}
  table.sort(armyIDList, function(army1, army2)
    local weight1 = armyltCtrl.getArmyAttrAndSp(army1, ARMY_ATTR.FREE_WEIGHT)
    local weight2 = armyltCtrl.getArmyAttrAndSp(army2, ARMY_ATTR.FREE_WEIGHT)
    if army1 == 701 then
      return true
    end
    if army2 == 701 then
      return false
    end
    if weight1 == weight2 then
      local armyID1 = army1 % 1000
      local armyID2 = army2 % 1000
      local armyLv1 = armyID1 % 100
      local armyLv2 = armyID2 % 100
      if armyLv1 == armyLv2 then
        return armyID1 < armyID2
      else
        return armyLv1 > armyLv2
      end
    else
      return weight1 > weight2
    end
  end)
end

function WorldDispatchArmyView:troopTypeSelectedCallback(selectType)
  if self.tableArmy and type(self.tableArmy) == "table" and not next(self.tableArmy) then
    return
  end
  self:resetArmySelect()
  local armyIDList = armyCtrl:getArmyIDList()
  if self.isIslandMode then
    armyIDList = armyCtrl:getAllHighestArmyIds()
  end
  self.selectType = selectType
  self:getArmyListBySelectedType(selectType, armyIDList)
  for _, v in ipairs(armyIDList) do
    local haveCount = armyCtrl:getArmyCount(v, gArmyOpType.normal)
    if self.isIslandMode then
      haveCount = self.allCount
    end
    if 0 < haveCount then
      table.insert(self.tableArmy, v)
    end
  end
  self:initScroll()
  self:quickChoose(true)
end

function WorldDispatchArmyView:getArmyListBySelectedType(selectType, armyIDList)
  if selectType == 1 then
    self:sortArmyListByLv(armyIDList)
  elseif selectType == 2 then
    self:sortArmyListBySpeed(armyIDList)
  elseif selectType == 3 then
    self:sortArmyListByWeight(armyIDList)
  end
end

function WorldDispatchArmyView:calculateCostPhysical(...)
  local buffid = skillDes.getBuffID(13026)
  local isOpen, buff = buffCtrl:isBuffOpen(buffid)
  local costPhysical
  if isOpen then
    local lordInfo = lordInfoCtrl:getLordInfo()
    local baseHealth = lordInfo.base.health
    if baseHealth > lordInfo.physicalUpper then
      costPhysical = lordInfo.physicalUpper
    else
      local modPhysical = baseHealth % 5
      costPhysical = baseHealth - modPhysical
    end
  end
  return costPhysical
end

function WorldDispatchArmyView:refreshTbArmyData(armyIDList)
  if self.isIslandMode then
    local list = islandCtrl:getArmyList()
    for _, armyId in ipairs(armyIDList) do
      local armyNum = math.min(list[tostring(armyId)], gConstValue.PVE_MAX_TROOP_NUM)
      table.insert(self.tableArmy, tonumber(armyId))
      local weight = armyDesRead.getFreeWeightAndSp(tonumber(armyId))
      self.tableArmyData[tonumber(armyId)] = {
        armyid = tonumber(armyId),
        armycount = armyNum,
        curCount = 0,
        weight = weight
      }
    end
  else
    for _, v in ipairs(armyIDList) do
      local haveCount = armyCtrl:getArmyCount(v, gArmyOpType.normal)
      if 0 < haveCount then
        table.insert(self.tableArmy, v)
        local weight = armyDesRead.getFreeWeightAndSp(v)
        self.tableArmyData[v] = {
          armyid = v,
          armycount = haveCount,
          curCount = 0,
          weight = weight
        }
      end
    end
  end
end

function WorldDispatchArmyView:initData(armyViewData, leftTime)
  dump(armyViewData, "armyViewData====adaad", 10)
  self.isIslandMode = armyViewData.isIslandMode
  self.isKingHoardMode = armyViewData.isKingHoardMode
  self.expType = gMapExpeditionType.plain
  self.leftTime = leftTime
  self.curTime = SoraDGetSocketTime()
  self.toPoint = armyViewData.toPoint
  self.dispatchType = armyViewData.dispatchType
  self.instanceID = armyViewData.instanceID
  self.instanceType = armyViewData.instanceType
  self.monsterPower = armyViewData.monsterPower or 0
  self.massInstanceType = armyViewData.massInstanceType
  self.shareOK = armyViewData.shareOk or false
  self.needArmyList = armyViewData.needArmyList
  local selectType = gMapDispatchArmyType[self.instanceType] or 1
  self.selectType = selectType
  local targetName = gClientTargetBuildName[self.instanceType]
  if armyViewData.massInstanceType then
    targetName = gClientTargetBuildName[armyViewData.massInstanceType]
  end
  if armyViewData.targetName then
    targetName = armyViewData.targetName
  end
  if armyViewData.otherData then
    self.otherData = armyViewData.otherData
  end
  self.expType = self:initExpType()
  local armyIDList = armyCtrl:getArmyIDList()
  if self.isIslandMode then
    armyIDList = islandCtrl:getArmyIDList()
    self.btnCountPlus:setVisible(false)
  elseif worldMapDefine.isInCloudPeak() then
    self.btnCountPlus:setVisible(false)
  end
  self:getArmyListBySelectedType(selectType, armyIDList)
  if armyViewData.maxCount then
    self.allowMaxCount = armyViewData.maxCount
  end
  self:initHeroData()
  self:refreshHeroView()
  self:updateCountLabel()
  self.curCount = 0
  self.dropUpBox:initData(selectType)
  self:refreshTbArmyData(armyIDList)
  self.labelNotice:setVisible(0 >= #self.tableArmy)
  self.btnConvene:setVisible(0 >= #self.tableArmy)
  self.labelCount:setTextDirectionMark(TextDirectionMark.None)
  self.labelCount:setString(string.formatnumberthousands(math.floor(self.curCount)) .. "/")
  self.txtTotal:setString(string.formatnumberthousands(math.floor(self.allCount)))
  self:refreshTxtPosX()
  self:updateColor()
  local size = self.scroll:getContentSize()
  local posY = self.scroll:getPositionY()
  self.Node_tip:setVisible(false)
  self.Image_shadow:setVisible(true)
  if self.instanceType == gMapObjTypeDef.mapObjTypeResource or self.dispatchType == worldMapDefine.worldMapTipButtonType_caiji then
    self.imgWeight:loadTexture(resDesRead.getSIcon(self.otherData.resourceType), ccui.TextureResType.plistType)
    self.imgWeight:ignoreContentAdaptWithSize(true)
    self.imgWeight:setScale(1.1)
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeBattlefieldSite or self.massInstanceType == gMapObjTypeDef.mapObjTypeBattlefieldSite then
    local x, y, type, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    targetName = worldMapDefine.getPyramidbuildingName(subMapType)
  elseif self.instanceType == gMapObjTypeDef.mapTypeFamousCity or self.massInstanceType == gMapObjTypeDef.mapTypeFamousCity then
    local famousCityRead = include("famousCityRead")
    local x, y, type, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    targetName = famousCityRead.getFamousCityName(tonumber(objId))
  elseif self.instanceType == gMapObjTypeDef.mapObjNewTrialCity or self.massInstanceType == gMapObjTypeDef.mapObjNewTrialCity then
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    if subMapType == 1 then
      targetName = i18n("devilvalley_text_48")
    else
      targetName = i18n("buildDes_name_103")
    end
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeRemainsWar or self.massInstanceType == gMapObjTypeDef.mapObjTypeRemainsWar then
    local remainsWarRead = include("remainsWarRead")
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    targetName = remainsWarRead.getBuildName(objId)
  elseif self.instanceType == gMapObjTypeDef.mapTypeCloudPeakWarBuilding then
    local cloudPeakRead = include("cloudPeakRead")
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    targetName = cloudPeakRead.getCloudPeakBuildingName(objId)
  elseif self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarBuild then
    local anaStarWarRead = include("anaStarWarRead")
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    targetName = anaStarWarRead.getBuildNameByBuildID(objId)
  elseif worldMapDefine.isInCloudPeak() and self.instanceType == gMapObjTypeDef.mapObjTypeBoss or self.instanceType == gMapObjTypeDef.mapTypeDragon then
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    local bossData = worldMapDefine.getWorldBossShow(objId)
    targetName = i18n(bossData.name)
  elseif self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc then
    local x, y, objType, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
    local anaStarWarRead = include("anaStarWarRead")
    local bossData = anaStarWarRead.getMonsterConfig(objId)
    targetName = i18n(bossData.name)
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeNpc then
    local physicalCount = 5
    local killRate = 1
    local remainCount = lordInfoCtrl:getDropGainBuffCount(811039) or 0
    if 0 < remainCount then
      killRate = 2
    end
    local beautyKillRate = buffCtrl:getBuffEffect(gBuffEffect.MUTI_KILL, gBuffSource.PERI) or 1
    if beautyKillRate ~= 1 then
      killRate = beautyKillRate
    end
    self.labelWeight:setString(physicalCount * killRate)
    self.imgWeight:ignoreContentAdaptWithSize(true)
    self.imgWeight:loadTexture(self._cfg.pngLingzhu, ccui.TextureResType.plistType)
    self.imgWeight:setScale(0.96)
    local costPhysical = self:calculateCostPhysical()
    if costPhysical then
      self.labelWeight:setString(costPhysical)
    end
    self.btnPhysicalPlus:loadTextures("common_plus02.png", "common_plus02.png", "common_plus02.png", ccui.TextureResType.plistType)
    size.height = size.height - self._cfg.scroll.monsterOffsetH
    self.Node_tip:setVisible(true)
    self.Image_shadow:setVisible(false)
  elseif self.otherData.mainInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeCorbanBull or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWildCattleRider or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
    self.nodeTitle:setTitle(i18n("common_text_292"))
    self.labelGoTitle:setString(i18n("common_text_292"))
    self.labelWeight:setString("20")
    self.imgWeight:ignoreContentAdaptWithSize(true)
    self.imgWeight:loadTexture(self._cfg.pngLingzhu, ccui.TextureResType.plistType)
    self.imgWeight:setScale(0.96)
    self.btnPhysicalPlus:loadTextures("common_plus02.png", "common_plus02.png", "common_plus02.png", ccui.TextureResType.plistType)
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_xuanZhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_fanjiXuanzhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_twoCityNeutralBuild_xuanZhan then
    if self.instanceType == gMapObjTypeDef.mapObjTypeTory then
      targetName = i18n("Treasure_title_01")
    end
    self.nodeTitle:setTitle(i18n("common_text_292"))
    self.labelGoTitle:setString(i18n("common_text_292"))
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_zuduiYuanzhu then
    self.nodeTitle:setTitle(i18n("common_text_483"))
    self.labelGoTitle:setString(i18n("common_text_483"))
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_xiefang then
  elseif self.instanceType == gMapObjTypeDef.mapTypeStronghold then
    self.nodeTitle:setTitle(i18n("hero_stronghold_title_05"))
    self.labelWeight:setString("20")
    self.imgWeight:ignoreContentAdaptWithSize(true)
    self.imgWeight:loadTexture(self._cfg.pngLingzhu, ccui.TextureResType.plistType)
    self.imgWeight:setScale(0.96)
    self.btnPhysicalPlus:loadTextures("common_plus02.png", "common_plus02.png", "common_plus02.png", ccui.TextureResType.plistType)
    if self.monsterPower and self.monsterPower > 0 then
      size.height = size.height - self._cfg.scroll.monsterOffsetH
      self.Node_tip:setVisible(true)
      self.Image_shadow:setVisible(false)
    end
  elseif self.instanceType == gMapObjTypeDef.mapTypePve then
    targetName = i18n("island_title_27")
    self.nodeTitle:setTitle(i18n("hero_stronghold_title_05"))
    local needHp = 0
    if self.otherData.islandPveType == gIslandPveType.daily then
      needHp = tonumber(constantRead.getValueByKey("DAILY_PVE_STRENGTH"))
    elseif self.otherData.islandPveType == gIslandPveType.main then
      needHp = tonumber(constantRead.getValueByKey("PVE_STRENGTH"))
    end
    self.labelWeight:setString(tostring(needHp))
    self.imgWeight:ignoreContentAdaptWithSize(true)
    self.imgWeight:loadTexture(self._cfg.pngLingzhu, ccui.TextureResType.plistType)
    self.imgWeight:setScale(0.96)
    self.btnPhysicalPlus:loadTextures("common_plus02.png", "common_plus02.png", "common_plus02.png", ccui.TextureResType.plistType)
    self.monsterPower = 0
    if self.monsterPower and self.monsterPower > 0 then
      size.height = size.height - self._cfg.scroll.monsterOffsetH
      self.Node_tip:setVisible(true)
      self.Image_shadow:setVisible(false)
    end
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeTory then
    targetName = i18n("Treasure_title_01")
  else
    if self.instanceType == gMapObjTypeDef.mapTypeRoseGarden then
      local showInfo = include("allianceRoseGardenltCtrl").getShowInfo()
      targetName = i18n(showInfo.activityName)
    else
    end
  end
  if gFormationIsLocked() then
    size.height = size.height + self._cfg.scroll.troopOffsetH
    posY = posY + self._cfg.scroll.troopOffsetH
    self.panelTopBg:setVisible(false)
    local y = self.topNode:getPositionY() + self._cfg.scroll.troopOffsetH
    self.topNode:setPositionY(y)
  end
  self.scroll:setContentSize(size)
  self.scroll:setPositionY(posY)
  if targetName then
    self.nodeTitle:setTitle(i18n("common_text_3515", {
      aim = i18n(targetName)
    }))
  end
  if self.otherData.monsterType and (self.otherData.monsterType == RUNINS_MONSTER_BATTLE_TYPE.BLUE_DRAKE or self.otherData.monsterType == RUNINS_MONSTER_BATTLE_TYPE.RED_DRAKE or self.otherData.monsterType == RUNINS_MONSTER_BATTLE_TYPE.ANCIENT_DRAGON or self.otherData.monsterType == RUNINS_MONSTER_BATTLE_TYPE.NIGHTMARE_DRAGON) then
    self.labelWeight:setString("0")
  end
  if self.dispatchType == worldMapDefine.worldMapTipButtonType_xiefang or self.dispatchType == worldMapDefine.worldMapTipButtonType_shibingYuabzhu then
    self.expType = gMapExpeditionType.help
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.massInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.massInstanceType == gMapObjTypeDef.mapTypeCorbanSheep or self.massInstanceType == gMapObjTypeDef.mapTypeCorbanBull or self.massInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.massInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.massInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
    self.expType = gMapExpeditionType.boss
  elseif self.massInstanceType == gMapObjTypeDef.mapTypeGodBeast or self.instanceType == gMapObjTypeDef.mapTypeGodBeast then
    self.expType = gMapExpeditionType.beast
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeNpc or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc then
    self.expType = gMapExpeditionType.npc
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_caiji or self.instanceType == gMapObjTypeDef.mapObjTypeResource then
    if self.otherData and self.otherData.resourceType then
      if self.otherData.resourceType == gIDDef.WOOD then
        self.expType = gMapExpeditionType.collect_wood
      elseif self.otherData.resourceType == gIDDef.FOOD then
        self.expType = gMapExpeditionType.collect_food
      elseif self.otherData.resourceType == gIDDef.IRON then
        self.expType = gMapExpeditionType.collect_iron
      elseif self.otherData.resourceType == gIDDef.MITHRIL then
        self.expType = gMapExpeditionType.collect_mithril
      elseif self.otherData.resourceType == gIDDef.GOLD then
        self.expType = gMapExpeditionType.collect_gold
      end
    end
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeAllianceBuild or self.instanceType == gMapObjTypeDef.mapObjTypeAllianceBuild then
    self.expType = gMapExpeditionType.alliance_build
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeCastale or self.instanceType == gMapObjTypeDef.mapObjTypeCastale then
    self.expType = gMapExpeditionType.kingdom_build
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeFortress or self.instanceType == gMapObjTypeDef.mapObjTypeFortress then
    self.expType = gMapExpeditionType.fortress
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeBattery or self.instanceType == gMapObjTypeDef.mapObjTypeBattery or self.instanceType == gMapObjTypeDef.mapObjNewTrialCity or self.massInstanceType == gMapObjTypeDef.mapObjNewTrialCity then
    self.expType = gMapExpeditionType.battery
  elseif self.instanceType == gMapObjTypeDef.mapObjTypePlayer then
    self.expType = gMapExpeditionType.castle
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_jianzao and self.instanceType == gMapObjTypeDef.mapObjTypeSuperResource then
    self.expType = gMapExpeditionType.alliance_super_build
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_yayun or self.dispatchType == worldMapDefine.worldMapTipButtonType_bangzhuyayun then
    self.expType = gMapExpeditionType.escort
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_lueduo then
    self.expType = gMapExpeditionType.plunder_escort
  elseif self.instanceType == gMapObjTypeDef.mapTypeStronghold or self.instanceType == gMapObjTypeDef.mapTypePve then
    self.expType = gMapExpeditionType.stronghold
  elseif self.instanceType == gMapObjTypeDef.mapTypePlain then
    self.expType = gMapExpeditionType.plain
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeCampsite then
    self.expType = gMapExpeditionType.campsite
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeRelics then
    self.expType = gMapExpeditionType.relics
  elseif self.instanceType == gMapObjTypeDef.worldMapTipButtonType_wajue or worldMapDefine.worldMapTipButtonType_zuduiwajue then
    self.expType = gMapExpeditionType.all
  end
  if self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
    self.labelWeight:setString("0")
  end
  if device.platform == "mac" then
  end
  self:initScroll()
  if self.instanceType == gMapObjTypeDef.mapTypePve then
    local guideCtrl = gametop.playertop_:getModule("guideCtrl")
    local isGuideNotDone = guideCtrl:isGuideNotCompleted(gGuideModule.PVE_CHAPTER)
    if isGuideNotDone then
      self:quickChoose(true)
    end
  else
    self:quickChoose(true)
  end
  if worldMapDefine.isInCloudPeak() then
    self.btnPhysicalPlus:setVisible(false)
    self.labelWeight:setVisible(false)
    self.imgWeight:setVisible(false)
  end
end

function WorldDispatchArmyView:initHeroData()
  self.curHeroList = {}
  self.curHeroIdList = {}
  self.garrisonHeroList = {}
  self.recommendationHeroIdList = {}
  local allHeros = heroMgr:getAllHeros()
  if SoraDRescueTaskQueueExist() then
    local fList = {}
    for k, v in pairs(allHeros) do
      if not SoraDIsHeroine(v.id) then
        fList[k] = v
      end
    end
    allHeros = fList
  end
  for k, v in pairs(allHeros) do
    if v:getHeroWorkState() ~= gHeroStatus.battle then
      self.curHeroList[k] = v
    end
  end
  if tonumber(SoraDGetConstantValue("RECOMMENDED_HERO_CLV")) > tonumber(gGetCastleLv()) and table.nums(self.curHeroList) > 1 then
    self.curHeroIdList = {}
    for k, _ in pairs(self.curHeroList) do
      table.insert(self.curHeroIdList, k)
    end
    table.sort(self.curHeroIdList, function(a, b)
      local aHero = self.curHeroList[a]
      local bHero = self.curHeroList[b]
      local aCombat = aHero:getCombat()
      local bCombat = bHero:getCombat()
      if aCombat ~= bCombat then
        return aCombat > bCombat
      end
      return a < b
    end)
  else
    self.curHeroIdList = expeditionTypeltCtrl.sortHeros(self.expType, self.curHeroList)
  end
  for i = #self.curHeroIdList, 1, -1 do
    local heroId = self.curHeroIdList[i]
    local hero = self.curHeroList[heroId]
    if hero:getHeroWorkState() == gHeroStatus.garrison then
      table.insert(self.garrisonHeroList, heroId)
      table.remove(self.curHeroIdList, i)
    end
  end
  for i = #self.garrisonHeroList, 1, -1 do
    local heroId = self.garrisonHeroList[i]
    table.insert(self.curHeroIdList, heroId)
  end
  for i = 1, 2 do
    if self.curHeroIdList[i] then
      self.recommendationHeroIdList[self.curHeroIdList[i]] = true
    end
  end
  dump(self.curHeroList, "curHeroList", 10)
  dump(self.curHeroIdList, "curHeroIdList", 10)
  dump(self.garrisonHeroList, "garrisonHeroList", 10)
  dump(self.recommendationHeroIdList, "recommendationHeroIdList", 10)
  if not (not self.isFirstIn or SoraDIsGameGuide()) or self.expType == gMapExpeditionType.escort then
    self.isFirstIn = false
    self:autoSelectHeros()
  end
end

function WorldDispatchArmyView:autoSelectHeros()
  for i = 1, 2 do
    local heroId = self.curHeroIdList[i]
    if heroId then
      local isHave = false
      for i, v in ipairs(self.garrisonHeroList) do
        if v == heroId then
          isHave = true
          break
        end
      end
      if isHave == false then
        table.insert(self.selectedHeroList, heroId)
      end
    end
  end
  dump(self.selectedHeroList, "selectedHeroList", 10)
end

function WorldDispatchArmyView:refreshHeroView()
  for i = 1, 2 do
    local data = {
      order = i,
      heroId = self.selectedHeroList[i]
    }
    self.tabHeros[i]:initData(data)
    self.tabHeros[i]:forceShowOrder()
  end
end

function WorldDispatchArmyView:onRemoveHero(redata)
  local order = redata.order
  local curHeroId = redata.heroId
  self.selectedHeroList[order] = nil
  self:updateCountLabel()
  self:refreshHeroView()
  self:updateView()
  if self.curCount > self.allCount then
    self:quickChoose(false)
    self:quickChoose(true)
  end
end

function WorldDispatchArmyView:onClickedHero(redata)
  local order = redata.order
  local curHeroId = redata.heroId
  local otherHeroId
  if order == 1 then
    otherHeroId = self.hero2:getData().heroId
  elseif order == 2 then
    otherHeroId = self.hero1:getData().heroId
  end
  self.showHeroIdList = {}
  self.recommendationHeroId = nil
  if curHeroId then
    table.insert(self.showHeroIdList, curHeroId)
  end
  for i, hId in ipairs(self.curHeroIdList) do
    if (otherHeroId and hId ~= otherHeroId or otherHeroId == nil) and hId ~= curHeroId then
      table.insert(self.showHeroIdList, hId)
    end
  end
  for i = 1, #self.showHeroIdList do
    local hId = self.showHeroIdList[i]
    if self.recommendationHeroIdList[hId] == true then
      self.recommendationHeroId = hId
      break
    end
  end
  dump(self.showHeroIdList, "showHeroIdList", 10)
  dump(self.recommendationHeroId, "recommendationHeroId", 10)
  self.heroListData = {}
  local heroDataList = {}
  for i, heroId in ipairs(self.showHeroIdList) do
    local heroData = heroAppointCtrl:getHeroData(heroId, false, true)
    if i == 1 then
      if self.selectedHeroList[order] ~= nil then
        heroData.order = order
      end
      self.heroListData.selectedHeroData = heroData
    end
    if curHeroId == heroId then
      self.heroListData.oldHeroData = heroData
    end
    if heroId == self.recommendationHeroId then
      heroData.isRecommended = true
    end
    table.insert(heroDataList, heroData)
  end
  self.heroListData.heroDataList = heroDataList
  self.heroListData.title = i18n("common_text_4481")
  self.selectedOrder = order
  if self:canOpenSelectionView() then
    self.selectionView = SoraDCreatePanel("heroSelectionView")
    self.selectionView:setIsAutoCloseMode(false)
    self.selectionView:setHandler(handler(self, self.onHeroSelected))
    self.selectionView:initData(self.heroListData)
    self.selectionView:show()
  end
end

function WorldDispatchArmyView:canOpenSelectionView()
  local canOpen = true
  if not next(self.heroListData.heroDataList) then
    SoraDShowMsgBox(i18n("common_text_4484"), i18n("hero_assign_button_03"), nil, function(type)
      if type == MSGBOX_CALLBACK_YES then
        local panel = SoraDCreatePanel("heroDrawCardView")
        panel:switchToHeroPage()
        panel:show()
      end
    end)
    canOpen = false
  end
  return canOpen
end

function WorldDispatchArmyView:onHeroSelected(heroData, event)
  local oldHeroId
  if self.heroListData.oldHeroData then
    oldHeroId = self.heroListData.oldHeroData:getHeroId()
  end
  local newHeroId = heroData:getHeroId()
  if event == "confirm" then
    if oldHeroId == nil or oldHeroId ~= newHeroId then
      local function setNewHero()
        self.selectedHeroList[self.selectedOrder] = newHeroId
        
        self:updateCountLabel()
        self:refreshHeroView()
        self:updateView()
        if self.isSelectFull and self.curCount > self.allCount then
          self:quickChoose(false)
          self:quickChoose(true)
        end
        if self.selectionView then
          self.selectionView:closePanel()
          self.selectionView = nil
        end
        if self.isIslandMode and self.curCount > self.allCount then
          self:quickChoose(false)
          self:quickChoose(true)
        end
      end
      
      local newHero = heroMgr:getHero(newHeroId)
      if newHero:getHeroWorkState() == gHeroStatus.garrison and not self.isIslandMode then
        SoraDShowMsgBox(i18n("common_text_4485"), i18n("common_text_204"), i18n("common_text_185"), function(type)
          if type == MSGBOX_CALLBACK_YES then
            setNewHero()
          end
        end)
      else
        setNewHero()
      end
    elseif self.selectionView then
      self.selectionView:closePanel()
      self.selectionView = nil
    end
  elseif event == "detail" then
    if self.heroListData.oldHeroData == nil or self.heroListData.oldHeroData == heroData then
      local panel = SoraDCreatePanel("heroAdditionDetailViewWithPet")
      panel:initWithData({
        oldHeroId or newHeroId
      }, self.expType, self.selectedPetId)
      panel:show()
    else
      local panel = include("heroAdditionCompareDetailView").new()
      panel:initWithData(oldHeroId, newHeroId, self.expType)
      panel:show()
    end
  end
end

function WorldDispatchArmyView:updateMaxCount(maxCount)
  self.allowMaxCount = maxCount
  self:updateCountLabel()
  if self.isSelectFull and self.curCount > self.allCount then
    self:quickChoose(true)
  end
end

function WorldDispatchArmyView:initScroll()
  local cellH = 119
  local topPadding = 12
  local bottomPadding = 12
  self.scroll:removeAllChildren()
  self.tableArmySingle = {}
  self.tableSpare = {}
  self.allSingles = {}
  local scrollH = math.max(self.scroll:getContentSize().height, cellH * #self.tableArmy + topPadding + bottomPadding)
  self.scroll:setInnerContainerSize(cc.size(640, scrollH))
  local topY = scrollH - topPadding
  for i, armyid in ipairs(self.tableArmy) do
    local posY = topY - (i - 1) * cellH
    table.insert(self.tableArmySingle, {
      armyid = armyid,
      posY = posY,
      point = nil
    })
  end
  self:updateScrollList()
end

function WorldDispatchArmyView:updateScrollList()
  local scrollInner = self.scroll:getInnerContainer()
  local offsetY = -scrollInner:getPositionY()
  local scrollH = self.scroll:getContentSize().height
  local tableShowH = {
    beginY = math.max(0, offsetY - 0.5 * scrollH),
    endY = offsetY + 1.5 * scrollH
  }
  for i, v in ipairs(self.tableArmySingle) do
    if v.point then
      if v.posY < tableShowH.beginY or v.posY > tableShowH.endY then
        v.point:setVisible(false)
        table.insert(self.tableSpare, v.point)
        v.point = nil
      end
    elseif tableShowH.beginY <= v.posY and tableShowH.endY >= v.posY then
      local single
      if 0 < #self.tableSpare then
        single = table.remove(self.tableSpare)
        single:setVisible(true)
      else
        single = SoraDCreatePanel("worldDispatchArmySingle")
        single:setSliderChangeBack(handler(self, self.singleSliderChange))
        single:setScroll(self.scroll)
        single:addTo(self.scroll)
        single:setVisible(true)
        if self.isIslandMode then
          single:setHideDissolve(true)
        end
        table.insert(self.allSingles, single)
      end
      local armyData = self.tableArmyData[v.armyid]
      if armyData then
        single:initData(armyData)
      end
      single:setPosition(cc.p(SoraDFPosXForRight(0), v.posY))
      single:setLocalZOrder(i)
      v.point = single
    end
  end
end

function WorldDispatchArmyView:singleSliderChange(target, data)
  self:setCurValByArmyid(data.armyid, data.armycount)
  self:updateView()
end

function WorldDispatchArmyView:initBattleShip()
  if not battleShipCtrl:isBattleShipUnLocked() then
    return
  end
  local maxArmyType = battleShipltCtrl.getMaxCountArmyType(self.tableArmyData)
  self.curShipType = battleShipltCtrl.getMapBattleShipTypeByArmyType(maxArmyType)
  self.curShipName = self.curShipType and battleShipltCtrl.getShipName(self.curShipType) or ""
  local battleShipBtnData = {
    pageName = self.curShipName,
    isBattleShip = true,
    shipType = self.curShipType
  }
  self.selectBattleShip:initData(battleShipBtnData)
  self.selectBattleShip:setNameColor(cc.c3b(255, 255, 255))
  if not self.selectBattleShipHasInit then
    self.selectBattleShip:setSelectedHandler(handler(self, self.onBattleShipNodeTouched))
    self.selectBattleShipHasInit = true
  end
end

function WorldDispatchArmyView:updateView()
  self:updateLabelAndWeight()
  if self.isIslandMode then
    self:uiForIsland()
  elseif self.isKingHoardMode then
    self:uiForKingHorad()
  else
    self:updateMoveTime()
  end
  self:updateAllTroopPower()
  self:updateScroll()
  self:initBattleShip()
end

function WorldDispatchArmyView:updateAllTroopPower()
  local power = 0
  for k, v in pairs(self.tableArmyData) do
    local tempPower = armyltCtrl.getArmyAttrAndSp(v.armyid, ARMY_ATTR.POWER) or 0
    power = power + tempPower * v.curCount
  end
  for i, v in pairs(self.selectedHeroList) do
    local hero = heroMgr:getHero(v)
    power = power + hero:getCombat()
  end
  self.labTroopPower:setString(i18n("common_text_4400", {
    num = string.formatnumberthousands(math.floor(power))
  }))
  if SoraDFIsRA() then
    self.btnHeroDetail:setPositionX(self.labTroopPower:getPositionX() - self.labTroopPower:getContentSize().width - 30)
  else
    self.btnHeroDetail:setPositionX(self.labTroopPower:getPositionX() + self.labTroopPower:getContentSize().width + 30)
  end
  if self.instanceType == gMapObjTypeDef.mapObjTypeNpc or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc or self.instanceType == gMapObjTypeDef.mapTypeStronghold and self.monsterPower and 0 < self.monsterPower or self.instanceType == gMapObjTypeDef.mapTypePve and self.monsterPower and 0 < self.monsterPower then
    local str, color, img = self:getMonsterTipAndColor(self.monsterPower, power)
    self.labelMonsterTip:setString(str)
    self.labelMonsterTip:setColor(color)
    self.imgMonsterBg:loadTexture(img, ccui.TextureResType.plistType)
    self.imgMonsterBg2:loadTexture(img, ccui.TextureResType.plistType)
  end
end

function WorldDispatchArmyView:getMonsterTipAndColor(monsterPower, myPower)
  local str, color, img
  if myPower <= 0.2 * monsterPower then
    str = i18n("common_text_4403")
    color = cc.c3b(250, 214, 214)
    img = "common_yh_tydt_ht.png"
  elseif myPower <= 0.5 * monsterPower then
    str = i18n("common_text_4404")
    color = cc.c3b(250, 214, 214)
    img = "common_yh_tydt_ht.png"
  elseif myPower <= 2 * monsterPower then
    str = i18n("common_text_4405")
    color = cc.c3b(234, 234, 234)
    img = "common_yh_tydt_hs.png"
  elseif myPower <= 5 * monsterPower then
    str = i18n("common_text_4406")
    color = cc.c3b(171, 255, 184)
    img = "common_yh_tydt_lt.png"
  else
    str = i18n("common_text_4407")
    color = cc.c3b(171, 255, 184)
    img = "common_yh_tydt_lt.png"
  end
  return str, color, img
end

function WorldDispatchArmyView:updateScroll()
  for i, v in pairs(self.tableArmySingle) do
    if v.point then
      v.point:updateView()
    end
  end
end

function WorldDispatchArmyView:updateLabelAndWeight()
  self.labelCount:setTextDirectionMark(TextDirectionMark.None)
  self.labelCount:setString(string.formatnumberthousands(math.floor(self.curCount)) .. "/")
  self.txtTotal:setString(string.formatnumberthousands(math.floor(self.allCount)))
  self:refreshTxtPosX()
  self:updateColor()
  if self.curCount <= 0 then
    self.btnQuickChoose:setTitleText(i18n("common_text_852"))
  else
    self.btnQuickChoose:setTitleText(i18n("common_text_4419"))
  end
  if self.instanceType ~= gMapObjTypeDef.mapObjTypeNpc and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapObjTypeBoss and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeHeroBattleBoss1 and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeHeroBattleBoss2 and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeAnaStarWarBoss and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeAnaStarWarNpc and self.instanceType ~= gMapObjTypeDef.mapTypeStronghold and self.instanceType ~= gMapObjTypeDef.mapTypePve and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeWildCattleRider and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeCorbanSheep and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeCorbanBull and self.otherData.mainInstanceType ~= gMapObjTypeDef.mapTypeWorshipBull then
    self.curWeight = 0
    local addWeight = 1 + kingdomMapCtrl:getArmyWeightPlus(self.selectedHeroList)
    for i, v in pairs(self.tableArmyData) do
      self.curWeight = self.curWeight + v.weight * v.curCount * addWeight
    end
    if self.instanceType == gMapObjTypeDef.mapObjTypeResource or self.dispatchType == worldMapDefine.worldMapTipButtonType_caiji then
      if self.otherData.resourceType == gIDDef.GOLD then
        self.curWeight = self.curWeight / 1000
      elseif self.otherData.resourceType == gIDDef.IRON then
        self.curWeight = self.curWeight / 6
      elseif self.otherData.resourceType == gIDDef.MITHRIL then
        self.curWeight = self.curWeight / 24
      end
    end
    self.labelWeight:setString(string.formatnumberthousands(math.floor(self.curWeight)))
  end
end

function WorldDispatchArmyView:updateMoveTime(otherData)
  local needGetList = {}
  for i, v in pairs(self.tableArmyData) do
    if v.curCount > 0 then
      table.insert(needGetList, {
        id = v.armyid,
        num = v.curCount
      })
    end
  end
  if 0 < #needGetList then
    local ret = kingdomMapCtrl:getArmyMoveTime(self.instanceType, self.dispatchType, needGetList, self.toPoint, self.otherData.mainInstanceType, self.selectedHeroList, self.instanceID, otherData)
    ret = math.ceil(ret)
    self.labelTime:setString(SoraDConvertSecondToString(ret))
    self.costTime = ret
  else
    self.labelTime:setString(SoraDConvertSecondToString(0))
    self.costTime = 0
  end
  SoraDAlignNodeArrayOnCenterX(self.btnGo:getContentSize().width * 0.5, {
    self.icon_hourglass_3,
    self.labelTime
  }, SoraDFIsRA(), {5})
end

function WorldDispatchArmyView:btnCountPlusClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    local buffid = 19
    local buffData = buffCtrl:queryCityBuff(buffid)
    local tableBuff = {
      bid = buffid,
      buffname = cityEffectInfoRead.getName(buffid),
      bufdes = cityEffectInfoRead.getDes(buffid),
      buftip = cityEffectInfoRead.getTip(buffid)
    }
    local panel = SoraDCreatePanel("citybuffItemView")
    panel:initData(tableBuff)
    panel:show()
  end
end

function WorldDispatchArmyView:btnPhysicalPlusClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    if self.instanceType == gMapObjTypeDef.mapObjTypeNpc or self.otherData.mainInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeCorbanSheep or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeCorbanBull or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWildCattleRider or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull or self.instanceType == gMapObjTypeDef.mapTypeStronghold or self.instanceType == gMapObjTypeDef.mapTypePve then
      self:physicalNotEnough()
    else
      SoraDShowHelpMsgTip(i18n("common_text_987"))
    end
  end
end

function WorldDispatchArmyView:btnConveneClickCallBack(button, event)
  if event == ccui.TouchEventType.ended then
    SoraDPlaySound()
    print("\229\143\172\233\155\134\229\163\171\229\133\181")
    SoraDCreatePanel("armyBuildingsView"):show()
  end
end

function WorldDispatchArmyView:btnFatClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    self:resetArmySelect()
    local tableWeight = {}
    for i, v in pairs(self.tableArmyData) do
      local curWeight = v.weight
      local insertI = #tableWeight + 1
      for j, w in ipairs(tableWeight) do
        if curWeight > w.weight then
          insertI = j
          break
        end
      end
      table.insert(tableWeight, insertI, {armyid = i, weight = curWeight})
    end
    if self.dispatchType == worldMapDefine.worldMapTipButtonType_zhanLing and self.instanceType == gMapObjTypeDef.mapObjTypeResource then
      local multiple = self.otherData.resourceType == gIDDef.GOLD and 1000 or self.otherData.resourceType == gIDDef.IRON and 6 or self.otherData.resourceType == gIDDef.MITHRIL and 24 or 1
      local curResCount = self.otherData.currentSourceNum * multiple
      local addWeight = 1 + kingdomMapCtrl:getArmyWeightPlus(self.selectedHeroList)
      for i, v in ipairs(tableWeight) do
        local armyMax = self:getArmyCount(v.armyid)
        local armyWeight = v.weight * addWeight
        local armyCount = math.min(armyMax, math.ceil(curResCount / armyWeight))
        self:setCurValByArmyid(v.armyid, armyCount)
        curResCount = math.max(0, curResCount - armyCount * armyWeight)
      end
    else
      for i, v in ipairs(tableWeight) do
        self:setCurValMax(v.armyid)
      end
    end
    self:updateView()
  end
end

function WorldDispatchArmyView:btnFastClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    local haveQB = false
    for i, armyid in ipairs(self.tableArmy) do
      if armyltCtrl.getSoldierType(armyid) == gArmyClass.cavalry then
        haveQB = true
        break
      end
    end
    if haveQB then
      self:resetArmySelect()
      for i, armyid in ipairs(self.tableArmy) do
        if armyltCtrl.getSoldierType(armyid) == gArmyClass.cavalry then
          self:setCurValMax(armyid)
        end
      end
      self:updateView()
    else
      SoraDShowMsgTip(i18n("common_text_2753"), "#icon_fight_speed_rank_01.png")
    end
  end
end

function WorldDispatchArmyView:physicalNotEnough(type)
  if type == nil or type == MSGBOX_CALLBACK_YES then
    local item = {
      300401,
      300402,
      300403
    }
    local backpackCtrl = gametop.playertop_:getModule("backpackCtrl")
    local itemBackPack = backpackCtrl:getBackpack(gBackpackDef.PROPS)
    local count
    for k, v in pairs(item) do
      count = itemBackPack:getItemCount(v)
      if 0 < count then
        break
      end
    end
    if 0 < count then
      SoraDCreatePanel("physicalBuyView"):show()
    else
      local panel = SoraDCreatePanel("physicalExchangeView")
      panel:initData(gPhysicalExchangeType.buyPhysical)
      panel:show()
    end
  end
end

function WorldDispatchArmyView:quickChoose(isFull)
  local armyData = gModuleMgr.sharedMgr("mildGuideManager"):getVariate(self.__cname, "armyData")
  if armyData then
    for armyid, v in pairs(self.tableArmyData) do
      if armyData[armyid] then
        local singleMax = self:getArmyCount(armyid)
        self:setCurValByArmyid(armyid, math.min(singleMax, armyData[armyid]))
      else
        self:setCurValByArmyid(armyid, 0)
      end
    end
  elseif isFull then
    if self.dispatchType == worldMapDefine.worldMapTipButtonType_zhanLing and self.instanceType == gMapObjTypeDef.mapObjTypeResource then
      local multiple = self.otherData.resourceType == gIDDef.GOLD and 1000 or self.otherData.resourceType == gIDDef.IRON and 6 or self.otherData.resourceType == gIDDef.MITHRIL and 24 or 1
      print(multiple, "WorldDispatchArmyView:quickChoose")
      local curResCount = self.otherData.currentSourceNum * multiple
      local addWeight = 1 + kingdomMapCtrl:getArmyWeightPlus(self.selectedHeroList)
      for i, armyid in pairs(self.tableArmy) do
        local armyData = self.tableArmyData[armyid]
        if armyData then
          local armyWeight = armyData.weight * addWeight
          local armyCount = math.min(armyData.armycount, math.ceil(curResCount / armyWeight))
          self:setCurValByArmyid(armyid, armyCount)
          curResCount = math.max(0, curResCount - armyCount * armyWeight)
        end
      end
    else
      for i, armyid in pairs(self.tableArmy) do
        self:setCurValMax(armyid)
      end
    end
  else
    self:resetArmySelect()
  end
  self:updateView()
  self.isSelectFull = isFull
end

function WorldDispatchArmyView:btnQuickClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    local setFull = false
    if self.curCount <= 0 then
      setFull = true
    else
      setFull = false
    end
    self:quickChoose(setFull)
  end
end

function WorldDispatchArmyView:btnGoClickCallBack(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    local userControlTime = SoraDGetSocketTime() - self.curTime
    if self.leftTime and self.leftTime - userControlTime < self.costTime then
      SoraDShowMsgBox(i18n("alliance_war_text_5"), i18n("common_text_054"), nil, function(callType)
        if callType == MSGBOX_CALLBACK_YES then
          self:judgeOpenTipsOrGo()
        end
      end)
    else
      self:judgeOpenTipsOrGo()
    end
  end
end

function WorldDispatchArmyView:judgeOpenTipsOrGo()
  print("-----chuzheng----instanceType----", self.instanceType)
  print("-----chuzheng----dispatchType----", self.dispatchType)
  print("-----chuzheng----expType----", self.expType)
  print("-----chuzheng----massInstanceType----", self.massInstanceType)
  print("-----chuzheng----mainInstanceType----", self.otherData.mainInstanceType)
  print("-----chuzheng----viewType----", self.viewType or "nil")
  print("-----chuzheng----judianState----", self.otherData.judianState)
  dump(self.otherData.famousCityCaptainer, "-----chuzheng----famousCityCaptainer----")
  local dispatchArmyList = {}
  for i, v in pairs(self.tableArmyData) do
    if v.curCount > 0 then
      table.insert(dispatchArmyList, {
        id = v.armyid,
        num = v.curCount
      })
    end
  end
  if #dispatchArmyList <= 0 then
    SoraDShowMsgBox(i18n("notice_0158"), i18n("common_text_204"))
    return
  end
  if not worldMapDefine.isInPyramid() and not worldMapDefine.isInNewTrial() and not worldMapDefine.isInWar() and (self.dispatchType == worldMapDefine.worldMapTipButtonType_xuanZhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_battle or self.dispatchType == worldMapDefine.worldMapTipButtonType_gongJi or self.dispatchType == worldMapDefine.worldMapTipButtonType_twoCityNeutralBuild_xuanZhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_judianGongji) and (self.viewType == nil or self.viewType == gAWarViewMemberType.NONE or self.viewType == gAWarViewMemberType.ATTACKER) and self:judgeIsPVP(self.instanceType) then
    if self.massInstanceType == nil and self.otherData.mainInstanceType == nil then
      SoraDShowPvpTipsPanel(handler(self, self.onGo))
      return
    elseif self.massInstanceType and self:judgeIsPVP(self.massInstanceType) then
      SoraDShowPvpTipsPanel(handler(self, self.onGo))
      return
    elseif self.otherData.mainInstanceType and self:judgeIsPVP(self.otherData.mainInstanceType) then
      SoraDShowPvpTipsPanel(handler(self, self.onGo))
      return
    end
  end
  if self.instanceType == gMapObjTypeDef.mapTypeTwoCityOrdnance then
    local isLimitToday = twoCityCtrl:isJunxiekuLimitToday()
    if isLimitToday then
      SoraDShowMsgBox(i18n("ordnance_buff_des5"), i18n("common_text_204"), i18n("common_text_185"), function(event)
        if event == MSGBOX_CALLBACK_YES then
          self:onGo()
        end
      end)
      return
    end
  end
  self:onGo()
end

function WorldDispatchArmyView:judgeIsPVP(type)
  if type == gMapObjTypeDef.mapObjTypePlayer or type == gMapObjTypeDef.mapObjTypeAllianceBuild or type == gMapObjTypeDef.mapObjTypeCastale or type == gMapObjTypeDef.mapTypePlain or type == gMapObjTypeDef.mapTypeNeutralBuild or type == gMapObjTypeDef.mapObjTypeFortress or type == gMapObjTypeDef.mapObjTypeResource or type == gMapObjTypeDef.mapObjTypeBattery or type == gMapObjTypeDef.mapObjTypeTory or type == gMapObjTypeDef.mapObjTypeCampsite or type == gMapObjTypeDef.mapTypeStronghold and self.otherData.judianState == gMapStrongholdStatus.player or type == gMapObjTypeDef.mapTypeFamousCity and self.otherData.famousCityCaptainer and next(self.otherData.famousCityCaptainer) and self.otherData.leagueID and self.otherData.leagueID > 0 then
    return true
  end
  return false
end

function WorldDispatchArmyView:onGo()
  local dispatchArmyList = {}
  for i, v in pairs(self.tableArmyData) do
    if v.curCount > 0 then
      table.insert(dispatchArmyList, {
        id = v.armyid,
        num = v.curCount
      })
    end
  end
  if 0 < #dispatchArmyList then
    if self.instanceType == gMapObjTypeDef.mapObjTypeNpc then
      local physical = lordInfoCtrl:getBaseInfo().physical
      local killRate = 1
      local remainCount = lordInfoCtrl:getDropGainBuffCount(811039) or 0
      if 0 < remainCount then
        killRate = 2
      end
      local beautyKillRate = buffCtrl:getBuffEffect(gBuffEffect.MUTI_KILL, gBuffSource.PERI) or 1
      if beautyKillRate ~= 1 then
        killRate = beautyKillRate
      end
      local needPhysical = HP_MIN_MONSTER_CHEST * killRate
      if physical < needPhysical then
        SoraDShowMsgBox(i18n("common_text_988"), i18n("common_text_204"), nil, handler(self, self.physicalNotEnough))
        return
      end
    elseif self.instanceType == gMapObjTypeDef.mapTypeFamousCity then
      local famousCityCtrl = gametop.playertop_:getModule("famousCityCtrl")
      local actInfo = famousCityCtrl:getFamousCityActivity()
      if actInfo.curState == gFamousCityActivityState.WAR then
        local famousCityRead = include("famousCityRead")
        local x, y, type, subMapType, objId = kingdomMapUtil.gSplitId(self.instanceID)
        local buildList = famousCityCtrl:getFamousCityInfoList()
        local buildInfo = buildList[tostring(objId)] or {}
        if buildInfo.ownerAid ~= 0 then
          SoraDShowMsgTip(i18n("notice_0026"))
          SoraDRemoveAllPanelFromManager()
          return
        end
      else
        SoraDShowMsgTip(i18n("notice_0026"))
        SoraDRemoveAllPanelFromManager()
        return
      end
    elseif self.otherData.mainInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull or self.instanceType == gMapObjTypeDef.mapTypeStronghold or self.instanceType == gMapObjTypeDef.mapTypePve then
      local physical = lordInfoCtrl:getBaseInfo().physical
      local needHp = HP_MIN_BOSS
      if self.isIslandMode then
        needHp = 0
      end
      if self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
        needHp = 0
      end
      if physical < needHp then
        SoraDShowMsgBox(i18n("common_text_988"), i18n("common_text_204"), nil, handler(self, self.physicalNotEnough))
        return
      end
    elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_bangzhuyayun then
      local member = true
      local allianceMgr = gametop.playertop_:getModule("allianceMgr")
      local alliance = allianceMgr:getAlliance()
      if alliance then
        member = alliance:hasMember(tonumber(self.instanceID))
      end
      if not alliance or not member then
        SoraDShowMsgTip(i18n("notice_0207"))
        SoraDRemoveAllPrePanelFromManager(self)
        return
      end
    elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_xuanZhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_fanjiXuanzhan then
      local allianceMgr = gametop.playertop_:getModule("allianceMgr")
      local hasJoinAlliance = allianceMgr:hasJoinAlliance(true)
      if not hasJoinAlliance then
        SoraDShowMsgTip(i18n("king_fight_text_11"))
        SoraDRemoveAllPrePanelFromManager(self)
        return
      end
    end
    if self.instanceType == gMapObjTypeDef.mapTypeGodBeast or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeGodBeast then
      local godBeastCtrl = gametop.playertop_:getModule("godBeastCtrl")
      local curBuyCount = godBeastCtrl:getCurAttackBuyCount()
      local maxCount = tonumber(constantRead.getValueByKey("GODBEAST_ATK_COUNT")) + curBuyCount
      local curCount = godBeastCtrl:getCurAttackCount()
      if maxCount <= curCount then
        local eventWorldBossltCtrl = include("eventWorldBossltCtrl")
        local data = eventWorldBossltCtrl.getGoldBeastBuyAtckCountInfo(curBuyCount)
        if data then
          local panel = SoraDCreatePanel("physicalExchangeView")
          panel:initData(gPhysicalExchangeType.godBeast, data)
          panel:show()
        else
          SoraDShowMsgTip(i18n("world_boss_text_39"))
          SoraDRemoveAllPanelFromManager(self)
        end
        return
      end
    end
    if self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
      local bullSacrificeCtrl = gametop.playertop_:getModule("bullSacrificeCtrl")
      local leftTimes = bullSacrificeCtrl:getLeftSacrificeTimes()
      if not leftTimes or leftTimes < 1 then
        local bossType = include("bullSacrificeRead").getCurSacrificeBossType()
        local sacrificeBossName = worldMapDefine.getWorldBossName(bossType)
        SoraDShowMsgTip(i18n("bull_text_51", {
          bossName1 = i18n(sacrificeBossName)
        }))
        SoraDRemoveAllPanelFromManager(self)
        return
      end
    end
    local heros = {}
    for i, v in pairs(self.selectedHeroList) do
      table.insert(heros, v)
    end
    if self.selectedPetId and self.selectedPetId < petRead.firstID then
      self.selectedPetId = nil
    end
    local pets = {
      self.selectedPetId
    }
    local runeSuit = {}
    table.insert(runeSuit, self.selectedArtifactIndex)
    if self.isIslandMode then
      local armyData = {
        otherData = self.otherData,
        armys = dispatchArmyList,
        heros = heros,
        needSend = self.shareOK,
        runeSuit = runeSuit,
        pets = pets,
        needArmyList = self.needArmyList
      }
      SoraDSendMessage({
        msg = "MESSAGE_UI_ISLAND_ARMY_EXPEDITION_DATA",
        armyData = armyData
      })
    elseif self.isKingHoardMode then
      local armyData = {
        otherData = self.otherData,
        armys = dispatchArmyList,
        heros = heros,
        runePages = runeSuit,
        pets = pets
      }
      SoraDSendMessage({
        msg = "MESSAGE_KINGHOARD_ATTACK",
        armyData = armyData
      })
    else
      if not ggg_debugDispatch and not worldMapDefine.checkMapZone(self.toPoint.x, self.toPoint.y, 1) then
        SoraDShowMsgTip(i18n("Empiretask_text_36"))
        return
      end
      local armyData = {
        dispatchType = self.dispatchType,
        otherData = self.otherData,
        toPoint = self.toPoint,
        instanceID = self.instanceID,
        armyList = dispatchArmyList,
        heros = heros,
        needSend = self.shareOK,
        runeSuit = runeSuit,
        pets = pets,
        needArmyList = self.needArmyList
      }
      worldMapFunction.gotoDispatch(armyData, true)
    end
    if self.dispatchType == worldMapDefine.worldMapTipButtonType_xuanZhan or self.dispatchType == worldMapDefine.worldMapTipButtonType_fanjiXuanzhan then
      SoraDPlaySound(soundFileRead:getWorldMapSound(14))
    else
      SoraDPlaySound(soundFileRead:getWorldMapSound(2))
    end
    if self.instanceType == gMapObjTypeDef.mapObjTypeNpc then
      local killRate = 1
      local remainCount = lordInfoCtrl:getDropGainBuffCount(811039) or 0
      if 0 < remainCount then
        killRate = 2
      end
      local beautyKillRate = buffCtrl:getBuffEffect(gBuffEffect.MUTI_KILL, gBuffSource.PERI) or 1
      if beautyKillRate ~= 1 then
        killRate = beautyKillRate
      end
      local needPhysical = HP_MIN_MONSTER_CHEST * killRate
      local costPhysical = self:calculateCostPhysical()
      if costPhysical then
        needPhysical = costPhysical
      end
      SoraDSendMessage({
        msg = "MESSAGE_WORLD_MAP_DISPATCH_ARMY",
        hp = needPhysical
      })
    elseif self.otherData.mainInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.otherData.mainInstanceType == gMapObjTypeDef.mapTypeWorshipBull or self.instanceType == gMapObjTypeDef.mapTypeStronghold then
      SoraDSendMessage({
        msg = "MESSAGE_WORLD_MAP_DISPATCH_ARMY",
        hp = HP_MIN_BOSS
      })
    end
    local guideStep = gModuleMgr.sharedMgr("mildGuideManager"):getVariate(self.__cname, "isGuide")
    if guideStep then
      local guideCtrl = gametop.playertop_:getModule("guideCtrl")
      guideCtrl:CompleteGuideStep(guideStep)
    end
    if self.instanceType == gMapObjTypeDef.mapObjTypePlayer then
      userSDKManager.report2firebase("reportPvp")
    end
    if self.isIslandMode or self.isKingHoardMode then
      self:closePanel()
    else
      SoraDRemoveAllPrePanelFromManager(self)
    end
  else
    SoraDShowMsgBox(i18n("notice_0158"), i18n("common_text_204"))
  end
end

function WorldDispatchArmyView:onEnterPanel()
end

function WorldDispatchArmyView:resetArmySelect()
  for i, v in pairs(self.tableArmyData) do
    v.curCount = 0
  end
  self.curCount = 0
  self:updateView()
end

function WorldDispatchArmyView:getArmyCurCount(armyid)
  local armyData = self.tableArmyData[armyid]
  if armyData then
    return armyData.curCount
  end
  return 0
end

function WorldDispatchArmyView:getArmyCount(armyid)
  local armyData = self.tableArmyData[armyid]
  if armyData then
    return armyData.armycount
  end
  return 0
end

function WorldDispatchArmyView:setCurValMax(armyid)
  local armyMax = self:getArmyCount(armyid)
  self:setCurValByArmyid(armyid, armyMax)
end

function WorldDispatchArmyView:setCurValByArmyid(armyid, curCount)
  local armyData = self.tableArmyData[armyid]
  if not armyData then
    print("setCurValByArmyid error", armyid, curCount)
    return 0
  end
  if curCount > armyData.armycount then
    print("setCurValByArmyid armycount error", armyid, curCount)
    return 0
  end
  local curArmyCount = self.curCount
  if 0 < armyData.curCount then
    curArmyCount = self.curCount - armyData.curCount
    if curArmyCount < 0 then
      print("setCurValByArmyid curCount error", armyid, curCount)
      return 0
    end
  end
  if curArmyCount + curCount > self.allCount and 0 < curCount then
    curCount = self.allCount - curArmyCount
  end
  armyData.curCount = curCount
  self.curCount = curArmyCount + curCount
  return curCount
end

function WorldDispatchArmyView:setCurValByIndex(index, curCount)
  local armyid = self.tableArmy[index]
  if checknumber(armyid) > 0 then
    return self:setCurValByArmyid(armyid, curCount)
  else
    print("setCurValByIndex error", index, curCount)
  end
  return 0
end

function WorldDispatchArmyView:scrollEventCallBack(target, event)
  if event == ccui.ScrollviewEventType.scrolling then
    self:updateScrollList()
  end
end

function WorldDispatchArmyView:btnHeroDetailCallback(button, type)
  if type == ccui.TouchEventType.ended then
    SoraDPlaySound()
    print("\230\137\147\229\188\128\232\139\177\233\155\132\232\175\166\230\131\133")
    local power = 0
    local armyNum = 0
    for k, v in pairs(self.tableArmyData) do
      local tempPower = armyltCtrl.getArmyAttrAndSp(v.armyid, ARMY_ATTR.POWER) or 0
      power = power + tempPower * v.curCount
      armyNum = armyNum + v.curCount
    end
    local panel = SoraDCreatePanel("dispatchArmyDetailInfo")
    panel:initData(armyNum, power, self.allCount, self.selectedHeroList)
    panel:show()
  end
end

function WorldDispatchArmyView:funcShowDesTipTest()
  local des = lMapExpeditionDes[tostring(self.expType)]
  SoraDShowMsgTip(des)
end

function WorldDispatchArmyView:uiForIsland()
  self.labelGoTitle:setVisible(not self.isIslandMode)
  self.labelTime:setVisible(not self.isIslandMode)
  self.icon_hourglass_3:setVisible(not self.isIslandMode)
  self.btnGo:setTitleText(i18n("common_text_481"))
end

function WorldDispatchArmyView:uiForKingHorad()
  self.labelGoTitle:setVisible(false)
  self.labelTime:setVisible(false)
  self.icon_hourglass_3:setVisible(false)
  self.btnGo:setTitleText(i18n("common_text_481"))
end

function WorldDispatchArmyView:initExpType()
  local expType = gMapExpeditionType.plain
  if self.dispatchType == worldMapDefine.worldMapTipButtonType_xiefang or self.dispatchType == worldMapDefine.worldMapTipButtonType_shibingYuabzhu then
    expType = gMapExpeditionType.help
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeBoss or self.massInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss1 or self.massInstanceType == gMapObjTypeDef.mapTypeCorbanSheep or self.massInstanceType == gMapObjTypeDef.mapTypeCorbanBull or self.massInstanceType == gMapObjTypeDef.mapTypeHeroBattleBoss2 or self.massInstanceType == gMapObjTypeDef.mapTypeAnaStarWarBoss or self.massInstanceType == gMapObjTypeDef.mapTypeWorshipBull then
    expType = gMapExpeditionType.boss
  elseif self.massInstanceType == gMapObjTypeDef.mapTypeGodBeast or self.instanceType == gMapObjTypeDef.mapTypeGodBeast then
    expType = gMapExpeditionType.beast
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeNpc or self.instanceType == gMapObjTypeDef.mapQuestMonster or self.instanceType == gMapObjTypeDef.mapTypeAnaStarWarNpc then
    expType = gMapExpeditionType.npc
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_caiji or self.instanceType == gMapObjTypeDef.mapObjTypeResource then
    if self.otherData and self.otherData.resourceType then
      if self.otherData.resourceType == gIDDef.WOOD then
        expType = gMapExpeditionType.collect_wood
      elseif self.otherData.resourceType == gIDDef.FOOD then
        expType = gMapExpeditionType.collect_food
      elseif self.otherData.resourceType == gIDDef.IRON then
        expType = gMapExpeditionType.collect_iron
      elseif self.otherData.resourceType == gIDDef.MITHRIL then
        expType = gMapExpeditionType.collect_mithril
      elseif self.otherData.resourceType == gIDDef.GOLD then
        expType = gMapExpeditionType.collect_gold
      end
    end
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeAllianceBuild or self.instanceType == gMapObjTypeDef.mapObjTypeAllianceBuild then
    expType = gMapExpeditionType.alliance_build
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeCastale or self.instanceType == gMapObjTypeDef.mapObjTypeCastale then
    expType = gMapExpeditionType.kingdom_build
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeFortress or self.instanceType == gMapObjTypeDef.mapObjTypeFortress then
    expType = gMapExpeditionType.fortress
  elseif self.massInstanceType == gMapObjTypeDef.mapObjTypeBattery or self.instanceType == gMapObjTypeDef.mapObjTypeBattery or self.instanceType == gMapObjTypeDef.mapObjNewTrialCity or self.massInstanceType == gMapObjTypeDef.mapObjNewTrialCity then
    expType = gMapExpeditionType.battery
  elseif self.instanceType == gMapObjTypeDef.mapObjTypePlayer then
    expType = gMapExpeditionType.castle
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_jianzao and self.instanceType == gMapObjTypeDef.mapObjTypeSuperResource then
    expType = gMapExpeditionType.alliance_super_build
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_yayun or self.dispatchType == worldMapDefine.worldMapTipButtonType_bangzhuyayun then
    expType = gMapExpeditionType.escort
  elseif self.dispatchType == worldMapDefine.worldMapTipButtonType_lueduo then
    expType = gMapExpeditionType.plunder_escort
  elseif self.instanceType == gMapObjTypeDef.mapTypeStronghold or self.instanceType == gMapObjTypeDef.mapTypePve then
    expType = gMapExpeditionType.stronghold
  elseif self.instanceType == gMapObjTypeDef.mapTypePlain then
    expType = gMapExpeditionType.plain
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeCampsite then
    expType = gMapExpeditionType.campsite
  elseif self.instanceType == gMapObjTypeDef.mapObjTypeRelics then
    expType = gMapExpeditionType.relics
  elseif self.instanceType == gMapObjTypeDef.worldMapTipButtonType_wajue or self.dispatchType == worldMapDefine.worldMapTipButtonType_zuduiwajue then
    expType = gMapExpeditionType.all
  end
  return expType
end

function WorldDispatchArmyView:gameGuide_getTarget(itemName, parameters)
  if itemName == "Button_go" or itemName == "selectHero1" then
    if parameters and parameters.armyData then
      self.curCount = 0
      for armyid, v in pairs(self.tableArmyData) do
        if parameters.armyData[armyid] then
          v.curCount = math.min(v.armycount, parameters.armyData[armyid])
        else
          v.curCount = 0
        end
        self.curCount = self.curCount + v.curCount
      end
    end
    self:updateView()
    if itemName == "selectHero1" then
      return self.hero1:getGuideSelectButn()
    end
  end
  print("SoraDGetChildByName(self, itemName)==", SoraDGetChildByName(self, itemName))
  return SoraDGetChildByName(self, itemName)
end

return WorldDispatchArmyView
