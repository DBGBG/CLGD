<template>
  <div class="report">
    <el-card>
      <template #header>
        <div class="report-header">
          <span>报表查询</span>
          <div class="search-form">
            <el-date-picker
              v-model="dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DD HH:mm:ss"
            />
            <el-select v-model="searchParams.reportType" placeholder="报表类型" clearable>
              <el-option
                v-for="type in reportTypes"
                :key="type.value"
                :label="type.label"
                :value="type.value"
              />
            </el-select>
            <el-button type="primary" @click="handleSearch">
              <el-icon><Search /></el-icon>查询
            </el-button>
            <el-button @click="handleExport">
              <el-icon><Download /></el-icon>导出
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="reportData" stripe border>
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="reportType" label="报表类型" width="150">
          <template #default="{ row }">
            <el-tag :type="getReportTypeColor(row.reportType)">
              {{ row.reportType }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="deviceName" label="设备名称" width="150" />
        <el-table-column prop="totalRunTime" label="总运行时间(h)" width="130" />
        <el-table-column prop="avgTemperature" label="平均温度(°C)" width="130" />
        <el-table-column prop="avgSpeed" label="平均速度(m/min)" width="140" />
        <el-table-column prop="alarmCount" label="报警次数" width="100">
          <template #default="{ row }">
            <el-tag :type="row.alarmCount > 0 ? 'danger' : 'success'">
              {{ row.alarmCount }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '已生成' ? 'success' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button type="success" size="small" @click="handleDownload(row)">
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pagination"
        v-model:current-page="searchParams.page"
        v-model:page-size="searchParams.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- 报表详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="报表详情" width="800px">
      <div v-if="selectedReport" class="report-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="日期">{{ selectedReport.date }}</el-descriptions-item>
          <el-descriptions-item label="报表类型">{{ selectedReport.reportType }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ selectedReport.deviceName }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedReport.status === '已生成' ? 'success' : 'warning'">
              {{ selectedReport.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="总运行时间">{{ selectedReport.totalRunTime }}h</el-descriptions-item>
          <el-descriptions-item label="平均温度">{{ selectedReport.avgTemperature }}°C</el-descriptions-item>
          <el-descriptions-item label="平均速度">{{ selectedReport.avgSpeed }}m/min</el-descriptions-item>
          <el-descriptions-item label="报警次数">
            <el-tag :type="selectedReport.alarmCount > 0 ? 'danger' : 'success'">
              {{ selectedReport.alarmCount }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-chart" ref="detailChartRef" style="height: 300px; margin-top: 20px"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted, nextTick } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const dateRange = ref<[string, string]>(['', ''])
const searchParams = ref({
  reportType: '',
  page: 1,
  pageSize: 10,
})
const total = ref(0)
const detailDialogVisible = ref(false)
const selectedReport = ref<any>(null)
const detailChartRef = ref<HTMLDivElement>()
let detailChart: echarts.ECharts | null = null

const reportTypes = ref([
  { value: 'daily', label: '日报表' },
  { value: 'weekly', label: '周报表' },
  { value: 'monthly', label: '月报表' },
  { value: 'alarm', label: '报警报表' },
])

const reportData = ref<any[]>([])

const getReportTypeColor = (type: string) => {
  const map: Record<string, string> = {
    '日报表': 'primary',
    '周报表': 'success',
    '月报表': 'warning',
    '报警报表': 'danger',
  }
  return map[type] || 'info'
}

const handleSearch = () => {
  ElMessage.info('查询报表数据')
}

const handleExport = () => {
  ElMessage.success('导出报表成功')
}

const handleView = (row: any) => {
  selectedReport.value = row
  detailDialogVisible.value = true
  nextTick(() => {
    initDetailChart()
  })
}

const handleDownload = (row: any) => {
  ElMessage.success(`下载报表: ${row.date} ${row.reportType}`)
}

const initDetailChart = () => {
  if (!detailChartRef.value) return
  detailChart = echarts.init(detailChartRef.value)
  // 无真实数据时显示空图表
  detailChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['温度', '速度'] },
    xAxis: {
      type: 'category',
      data: [],
    },
    yAxis: [
      { type: 'value', name: '温度(°C)', position: 'left' },
      { type: 'value', name: '速度(m/min)', position: 'right' },
    ],
    series: [
      {
        name: '温度',
        type: 'line',
        data: [],
        itemStyle: { color: '#F56C6C' },
      },
      {
        name: '速度',
        type: 'line',
        yAxisIndex: 1,
        data: [],
        itemStyle: { color: '#409EFF' },
      },
    ],
  })
}

const handleSizeChange = (val: number) => {
  searchParams.value.pageSize = val
}

const handlePageChange = (val: number) => {
  searchParams.value.page = val
}

onUnmounted(() => {
  detailChart?.dispose()
})
</script>

<style scoped>
.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  display: flex;
  gap: 12px;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.report-detail {
  padding: 10px;
}

.detail-chart {
  margin-top: 20px;
}
</style>
