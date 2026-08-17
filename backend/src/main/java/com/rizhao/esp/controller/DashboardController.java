package com.rizhao.esp.controller;

import com.rizhao.esp.entity.*;
import com.rizhao.esp.service.RollerService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 仪表盘数据控制器
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
@RestController
@RequestMapping("/api")
public class DashboardController {

    private final RollerService rollerService;

    @Autowired
    public DashboardController(RollerService rollerService) {
        this.rollerService = rollerService;
    }

    /**
     * 获取所有辊道信息（按组）
     */
    @GetMapping("/rollers")
    public ApiResponse<Map<String, List<MeterLedger>>> getRollersByGroup() {
        return ApiResponse.success(rollerService.getRollersByGroup());
    }

    /**
     * 获取辊道电流数据
     */
    @GetMapping("/current")
    public ApiResponse<Map<String, RollerCurrent>> getCurrentData() {
        return ApiResponse.success(rollerService.getCurrentData());
    }

    /**
     * 获取设备统计
     */
    @GetMapping("/stats/equipment")
    public ApiResponse<EquipmentStats> getEquipmentStats() {
        return ApiResponse.success(rollerService.getEquipmentStats());
    }

    /**
     * 获取报警统计
     */
    @GetMapping("/stats/alarm")
    public ApiResponse<AlarmStats> getAlarmStats() {
        return ApiResponse.success(rollerService.getAlarmStats());
    }

    /**
     * 获取更换统计
     */
    @GetMapping("/stats/replace")
    public ApiResponse<ReplaceStats> getReplaceStats() {
        return ApiResponse.success(rollerService.getReplaceStats());
    }
}
