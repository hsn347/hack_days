# -*- coding: utf-8 -*-
from .base_task import BaseTask, TaskResult, TaskScheduler
from .watermill import WatermillTask
from .caravan import CaravanTask
from .pet_patrol import PetPatrolTask
from .alliance import AllianceTask
from .stamina import StaminaTask
from .savings_bank import SavingsBankTask
from .shield import ShieldTask
from .hero_draw import HeroDrawTask
from .material_workshop import MaterialWorkshopTask
from .tactics_hall import TacticsHallTask
from .train import TrainTask
from .fortress import FortressTask
from .merchant import MerchantTask
from .skills import SkillsTask
from .fountain import FountainTask
from .port_delegate import PortDelegateTask
from .territory_expansion import TerritoryExpansionTask
from .gold_gather import GoldGatherTask
from .research import ResearchTask
from .building import BuildingTask
from .city_harvest import CityHarvestTask
from .prestige import PrestigeTask
from .prestige_box import PrestigeBoxTask
from .treasure_pavilion import TreasurePavilionTask
from .blacksmith_forge import BlacksmithForgeTask
from .imperial_mausoleum import ImperialMausoleumTask
from .alliance_treasure import AllianceTreasureTask
from .daily_luxury_gift import DailyLuxuryGiftTask
from .vip_gift import VipGiftTask
from .troy_treasure import TroyTreasureTask

__all__ = [
    'BaseTask', 'TaskResult', 'TaskScheduler',
    'WatermillTask', 'CaravanTask', 'PetPatrolTask', 'AllianceTask',
    'StaminaTask', 'SavingsBankTask', 'ShieldTask', 'HeroDrawTask',
    'MaterialWorkshopTask', 'TacticsHallTask', 'TrainTask', 'FortressTask',
    'MerchantTask', 'SkillsTask', 'FountainTask', 'PortDelegateTask',
    'TerritoryExpansionTask', 'GoldGatherTask', 'ResearchTask', 'BuildingTask',
    'CityHarvestTask', 'PrestigeTask', 'PrestigeBoxTask', 'TreasurePavilionTask', 'BlacksmithForgeTask',
    'ImperialMausoleumTask', 'AllianceTreasureTask', 'DailyLuxuryGiftTask', 'VipGiftTask', 'TroyTreasureTask'
]

