# 层冷辊道监控系统 技术规格说明

## 项目概述

层冷辊道监控系统是用于日照钢铁 1#ESP 产线的层冷辊道实时监控平台，提供设备统计、参数监控、历史数据、报警管理和报表查询等功能。

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4.x | 前端框架 |
| TypeScript | 5.4.x | 类型系统 |
| Vite | 5.2.x | 构建工具 |
| Element Plus | 2.7.x | UI 组件库 |
| Vue Router | 4.3.x | 路由管理 |
| Pinia | 2.1.x | 状态管理 |
| ECharts | 5.5.x | 数据可视化 |
| Axios | 1.7.x | HTTP 请求 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Java | 8+/11+ | 后端服务语言 |
| Spring Boot | 2.x/3.x | 后端框架 |
| MySQL | 8.x | 数据存储 |

### 开发辅助

| 技术 | 版本 | 用途 |
|------|------|------|
| Node.js | 18+ | 前端开发环境 |
| Express | 5.2.x | 开发环境模拟后端 |

## 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── api/               # API 接口封装
│   │   └── dashboard.ts   # 仪表盘相关接口
│   ├── components/        # 公共组件
│   │   └── Layout.vue     # 布局组件
│   ├── router/            # 路由配置
│   │   └── index.ts
│   ├── stores/            # Pinia 状态管理
│   ├── utils/             # 工具函数
│   │   └── request.ts    # Axios 封装（适配 Java 后端）
│   ├── views/             # 页面视图
│   │   ├── Dashboard.vue  # 主控界面（产线总览）
│   │   ├── Monitor.vue   # 参数监控
│   │   ├── History.vue   # 历史数据
│   │   ├── Alarm.vue     # 报警管理
│   │   └── Report.vue    # 报表查询
│   ├── App.vue            # 根组件
│   └── main.ts            # 入口文件
├── .env.development       # 开发环境变量
├── .env.production        # 生产环境变量
├── env.d.ts              # 环境变量类型声明
├── server.mjs             # Node.js 开发模拟后端
├── package.json           # 依赖配置
├── vite.config.ts         # Vite 配置
├── tsconfig.json          # TypeScript 配置
├── .eslintrc.cjs          # ESLint 配置
├── .prettierrc            # Prettier 配置
├── SPEC.md               # 本文件
└── API_SPEC.md           # API 接口文档
```

## 开发规范

### 命名规范

- **组件文件**: PascalCase (如 `Dashboard.vue`)
- **工具函数**: camelCase (如 `request.ts`)
- **常量**: UPPER_SNAKE_CASE
- **接口/类型**: PascalCase 前缀加类型描述 (如 `EquipmentStats`, `RollerCurrent`)

### 代码风格

- 使用 2 空格缩进
- 单引号
- 不使用分号
- 单行最大长度 120 字符
- 使用组合式 API (`<script setup>`)

### 组件规范

- 组件名使用多词组合（根组件 App.vue 除外）
- Props 使用明确的类型定义
- 事件使用 emit 声明
- 使用 TypeScript 类型注解

## 路由结构

| 路径 | 名称 | 说明 |
|------|------|------|
| `/dashboard` | Dashboard | 主控界面（默认页） |
| `/monitor` | Monitor | 参数监控 |
| `/history` | History | 历史数据 |
| `/alarm` | Alarm | 报警管理 |
| `/report` | Report | 报表查询 |

## 后端接口配置

### Java 后端接口

前端通过 Vite proxy 代理到 Java 后端服务。

**开发环境配置** (`.env.development`):

```
VITE_JAVA_API_TARGET=http://localhost:8080
```

**生产环境配置** (`.env.production`):

```
VITE_APP_API_URL=/api
```

### 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/rollers` | 获取辊道信息（按组） |
| GET | `/api/current` | 获取辊道电流数据 |
| GET | `/api/stats/equipment` | 获取设备统计 |
| GET | `/api/stats/alarm` | 获取报警统计 |
| GET | `/api/stats/replace` | 获取更换统计 |

详细 API 文档见 [API_SPEC.md](./API_SPEC.md)。

### Java 后端响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | number | 0=成功，其他=错误 |
| message | string | 提示信息 |
| data | object/array | 业务数据 |

## 数据来源

- **CSV 文件**: `meter_ledger.csv` - 辊道台账数据（开发环境模拟用）
- **Java 后端**: 提供实时电流数据、统计数据等
- **开发模拟**: `server.mjs` - Node.js 服务，模拟 Java 后端接口

## 构建与部署

### 开发模式

```bash
# 1. 启动开发模拟后端（可选，如果没有 Java 后端）
npm run server

# 2. 启动前端开发服务器
npm run dev
```

访问地址: `http://localhost:3000`

### 生产构建

```bash
# 构建生产包
npm run build

# 预览构建结果
npm run preview
```

### 连接 Java 后端

修改 `.env.development` 中的 `VITE_JAVA_API_TARGET` 为 Java 后端实际地址：

```
VITE_JAVA_API_TARGET=http://your-java-server:8080
```

## 开发注意事项

1. **后端 API 依赖**: 开发时需启动 Java 后端服务，或使用 `npm run server` 启动模拟服务
2. **代理配置**: Vite 开发服务器通过 proxy 代理到 Java 后端
3. **认证**: 前端请求会自动携带 localStorage 中的 `token`（JWT）
4. **类型检查**: 构建时会执行 `vue-tsc` 进行类型检查
5. **ESLint 警告**: 生产环境禁止 `console` 和 `debugger`
