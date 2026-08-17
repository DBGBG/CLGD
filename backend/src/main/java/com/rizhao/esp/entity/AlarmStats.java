package com.rizhao.esp.entity;

/**
 * 报警统计实体类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class AlarmStats {

    /** 总报警数 */
    private int total;

    /** 待处理数 */
    private int pending;

    /** 已处理数 */
    private int processed;

    /** 已忽略数 */
    private int ignored;

    public AlarmStats() {
    }

    public AlarmStats(int total, int pending, int processed, int ignored) {
        this.total = total;
        this.pending = pending;
        this.processed = processed;
        this.ignored = ignored;
    }

    // ==================== Getter / Setter ====================

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public int getPending() {
        return pending;
    }

    public void setPending(int pending) {
        this.pending = pending;
    }

    public int getProcessed() {
        return processed;
    }

    public void setProcessed(int processed) {
        this.processed = processed;
    }

    public int getIgnored() {
        return ignored;
    }

    public void setIgnored(int ignored) {
        this.ignored = ignored;
    }
}
