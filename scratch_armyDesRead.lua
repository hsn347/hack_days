local armyDesRead = {}
armyDesRead.tableArmyDes = require("app.localtb.config_client.armydescribe")
armyDesRead.tableArmyModel = require("app.localtb.config_client.armymodel")
armyDesRead.tableArmySkill = require("app.localtb.config_client.specialitydescribe")
armyDesRead.tableArmyInfo = require("app.localtb.config_server.armyinfo")
armyDesRead.tableLoadingText = require("app.localtb.config_client.loading_text")
armyDesRead.tableArmySubTypeDes = require("app.localtb.config_client.godbeast_armydes")
armyDesRead.mapArmyInfo = {}

function armyDesRead.getName(aid)
  aid = tonumber(aid)
  return i18n(armyDesRead.tableArmyDes[aid].armyName)
end

function armyDesRead.getDes(aid)
  aid = tonumber(aid)
  return i18n(armyDesRead.tableArmyDes[aid].armyDes)
end

function armyDesRead.getTip(aid)
  aid = tonumber(aid)
  return i18n(armyDesRead.tableArmyDes[aid].tip)
end

function armyDesRead.getTipDes(aid)
  aid = tonumber(aid)
  return i18n(armyDesRead.tableArmyDes[aid].tiptwo)
end

function armyDesRead.getCostFood(aid)
  aid = tonumber(aid)
  return armyDesRead.tableArmyDes[aid].costFood
end

function armyDesRead.getArmySubTypeName(subType)
  for k, v in ipairs(armyDesRead.tableArmySubTypeDes) do
    if v.armyType == subType then
      return i18n(v.armyDes)
    end
  end
  return i18n("armyName_402")
end

function armyDesRead.getSkill(aid)
  aid = tonumber(aid)
  return armyDesRead.tableArmyDes[aid].speciality
end

function armyDesRead.getArmySound(aid)
  aid = tonumber(aid)
  return armyDesRead.tableArmyDes[aid].sound
end

function armyDesRead.getLvImg(aid, fromMemory)
  aid = tonumber(aid)
  local armyLogic = include("armyLogic")
  local alv = armyLogic.getArmyOrTrapLv(aid)
  if fromMemory then
    return "#" .. (SoraDFIsRA() and "commom_arab" or "commom_rome") .. alv .. ".png"
  end
  return (SoraDFIsRA() and "commom_arab" or "commom_rome") .. alv .. ".png"
end

function armyDesRead.getArabLvImg(aid, fromMemory)
  aid = tonumber(aid)
  local armyLogic = include("armyLogic")
  local alv = armyLogic.getArmyOrTrapLv(aid)
  if fromMemory then
    return "#" .. "commom_arab" .. alv .. ".png"
  end
  return "commom_arab" .. alv .. ".png"
end

function armyDesRead.getTrapLvImg(aid, fromMemory)
  aid = tonumber(aid)
  local armyLogic = include("armyLogic")
  local alv = armyLogic.getTrapLV(aid)
  if fromMemory then
    return "#" .. (SoraDFIsRA() and "commom_arab" or "commom_rome") .. alv .. ".png"
  end
  return (SoraDFIsRA() and "commom_arab" or "commom_rome") .. alv .. ".png"
end

function armyDesRead.getPortrait(aid, fromMemory)
  aid = tonumber(aid)
  if fromMemory then
    return "#" .. armyDesRead.tableArmyDes[aid].armyPic
  end
  return armyDesRead.tableArmyDes[aid].armyPic
end

function armyDesRead.getIcon(aid, fromMemory)
  aid = tonumber(aid)
  if fromMemory then
    return "#" .. armyDesRead.tableArmyDes[aid].armySmallPic
  end
  return armyDesRead.tableArmyDes[aid].armySmallPic
end

function armyDesRead.loadSoldierPromotionRes()
  local plistName = "icon/icon_soldiers1_ext.plist"
  local imgName = getImageFileNameByPlatform("icon/icon_soldiers1")
  display.addSpriteFrames(plistName, imgName)
  plistName = "icon/icon_soldiers2_ext.plist"
  imgName = getImageFileNameByPlatform("icon/icon_soldiers2")
  display.addSpriteFrames(plistName, imgName)
  plistName = "icon/icon_soldiers3_ext.plist"
  imgName = getImageFileNameByPlatform("icon/icon_soldiers3")
  display.addSpriteFrames(plistName, imgName)
  plistName = "icon/icon_soldiers4_ext.plist"
  imgName = getImageFileNameByPlatform("icon/icon_soldiers4")
  display.addSpriteFrames(plistName, imgName)
  plistName = "icon/icon_soldiers5_ext.plist"
  imgName = getImageFileNameByPlatform("icon/icon_soldiers5")
  display.addSpriteFrames(plistName, imgName)
end

function armyDesRead.getPromotionImg(aid, fromMemory)
  aid = tonumber(aid)
  if fromMemory then
    return "#armyicon_b_" .. aid .. "_head.png"
  end
  return "armyicon_b_" .. aid .. "_head.png"
end

