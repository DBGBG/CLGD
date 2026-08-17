import express from 'express'
import cors from 'cors'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
app.use(cors())
app.use(express.json())

// 外部 API 配置
const API_URL = 'https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exDataManage/samplingQuery?appKey=240622160158015900001'

// 读取 CSV 文件并解析
function readCsv(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8')
  const lines = content.trim().split('\n')
  const headers = lines[0].split(',').map(h => h.trim())
  
  const data = []
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',')
    const row = {}
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = values[j]?.trim() || ''
    }
    data.push(row)
  }
  return data
}

// 缓存辊道数据
let rollerData = null
function getRollerData() {
  if (!rollerData) {
    const csvPath = path.join(__dirname, '..', 'meter_ledger.csv')
    rollerData = readCsv(csvPath)
  }
  return rollerData
}

// 按工段分组获取辊道信息
function getRollersByGroup() {
  const data = getRollerData()
  const groups = {}
  
  data.forEach(item => {
    const groupName = item.GDMC || '其他'
    if (!groups[groupName]) {
      groups[groupName] = []
    }
    groups[groupName].push({
      id: parseInt(item.id),
      instance_name: item.instance_name,
      attr_id: parseInt(item.attr_id),
      group: groupName,
    })
  })
  
  return groups
}

// 从外部 API 获取实时电流数据
async function fetchCurrentDataFromApi() {
  const data = getRollerData()
  const attrIds = data.map(item => parseInt(item.attr_id))
  
  const endTime = Date.now()
  const startTime = endTime - (30 * 60 * 1000) // 最近30分钟
  
  try {
    console.log('[INFO] 正在从外部 API 获取实时电流数据...')
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        attrIds: attrIds,
        startTime: String(startTime),
        endTime: String(endTime),
      }),
    })
    
    if (!response.ok) {
      console.log(`[警告] API 响应失败: ${response.status}`)
      return {}
    }
    
    const result = await response.json()
    
    if (result.code !== '0' && result.code !== 0) {
      console.log(`[警告] API 返回失败: ${result.code}`)
      return {}
    }
    
    // 解析响应数据
    const currentMap = {}
    const sensorData = result.data || {}
    
    for (const [attrId, values] of Object.entries(sensorData)) {
      if (Array.isArray(values) && values.length > 0) {
        // 取最新一条数据
        const latest = values[values.length - 1]
        // 从数据项中获取电流值（排除 time 字段）
        let currentValue = null
        for (const [key, value] of Object.entries(latest)) {
          if (key !== 'time' && value !== null && value !== undefined) {
            currentValue = parseFloat(value)
            break
          }
        }
        if (!isNaN(currentValue)) {
          currentMap[parseInt(attrId)] = currentValue
        }
      }
    }
    
    console.log(`[INFO] API 数据获取成功，共 ${Object.keys(currentMap).length} 条`)
    return currentMap
    
  } catch (error) {
    console.error('[错误] 从 API 获取数据失败:', error.message)
    return {}
  }
}

// 获取电流数据（优先从外部 API，失败则返回 null）
async function getCurrentData() {
  const data = getRollerData()
  const currentMap = await fetchCurrentDataFromApi()
  const currentData = {}
  
  data.forEach(item => {
    const attrId = parseInt(item.attr_id)
    const current = currentMap[attrId]
    
    currentData[item.attr_id] = {
      id: parseInt(item.id),
      instance_name: item.instance_name,
      attr_id: attrId,
      current: current !== undefined ? current : null, // 无数据时返回 null
      group: item.GDMC,
      timestamp: new Date().toISOString(),
    }
  })
  
  return currentData
}

// API: 获取所有辊道信息
app.get('/api/rollers', (req, res) => {
  try {
    const groups = getRollersByGroup()
    res.json({
      code: 0,
      message: 'success',
      data: groups,
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取辊道电流数据
app.get('/api/current', async (req, res) => {
  try {
    const currentData = await getCurrentData()
    res.json({
      code: 0,
      message: 'success',
      data: currentData,
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取指定组的电流数据
app.get('/api/current/:group', async (req, res) => {
  try {
    const group = req.params.group
    const currentData = await getCurrentData()
    const filtered = Object.values(currentData).filter(
      item => item.group === group
    )
    res.json({
      code: 0,
      message: 'success',
      data: filtered,
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取设备统计
app.get('/api/stats/equipment', async (req, res) => {
  try {
    const groups = getRollersByGroup()
    const groupNames = Object.keys(groups)
    const data = getRollerData()
    const currentMap = await fetchCurrentDataFromApi()
    
    let faultRollers = 0
    const THRESHOLD = 6.0
    
    data.forEach(item => {
      const attrId = parseInt(item.attr_id)
      const current = currentMap[attrId]
      if (current !== undefined && current > THRESHOLD) {
        faultRollers++
      }
    })
    
    // 统计故障组
    let faultGroups = 0
    for (const [groupName, rollers] of Object.entries(groups)) {
      let hasFault = false
      for (const roller of rollers) {
        const current = currentMap[roller.attr_id]
        if (current !== undefined && current > THRESHOLD) {
          hasFault = true
          break
        }
      }
      if (hasFault) faultGroups++
    }
    
    res.json({
      code: 0,
      message: 'success',
      data: {
        totalGroups: groupNames.length,
        faultGroups,
        normalGroups: groupNames.length - faultGroups,
        totalRollers: data.length,
        faultRollers,
        normalRollers: data.length - faultRollers,
      },
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取报警统计
app.get('/api/stats/alarm', (req, res) => {
  try {
    res.json({
      code: 0,
      message: 'success',
      data: {
        total: 0,
        pending: 0,
        processed: 0,
        ignored: 0,
      },
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取更换统计
app.get('/api/stats/replace', (req, res) => {
  try {
    res.json({
      code: 0,
      message: 'success',
      data: {
        monthlyReplace: 0,
        replaceRollers: 0,
      },
    })
  } catch (error) {
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

const PORT = 8080
app.listen(PORT, () => {
  console.log(`ESP层冷辊道数据API服务已启动，端口: ${PORT}`)
  console.log(`API地址: http://localhost:${PORT}/api`)
})
