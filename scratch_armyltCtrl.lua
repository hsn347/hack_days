local armyltCtrl = {}
armyltCtrl.armyInfo = {}
armyltCtrl.build_wlv_army_list = {}
armyltCtrl.biuld_army_list = {}
armyltCtrl.armyspeciality = {}
armyltCtrl.armyAttcakMax = 0
armyltCtrl.armyDeffenMax = 0
armyltCtrl.armyBloodMax = 0
armyltCtrl.trapAttcakMax = 0

function armyltCtrl.init()
  local armyinfo = require("app.localtb.config_server.armyinfo")
  for i, v in ipairs(armyinfo) do
    armyltCtrl.armyInfo[v.armyID] = v
    if armyltCtrl.armyAttcakMax < v.attack and v.barrackID >= 116 and v.barrackID <= 119 then
      armyltCtrl.armyAttcakMax = v.attack
    end
    if armyltCtrl.armyDeffenMax < v.defense and v.barrackID >= 116 and v.barrackID <= 119 then
      armyltCtrl.armyDeffenMax = v.defense
    end
    if armyltCtrl.armyBloodMax < v.life and v.barrackID >= 116 and v.barrackID <= 119 then
      armyltCtrl.armyBloodMax = v.life
    end
    if armyltCtrl.trapAttcakMax < v.attack and v.barrackID == 120 then
      armyltCtrl.trapAttcakMax = v.attack
    end
    local bid = v.barrackID
    local blv = v.barrackLevel
    armyltCtrl.biuld_army_list[bid] = armyltCtrl.biuld_army_list[bid] or {}
    table.insert(armyltCtrl.biuld_army_list[bid], v.armyID)
    local wlv = 0
    armyltCtrl.build_wlv_army_list[bid] = armyltCtrl.build_wlv_army_list[bid] or {}
    armyltCtrl.build_wlv_army_list[bid][wlv] = armyltCtrl.build_wlv_army_list[bid][wlv] or {}
    table.insert(armyltCtrl.build_wlv_army_list[bid][wlv], v.armyID)
  end
  local armyspeciality = require("app.localtb.config_server.armyspeciality")
  for _, spec in pairs(armyspeciality) do
    if string.trim(spec.armyspecialityeffect1) ~= "" then
      spec.effect1 = string.split(spec.armyspecialityeffect1, ";")
    end
    if string.trim(spec.armyspecialityeffect2) ~= "" then
      spec.effect2 = string.split(spec.armyspecialityeffect2, ";")
    end
    if string.trim(spec.armyspecialityeffect3) ~= "" then
      spec.effect3 = string.split(spec.armyspecialityeffect3, ";")
    end
  end
  local mapArmySp = {}
  for _, army in pairs(armyinfo) do
    local armySp = {}
    armySp.resourceWarAkPlus = 0
    armySp.immuneTrap = false
    armySp.akBackrowRate = 0
    armySp.restrainArmyTypeAtkAddDmg = {}
    armySp.restrainArmyTypeDfsRedDmg = {}
    armySp.dodge = 0
    armySp.cityWarAkPlus = 0
    armySp.cityWarDfPlus = 0
    armySp.priorAkArmyClass = 0
    armySp.immuneDf = false
    armySp.hpPlus = 0
    armySp.dfPlus = 0
    armySp.akPlus = 0
    armySp.atkInvPlus = 0
    armySp.speedPlus = 0
    armySp.freeWeightPlus = 0
    armySp.penetrateRate = 0
    armySp.penetrateDmgRate = 0
    armySp.akBackrowDmgPlus = 0
    armySp.alertRate = 0
    armySp.alertDmgPlus = 0
    armySp.isShelter = false
    armySp.shelterDfPlus = 0
    armySp.critRate = 0
    armySp.rebound = 0
    armySp.spurting = 0
    mapArmySp[army.armyID] = armySp
    for _, id in pairs(army.speciality) do
      local specialityData = armyspeciality[id]
      if not specialityData then
        break
      end
      local arrSpec = {}
      if 0 < specialityData.armyspecialitytype1 then
        table.insert(arrSpec, {
          sType = specialityData.armyspecialitytype1,
          effect = specialityData.effect1
        })
      end
      if 0 < specialityData.armyspecialitytype2 then
        table.insert(arrSpec, {
          sType = specialityData.armyspecialitytype2,
          effect = specialityData.effect2
        })
      end
      if 0 < specialityData.armyspecialitytype3 then
        table.insert(arrSpec, {
          sType = specialityData.armyspecialitytype3,
          effect = specialityData.effect3
        })
      end
      for _, spec in pairs(arrSpec) do
        local sType = spec.sType
        local effect = spec.effect
        if spec.effect and 0 < #spec.effect then
          if sType == gArmySpeciality.resourceWarAkPlus then
            armySp.resourceWarAkPlus = serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.infantryAkRestrain then
            armySp.restrainArmyTypeAtkAddDmg[gArmyType.infantryAk] = serviceFunctions.getPermillageValue(effect[1])
            armySp.restrainArmyTypeDfsRedDmg[gArmyType.infantryAk] = serviceFunctions.getPermillageValue(effect[2])
          elseif sType == gArmySpeciality.cavalryRestrain then
            armySp.restrainArmyTypeAtkAddDmg[gArmyType.archer] = serviceFunctions.getPermillageValue(effect[1])
            armySp.restrainArmyTypeDfsRedDmg[gArmyType.archer] = serviceFunctions.getPermillageValue(effect[2])
          elseif sType == gArmySpeciality.cavalryArrowRestrain then
            armySp.restrainArmyTypeAtkAddDmg[gArmyType.crossbow] = serviceFunctions.getPermillageValue(effect[1])
            armySp.restrainArmyTypeDfsRedDmg[gArmyType.crossbow] = serviceFunctions.getPermillageValue(effect[2])
          elseif sType == gArmySpeciality.archerRestrain then
            armySp.restrainArmyTypeAtkAddDmg[gArmyType.cavalry] = serviceFunctions.getPermillageValue(effect[1])
            armySp.restrainArmyTypeDfsRedDmg[gArmyType.cavalry] = serviceFunctions.getPermillageValue(effect[2])
          elseif sType == gArmySpeciality.crossbowRestrain then
            armySp.restrainArmyTypeAtkAddDmg[gArmyType.cavalryArrow] = serviceFunctions.getPermillageValue(effect[1])
            armySp.restrainArmyTypeDfsRedDmg[gArmyType.cavalryArrow] = serviceFunctions.getPermillageValue(effect[2])
          elseif sType == gArmySpeciality.dodge then
            armySp.dodge = serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.cityWarAkPlus then
            armySp.cityWarAkPlus = serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.cityWarDfPlus then
            armySp.cityWarDfPlus = serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.priorInfantry then
            armySp.priorAkArmyClass = gArmyClass.infantry
          elseif sType == gArmySpeciality.priorCavalry then
            armySp.priorAkArmyClass = gArmyClass.cavalry
          elseif sType == gArmySpeciality.priorArcher then
            armySp.priorAkArmyClass = gArmyClass.archer
          elseif sType == gArmySpeciality.immuneDf then
            armySp.immuneDf = true
          elseif sType == gArmySpeciality.hpPlus then
            armySp.hpPlus = armySp.hpPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.dfPlus then
            armySp.dfPlus = armySp.dfPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.akPlus then
            armySp.akPlus = armySp.akPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.atkInvPlus then
            armySp.atkInvPlus = armySp.atkInvPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.moveSpeed then
            armySp.speedPlus = armySp.speedPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.weightPlus then
            armySp.freeWeightPlus = armySp.freeWeightPlus + serviceFunctions.getPermillageValue(effect[1])
          elseif sType == gArmySpeciality.crit then
            armySp.critRate = armySp.critRate + serviceFunctions.getPermillageValue(effect[1])
          end
        end
      end
    end
  end
  armyltCtrl.mapArmySp = mapArmySp
  armyltCtrl.armyspeciality = armyspeciality
