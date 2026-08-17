<template>
  <div class="dashboard">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <!-- 设备统计 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card class="stat-card" shadow="hover" :body-style="{ padding: '12px' }">
          <div class="card-title">设备统计</div>
          <div class="equip-stats">
            <div class="equip-row">
              <div class="equip-item">
                <span class="equip-label">辊道组</span>
                <span class="equip-value">{{ equipStats.totalGroups }}</span>
              </div>
              <div class="equip-item">
                <span class="equip-label">辊道组</span>
                <span class="equip-value">{{ equipStats.faultGroups }}</span>
              </div>
              <div class="equip-item">
                <span class="equip-label">辊道组</span>
                <span class="equip-value">{{ equipStats.normalGroups }}</span>
              </div>
            </div>
            <div class="equip-row">
              <div class="equip-item">
                <span class="equip-label">辊道总数</span>
                <span class="equip-value">{{ equipStats.totalRollers }}</span>
              </div>
              <div class="equip-item">
                <span class="equip-label red">辊道故障</span>
                <span class="equip-value red">{{ equipStats.faultRollers }}</span>
              </div>
              <div class="equip-item">
                <span class="equip-label">辊道正常</span>
                <span class="equip-value">{{ equipStats.normalRollers }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 报警统计 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card class="stat-card" shadow="hover" :body-style="{ padding: '12px' }">
          <div class="card-title">
            <span>报警统计</span>
            <el-link type="primary" :underline="'never'" class="detail-link" @click="router.push('/alarm')">
              报警详情 <el-icon><ArrowRight /></el-icon>
            </el-link>
          </div>
          <div class="alarm-chart" ref="alarmChartRef"></div>
        </el-card>
      </el-col>

      <!-- 更换统计 -->
      <el-col :xs="24" :sm="12" :lg="8">
        <el-card class="stat-card" shadow="hover" :body-style="{ padding: '12px' }">
          <div class="card-title">更换统计</div>
          <div class="change-content">
            <div class="change-item">
              <span class="change-label">月更换量</span>
              <span class="change-value">{{ replaceStats.monthlyReplace }}</span>
            </div>
            <div class="change-item">
              <span class="change-label">更换辊道</span>
              <span class="change-value">{{ replaceStats.replaceRollers }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 组转速监测 -->
    <el-card class="speed-monitor" shadow="hover" :body-style="{ padding: '16px' }" style="margin-bottom: 16px;">
      <div class="monitor-header">
        <span class="monitor-title">组转速监测</span>
      </div>
      <div class="speed-groups">
        <div v-for="item in speedData" :key="item.group" class="speed-item">
          <div class="speed-group-name">{{ item.group }}</div>
          <div class="speed-value" :class="{ 'speed-low': item.speed < 20 }">
            {{ item.speed.toFixed(1) }}
          </div>
          <div class="speed-unit">r/min</div>
        </div>
      </div>
    </el-card>

    <!-- 辊道电机电流监测 -->
    <el-card class="current-monitor" shadow="hover" :body-style="{ padding: '16px' }">
      <div class="monitor-header">
        <span class="monitor-title">辊道电机电流监测</span>
      </div>
      <div class="roller-groups" v-loading="loading">
        <div v-for="group in rollerGroups" :key="group.name" class="roller-group">
          <div class="group-badge">{{ group.name }}</div>
          <div class="roller-grid">
            <div
              v-for="roller in group.rollers"
              :key="roller.id"
              class="roller-item"
              :class="{ 'has-warning': roller.current > 6.0 }"
            >
              <div class="roller-num">{{ roller.id }}</div>
              <div class="roller-current">{{ roller.current !== null && roller.current !== undefined ? roller.current.toFixed(2) : '-' }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getEquipmentStats,
  getAlarmStats,
  getReplaceStats,
  getCurrentData,
  getSpeedData,
} from '@/api/dashboard'
import type { EquipmentStats, AlarmStats, ReplaceStats } from '@/api/dashboard'

const router = useRouter()

const loading = ref(false)
const alarmChartRef = ref<HTMLDivElement>()
let alarmChart: echarts.ECharts | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 设备统计数据
const equipStats = ref<EquipmentStats>({
  totalGroups: 0,
  faultGroups: 0,
  normalGroups: 0,
  totalRollers: 0,
  faultRollers: 0,
  normalRollers: 0,
})

// 报警统计数据
const alarmStats = ref<AlarmStats>({
  total: 0,
  pending: 0,
  processed: 0,
  ignored: 0,
})

// 更换统计数据
const replaceStats = ref<ReplaceStats>({
  monthlyReplace: 0,
  replaceRollers: 0,
})

// 辊道组数据
interface RollerItem {
  id: number
  current: number
}

interface RollerGroup {
  name: string
  rollers: RollerItem[]
}

const rollerGroups = ref<RollerGroup[]>([])

// 转速数据
interface SpeedItem {
  group: string
  instance_name: string
  attr_id: number
  speed: number
}

const speedData = ref<SpeedItem[]>([])

// 获取设备统计
const fetchEquipmentStats = async () => {
  try {
    const res = await getEquipmentStats() as any
    if (res.data) {
      equipStats.value = res.data
    }
  } catch (error) {
    console.error('获取设备统计失败:', error)
  }
}

// 获取报警统计
const fetchAlarmStats = async () => {
  try {
    const res = await getAlarmStats() as any
    if (res.data) {
      alarmStats.value = res.data
    }
  } catch (error) {
    console.error('获取报警统计失败:', error)
  }
}

// 获取更换统计
const fetchReplaceStats = async () => {
  try {
    const res = await getReplaceStats() as any
    if (res.data) {
      replaceStats.value = res.data
    }
  } catch (error) {
    console.error('获取更换统计失败:', error)
  }
}

// 获取辊道电流数据
const fetchCurrentData = async (showLoading = true) => {
  try {
    if (showLoading) loading.value = true
    const res = await getCurrentData() as any
    if (res.data) {
      // 按 group 分组
      const groupMap: Record<string, RollerItem[]> = {}
      Object.values(res.data).forEach((item: any) => {
        const groupName = item.group
        if (!groupMap[groupName]) {
          groupMap[groupName] = []
        }
        groupMap[groupName].push({
          id: item.id,
          current: item.current,
        })
      })

      // 转换为数组并排序（过滤掉转速组，组名以 Z 结尾）
      rollerGroups.value = Object.entries(groupMap)
        .filter(([name]) => !name.endsWith('Z'))
        .map(([name, rollers]) => ({
          name,
          rollers: rollers.sort((a, b) => a.id - b.id),
        }))
    }
  } catch (error) {
    console.error('获取电流数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取转速数据
const fetchSpeedData = async () => {
  try {
    const res = await getSpeedData() as any
    if (res.data) {
      speedData.value = Object.values(res.data).map((item: any) => ({
        group: item.group,
        instance_name: item.instance_name,
        attr_id: item.attr_id,
        speed: item.speed,
      }))
    }
  } catch (error) {
    console.error('获取转速数据失败:', error)
  }
}

// 初始化报警统计图表
const initAlarmChart = () => {
  if (!alarmChartRef.value) return
  alarmChart = echarts.init(alarmChartRef.value)
  updateAlarmChart()
}

// 更新报警统计图表
const updateAlarmChart = () => {
  if (!alarmChart) return
  
  // 获取按类型分类的数据（如果没有byType则使用兼容模式）
  const byType = alarmStats.value.byType
  const hasByType = byType && byType['跳闸报警']
  
  let pendingData: number[]
  let processedData: number[]
  
  if (hasByType) {
    pendingData = [
      byType!['跳闸报警'].pending,
      byType!['严重跳闸报警'].pending,
      byType!['卡阻报警'].pending,
    ]
    processedData = [
      byType!['跳闸报警'].processed,
      byType!['严重跳闸报警'].processed,
      byType!['卡阻报警'].processed,
    ]
  } else {
    // 兼容旧格式
    pendingData = [alarmStats.value.pending, 0, 0]
    processedData = [alarmStats.value.processed, 0, 0]
  }
  
  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      data: ['未处理', '已处理'],
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: '#666', fontSize: 10 },
    },
    grid: {
      left: '5%',
      right: '5%',
      bottom: '5%',
      top: '18%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: ['跳闸报警', '严重跳闸', '卡阻报警'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#666', fontSize: 10, interval: 0 },
    },
    yAxis: {
      type: 'value',
      show: false,
    },
    series: [
      {
        name: '未处理',
        type: 'bar',
        barWidth: 12,
        data: pendingData,
        itemStyle: { color: '#f56c6c', borderRadius: [2, 2, 0, 0] },
        label: { show: true, position: 'top', color: '#333', fontSize: 10 },
      },
      {
        name: '已处理',
        type: 'bar',
        barWidth: 12,
        data: processedData,
        itemStyle: { color: '#67c23a', borderRadius: [2, 2, 0, 0] },
        label: { show: true, position: 'top', color: '#333', fontSize: 10 },
      },
    ],
  }
  alarmChart.setOption(option)
}

onMounted(async () => {
  // 首次加载：获取所有数据
  await Promise.all([
    fetchEquipmentStats(),
    fetchAlarmStats(),
    fetchReplaceStats(),
    fetchCurrentData(),
    fetchSpeedData(),
  ])

  // 初始化图表
  initAlarmChart()

  window.addEventListener('resize', () => {
    alarmChart?.resize()
  })

  // 定时刷新电流数据和转速数据（每 10 秒），不显示 loading
  refreshTimer = setInterval(() => {
    fetchCurrentData(false)
    fetchSpeedData()
  }, 10000)
})

onUnmounted(() => {
  alarmChart?.dispose()
  // 清除定时器
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  height: 200px;
}

.card-title {
  font-size: 15px;
  font-weight: bold;
  color: #333;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-link {
  font-size: 12px;
}

/* 设备统计 */
.equip-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.equip-row {
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.equip-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.equip-label {
  font-size: 11px;
  color: #999;
}

.equip-label.red {
  color: #f56c6c;
}

.equip-value {
  font-size: 22px;
  font-weight: bold;
  color: #333;
}

.equip-value.red {
  color: #f56c6c;
}

/* 报警统计 */
.alarm-chart {
  height: 130px;
}

/* 更换统计 */
.change-content {
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 100%;
  padding-top: 8px;
}

.change-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.change-label {
  font-size: 11px;
  color: #999;
}

.change-value {
  font-size: 22px;
  font-weight: bold;
  color: #333;
}

/* 辊道电机电流监测 */
.current-monitor {
  margin-top: 0;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.monitor-title {
  font-size: 15px;
  font-weight: bold;
  color: #333;
}

.roller-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.roller-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.group-badge {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #67c23a, #85ce61);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: bold;
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 2px;
}

.roller-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}

.roller-item {
  width: 56px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 3px 2px;
  text-align: center;
  background: #fff;
  transition: all 0.3s;
  flex-shrink: 0;
}

.roller-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
}

.roller-item.has-warning {
  border-color: #f56c6c;
  background: #fef0f0;
}

.roller-num {
  font-size: 10px;
  color: #999;
  line-height: 1.2;
}

.roller-current {
  font-size: 12px;
  font-weight: bold;
  color: #333;
  line-height: 1.4;
}

/* 转速监测 */
.speed-monitor {
  margin-top: 0;
}

.speed-groups {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.speed-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #f5f7fa;
  min-width: 120px;
}

.speed-group-name {
  font-size: 13px;
  font-weight: bold;
  color: #333;
  margin-bottom: 4px;
}

.speed-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.speed-value.speed-low {
  color: #f56c6c;
}

.speed-unit {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}
</style>
