# 层冷辊道监控系统 API 接口规格说明

> **后端**: Java (Spring Boot)
> **服务地址**: `http://localhost:8080`
> **前端代理路径**: `/api`

---

## 接口概述

本系统前端通过 Axios 发送 HTTP 请求到 Java 后端服务。

**请求配置**:

- `baseURL`: `/api`
- `Content-Type`: `application/json`
- `timeout`: 15000ms
- **认证**: 请求头携带 `Authorization: Bearer <token>`

**响应格式** (Java 后端统一返回):

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

---

## 1. 辊道信息接口

### GET /api/rollers

获取所有辊道信息，按工段分组。

**请求头:**

```
Authorization: Bearer <token>
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "1ESP1": [
      {
        "id": 1,
        "instance_name": "LcRt1",
        "attr_id": 133,
        "group": "1ESP1"
      }
    ],
    "1ESP2": [...],
    "1ESP3": [...],
    "ZS": [...]
  }
}
```

---

## 2. 辊道电流数据接口

### GET /api/current

获取所有辊道的电流数据。

**请求头:**

```
Authorization: Bearer <token>
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "133": {
      "id": 1,
      "instance_name": "LcRt1",
      "attr_id": 133,
      "current": 4.56,
      "group": "1ESP1",
      "timestamp": "2025-01-15T10:30:00.000Z"
    }
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | number | 辊道序号 |
| instance_name | string | 实例名称 (如 LcRt1) |
| attr_id | number | 点位ID |
| current | number | 电流值 (A) |
| group | string | 所属工段 |
| timestamp | string | 数据时间戳 (ISO 8601) |

---

## 3. 设备统计接口

### GET /api/stats/equipment

获取设备统计信息。

**请求头:**

```
Authorization: Bearer <token>
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "totalGroups": 4,
    "faultGroups": 0,
    "normalGroups": 4,
    "totalRollers": 145,
    "faultRollers": 22,
    "normalRollers": 123
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| totalGroups | number | 辊道组总数 |
| faultGroups | number | 故障组数 |
| normalGroups | number | 正常组数 |
| totalRollers | number | 辊道总数 |
| faultRollers | number | 故障辊道数 |
| normalRollers | number | 正常辊道数 |

---

## 4. 报警统计接口

### GET /api/stats/alarm

获取报警统计数据。

**请求头:**

```
Authorization: Bearer <token>
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 155,
    "pending": 50,
    "processed": 100,
    "ignored": 5
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | number | 总报警数 |
| pending | number | 待处理数 |
| processed | number | 已处理数 |
| ignored | number | 已忽略数 |

---

## 5. 更换统计接口

### GET /api/stats/replace

获取更换统计数据。

**请求头:**

```
Authorization: Bearer <token>
```

**响应示例:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "monthlyReplace": 0,
    "replaceRollers": 0
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| monthlyReplace | number | 月更换量 |
| replaceRollers | number | 更换辊道数 |

---

## 状态码说明

| code | 说明 |
|------|------|
| 0 | 成功 |
| 401 | 未授权（Token 无效或过期） |
| 403 | 权限不足 |
| 404 | 接口不存在 |
| 500 | 服务器内部错误 |

---

## 前端调用示例

```typescript
import request from '@/utils/request'

// 获取设备统计
const stats = await request.get('/stats/equipment')
console.log(stats.data.totalRollers)

// 获取电流数据
const current = await request.get('/current')
console.log(current.data['133'].current)
```

---

## Java 后端实现参考

### Spring Boot Controller 示例

```java
@RestController
@RequestMapping("/api")
public class DashboardController {

    @Autowired
    private RollerService rollerService;

    @GetMapping("/current")
    public ApiResponse<Map<String, RollerCurrent>> getCurrentData() {
        return ApiResponse.success(rollerService.getCurrentData());
    }

    @GetMapping("/stats/equipment")
    public ApiResponse<EquipmentStats> getEquipmentStats() {
        return ApiResponse.success(rollerService.getEquipmentStats());
    }
}
```

### 通用响应封装类

```java
@Data
public class ApiResponse<T> {
    private int code;
    private String message;
    private T data;

    public static <T> ApiResponse<T> success(T data) {
        ApiResponse<T> response = new ApiResponse<>();
        response.setCode(0);
        response.setMessage("success");
        response.setData(data);
        return response;
    }
}
```