end

function armyltCtrl.armyAttr(armyid, attr)
  armyid = tonumber(armyid)
  local army = armyltCtrl.armyInfo[armyid]
  if army then
    local ret = army[attr]
    if ret then
      return ret
    else
      print("armyltCtrl.armyAttr attr not found attr=", attr)
    end
  else
    print("armyltCtrl.armyAttr armyid not found armyid=", armyid)
  end
end

function armyltCtrl.getArmyIDList(bid)
  local bid = tonumber(bid)
  local ret = {}
  for k, v in pairs(armyltCtrl.armyInfo) do
    if bid == armyltCtrl.armyAttr(k, ARMY_ATTR.BARRACK_ID) then
      table.insert(ret, k)
    end
  end
  return ret
end

function armyltCtrl.getTrainArmyIDList(bid, wlv)
  return clone(armyltCtrl.biuld_army_list[bid])
end

function armyltCtrl.getSoldierType(armyid)
  local armyType = armyltCtrl.armyAttr(armyid, ARMY_ATTR.ARMY_TYPE)
  if gArmyType.infantryDf == armyType or gArmyType.infantryAk == armyType then
    return gArmyClass.infantry
  elseif gArmyType.cavalry == armyType or gArmyType.cavalryArrow == armyType then
    return gArmyClass.cavalry
  elseif gArmyType.archer == armyType or gArmyType.crossbow == armyType then
    return gArmyClass.archer
  elseif gArmyType.charists == armyType or gArmyType.siegeVehicles == armyType then
    return gArmyClass.charists
  elseif gArmyType.elite == armyType then
    return gArmyClass.elite
  elseif gArmyType.trap == armyType then
    local value1 = math.fmod(armyid, 100)
    local value2 = math.floor(value1 / 10)
    if value2 == 0 then
      return gArmyClass.stone
    elseif value2 == 1 then
      return gArmyClass.arrow
    elseif value2 == 2 then
      return gArmyClass.wood
    end
  end
