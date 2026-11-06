// ════════════════════════════════════════════════════
//  Firebase Types — مشتقة من firebase_schema.json
// ════════════════════════════════════════════════════

export interface Subscription {
  plan_id?: string
  plan_name: string
  status: 'active' | 'expired' | 'suspended' | 'pending_approval'
  started_at: string
  expires_at: string
  days_remaining: number
  months_duration?: number
  max_castles_allowed: number
  current_castles_count: number
  pending_castles_count?: number
}

export interface User {
  uid: string
  username: string
  email: string
  phone?: string
  role: 'user' | 'admin' | 'merchant_admin' | string
  tenant_domain?: string
  is_super_admin?: boolean
  is_merchant_admin?: boolean
  created_at: string
  is_banned: boolean
  banned_reason?: string
  subscription: Subscription
}

export interface CastleInfo {
  lord_name: string
  castle_name: string
  server_id: number
  castle_level: number
  lord_power: number
  vip_level: number
  alliance_name: string
  coordinates: { x: number; y: number }
  avatar?: string
  image_id?: number
}

export interface Resources {
  food: number
  wood: number
  iron: number
  diamond: number
  gold: number
  stamina: number
  unprotected_food?: number
  unprotected_wood?: number
  unprotected_iron?: number
  unprotected_diamond?: number
  safe_food?: number
  safe_wood?: number
  safe_iron?: number
  safe_diamond?: number
  last_updated: string
}

export type BotState = 'running' | 'idle' | 'error' | 'paused' | 'pending' | 'disconnected' | 'reconnecting' | 'waiting' | 'deploying'

export interface BotStatus {
  state: BotState
  last_run_time: string
  next_run_time: string
  last_run_message: string
  active_marches: number
  max_marches: number
  last_error: string | null
  // حالة الاتصال الفعلية (connected | disconnected | reconnecting | waiting | idle)
  conn_state?: string
  conn_message?: string
  conn_updated?: string
}

// ─── Task Configs ─────────────────────────────────────
export interface BaseTaskConfig {
  enabled: boolean
}

export interface TrainLevels {
  infantry: number
  cavalry: number
  archers: number
  chariots: number
}

export interface MarchManagerConfig extends BaseTaskConfig {
  max_queues?: number
  priority_order?: string[]
  abra?: AbraConfig
  prestige_invaders?: { enabled: boolean }
  prestige_stronghold?: { enabled: boolean }
  prestige_gather?: { enabled: boolean }
  transport: { enabled: boolean; target_x: number | null; target_y: number | null; resource_ids: number[] }
  ruins: { enabled: boolean; explore_time: number; formation_id: number }
  combat: { enabled: boolean; choice: 'elf' | 'invaders' | 'rebels'; level: number; formation_id: number }
  invaders: { enabled: boolean; level: number; formation_id: number }
  rebels: { enabled: boolean; level: number; formation_id: number }
  stronghold: { enabled: boolean; level: number; count: number; formation_id: number }
  gold_gather?: { enabled: boolean; locations?: GoldLocation[] }
  gather: { enabled: boolean; res_type: number; level: number; search_range: number; use_boost?: boolean }
}

export interface PrestigeSubtasks {
  smuggler: boolean
  watermill: boolean
  train: boolean
  fortress: boolean
}

export interface CastleConfig {
  city_harvest: BaseTaskConfig
  research: BaseTaskConfig
  alliance: BaseTaskConfig & { gold_donations: number; auto_help?: boolean; open_treasure?: boolean }
  port: BaseTaskConfig
  train: BaseTaskConfig & { levels: TrainLevels }
  pet_patrol: BaseTaskConfig & { pet?: string; destination?: number }
  territory_expansion: BaseTaskConfig
  torch_chest?: BaseTaskConfig
  open_torch_chest?: BaseTaskConfig
  hero_consign?: BaseTaskConfig
  shield: BaseTaskConfig & { duration: '8h' | '24h' | '3d'; allow_gold: boolean }
  stamina: BaseTaskConfig & { gold_buys: number }
  skills: BaseTaskConfig & { target_skills: string[] }
  hero_draw: BaseTaskConfig
  treasure_pavilion: BaseTaskConfig
  blacksmith_forge: BaseTaskConfig
  imperial_mausoleum: BaseTaskConfig
  alliance_treasure: BaseTaskConfig & { index?: number }
  daily_luxury_gift: BaseTaskConfig
  vip_gift: BaseTaskConfig
  tactics_hall: BaseTaskConfig & { tactic: string }
  watermill: BaseTaskConfig & { types: string; allow_shop_buy: boolean }
  fountain: BaseTaskConfig & { resources: string[]; allow_gold: boolean; gold_times: number; use_gold?: boolean }
  material_workshop: BaseTaskConfig & { materials: string[] }
  caravan: BaseTaskConfig
  port_delegate: BaseTaskConfig & { shop_item: string }
  savings_bank: BaseTaskConfig & { days: number; deposit?: number }
  building: BaseTaskConfig & { upgrade_castle: boolean; speedup_castle: boolean; upgrade_support_buildings: boolean; target_buildings?: Record<string, boolean> }
  prestige: BaseTaskConfig & { subtasks: PrestigeSubtasks }
  march_manager: MarchManagerConfig
  elf?: BaseTaskConfig & { formation_id: number }
  troy_treasure?: BaseTaskConfig & {
    subtasks?: {
      claim_quests?: boolean
      [key: string]: any
    }
  }
  warrior_exchange?: BaseTaskConfig & { count: number }
  auction?: BaseTaskConfig & { max_gold: number }
  hospital?: BaseTaskConfig & { mode?: 'prestige' | 'all' }
  gather_boost?: BaseTaskConfig
  gold_gather?: { enabled: boolean; locations: GoldLocation[] }
  abra?: AbraConfig
}

