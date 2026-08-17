<template>
  <div class="monitor">
    <el-row :gutter="20">
      <el-col :span="8" v-for="param in params" :key="param.name">
        <el-card class="param-card">
          <template #header>
            <div class="param-header">
              <span>{{ param.name }}</span>
              <el-tag :type="param.status === '正常' ? 'success' : 'danger'">{{ param.status }}</el-tag>
            </div>
          </template>
          <div class="param-value">
            <span class="value">{{ param.value }}</span>
            <span class="unit">{{ param.unit }}</span>
          </div>
          <div class="param-range">
            范围: {{ param.min }} - {{ param.max }} {{ param.unit }}
          </div>
          <el-progress
            :percentage="param.percentage"
            :color="param.percentage > 90 ? '#F56C6C' : param.percentage > 70 ? '#E6A23C' : '#67C23A'"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>实时参数曲线</span>
          </template>
          <div ref="paramChart" style="height: 400px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const params = ref<any[]>([])

const paramChart = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (paramChart.value) {
    chartInstance = echarts.init(paramChart.value)
    // 无真实数据时显示空图表
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['辊道速度', '钢板温度', '冷却水流量'] },
      xAxis: {
        type: 'category',
        data: [],
      },
      yAxis: [
        { type: 'value', name: '速度(m/min)', position: 'left' },
        { type: 'value', name: '温度(°C)', position: 'right' },
      ],
      series: [
        {
          name: '辊道速度',
          type: 'line',
          data: [],
          itemStyle: { color: '#409EFF' },
        },
        {
          name: '钢板温度',
          type: 'line',
          yAxisIndex: 1,
          data: [],
          itemStyle: { color: '#67C23A' },
        },
        {
          name: '冷却水流量',
          type: 'line',
          data: [],
          itemStyle: { color: '#E6A23C' },
        },
      ],
    })
  }
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chartInstance?.resize())
})

onUnmounted(() => {
  chartInstance?.dispose()
})
</script>

<style scoped>
.param-card {
  margin-bottom: 20px;
}

.param-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-value {
  margin: 16px 0;
}

.value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
}

.unit {
  font-size: 16px;
  color: #666;
  margin-left: 8px;
}

.param-range {
  font-size: 12px;
  color: #999;
  margin-bottom: 12px;
}

.mt-20 {
  margin-top: 20px;
}
</style>
