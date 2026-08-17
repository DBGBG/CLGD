<template>
  <div class="alarm">
    <el-card>
      <template #header>
        <div class="alarm-header">
          <span>报警管理</span>
          <div class="alarm-actions">
            <el-button type="success" @click="handleAcknowledgeAll">全部确认</el-button>
            <el-button type="danger" @click="handleClearAll">清空已确认</el-button>
          </div>
        </div>
      </template>
      <div class="filter-row">
        <el-radio-group v-model="filterStatus" @change="handleFilterChange">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="unconfirmed">未确认</el-radio-button>
          <el-radio-button value="confirmed">已确认</el-radio-button>
        </el-radio-group>
      </div>
      <el-table :data="paginatedAlarmData" stripe border v-loading="loading">
        <el-table-column prop="alertTime" label="报警时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.alertTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="startTime" label="告警开始时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.startTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="endTime" label="告警结束时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.endTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="instanceName" label="设备名称" width="150" />
        <el-table-column prop="alertType" label="报警类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getAlertTypeType(row.alertType)">
              {{ row.alertType }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="持续时间" width="120">
          <template #default="{ row }">
            {{ row.duration?.toFixed(1) }} 秒
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'unconfirmed' ? 'danger' : 'success'">
              {{ row.status === 'unconfirmed' ? '未确认' : '已确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              :disabled="row.status === 'confirmed'"
              @click="handleAcknowledge(row)"
            >
              确认
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pagination"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

interface AlarmItem {
  id: number
  attrId: number
  instanceName: string
  groupName: string
  alertType: string
  alertTime: string
  startTime: string
  endTime: string
  duration: number
  description: string
  status: string
}

const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const loading = ref(false)
const filterStatus = ref('')

const alarmData = ref<AlarmItem[]>([])
let refreshTimer: ReturnType<typeof setInterval> | null = null

const paginatedAlarmData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  const end = start + pageSize.value
  return alarmData.value.slice(start, end)
})

const getAlertTypeType = (type: string) => {
  const map: Record<string, string> = {
    '严重跳闸报警': 'danger',
    '跳闸报警': 'warning',
    '卡阻报警': 'info',
  }
  return map[type] || 'info'
}

// 格式化日期时间
const formatDateTime = (dateTime: string | Date | null) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  if (isNaN(date.getTime())) return '-'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

// 获取报警数据
const fetchAlarms = async () => {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const response = await axios.get('/api/alarms', { params })
    if (response.data.code === 0) {
      alarmData.value = (response.data.data || []).map((item: any) => ({
        id: item.id,
        attrId: item.attrId,
        instanceName: item.instanceName,
        groupName: item.groupName,
        alertType: item.alertType,
        alertTime: item.alertTime,
        startTime: item.startTime,
        endTime: item.endTime,
        duration: item.duration,
        description: item.description,
        status: item.status || 'unconfirmed',
      }))
      total.value = alarmData.value.length
    }
  } catch (error) {
    console.error('获取报警数据失败:', error)
    ElMessage.error('获取报警数据失败')
  } finally {
    loading.value = false
  }
}

// 筛选状态变化
const handleFilterChange = () => {
  page.value = 1
  fetchAlarms()
}

// 确认单条报警
const handleAcknowledge = async (row: AlarmItem) => {
  try {
    await ElMessageBox.confirm(
      `确认已处理该报警 [${row.instanceName} - ${row.alertType}]？`,
      '确认报警',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.post(`/api/alarms/${row.id}/acknowledge`)
    ElMessage.success('报警已确认')
    // 刷新列表
    await fetchAlarms()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('确认报警失败:', error)
      ElMessage.error('确认报警失败')
    }
  }
}

// 确认全部报警
const handleAcknowledgeAll = async () => {
  if (alarmData.value.length === 0) {
    ElMessage.warning('当前没有未确认的报警')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认处理全部 ${alarmData.value.length} 条报警？`,
      '全部确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.post('/api/alarms/acknowledge-all')
    ElMessage.success('全部报警已确认')
    // 刷新列表
    await fetchAlarms()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('全部确认失败:', error)
      ElMessage.error('全部确认失败')
    }
  }
}

// 删除报警（调用后端API）
const handleDelete = async (row: AlarmItem) => {
  try {
    await ElMessageBox.confirm(
      `确定删除该报警记录 [${row.instanceName}]？`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'error' }
    )
    await axios.delete(`/api/alarms/${row.id}`)
    ElMessage.success('报警已删除')
    // 刷新列表
    await fetchAlarms()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除报警失败:', error)
      ElMessage.error('删除报警失败')
    }
  }
}

// 清空已确认的报警（调用后端API）
const handleClearAll = async () => {
  const confirmedCount = alarmData.value.filter((item) => item.status === 'confirmed').length
  if (confirmedCount === 0) {
    ElMessage.warning('没有已确认的报警需要清空')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定清空全部 ${confirmedCount} 条已确认的报警？`,
      '清空确认',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete('/api/alarms/clear-confirmed')
    ElMessage.success(`已清空 ${confirmedCount} 条已确认的报警`)
    // 刷新列表
    await fetchAlarms()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清空已确认报警失败:', error)
      ElMessage.error('清空已确认报警失败')
    }
  }
}

onMounted(() => {
  fetchAlarms()
  // 定时刷新数据（每 5 秒）
  refreshTimer = setInterval(() => {
    fetchAlarms()
  }, 5000)
})
onUnmounted(() => {
  // 清除定时器
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.alarm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alarm-actions {
  display: flex;
  gap: 12px;
}

.filter-row {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