export interface AbraConfig extends BaseTaskConfig {
  x: number
  y: number
  killing_blow: boolean
  formation_id?: number
}


export interface Castle {
  id: string
  castle_id: string
  email: string
  password?: string
  is_active: boolean
  created_at: string
  castle_info: CastleInfo
  resources: Resources
  bot_status: BotStatus
  config: CastleConfig
  version?: number
  loop_interval?: number
}

export const DEFAULT_CASTLE_CONFIG: CastleConfig = {
  // جميع المهام مغلقة افتراضياً عند إضافة قلعة جديدة باستثناء جمع القمح لفل 4
  city_harvest: { enabled: false },
  research: { enabled: false },
  alliance: { enabled: false, gold_donations: 0, open_treasure: true },
  port: { enabled: false },
  train: { enabled: false, levels: { infantry: 0, cavalry: 0, archers: 0, chariots: 0 } },
  pet_patrol: { enabled: false, pet: 'الأسد', destination: 1350 },
  territory_expansion: { enabled: false },
  torch_chest: { enabled: false },
  open_torch_chest: { enabled: false },
  hero_consign: { enabled: false },
  shield: { enabled: false, duration: '8h', allow_gold: false },
  stamina: { enabled: false, gold_buys: 0 },
  skills: { enabled: false, target_skills: [] },
  hero_draw: { enabled: false },
  treasure_pavilion: { enabled: false },
  blacksmith_forge: { enabled: false },
  imperial_mausoleum: { enabled: false },
  alliance_treasure: { enabled: false, index: 1 },
  daily_luxury_gift: { enabled: false },
  vip_gift: { enabled: false },
  tactics_hall: { enabled: false, tactic: 'القلعة الفارغة' },
  watermill: { enabled: false, types: 'food', allow_shop_buy: false },
  fountain: { enabled: false, resources: ['food', 'wood', 'iron', 'diamond'], allow_gold: false, gold_times: 0 },
  material_workshop: { enabled: false, materials: [] },
  caravan: { enabled: false },
  port_delegate: { enabled: false, shop_item: 'all' },
  savings_bank: { enabled: false, days: 7, deposit: 2000 },
  building: { enabled: false, upgrade_castle: false, speedup_castle: false, upgrade_support_buildings: false },
  prestige: {
    enabled: false,
    subtasks: {
      smuggler: false,
      watermill: false,
      train: false,
      fortress: false,
    },
  },
  troy_treasure: {
    enabled: false,
    subtasks: {
      claim_quests: false,
    },
  },
  warrior_exchange: { enabled: false, count: 15 },
  hospital: { enabled: false, mode: 'prestige' },
  gather_boost: { enabled: false },
  elf: { enabled: false, formation_id: 1 },
  march_manager: {
    enabled: true,
    abra: { enabled: false, x: 0, y: 0, killing_blow: false, formation_id: 1 },
    prestige_invaders: { enabled: false },
    prestige_stronghold: { enabled: false },
    prestige_gather: { enabled: false },
    transport: { enabled: false, target_x: null, target_y: null, resource_ids: [] },
    ruins: { enabled: false, explore_time: 900, formation_id: 1 },
    combat: { enabled: false, choice: 'invaders', level: 15, formation_id: 1 },
    invaders: { enabled: false, level: 15, formation_id: 1 },
    rebels: { enabled: false, level: 5, formation_id: 1 },
    stronghold: { enabled: false, level: 5, count: 1, formation_id: 1 },
    gold_gather: { enabled: false, locations: [] },
    gather: { enabled: true, res_type: 2, level: 4, search_range: 100 },
  },
}

