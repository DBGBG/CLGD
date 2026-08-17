import request from '@/utils/request'

// ==================== 类型定义 ====================

/** 设备统计 */
export interface EquipmentStats {
  totalGroups: number
  faultGroups: number
  normalGroups: number
  totalRollers: number
  faultRollers: number
  normalRollers: number
}

/** 报警统计 */
export interface AlarmStats {
  total: number
  pending: number
  processed: number
  ignored: number
  byType?: {
    '跳闸报警': { pending: number; processed: number }
    '严重跳闸报警': { pending: number; processed: number }
    '卡阻报警': { pending: number; processed: number }
  }
}

/** 更换统计 */
export interface ReplaceStats {
  monthlyReplace: number
  replaceRollers: number
}

/** 辊道电流数据 */
export interface RollerCurrent {
  id: number
  instance_name: string
  attr_id: number
  current: number
  group: string
  timestamp: string
}

/** 转速数据 */
export interface SpeedData {
  group: string
  instance_name: string
  attr_id: number
  speed: number
}

/** 辊道项（前端展示用） */
export interface RollerItem {
  id: number
  current: number
}

/** 辊道组（前端展示用） */
export interface RollerGroup {
  name: string
  rollers: RollerItem[]
}

/** 通用响应格式 */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

// ==================== API 接口 ====================

/**
 * 获取设备统计
 * @returns 设备统计数据
 */
export function getEquipmentStats(): Promise<ApiResponse<EquipmentStats>> {
  return request.get('/stats/equipment')
}

/**
 * 获取报警统计
 * @returns 报警统计数据
 */
export function getAlarmStats(): Promise<ApiResponse<AlarmStats>> {
  return request.get('/stats/alarm')
}

/**
 * 获取更换统计
 * @returns 更换统计数据
 */
export function getReplaceStats(): Promise<ApiResponse<ReplaceStats>> {
  return request.get('/stats/replace')
}

/**
 * 获取辊道电流数据
 * @returns 所有辊道的电流数据
 */
export function getCurrentData(): Promise<ApiResponse<Record<string, RollerCurrent>>> {
  return request.get('/current')
}

/**
 * 获取转速数据
 * @returns 各组转速数据
 */
export function getSpeedData(): Promise<ApiResponse<Record<string, SpeedData>>> {
  return request.get('/speed')
}

/**
 * 获取辊道信息（按组）
 * @returns 按工段分组的辊道信息
 */
export function getRollersByGroup(): Promise<ApiResponse<Record<string, any[]>>> {
  return request.get('/rollers')
}
