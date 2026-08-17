import express from 'express'
import cors from 'cors'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import mysql from 'mysql2/promise'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
app.use(cors())
app.use(express.json())

// 缓存配置（避免每次请求都重新获取外部 API 数据）
let currentDataCache = null
let currentDataCacheTime = 0
const CACHE_TTL_MS = 30 * 1000 // 缓存 30 秒

let speedDataCache = null
let speedDataCacheTime = 0

// 外部 API 配置（单个点位最新数据）
const API_URL = 'https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exRedisManage/recentVal/single?appKey=240622160158015900001'

// MySQL 数据库配置
const DB_CONFIG = {
  host: '10.51.190.70',
  port: 3306,
  user: 'test',
  password: '1234',
  database: 'laminar_rt_db',
  charset: 'utf8mb4',
}

// 创建数据库连接池
const pool = mysql.createPool({
  ...DB_CONFIG,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
})

// 初始化数据库表结构（添加 status 字段）
async function initDatabase() {
  try {
    const connection = await pool.getConnection()
    try {
      // 检查 roller_alerts 表是否存在 status 字段
      const [columns] = await connection.execute(
        `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
         WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'roller_alerts' AND COLUMN_NAME = 'status'`,
        [DB_CONFIG.database]
      )
      if (columns.length === 0) {
        await connection.execute(`ALTER TABLE roller_alerts ADD COLUMN status VARCHAR(20) DEFAULT 'unconfirmed'`)
        await connection.execute(`UPDATE roller_alerts SET status = 'unconfirmed' WHERE status IS NULL`)
        console.log('[INFO] 已给 roller_alerts 表添加 status 字段')
      }
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('[警告] 初始化数据库失败:', error.message)
  }
}

// 启动时初始化数据库
initDatabase()

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
    const csvPath = path.join(__dirname, 'meter_ledger.csv')
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
    // 过滤掉 ZS 组
    if (groupName === 'ZS') {
      return
    }
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

// 获取单个点位的最新数据
async function fetchSinglePointData(attrId) {
  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        attrId: attrId,
      }),
    })
    
    if (!response.ok) {
      return null
    }
    
    const result = await response.json()
    
    if (result.code !== '0' && result.code !== 0) {
      return null
    }
    
    // 解析返回的数据 { time: xxx, value: xxx }
    const data = result.data
    if (data && data.value !== null && data.value !== undefined) {
      return parseFloat(data.value)
    }
    return null
    
  } catch (error) {
    return null
  }
}

// 从外部 API 获取实时电流数据（批量）
async function fetchCurrentDataFromApi() {
  // 检查缓存是否有效
  const now = Date.now()
  if (currentDataCache && (now - currentDataCacheTime) < CACHE_TTL_MS) {
    console.log(`[INFO] 使用缓存的电流数据，缓存时间: ${new Date(currentDataCacheTime).toLocaleString()}`)
    return currentDataCache
  }
  
  const data = getRollerData()
  // 过滤掉 ZS 组
  const validItems = data.filter(item => item.GDMC !== 'ZS')
  
  const currentMap = {}
  const BATCH_SIZE = 10 // 每批并发请求10个
  
  console.log(`[INFO] 正在从外部 API 获取 ${validItems.length} 个点位的最新电流数据...`)
  
  for (let i = 0; i < validItems.length; i += BATCH_SIZE) {
    const batch = validItems.slice(i, i + BATCH_SIZE)
    const promises = batch.map(async (item) => {
      const attrId = parseInt(item.attr_id)
      const currentValue = await fetchSinglePointData(attrId)
      if (currentValue !== null) {
        currentMap[attrId] = currentValue
      }
    })
    
    await Promise.all(promises)
    
    // 打印进度
    const progress = Math.min(i + BATCH_SIZE, validItems.length)
    if (progress % 50 === 0 || progress === validItems.length) {
      console.log(`[INFO] 进度: ${progress}/${validItems.length}`)
    }
  }
  
  console.log(`[INFO] API 数据获取成功，共 ${Object.keys(currentMap).length} 条`)
  const result = { currentMap, timestamp: new Date().toISOString() }
  
  // 更新缓存
  currentDataCache = result
  currentDataCacheTime = now
  
  return result
}

