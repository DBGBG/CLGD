<template>
  <div class="history">
    <el-card>
      <template #header>
        <div class="search-header">
          <span>历史数据查询</span>
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
            <el-select v-model="searchParams.device" placeholder="选择设备" clearable>
              <el-option
                v-for="device in devices"
                :key="device.value"
                :label="device.label"
                :value="device.value"
              />
            </el-select>
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-button @click="handleExport">导出</el-button>
          </div>
        </div>
      </template>
      <el-table :data="historyData" stripe border>
        <el-table-column prop="time" label="时间" width="180" />
        <el-table-column prop="deviceName" label="设备名称" width="120" />
        <el-table-column prop="temperature" label="温度(°C)" width="100" />
        <el-table-column prop="speed" label="速度(m/min)" width="120" />
        <el-table-column prop="waterFlow" label="水流量(m³/h)" width="130" />
        <el-table-column prop="waterPressure" label="水压力(MPa)" width="130" />
        <el-table-column prop="motorCurrent" label="电机电流(A)" width="130" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'normal' ? 'success' : 'danger'">
              {{ row.status === 'normal' ? '正常' : '异常' }}
            </el-tag>
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const dateRange = ref<[string, string]>(['', ''])
const searchParams = ref({
  device: '',
  page: 1,
  pageSize: 10,
})
const total = ref(0)

const devices = ref([
  { value: '1', label: '1#层冷辊道' },
  { value: '2', label: '2#层冷辊道' },
  { value: '3', label: '3#层冷辊道' },
  { value: '4', label: '4#层冷辊道' },
  { value: '5', label: '5#层冷辊道' },
])

const historyData = ref<any[]>([])

const handleSearch = () => {
  console.log('搜索参数:', searchParams.value, dateRange.value)
}

const handleExport = () => {
  console.log('导出数据')
}

const handleSizeChange = (val: number) => {
  searchParams.value.pageSize = val
}

const handlePageChange = (val: number) => {
  searchParams.value.page = val
}
</script>

<style scoped>
.search-header {
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
</style>
