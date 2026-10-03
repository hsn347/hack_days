local gameModule = include("GameModule")
local gametop = gModuleMgr.getObject("gametop")
local serverproxy = gModuleMgr.getObject("serverproxy")
local allianceltCtrl = include("allianceltCtrl")
local msgCtrl = include("msgCtrl")
local allianceScience = class("allianceScience", gameModule)

function allianceScience:ctor(properties)
  allianceScience.super.ctor(self, properties)
  self:resetData()
end

function allianceScience:resetData()
  self.scienceList = {}
  self.scienceList.queue = {}
  self.donatequeue = {}
  self.superqueue = {}
  self.superQueuetypes = {
    [37001] = ALLIANCE_DONATE_SUPER_QUEUE_37001,
    [37002] = ALLIANCE_DONATE_SUPER_QUEUE_37002
  }
end

function allianceScience:getDonateHonorAdd()
  local buffCtrl = gametop.playertop_:getModule("buffCtrl")
  local addrate = (buffCtrl:getBuffEffect(gBuffEffect.AT_DONATE_HONOR_BOOST, gBuffSource.ACTIVITY) or 0) / 1000
  return addrate
end

function allianceScience:getDonateScoreAdd()
  local buffCtrl = gametop.playertop_:getModule("buffCtrl")
  local addrate = (buffCtrl:getBuffEffect(gBuffEffect.AT_DONATE_BONUS_BOOST, gBuffSource.ACTIVITY) or 0) / 1000
  return addrate
end

function allianceScience:researchSciQueueCallBack(event)
  local date = event.data
  local sciid = date.sciid
  local data = {
    uid = gametop.playertop_:getPlayerID()
  }
  local allianceMgr = gametop.playertop_:getModule("allianceMgr")
  allianceMgr:reqGetAllianceScience(data)
  SoraDSendMessage({
    msg = "MESSAGE_ALLIANCE_STUDY_END",
    sciid = sciid
  })
end

function allianceScience:donateSciQueueCallBack(event)
  local memberMgr = gametop.playertop_:getModule("memberMgr")
  local member = memberMgr:getOwnMember()
  member:setProperty("donateLock", 0)
  SoraDSendMessage({
    msg = "MESSAGE_ALLIACNE_DONATE_CD_CLEAN_SUCCESS"
  })
end

function allianceScience:setScienceList(sciencelist)
  for groupid, groupscilist in pairs(sciencelist.scilist) do
    table.sort(groupscilist, function(l, r)
      if l and r then
        return l.id < r.id
      else
        return false
      end
    end)
  end
  self.scienceList.scilist = sciencelist.scilist
  for i, group in pairs(sciencelist.scilist) do
    for _, v in pairs(group or {}) do
      if self:isSuperQueuetype(v.id) and v.useTime then
        self:addSuperQueue(v.id, v.lv)
      end
    end
  end
  local researchsciqueue = sciencelist.queue[SCIENCE_RESEARCH_QUEUE]
  if researchsciqueue then
    local starttime = researchsciqueue.starttime
    local totaltime = researchsciqueue.totaltime
    local nowtime = serviceFunctions.systemTime()
    local lasttime = nowtime - starttime
    local lefttime = totaltime - lasttime
    if lefttime <= 0 then
      lefttime = 0
    end
    self:addQueue(SCIENCE_RESEARCH_QUEUE, starttime, totaltime, lefttime, researchsciqueue.data)
  end
end

function allianceScience:updateScienceData(list)
  if istable(list) then
    for i, v in pairs(list) do
      for i1, v1 in pairs(self.scienceList.scilist) do
        for i2, v2 in pairs(v1) do
          if v2.id == v.id then
            self.scienceList.scilist[i1][i2] = v
            local queuetype = self.superQueuetypes[v2.id]
            local queue = self:queryQueue(queuetype)
            if queue and not v.useTime then
              self:removeQueue(queuetype)
            end
            if v.useTime and not queue then
              self:addSuperQueue(v2.id, v.lv)
            end
            SoraDSendMessage({
              msg = "MESSAGE_ALLIANCE_SCIENCE_CHANGE_BACK",
              sciid = v2.id
            })
          end
        end
      end
    end
  end
end

function allianceScience:getScienceGroup()
  return self.scienceList.scilist
end

function allianceScience:getRecommendList()
  local rect = {}
  for k, v in pairs(self.scienceList.scilist) do
    for _k, _v in pairs(v) do
      if _v.recommend then
        table.insert(rect, _v)
      end
    end
  end
  return rect
