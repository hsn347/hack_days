ARMY_ATTR = {
  ARMY_ID = "armyID",
  ARMY_TYPE = "armyType",
  BARRACK_ID = "barrackID",
  BARRACK_LEVEL = "barrackLevel",
  TRAINING_TIME = "trainingTime",
  COSTRES = "costRes",
  COST_ELITE_POINT = "UseElitePoint",
  GET_ELITE_POINT = "GetElitePoint",
  ELITE_POINT_MIN = "ElitePointMin",
  ATTACK = "attack",
  DEFENSE = "defense",
  LIFE = "life",
  ATK_INTERVAL = "atkInterval",
  ATK_DISTANCE = "atkDistance",
  STRIKE = "strike",
  POSITION = "position",
  SPEED = "speed",
  FREE_WEIGHT = "freeWeight",
  COSTFOOD = "costFood",
  POWER = "power",
  TRIGGER = "trigger",
  SPECIALITY = "speciality"
}
gArmyOpType = {
  normal = 1,
  wounded = 2,
  all = 3
}
TRAIN_TYPE = {
  SOLDIERS = 1,
  TRAP = 2,
  PROMOTION = 3
}
eWarObj = {
  null = 0,
  soldier = 1,
  trap = 2,
  tower = 3
}
gArmySpeciality = {
  resourceWarAkPlus = 1,
  charge = 3,
  infantryAkRestrain = 4,
  archerRestrain = 5,
  crossbowRestrain = 6,
  cavalryRestrain = 7,
  cavalryArrowRestrain = 8,
  dodge = 9,
  cityWarAkPlus = 10,
  cityWarDfPlus = 11,
  priorInfantry = 12,
  priorCavalry = 13,
  priorArcher = 14,
  immuneDf = 15,
  hpPlus = 16,
  dfPlus = 17,
  akPlus = 18,
  atkInvPlus = 19,
  moveSpeed = 20,
  weightPlus = 22,
  crit = 27
}
gS2CArmyAttr = {
  MASSACRE = 1,
  REDEMPTION = 2,
  SIEGEKILL = 3,
  ATTACK = 4,
  DEFENCE = 5,
  LIFE = 6,
  HURT = 7,
  TRAP_ATK = 8,
  TRAP_HURT = 9,
  SUB_HURT = 10
}
gArmyType = {
  infantryDf = 1,
  infantryAk = 2,
  cavalry = 3,
  cavalryArrow = 4,
  archer = 5,
  crossbow = 6,
  charists = 7,
  siegeVehicles = 8,
  trap = 9,
  tower = 10,
  elite = 13
}
gArmyTypeDes = {
  [gArmyType.infantryDf] = "armyName_410",
  [gArmyType.infantryAk] = "armyName_411",
  [gArmyType.cavalry] = "armyName_510",
  [gArmyType.cavalryArrow] = "armyName_511",
  [gArmyType.archer] = "armyName_610",
  [gArmyType.crossbow] = "armyName_611",
  [gArmyType.charists] = "armyName_710",
  [gArmyType.siegeVehicles] = "armyName_711",
  [gArmyType.tower] = "buildDes_name_103"
}
gArmyTypeIcon = {
  [gArmyType.infantryDf] = "kezhi_dunbing.png",
  [gArmyType.infantryAk] = "kezhi_maobing.png",
  [gArmyType.cavalry] = "kezhi_jinzhanqibing.png",
  [gArmyType.cavalryArrow] = "kezhi_gongqibing.png",
  [gArmyType.archer] = "kezhi_gongbing.png",
  [gArmyType.crossbow] = "kezhi_huoqiangbing.png",
  [gArmyType.charists] = "kezhi_toushiche.png",
  [gArmyType.siegeVehicles] = "kezhi_gongchengche.png"
}
gArmyClass = {
  infantry = 1,
  cavalry = 2,
  archer = 3,
  charists = 4,
  stone = 5,
  arrow = 6,
  wood = 7,
  elite = 8
}
gArmyTypeAdditionKey = {
  infantryDf = "infantryDf_Property",
  infantryAk = "infantryAk_Property",
  cavalry = "cavalry_Property",
  cavalryArrow = "cavalryArrow_Property",
  archer = "archer_Property",
  crossbow = "crossbow_Property",
  charists = "charists_Property",
  siegeVehicles = "siegeVehicles_Property"
}
gArmyTypeRefForClass = {
  [gArmyTypeAdditionKey.infantryDf] = gArmyClass.infantry,
  [gArmyTypeAdditionKey.infantryAk] = gArmyClass.infantry,
  [gArmyTypeAdditionKey.cavalry] = gArmyClass.cavalry,
  [gArmyTypeAdditionKey.cavalryArrow] = gArmyClass.cavalry,
  [gArmyTypeAdditionKey.archer] = gArmyClass.archer,
  [gArmyTypeAdditionKey.crossbow] = gArmyClass.archer,
  [gArmyTypeAdditionKey.charists] = gArmyClass.charists,
  [gArmyTypeAdditionKey.siegeVehicles] = gArmyClass.charists
}
eArmyIdRange = {
  [gArmyClass.infantry] = {min = 401, max = 499},
  [gArmyClass.cavalry] = {min = 501, max = 599},
  [gArmyClass.archer] = {min = 601, max = 699},
  [gArmyClass.charists] = {min = 701, max = 799},
  [gArmyClass.stone] = {min = 801, max = 810},
  [gArmyClass.arrow] = {min = 811, max = 820},
  [gArmyClass.wood] = {min = 821, max = 830}
}
gArmyAdditionDes = {
  ["1_1"] = {
    des = "lordpower_text_07",
    target = 7,
    attribute = 1,
    oldBuff = {1, 105},
    lordTecBuff = {1, 67},
    tecBuff = {29},
    wargemBuff = {1, 105},
    equipBuff = {20, 39}
  },
  ["1_2"] = {
    des = "lordpower_text_08",
    target = 7,
    attribute = 2,
    oldBuff = {3, 109},
    lordTecBuff = {2, 67},
    tecBuff = {33},
    wargemBuff = {3, 109},
    equipBuff = {24, 40}
  },
  ["1_3"] = {
    des = "lordpower_text_09",
    target = 7,
    attribute = 3,
    oldBuff = {28, 113},
    lordTecBuff = {3, 67},
    tecBuff = {37},
    wargemBuff = {28, 113},
    equipBuff = {28, 38}
  },
  ["2_1"] = {
    des = "lordpower_text_01",
    target = 8,
    attribute = 1,
    oldBuff = {1, 105},
    lordTecBuff = {1, 67},
    tecBuff = {29},
    wargemBuff = {1, 105},
    equipBuff = {20, 39}
  },
  ["2_2"] = {
    des = "lordpower_text_02",
    target = 8,
    attribute = 2,
    oldBuff = {3, 109},
    lordTecBuff = {2, 67},
    tecBuff = {33},
    wargemBuff = {3, 109},
    equipBuff = {24, 40}
  },
  ["2_3"] = {
    des = "lordpower_text_03",
    target = 8,
    attribute = 3,
    oldBuff = {28, 113},
    lordTecBuff = {3, 67},
    tecBuff = {37},
    wargemBuff = {28, 113},
    equipBuff = {28, 38}
  },
  ["3_1"] = {
    des = "lordpower_text_18",
    target = 12,
    attribute = 1,
    oldBuff = {1, 106},
    lordTecBuff = {5, 67},
    tecBuff = {30},
    wargemBuff = {1, 106},
    equipBuff = {21, 39}
  },
  ["3_2"] = {
    des = "lordpower_text_19",
    target = 12,
    attribute = 2,
    oldBuff = {3, 110},
    lordTecBuff = {6, 67},
    tecBuff = {34},
    wargemBuff = {3, 110},
    equipBuff = {25, 40}
  },
  ["3_3"] = {
    des = "lordpower_text_20",
    target = 12,
    attribute = 3,
    oldBuff = {28, 114},
    lordTecBuff = {7, 67},
    tecBuff = {38},
    wargemBuff = {28, 114},
    equipBuff = {29, 38}
  },
  ["4_1"] = {
    des = "lordpower_text_13",
    target = 11,
    attribute = 1,
    oldBuff = {1, 106},
    lordTecBuff = {5, 68},
    tecBuff = {30},
    wargemBuff = {1, 106},
    equipBuff = {21, 39}
  },
  ["4_2"] = {
    des = "lordpower_text_14",
    target = 11,
    attribute = 2,
    oldBuff = {3, 110},
    lordTecBuff = {6, 68},
    tecBuff = {34},
    wargemBuff = {3, 110},
    equipBuff = {25, 40}
  },
  ["4_3"] = {
    des = "lordpower_text_15",
    target = 11,
    attribute = 3,
    oldBuff = {28, 114},
    lordTecBuff = {7, 68},
    tecBuff = {38},
    wargemBuff = {28, 114},
    equipBuff = {29, 38}
  },
  ["5_1"] = {
    des = "lordpower_text_28",
    target = 9,
    attribute = 1,
    oldBuff = {1, 107},
    lordTecBuff = {9, 68},
    tecBuff = {31},
    wargemBuff = {1, 107},
    equipBuff = {22, 39}
  },
  ["5_2"] = {
    des = "lordpower_text_29",
    target = 9,
    attribute = 2,
    oldBuff = {3, 111},
    lordTecBuff = {10, 68},
    tecBuff = {35},
    wargemBuff = {3, 111},
    equipBuff = {26, 40}
  },
  ["5_3"] = {
    des = "lordpower_text_30",
    target = 9,
    attribute = 3,
    oldBuff = {28, 115},
    lordTecBuff = {11, 68},
    tecBuff = {39},
    wargemBuff = {28, 115},
    equipBuff = {30, 38}
  },
  ["6_1"] = {
    des = "lordpower_text_23",
    target = 10,
    attribute = 1,
    oldBuff = {1, 107},
    lordTecBuff = {9, 68},
    tecBuff = {31},
    wargemBuff = {1, 107},
    equipBuff = {22, 39}
  },
  ["6_2"] = {
    des = "lordpower_text_24",
    target = 10,
    attribute = 2,
    oldBuff = {3, 111},
    lordTecBuff = {10, 68},
    tecBuff = {35},
    wargemBuff = {3, 111},
    equipBuff = {26, 40}
  },
  ["6_3"] = {
    des = "lordpower_text_25",
    target = 10,
    attribute = 3,
    oldBuff = {28, 115},
    lordTecBuff = {11, 68},
    tecBuff = {39},
    wargemBuff = {28, 115},
    equipBuff = {30, 38}
  },
  ["7_1"] = {
    des = "lordpower_text_38",
    target = 14,
    attribute = 1,
    oldBuff = {1, 108},
    lordTecBuff = {13, 68},
    tecBuff = {32},
    wargemBuff = {1, 108},
    equipBuff = {23, 39}
  },
  ["7_2"] = {
    des = "lordpower_text_39",
    target = 14,
    attribute = 2,
    oldBuff = {3, 112},
    lordTecBuff = {14, 68},
    tecBuff = {36},
    wargemBuff = {3, 112},
    equipBuff = {27, 40}
  },
  ["7_3"] = {
    des = "lordpower_text_40",
    target = 14,
    attribute = 3,
    oldBuff = {28, 116},
    lordTecBuff = {15, 68},
    tecBuff = {40},
    wargemBuff = {28, 116},
    equipBuff = {31, 38}
  },
  ["8_1"] = {
    des = "lordpower_text_33",
    target = 13,
    attribute = 1,
    oldBuff = {1, 108},
    lordTecBuff = {13, 67},
    tecBuff = {32},
    wargemBuff = {1, 108},
    equipBuff = {23, 39}
  },
  ["8_2"] = {
    des = "lordpower_text_34",
    target = 13,
    attribute = 2,
    oldBuff = {3, 112},
    lordTecBuff = {14, 67},
    tecBuff = {36},
    wargemBuff = {3, 112},
    equipBuff = {27, 40}
  },
  ["8_3"] = {
    des = "lordpower_text_35",
    target = 13,
    attribute = 3,
    oldBuff = {28, 116},
    lordTecBuff = {15, 67},
    tecBuff = {40},
    wargemBuff = {28, 116},
    equipBuff = {31, 38}
  }
}
gHightLvArmyId = {
  [gArmyType.infantryDf] = 412,
  [gArmyType.infantryAk] = 411,
  [gArmyType.cavalry] = 512,
  [gArmyType.cavalryArrow] = 511,
  [gArmyType.archer] = 612,
  [gArmyType.crossbow] = 611,
  [gArmyType.charists] = 712,
  [gArmyType.siegeVehicles] = 711
}
