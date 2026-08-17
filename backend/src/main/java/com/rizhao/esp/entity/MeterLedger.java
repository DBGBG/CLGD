package com.rizhao.esp.entity;

/**
 * 辊道台账实体类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class MeterLedger {

    /** 序号 */
    private int id;

    /** 实例名称 (如 LcRt1) */
    private String instanceName;

    /** 点位ID */
    private int attrId;

    /** 工段名称 (如 1ESP1, 1ESP2, 1ESP3, ZS) */
    private String gdmc;

    public MeterLedger() {
    }

    public MeterLedger(int id, String instanceName, int attrId, String gdmc) {
        this.id = id;
        this.instanceName = instanceName;
        this.attrId = attrId;
        this.gdmc = gdmc;
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

    public String getGdmc() {
        return gdmc;
    }

    public void setGdmc(String gdmc) {
        this.gdmc = gdmc;
    }
}