end

function allianceScience:getCurMaxGroupID()
  local ret = gAScienceGroup.G1
  for k, v in pairs(table.keys(self.scienceList.scilist)) do
    if ret < tonumber(v) then
      ret = tonumber(v)
    end
  end
  return ret
end

function allianceScience:getNextGroupSciIDList()
  local nextgroupid = self:getCurMaxGroupID() + 1
  if nextgroupid <= gAScienceGroup.G7 then
    local ret = allianceltCtrl.getScienceIDList(nextgroupid)
    table.sort(ret)
    local needlv = allianceltCtrl.scienceAttr(ret[1], gAScienceInfo.OPENLV)
    return ret, needlv
  end
end

function allianceScience:getCurSciTotalLv()
  local ret = 0
  for groupid, groupscilist in pairs(self.scienceList.scilist) do
    for k, scidata in pairs(groupscilist) do
      ret = ret + scidata.lv
    end
  end
  return ret
end

function allianceScience:getScienceData(id)
  if id then
    for groupid, groupscilist in pairs(self.scienceList.scilist) do
      for _k, _v in pairs(groupscilist) do
        if _v.id == id then
          return _v
        end
      end
    end
  end
end

function allianceScience:getScienceAddValue(scitype)
  local gametop = gModuleMgr.getObject("gametop")
  local allianceMgr = gametop.playertop_:getModule("allianceMgr")
  local ownalliid = allianceMgr:getOwnAid()
  if not ownalliid then
    return 0
  end
  local ret = 0
  local sciidlist = allianceltCtrl.getSciIDListBySciType(scitype)
  for k, sciid in pairs(sciidlist) do
    local scidata = self:getScienceData(sciid)
    if scidata then
      local dtype, addvalue = allianceltCtrl.getScienceValue(sciid, scidata.lv)
      ret = ret + addvalue
    end
  end
  return ret
end

function allianceScience:EnterGame()
  allianceScience.super.EnterGame(self)
  msgCtrl.register(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_DONATE_SCI, handler(self, self.DonateSciRsp))
  msgCtrl.register(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_RESEARCH_SCI, handler(self, self.ResearchSciRsp))
  msgCtrl.register(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_CLEAN_DONATE_SCI_CD, handler(self, self.CleanDonateSciCDRsp))
  msgCtrl.register(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_RECOMMENT_SCIENCE, handler(self, self.RecommentRsp))
  msgCtrl.register(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_USE_TECH, handler(self, self.useSuperScienceRsp))
  self:addEventListener(SCIENCE_RESEARCH_QUEUE, handler(self, self.researchSciQueueCallBack))
  self:addEventListener(SCIENCE_DONATE_QUEUE, handler(self, self.donateSciQueueCallBack))
end

function allianceScience:Logout()
  allianceScience.super.Logout(self)
  self:resetData()
end

function allianceScience:addQueue(queuetype, starttime, totaltime, lefttime, data)
  local curqueue = self:queryQueue(queuetype)
  if not curqueue then
    local function dispatchQueueEvent()
      local event = {name = queuetype, data = data}
      
      if queuetype == SCIENCE_RESEARCH_QUEUE then
        self.scienceList.queue[SCIENCE_RESEARCH_QUEUE] = nil
      elseif self:isSuperQueuetype(nil, queuetype) then
        self.superqueue[queuetype] = nil
      else
        self.donatequeue[queuetype] = nil
      end
      self:dispatchEvent(event)
    end
    
    local queue = {}
    queue.qtype = queuetype
    queue.starttime = starttime
    queue.totaltime = totaltime
    queue.data = data
    local timerList = gModuleMgr.getObject("timerList")
    local ok, node = timerList:createTimer(lefttime, timerHandler(dispatchQueueEvent))
    if ok then
      queue.timerNode = node
      if queuetype == SCIENCE_RESEARCH_QUEUE then
        self.scienceList.queue[SCIENCE_RESEARCH_QUEUE] = queue
      elseif self:isSuperQueuetype(nil, queuetype) then
        self.superqueue[queuetype] = queue
      else
        self.donatequeue[queuetype] = queue
      end
    end
  end
end

