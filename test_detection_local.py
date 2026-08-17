#!/usr/bin/env python3
"""
本地测试脚本 - 验证模型数据获取和检测逻辑
不连接数据库，只打印检测结果到控制台
"""
import numpy as np
import pandas as pd
import csv
import os
import requests
import datetime

# ==================== 配置 ====================
CSV_FILE = r"d:\程序开发\层冷辊道软件自立项目\meter_ledger.csv"
API_URL = "https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exDataManage/samplingQuery?appKey=240622160158015900001"

# ==================== 读取CSV ====================
def read_csv(csv_path):
    """读取CSV文件"""
    data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def get_speed_points(data):
    """获取转速点位"""
    return [item for item in data if item.get('GDMC', '').endswith('ZS') and item.get('attr_id')]

def get_current_points(data):
    """获取电流点位"""
    return [item for item in data if not item.get('GDMC', '').endswith('ZS') and item.get('attr_id')]

# ==================== API测试 ====================
def test_api(points, name="电流", sample_size=3):
    """测试API是否正常"""
    import random
    sample = random.sample(points, min(sample_size, len(points)))
    attr_ids = [int(p['attr_id']) for p in sample]
    
    end_dt = datetime.datetime.now()
    start_dt = end_dt - datetime.timedelta(minutes=5)
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    payload = {"attrIds": attr_ids, "startTime": str(start_ts), "endTime": str(end_ts)}
    
    print(f"\n{'='*60}")
    print(f"测试{name}API ({len(sample)}个点位)")
    print(f"{'='*60}")
    print(f"时间范围: {start_dt} ~ {end_dt}")
    print(f"点位: {[p['instance_name'] for p in sample]}")
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if str(data.get('code')) == "0":
                sensor_data = data.get('data', {})
                total = sum(len(v) for v in sensor_data.values())
                print(f"✅ API正常，获取到 {len(sensor_data)} 个点位，共 {total} 条数据")
                
                # 打印第一条数据示例
                for attr_id, values in list(sensor_data.items())[:1]:
                    if values:
                        print(f"   示例: {attr_id} -> {values[0]}")
                return True
            else:
                print(f"❌ API返回错误: {data.get('message')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"   响应: {response.text[:200]}")
    except Exception as e:
        print(f"❌ 请求异常: {e}")
    
    return False

# ==================== 主函数 ====================
def main():
    print("="*60)
    print("层冷辊道模型检测 - 本地测试")
    print("="*60)
    
    # 1. 检查CSV文件
    print(f"\n📋 CSV文件: {CSV_FILE}")
    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV文件不存在!")
        return
    
    data = read_csv(CSV_FILE)
    print(f"✅ CSV读取成功，共 {len(data)} 条记录")
    
    # 2. 分离电流和转速
    speed_points = get_speed_points(data)
    current_points = get_current_points(data)
    
    print(f"\n📊 点位统计:")
    print(f"   电流点位: {len(current_points)} 个")
    print(f"   转速点位: {len(speed_points)} 个")
    
    if speed_points:
        print(f"\n   转速点位详情:")
        for p in speed_points:
            print(f"     - {p['instance_name']}: attr_id={p['attr_id']}, GDMC={p['GDMC']}")
    
    # 3. 测试API
    print("\n" + "="*60)
    print("开始API测试...")
    
    # 测试电流API
    if current_points:
        test_api(current_points, "电流", 3)
    
    # 测试转速API
    if speed_points:
        test_api(speed_points, "转速", 3)
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == '__main__':
    main()
