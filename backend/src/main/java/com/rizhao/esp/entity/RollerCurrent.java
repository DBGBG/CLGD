package com.rizhao.esp.entity;

/**
 * 辊道电流数据实体类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class RollerCurrent {

    /** 辊道序号 */
    private int id;

    /** 实例名称 (如 LcRt1) */
    private String instanceName;

    /** 点位ID */
    private int attrId;

    /** 电流值 (A) */
    private double current;

    /** 所属工段 */
    private String group;

    /** 数据时间戳 */
    private String timestamp;

    public RollerCurrent() {
    }

    public RollerCurrent(int id, String instanceName, int attrId, double current, String group, String timestamp) {
        this.id = id;
        this.instanceName = instanceName;
        this.attrId = attrId;
        this.current = current;
        this.group = group;
        this.timestamp = timestamp;
    }

    // ==================== Getter / Setter ====================

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getInstanceName() {
        return instanceName;
    }

    public void setInstanceName(String instanceName) {
        this.instanceName = instanceName;
    }

    public int getAttrId() {
        return attrId;
    }

    public void setAttrId(int attrId) {
        this.attrId = attrId;
    }

    public double getCurrent() {
        return current;
    }

    public void setCurrent(double current) {
        this.current = current;
    }

    public String getGroup() {
        return group;
    }

    public void setGroup(String group) {
        this.group = group;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }
}