function allianceScience:removeQueue(queuetype)
  local issuccess = false
  local queue = self:queryQueue(queuetype)
  if queue then
    issuccess = true
    local timerList = gModuleMgr.getObject("timerList")
    timerList:cancelTimer(queue.timerNode)
    if queuetype == SCIENCE_RESEARCH_QUEUE then
      self.scienceList.queue[queuetype] = nil
    elseif self:isSuperQueuetype(nil, queuetype) then
      self.superqueue[queuetype] = nil
    else
      self.donatequeue[queuetype] = nil
    end
  end
  return issuccess
end

function allianceScience:queryQueue(queuetype)
  if queuetype == SCIENCE_RESEARCH_QUEUE then
    local ret = self.scienceList.queue[SCIENCE_RESEARCH_QUEUE]
    if ret then
      return ret
    end
  elseif self:isSuperQueuetype(nil, queuetype) then
    local ret = self.superqueue[queuetype]
    if ret then
      return ret
    end
  else
    local ret = self.donatequeue[queuetype]
    if ret then
      return ret
    end
  end
end

function allianceScience:getScienceTechTime(scienceid)
  local buffCtrl = gametop.playertop_:getModule("buffCtrl")
  local addrate = (buffCtrl:getBuffEffect(gBuffEffect.AT_RESEARCH_SPEED_BOOST, gBuffSource.ACTIVITY) or 0) / 1000
  local scidata = self:getScienceData(scienceid)
  local allianceltCtrl = include("allianceltCtrl")
  local basetime = allianceltCtrl.scienceLvInfo(scidata.id, scidata.lv, gAScienceLv.RESEARCH_TIME) or 0
  local addalliacnesci = self:getScienceAddValue(gAScienceType.ALLIANCE_SCIENCE_RESEARCH_TIME)
  local researchtime = basetime * (1 / (1 + addalliacnesci))
  local activitytime = basetime * (1 / (1 + addalliacnesci + addrate))
  return researchtime, activitytime
end

function allianceScience:reqDonateSci(sciid, donatetype, ...)
  serverproxy:Request(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_DONATE_SCI, {sciid = sciid, donatetype = donatetype}, ...)
end

function allianceScience:reqResearchSci(sciid, ...)
  serverproxy:Request(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_RESEARCH_SCI, {sciid = sciid}, ...)
end

function allianceScience:reqCleanDonateSciCD(...)
  serverproxy:Request(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_CLEAN_DONATE_SCI_CD, {}, ...)
end

function allianceScience:reqSetRecommend(data)
  dump(data, "\232\174\190\231\189\174\230\142\168\232\141\144\232\129\148\231\155\159\231\167\145\230\138\128")
  serverproxy:Request(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_RECOMMENT_SCIENCE, data)
end

function allianceScience:reqUseSuperScience(id)
  print("allianceScience:reqUseSuperScience", id)
  local data = {sciid = id}
  serverproxy:Request(gCmd.CMD_ALLIANCE_MODULE, gCmd.REQ_ALLIANCE_USE_TECH, data)
end

function allianceScience:useSuperScienceRsp(content)
  dump(content, "allianceScience:useSuperScienceRsp", 10)
  if content.err ~= gErrDef.Err_None or content.data then
  end
end

function allianceScience:addSuperQueue(id, lv)
  if self:isSuperQueuetype(id) then
    local data = self:getScienceData(id)
    local useTime = data.useTime
    if useTime then
      local totalTime = allianceltCtrl.scienceLvInfo(id, lv, "attrBuffTime")
      if 0 < totalTime then
        local nowtime = serviceFunctions.systemTime()
        local lasttime = nowtime - useTime
        local lefttime = totalTime - lasttime
        if lefttime <= 0 then
          lefttime = 0
        end
        self:addQueue(self.superQueuetypes[id], useTime, totalTime, lefttime, data)
      end
    end
  end
end

function allianceScience:isSuperQueuetype(id, qtype)
  for i, v in pairs(self.superQueuetypes) do
    if i == id or v == qtype then
      return true
    end
  end
end

function allianceScience:getSuperQueueType(id)
  return self.superQueuetypes[id]
end

