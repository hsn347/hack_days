// ════════════════════════════════════════════════════
//  Firebase Types — مشتقة من firebase_schema.json
// ════════════════════════════════════════════════════

export interface Subscription {
  plan_id: 'free' | 'basic' | 'pro' | 'vip_pro' | 'enterprise'
  plan_name: string
  status: 'active' | 'expired' | 'suspended'
  started_at: string
  expires_at: string
  days_remaining: number
  max_castles_allowed: number
  current_castles_count: number
}

export interface User {
  uid: string
  username: string
  email: string
  phone?: string
  role: 'user' | 'admin'
  created_at: string
  is_banned: boolean
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
}

export interface Resources {
  food: number
  wood: number
  iron: number
  diamond: number
  gold: number
  stamina: number
  last_updated: string
}

export type BotState = 'running' | 'idle' | 'error' | 'paused' | 'pending'

export interface BotStatus {
  state: BotState
  last_run_time: string
  next_run_time: string
  last_run_message: string
  active_marches: number
  max_marches: number
  last_error: string | null
}

// ─── Task Configs ─────────────────────────────────────
export interface ScheduleConfig {
  times_per_day?: number
  hours?: number[]
  active_window?: { from: number; to: number }
}

export interface BaseTaskConfig {
  enabled: boolean
  schedule?: ScheduleConfig
}

export interface TrainLevels {
  infantry: number
  cavalry: number
  archers: number
  chariots: number
}

export interface MarchManagerConfig extends BaseTaskConfig {
  max_queues: number
  priority_order: string[]
  transport: { enabled: boolean; target_x: number | null; target_y: number | null; resource_ids: number[] }
  ruins: { enabled: boolean; explore_time: number; formation_id: number }
  combat: { enabled: boolean; choice: 'elf' | 'invaders' | 'rebels'; level: number; formation_id: number; count: number }
  elf: { enabled: boolean; formation_id: number }
  invaders: { enabled: boolean; level: number; formation_id: number; count: number }
  rebels: { enabled: boolean; level: number; formation_id: number; count: number }
  stronghold: { enabled: boolean; level: number; count: number; formation_id: number }
  gather: { enabled: boolean; res_type: number; level: number; search_range: number }
}

export interface PrestigeSubtasks {
  smuggler: boolean
  invaders: boolean
  stronghold: boolean
  gather: boolean
  watermill: boolean
  train: boolean
  fortress: boolean
}

export interface CastleConfig {
  city_harvest: BaseTaskConfig
  research: BaseTaskConfig
  alliance: BaseTaskConfig & { auto_help: boolean; gold_donations: number }
  port: BaseTaskConfig
  train: BaseTaskConfig & { levels: TrainLevels }
  pet_patrol: BaseTaskConfig & { pet: string }
  territory_expansion: BaseTaskConfig
  shield: BaseTaskConfig & { duration: '8h' | '24h' | '3d'; allow_gold: boolean }
  stamina: BaseTaskConfig & { gold_buys: number }
  skills: BaseTaskConfig & { target_skills: string[] }
  hero_draw: BaseTaskConfig
  tactics_hall: BaseTaskConfig & { tactic: string }
  watermill: BaseTaskConfig & { types: string; allow_shop_buy: boolean }
  fountain: BaseTaskConfig & { resources: string[]; allow_gold: boolean; gold_times: number }
  material_workshop: BaseTaskConfig & { materials: string[] }
  caravan: BaseTaskConfig
  port_delegate: BaseTaskConfig & { shop_item: string }
  savings_bank: BaseTaskConfig & { days: number }
  building: BaseTaskConfig & { upgrade_castle: boolean; speedup_castle: boolean; upgrade_support_buildings: boolean }
  prestige: BaseTaskConfig & { invaders_max_lv: number; subtasks: PrestigeSubtasks }
  march_manager: MarchManagerConfig
  gold_gather?: { enabled: boolean; locations: GoldLocation[] }
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
}

export const DEFAULT_CASTLE_CONFIG: CastleConfig = {
  // كل المهام معطّلة افتراضياً — يفعّلها المستخدم من لوحة التحكم
  city_harvest: { enabled: false },
  research: { enabled: false, schedule: { times_per_day: 2 } },
  alliance: { enabled: false, auto_help: true, gold_donations: 0 },
  port: { enabled: false },
  train: { enabled: false, levels: { infantry: 0, cavalry: 0, archers: 0, chariots: 0 } },
  pet_patrol: { enabled: false, pet: 'غزال' },
  territory_expansion: { enabled: false },
  shield: { enabled: false, duration: '8h', allow_gold: false },
  stamina: { enabled: false, gold_buys: 0 },
  skills: { enabled: false, target_skills: [] },
  hero_draw: { enabled: false },
  tactics_hall: { enabled: false, tactic: 'القلعة الفارغة', schedule: { times_per_day: 2 } },
  watermill: { enabled: false, types: 'food', allow_shop_buy: false },
  fountain: { enabled: false, resources: [], allow_gold: false, gold_times: 0, schedule: { times_per_day: 2 } },
  material_workshop: { enabled: false, materials: [], schedule: { times_per_day: 2 } },
  caravan: { enabled: false, schedule: { times_per_day: 2 } },
  port_delegate: { enabled: false, shop_item: 'all' },
  savings_bank: { enabled: false, days: 7 },
  building: { enabled: false, upgrade_castle: true, speedup_castle: false, upgrade_support_buildings: true },
  prestige: {
    enabled: false,
    invaders_max_lv: 15,
    subtasks: {
      smuggler: false,
      invaders: false,
      stronghold: false,
      gather: false,
      watermill: false,
      train: false,
      fortress: false,
    },
  },
  march_manager: {
    enabled: true,
    max_queues: 4,
    priority_order: ['gather', 'combat'],
    transport: { enabled: false, target_x: null, target_y: null, resource_ids: [] },
    ruins: { enabled: false, explore_time: 120, formation_id: 1 },
    combat: { enabled: false, choice: 'invaders', level: 15, formation_id: 1, count: 5 },
    elf: { enabled: false, formation_id: 1 },
    invaders: { enabled: false, level: 15, formation_id: 1, count: 5 },
    rebels: { enabled: false, level: 5, formation_id: 1, count: 1 },
    stronghold: { enabled: false, level: 5, count: 1, formation_id: 1 },
    gather: { enabled: false, res_type: 2, level: 5, search_range: 20 },
  },
  gold_gather: { enabled: false, locations: [] },
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