// 获取电流数据（优先从外部 API，失败则返回 null）
async function getCurrentData() {
  const data = getRollerData()
  const apiResult = await fetchCurrentDataFromApi()
  const currentMap = apiResult.currentMap || {}
  const apiTimestamp = apiResult.timestamp || new Date().toISOString()
  const currentData = {}
  
  data.forEach(item => {
    const attrId = parseInt(item.attr_id)
    // 过滤掉 ZS 组
    if (item.GDMC === 'ZS') {
      return
    }
    const current = currentMap[attrId]
    
    currentData[item.attr_id] = {
      id: parseInt(item.id),
      instance_name: item.instance_name,
      attr_id: attrId,
      current: current !== undefined ? current : null, // 无数据时返回 null
      group: item.GDMC,
      timestamp: apiTimestamp,
    }
  })
  
  return currentData
}

// 获取转速数据（组级）
async function fetchSpeedDataFromApi() {
  // 检查缓存是否有效
  const now = Date.now()
  if (speedDataCache && (now - speedDataCacheTime) < CACHE_TTL_MS) {
    console.log(`[INFO] 使用缓存的转速数据，缓存时间: ${new Date(speedDataCacheTime).toLocaleString()}`)
    return speedDataCache
  }
  
  const data = getRollerData()
  // 筛选转速点位（GDMC以ZS结尾）
  const speedItems = data.filter(item => item.GDMC && item.GDMC.endsWith('ZS') && item.attr_id)

  const speedMap = {}

  for (const item of speedItems) {
    const attrId = parseInt(item.attr_id)
    const groupName = item.GDMC.replace('ZS', '')
    const speedValue = await fetchSinglePointData(attrId)
    if (speedValue !== null) {
      speedMap[groupName] = {
        group: groupName,
        instance_name: item.instance_name,
        attr_id: attrId,
        speed: speedValue,
      }
    }
  }

  // 更新缓存
  speedDataCache = speedMap
  speedDataCacheTime = now

  return speedMap
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

// API: 获取转速数据
app.get('/api/speed', async (req, res) => {
  try {
    const speedData = await fetchSpeedDataFromApi()
    res.json({
      code: 0,
      message: 'success',
      data: speedData,
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
    // 过滤掉转速组（组名以 'Z' 结尾）
    const filteredGroups = Object.fromEntries(
      Object.entries(groups).filter(([name]) => !name.endsWith('Z'))
    )
    const groupNames = Object.keys(filteredGroups)
    const data = getRollerData()
    const apiResult = await fetchCurrentDataFromApi()
    const currentMap = apiResult.currentMap || {}
    
    let faultRollers = 0
    const THRESHOLD = 6.0
    
    data.forEach(item => {
      const attrId = parseInt(item.attr_id)
      const current = currentMap[attrId]
      if (current !== undefined && current > THRESHOLD) {
        faultRollers++
      }
    })
    
    // 统计故障组（只统计非转速组）
    let faultGroups = 0
    for (const [groupName, rollers] of Object.entries(filteredGroups)) {
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
app.get('/api/stats/alarm', async (req, res) => {
  try {
    const connection = await pool.getConnection()
    try {
      // 查询最近24小时内的报警统计（按类型和状态分类）
      const alertTypes = ['跳闸报警', '严重跳闸报警', '卡阻报警']
      const result = {}
      
      for (const type of alertTypes) {
        // 未处理（unconfirmed）
        const [pendingRows] = await connection.execute(
          `SELECT COUNT(*) as count FROM roller_alerts WHERE alert_type = ? AND status = 'unconfirmed' AND alert_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)`,
          [type]
        )
        // 已处理（confirmed）
        const [processedRows] = await connection.execute(
          `SELECT COUNT(*) as count FROM roller_alerts WHERE alert_type = ? AND status = 'confirmed' AND alert_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)`,
          [type]
        )
        result[type] = {
          pending: pendingRows[0].count,
          processed: processedRows[0].count,
        }
      }
      
      res.json({
        code: 0,
        message: 'success',
        data: {
          // 兼容旧格式
          total: result['跳闸报警'].pending + result['跳闸报警'].processed +
                 result['严重跳闸报警'].pending + result['严重跳闸报警'].processed +
                 result['卡阻报警'].pending + result['卡阻报警'].processed,
          pending: result['跳闸报警'].pending + result['严重跳闸报警'].pending + result['卡阻报警'].pending,
          processed: result['跳闸报警'].processed + result['严重跳闸报警'].processed + result['卡阻报警'].processed,
          ignored: 0,
          // 新格式：按类型分类
          byType: result,
        },
      })
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('查询报警统计失败:', error.message)
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

// API: 获取报警记录（从数据库读取 roller_alerts 表，支持按状态筛选）
app.get('/api/alarms', async (req, res) => {
  try {
    const { status } = req.query
    const connection = await pool.getConnection()
    try {
      let query = `SELECT id, instance_name, alert_type, alert_time, start_time, end_time, duration, description, status
         FROM roller_alerts
         WHERE 1=1`
      const params = []
      
      // 按状态筛选
      if (status === 'unconfirmed') {
        query += ` AND (status IS NULL OR status = 'unconfirmed')`
      } else if (status === 'confirmed') {
        query += ` AND status = 'confirmed'`
      }
      // 如果不传 status 参数，返回所有记录
      
      query += ` ORDER BY alert_time DESC`
      
      const [rows] = await connection.execute(query, params)
      
      res.json({
        code: 0,
        message: 'success',
        data: rows.map(row => ({
          id: row.id,
          attrId: null,
          instanceName: row.instance_name,
          groupName: null,
          alertType: row.alert_type,
          alertTime: row.alert_time,
          startTime: row.start_time,
          endTime: row.end_time,
          duration: row.duration,
          description: row.description,
          status: row.status || 'unconfirmed',
        })),
      })
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('查询报警记录失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: [] })
  }
})

// API: 确认单条报警
app.post('/api/alarms/:id/acknowledge', async (req, res) => {
  try {
    const { id } = req.params
    const connection = await pool.getConnection()
    try {
      const [result] = await connection.execute(
        `UPDATE roller_alerts SET status = 'confirmed' WHERE id = ?`,
        [id]
      )
      if (result.affectedRows > 0) {
        res.json({ code: 0, message: '确认成功', data: { id } })
      } else {
        res.status(404).json({ code: 404, message: '报警记录不存在', data: null })
      }
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('确认报警失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 确认全部报警
app.post('/api/alarms/acknowledge-all', async (req, res) => {
  try {
    const connection = await pool.getConnection()
    try {
      const [result] = await connection.execute(
        `UPDATE roller_alerts SET status = 'confirmed' 
         WHERE (status IS NULL OR status != 'confirmed')`
      )
      res.json({ code: 0, message: '全部确认成功', data: { affectedRows: result.affectedRows } })
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('全部确认报警失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 删除单条报警
app.delete('/api/alarms/:id', async (req, res) => {
  try {
    const { id } = req.params
    const connection = await pool.getConnection()
    try {
      const [result] = await connection.execute(
        `DELETE FROM roller_alerts WHERE id = ?`,
        [id]
      )
      if (result.affectedRows > 0) {
        res.json({ code: 0, message: '删除成功', data: { id } })
      } else {
        res.status(404).json({ code: 404, message: '报警记录不存在', data: null })
      }
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('删除报警失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 清空已确认报警
app.delete('/api/alarms/clear-confirmed', async (req, res) => {
  try {
    const connection = await pool.getConnection()
    try {
      const [result] = await connection.execute(
        `DELETE FROM roller_alerts WHERE status = 'confirmed'`
      )
      res.json({ code: 0, message: '清空已确认报警成功', data: { affectedRows: result.affectedRows } })
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('清空已确认报警失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: null })
  }
})

// API: 获取历史数据（从数据库读取指定点位的历史记录）
app.get('/api/history', async (req, res) => {
  try {
    const { attrId, startTime, endTime } = req.query
    
    if (!attrId) {
      return res.status(400).json({ code: 400, message: '缺少 attrId 参数', data: [] })
    }
    
    const connection = await pool.getConnection()
    try {
      let query = `SELECT attr_id, attr_value, record_time FROM sensor_data WHERE attr_id = ?`
      const params = [attrId]
      
      if (startTime && endTime) {
        query += ` AND record_time BETWEEN ? AND ?`
        params.push(startTime, endTime)
      } else {
        // 默认查询最近24小时
        query += ` AND record_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)`
      }
      
      query += ` ORDER BY record_time DESC LIMIT 1000`
      
      const [rows] = await connection.execute(query, params)
      
      res.json({
        code: 0,
        message: 'success',
        data: rows.map(row => ({
          attrId: row.attr_id,
          currentValue: row.attr_value,
          recordTime: row.record_time,
        })),
      })
    } finally {
      connection.release()
    }
  } catch (error) {
    console.error('查询历史数据失败:', error.message)
    res.status(500).json({ code: 500, message: error.message, data: [] })
  }
})

const PORT = 8080
app.listen(PORT, () => {
  console.log(`ESP层冷辊道数据API服务已启动，端口: ${PORT}`)
  console.log(`API地址: http://localhost:${PORT}/api`)
})