end

function armyltCtrl.getArmyTypr(armyid)
  local armyType = armyltCtrl.armyAttr(armyid, ARMY_ATTR.ARMY_TYPE)
  return armyType
end

function armyltCtrl.getArmySpecialityLv(speciality)
  if speciality then
    return armyltCtrl.armyspeciality[speciality].armyspecialityLv
  end
end

function armyltCtrl.getEliteAllAbility(blv)
  local armyinfo = require("app.localtb.config_server.armyinfo")
  local armyID = 0
  for k, v in pairs(armyinfo) do
    if BUILDID.ELITE_PALACE == v.barrackID and blv >= v.barrackLevel and armyID < v.armyID then
      armyID = v.armyID
    end
  end
  local ability = 0
  if 0 < armyID then
    local akPlus = armyltCtrl.mapArmySp[armyID].akPlus
    local dfPlus = armyltCtrl.mapArmySp[armyID].dfPlus
    local hpPlus = armyltCtrl.mapArmySp[armyID].hpPlus
    if 0 < akPlus and akPlus == dfPlus and dfPlus == hpPlus then
      ability = akPlus
    end
  end
  return ability
end

local armyAttr_armySpeciality = {
  [ARMY_ATTR.ATTACK] = "akPlus",
  [ARMY_ATTR.DEFENSE] = "dfPlus",
  [ARMY_ATTR.LIFE] = "hpPlus",
  [ARMY_ATTR.STRIKE] = "critRate",
  [ARMY_ATTR.SPEED] = "speedPlus",
  [ARMY_ATTR.FREE_WEIGHT] = "freeWeightPlus"
}

function armyltCtrl.getSpecialityAddition(armyID)
  local ret = {}
  local info = armyltCtrl.mapArmySp[armyID]
  if info then
    for attr, key in pairs(armyAttr_armySpeciality) do
      local value = info[key]
      if "number" == type(value) then
        if 0 < value then
          ret[attr] = true
        else
          ret[attr] = false
        end
      elseif value then
        ret[attr] = true
      else
        ret[attr] = false
      end
    end
  end
  return ret
end

function armyltCtrl.getArmyAttrAndSp(armyID, attrKey)
  local attr = armyltCtrl.armyAttr(armyID, attrKey) or 0
  if "number" ~= type(attr) then
    return attr
  end
  local sp = 0
  local spKey = armyAttr_armySpeciality[attrKey]
  if spKey then
    local spInfo = armyltCtrl.mapArmySp[armyID]
    if spInfo then
      sp = spInfo[spKey] or 0
    end
  end
  local total = attr
  local spRate = sp
  if 0 < sp then
    sp = attr * (sp / 1000) * 10
    sp = tostring(sp)
    sp = tonumber(sp)
    sp = math.ceil(sp)
    sp = sp / 10
    total = total + sp
  end
  if 0 < spRate and sp == 0 then
    print("EX armyID: " .. tostring(armyID) .. "(" .. tostring(attrKey) .. ")")
  end
  if attrKey == ARMY_ATTR.ATTACK or attrKey == ARMY_ATTR.DEFENSE or attrKey == ARMY_ATTR.LIFE then
    local bid = armyltCtrl.armyAttr(armyID, ARMY_ATTR.BARRACK_ID)
    if bid and bid >= BUILDID.STABLES and bid <= BUILDID.BARRACKS and gHasHonorBoost(bid) then
      local buildLogic = include("buildLogic")
      local honorLv = buildLogic.getBuildMaxHonorLv(bid)
      local honorCfg = buildLogic.getHonorBuildCfg(bid, honorLv)
      local spDetailNum = honorCfg and honorCfg.spDetailNum or 0
      if 0 < spDetailNum then
        total = total * (1 + spDetailNum / 1000)
      end
    end
  end
  return total
end

function armyltCtrl.getArmySp(armyID)
  return armyltCtrl.mapArmySp[armyID]
end

function armyltCtrl.getTrainCostElitePoint(armyID)
  return armyltCtrl.armyAttr(armyID, ARMY_ATTR.COST_ELITE_POINT)
end

function armyltCtrl.getDeadToElitePoint(armyID)
  return armyltCtrl.armyAttr(armyID, ARMY_ATTR.GET_ELITE_POINT)
end

armyltCtrl.init()
return armyltCtrl