function allianceScience:DonateSciRsp(content)
  if content.err == gErrDef.Err_None then
    local data = content.data.retdata
    local memberinfo = data.memberinfo
    local member = include("member").new()
    member:setProperty("minfo", memberinfo)
    local memberMgr = gametop.playertop_:getModule("memberMgr")
    memberMgr:addMember(member)
    local addTime = gConstValue.ALLIANCE_DONATE_CD_TIME_EVERYTIME
    local queue = self:queryQueue(SCIENCE_DONATE_QUEUE)
    if queue then
      local timerList = gModuleMgr.getObject("timerList")
      timerList:increaseTime(queue.timerNode, addTime)
    else
      local starttime = serviceFunctions.systemTime()
      local totaltime = addTime
      local lefttime = addTime
      self:addQueue(SCIENCE_DONATE_QUEUE, starttime, totaltime, lefttime)
    end
    local costres = data.costres
    local get = data.get
    if get then
      local addhonor = get.honor
      local score = get.score
      local addscipoint = get.scipoint
      local scidouble = get.scidouble
      local honordouble = get.honordouble
      local rate = get.rate
      local msgNotice = include("msgNotice")
      msgNotice.notice("notice_0079", {count1 = addhonor, count2 = score})
      if scidouble and not honordouble then
        SoraDSendMessage({
          msg = "MESSAGE_ALLIANCE_CONTRIBUTE_DOUBLE",
          bType = 1
        })
      end
      if honordouble and not scidouble then
        SoraDSendMessage({
          msg = "MESSAGE_ALLIANCE_CONTRIBUTE_DOUBLE",
          bType = 2
        })
      end
      if scidouble and honordouble then
        SoraDSendMessage({
          msg = "MESSAGE_ALLIANCE_CONTRIBUTE_DOUBLE",
          bType = 3
        })
      end
      if rate and 1 < rate then
        SoraDSendMessage({
          msg = "MESSAGE_ALLIANCE_DONATE_CRIT",
          crit = rate
        })
      end
    end
  else
    print("rsp error: ", content.err)
    if content.err == gErrDef.Err_ALLIANCE_SCORE_DONATE_MAX then
      local msgNotice = include("msgNotice")
      msgNotice.notice("notice_0185", {count = ALLIANCE_SCORE_DONATE_MAX_COUNT_DAY})
    end
  end
  SoraDSendMessage({
    msg = "MESSAGE_ALLIACNE_DONATE_SUCCESS",
    sciid = content.data.sciid
  })
end

function allianceScience:RecommentRsp(content)
  dump(content, "\232\174\190\231\189\174\230\142\168\232\141\144\231\167\145\230\138\128\229\147\141\229\186\148")
  if content.err == gErrDef.Err_None then
    SoraDSendMessage({
      msg = "MESSAGE_ALLIACNE_REMMOND_SCIENCE"
    })
    SoraDShowMsgTip(i18n("common_text_4131"))
  elseif content.err == gErrDef.Err_ALLIANCE_SCIENCE_RECOMMEND_LIMIT then
    SoraDShowMsgTip(i18n("alliance_science_des_01"))
  end
end

function allianceScience:ResearchSciRsp(content)
  dump(content, "\231\160\148\231\169\182\232\129\148\231\155\159\231\167\145\230\138\128\229\147\141\229\186\148", 10)
  if content.err == gErrDef.Err_None then
  else
    SoraDShowMsgTip(i18n("notice_0026"))
    SoraDSendMessage({
      msg = "MESSAGE_ALLIANCE_STUDY_END"
    })
  end
end

function allianceScience:CleanDonateSciCDRsp(content)
  if content.err == gErrDef.Err_None then
    local data = content.data.retdata
    local memberinfo = data.memberinfo
    local member = include("member").new()
    member:setProperty("minfo", memberinfo)
    local memberMgr = gametop.playertop_:getModule("memberMgr")
    memberMgr:addMember(member)
    self:removeQueue(SCIENCE_DONATE_QUEUE)
    SoraDSendMessage({
      msg = "MESSAGE_ALLIACNE_DONATE_CD_CLEAN_SUCCESS"
    })
  else
    print("rsp error: ", content.err)
  end
end

function allianceScience:getAllianceFlagInfo()
  local scitype = gAScienceType.ADD_ALLIANCE_FLAG_NUM
  local ret = {}
  ret.curSciAddCount = self:getScienceAddValue(scitype)
  ret.maxSciAddCount = 0
  local sciidlist = allianceltCtrl.getSciIDListBySciType(scitype)
  for k, sciid in pairs(sciidlist) do
    local maxLv = allianceltCtrl.scienceAttr(sciid, gAScienceInfo.MAXLV)
    local dtype, addCount = allianceltCtrl.getScienceValue(sciid, maxLv)
    if addCount then
      ret.maxSciAddCount = ret.maxSciAddCount + addCount
    end
  end
  return ret
end

function allianceScience:dump()
  print("==============allianceScience:dump()=================")
  dump(self.scienceList)
end

return allianceScience
