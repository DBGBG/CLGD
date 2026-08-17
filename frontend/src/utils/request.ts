import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_APP_API_URL || '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 Token（如果 Java 后端需要 JWT 认证）
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    // Java 后端返回的数据格式：{ code, message, data }
    // 统一处理响应数据
    const res = response.data
    if (res.code !== undefined && res.code !== 0) {
      // 业务错误，转换为异常抛出
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res
  },
  (error) => {
    // 处理 HTTP 错误
    if (error.response) {
      const status = error.response.status
      switch (status) {
        case 401:
          // 未授权，跳转到登录页
          window.location.href = '/login'
          break
        case 403:
          console.error('权限不足')
          break
        case 404:
          console.error('接口不存在')
          break
        case 500:
          console.error('服务器内部错误')
          break
        default:
          console.error(`请求错误: ${status}`)
      }
    } else if (error.request) {
      console.error('网络请求失败，请检查后端服务是否启动')
    }
    return Promise.reject(error)
  }
)

export default request