export const FIXED_PRESET_CONFIG: CastleConfig = {
  // 1. جمع الموارد بتحديد مورد الحديد (Iron = 4)
  march_manager: {
    enabled: true,
    prestige_invaders: { enabled: false },
    prestige_stronghold: { enabled: false },
    prestige_gather: { enabled: false },
    transport: { enabled: false, target_x: null, target_y: null, resource_ids: [] },
    ruins: { enabled: false, explore_time: 900, formation_id: 1 },
    combat: { enabled: false, choice: 'elf', level: 30, formation_id: 1 },
    invaders: { enabled: false, level: 30, formation_id: 1 },
    rebels: { enabled: false, level: 5, formation_id: 1 },
    stronghold: { enabled: false, level: 30, count: 2, formation_id: 1 },
    gold_gather: { enabled: false, locations: [] },
    gather: { enabled: true, res_type: 4, level: 5, search_range: 100 },
  },
  // 2. مكافأة الطاحونة لكل الموارد مع السماح للشراء من المتجر
  watermill: { enabled: true, types: 'all', allow_shop_buy: true },
  // 3. مهمة قافلة الغنيمة
  caravan: { enabled: true },
  // 4. مهام التحالف مع التبرع للتحالف
  alliance: { enabled: true, gold_donations: 0, open_treasure: true },
  // 5. دورية الحيوانات على حيوان كلب الكانغال (1371)
  pet_patrol: { enabled: true, pet: 'كلب الكنغال', destination: 1371 },
  // 6. دراسة الاستراتيجيات على القلعة الفارغة
  tactics_hall: { enabled: true, tactic: 'القلعة الفارغة' },
  // 7. نافورة الأمنيات على كل الموارد بدون شراء من المتجر
  fountain: { enabled: true, resources: ['food', 'wood', 'iron', 'coal', 'diamond'], allow_gold: false, gold_times: 0 },
  // 8. ورشة المواد على كل المواد
  material_workshop: { enabled: true, materials: ['fang', 'fur', 'metal', 'coal'] },
  // 9 & 10. مكافأة الجمع السريع ومكافأة الحصاد
  skills: { enabled: true, target_skills: ['harvest', 'gather'] },
  // 11. الزنزانة الأساسية لكل العناصر
  port_delegate: { enabled: true, shop_item: 'all' },
  // 12. التوسع الإقليمي
  territory_expansion: { enabled: true },
  torch_chest: { enabled: false },
  open_torch_chest: { enabled: false },
  hero_consign: { enabled: false },

  // المهام الأساسية
  city_harvest: { enabled: true },
  research: { enabled: false },
  port: { enabled: false },
  train: { enabled: false, levels: { infantry: 0, cavalry: 0, archers: 0, chariots: 0 } },
  shield: { enabled: false, duration: '8h', allow_gold: false },
  stamina: { enabled: false, gold_buys: 0 },
  hero_draw: { enabled: false },
  treasure_pavilion: { enabled: true },
  blacksmith_forge: { enabled: true },
  imperial_mausoleum: { enabled: true },
  alliance_treasure: { enabled: true, index: 1 },
  daily_luxury_gift: { enabled: true },
  vip_gift: { enabled: true },
  savings_bank: { enabled: false, days: 7, deposit: 2000 },
  building: { enabled: false, upgrade_castle: false, speedup_castle: false, upgrade_support_buildings: false },
  prestige: {
    enabled: false,
    subtasks: {
      smuggler: false,
      watermill: false,
      train: false,
      fortress: false,
    },
  },
  troy_treasure: {
    enabled: true,
    subtasks: {
      claim_quests: true,
    },
  },
  warrior_exchange: { enabled: false, count: 15 },
  hospital: { enabled: false, mode: 'prestige' },
  gather_boost: { enabled: false },
  elf: { enabled: false, formation_id: 1 },
  abra: { enabled: false, x: 0, y: 0, killing_blow: false },
}

export interface CastleLog {
  id: string
  timestamp: string
  step: string
  title: string
  status: 'success' | 'error' | 'warning' | 'info'
  details: Record<string, unknown>
  message: string
}

// ─── UI Types ────────────────────────────────────────
export type Theme = 'dark' | 'light'
export type Language = 'ar' | 'en' | 'tr'

export type TaskTab =
  | 'gather'
  | 'train'
  | 'combat'
  | 'watermill'
  | 'transport'
  | 'prestige'
  | 'daily'
  | 'building'
  | 'events'
  | 'gold'
  | 'gold_bot'

export interface GoldLocation {
  x: number
  y: number
  alliance_tag?: string
}

export interface StatsCard {
  label: string
  value: string | number
  icon: string
  color: string
  delta?: string
}
