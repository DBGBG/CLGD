package com.rizhao.esp.entity;

/**
 * 设备统计实体类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class EquipmentStats {

    /** 辊道组总数 */
    private int totalGroups;

    /** 故障组数 */
    private int faultGroups;

    /** 正常组数 */
    private int normalGroups;

    /** 辊道总数 */
    private int totalRollers;

    /** 故障辊道数 */
    private int faultRollers;

    /** 正常辊道数 */
    private int normalRollers;

    public EquipmentStats() {
    }

    public EquipmentStats(int totalGroups, int faultGroups, int normalGroups,
                          int totalRollers, int faultRollers, int normalRollers) {
        this.totalGroups = totalGroups;
        this.faultGroups = faultGroups;
        this.normalGroups = normalGroups;
        this.totalRollers = totalRollers;
        this.faultRollers = faultRollers;
        this.normalRollers = normalRollers;
    }

    // ==================== Getter / Setter ====================

    public int getTotalGroups() {
        return totalGroups;
    }

    public void setTotalGroups(int totalGroups) {
        this.totalGroups = totalGroups;
    }

    public int getFaultGroups() {
        return faultGroups;
    }

    public void setFaultGroups(int faultGroups) {
        this.faultGroups = faultGroups;
    }

    public int getNormalGroups() {
        return normalGroups;
    }

    public void setNormalGroups(int normalGroups) {
        this.normalGroups = normalGroups;
    }

    public int getTotalRollers() {
        return totalRollers;
    }

    public void setTotalRollers(int totalRollers) {
        this.totalRollers = totalRollers;
    }

    public int getFaultRollers() {
        return faultRollers;
    }

    public void setFaultRollers(int faultRollers) {
        this.faultRollers = faultRollers;
    }

    public int getNormalRollers() {
        return normalRollers;
    }

    public void setNormalRollers(int normalRollers) {
        this.normalRollers = normalRollers;
    }
}