function armyDesRead.changePromotionImgDisplay(aid, target, originScale)
  originScale = originScale / 1.33
  local frame = SoraDCheckPNG(armyDesRead.getPromotionImg(aid), "armyicon_b_" .. 601 .. "_head.png")
  target:setScaleY(math.abs(armyDesRead.getArmyHeadScaleByAid(aid) * originScale))
  target:setScaleX(armyDesRead.getArmyHeadScaleByAid(aid) * originScale)
  local targetType = tolua.type(target)
  if targetType == "cc.Sprite" then
    target:setSpriteFrame(frame)
  elseif targetType == "ccui.ImageView" then
    target:loadTexture(frame, ccui.TextureResType.plistType)
  end
end

function armyDesRead.getArmyHeadScaleByAid(aid)
  local scale = include("soldierScale")
  dump(scale, "soldierScale", nesting)
  return scale[aid] or 1
end

function armyDesRead.getAvatarPic(aid, fromMemory)
  aid = tonumber(aid)
  if fromMemory then
    return "#" .. armyDesRead.tableArmyDes[aid].armyAvatarPic
  end
  return armyDesRead.tableArmyDes[aid].armyAvatarPic
end

function armyDesRead.getWarLv(aid)
  aid = tonumber(aid)
  local warLv = math.floor(aid / 1000)
  if warLv ~= 0 then
    warLv = warLv % 10000 + 1
  end
  return warLv
end

function armyDesRead.getModelType(aid)
  aid = tonumber(aid)
  return armyDesRead.tableArmyDes[aid].modelType
end

function armyDesRead.getModelImage(armyModel)
  armyModel = tonumber(armyModel)
  return armyDesRead.tableArmyModel[armyModel] and armyDesRead.tableArmyModel[armyModel].modelImage
end

function armyDesRead.getSkillIcon(sid)
  sid = tonumber(sid)
  return armyDesRead.tableArmySkill[sid].specialityPic, ccui.TextureResType.plistType
end

function armyDesRead.getSkillName(sid)
  sid = tonumber(sid)
  return i18n(armyDesRead.tableArmySkill[sid].specialityName, {
    lv = armyDesRead.getSkillLv(sid)
  })
end

function armyDesRead.getSkillDes(sid)
  sid = tonumber(sid)
  return i18n(armyDesRead.tableArmySkill[sid].specialityDes)
end

function armyDesRead.getSkillLv(sid)
  sid = tonumber(sid)
  return armyDesRead.tableArmySkill[sid].specialityLv
end

function armyDesRead.getFreeWeight(sid)
  sid = tonumber(sid)
  local fW
  for _, v in ipairs(armyDesRead.tableArmyInfo) do
    if v.armyID == sid then
      fW = v.freeWeight
      break
    end
  end
  return fW
end

function armyDesRead.getArmyAtkInterval(sid)
  sid = tonumber(sid)
  local atkInterval
  for _, v in ipairs(armyDesRead.tableArmyInfo) do
    if v.armyID == sid then
      atkInterval = v.atkInterval
      break
    end
  end
  return atkInterval
end

function armyDesRead.getArmyPosition(sid)
  sid = tonumber(sid)
  local pos
  for _, v in ipairs(armyDesRead.tableArmyInfo) do
    if v.armyID == sid then
      pos = v.position
      break
    end
  end
  return pos
end

function armyDesRead.getFreeWeightAndSp(sid)
  local armyltCtrl = include("armyltCtrl")
  sid = tonumber(sid)
  local fW = armyltCtrl.getArmyAttrAndSp(sid, ARMY_ATTR.FREE_WEIGHT)
  return fW
end

function armyDesRead.getBuildID(aid)
  aid = tonumber(aid)
  local armyLogic = include("armyLogic")
  local bidList = {
    BUILDID.STABLES,
    BUILDID.RANGE,
    BUILDID.CHARIOT_PLANT,
    BUILDID.BARRACKS,
    BUILDID.FORTRESS,
    BUILDID.ELITE_PALACE
  }
  for i, v in ipairs(bidList) do
    if armyLogic.armyIdMatchBid(v, aid) then
      return v
    end
  end
  return BUILDID.STABLES
end

function armyDesRead.getArmyTpyeName(bid)
  local tableArmyTypeName = {
    [tostring(BUILDID.CHARIOT_PLANT)] = i18n("common_text_143"),
    [tostring(BUILDID.STABLES)] = i18n("common_text_144"),
    [tostring(BUILDID.RANGE)] = i18n("common_text_145"),
    [tostring(BUILDID.BARRACKS)] = i18n("common_text_146")
  }
  return tableArmyTypeName[tostring(bid)]
end

function armyDesRead.getRandomText()
  math.randomseed(tostring(os.time()):reverse():sub(1, 6) * math.random())
  local randIndex = math.random(#armyDesRead.tableLoadingText)
  return i18n(armyDesRead.tableLoadingText[randIndex].key)
end

function armyDesRead.getAttrAdditionData(armyType, desType)
  local data = {}
  if armyType then
    local ret = tostring(armyType) .. "_" .. tostring(desType)
    data = gArmyAdditionDes[ret] and gArmyAdditionDes[ret] or {}
  end
  return data
end

function armyDesRead.getArmyType(armyID)
  local cfg = armyDesRead.mapArmyInfo[armyID] or {}
  return cfg.armyType
end

function armyDesRead.getAidByArmyType(armyType)
  local armyId = gHightLvArmyId[armyType]
  return armyDesRead.getAvatarPic(armyId)
end

function armyDesRead.init()
  for _, v in pairs(armyDesRead.tableArmyInfo or {}) do
    armyDesRead.mapArmyInfo[v.armyID] = v
  end
end

armyDesRead.init()
return armyDesRead
