package com.rizhao.esp.entity;

/**
 * 更换统计实体类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class ReplaceStats {

    /** 月更换量 */
    private int monthlyReplace;

    /** 更换辊道数 */
    private int replaceRollers;

    public ReplaceStats() {
    }

    public ReplaceStats(int monthlyReplace, int replaceRollers) {
        this.monthlyReplace = monthlyReplace;
        this.replaceRollers = replaceRollers;
    }

    // ==================== Getter / Setter ====================

    public int getMonthlyReplace() {
        return monthlyReplace;
    }

    public void setMonthlyReplace(int monthlyReplace) {
        this.monthlyReplace = monthlyReplace;
    }

    public int getReplaceRollers() {
        return replaceRollers;
    }

    public void setReplaceRollers(int replaceRollers) {
        this.replaceRollers = replaceRollers;
    }
}
