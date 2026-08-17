package com.rizhao.esp.entity;

import java.util.List;
import java.util.Map;

/**
 * 外部 API 响应数据结构
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class ApiDataResponse {

    /** 响应码 */
    private String code;

    /** 响应消息 */
    private String message;

    /** 传感器数据 - key 为 attr_id，value 为数据列表 */
    private Map<String, List<Map<String, Object>>> data;

    public ApiDataResponse() {
    }

    // ==================== Getter / Setter ====================

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public Map<String, List<Map<String, Object>>> getData() {
        return data;
    }

    public void setData(Map<String, List<Map<String, Object>>> data) {
        this.data = data;
    }
}
