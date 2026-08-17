#!/usr/bin/env python3
"""
调试脚本 - 检测指定时间窗口的报警
专门排查2026-05-07 20:15:05的报警为什么没有被检测出来
"""
import datetime
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from comprehensive_detection_v3 import (
    load_current_data_from_api,
    load_speed_data_from_api,
    full_detection,
    DBConnector,
    StateExtractor,
    CONFIG,
    logger,
)

# 目标时间：2026-05-07 20:15:05
target_time = datetime.datetime(2026, 5, 7, 20, 15, 5)
start_time = target_time - datetime.timedelta(minutes=5)
end_time = target_time + datetime.timedelta(minutes=5)

start_ts = int(start_time.timestamp() * 1000)
end_ts = int(end_time.timestamp() * 1000)

csv_path = os.path.join(SCRIPT_DIR, 'meter_ledger.csv')

print("=" * 60)
print(f"调试窗口: {start_time} ~ {end_time}")
print(f"时间戳: {start_ts} ~ {end_ts}")
print("=" * 60)

# 获取电流数据
print("\n[1] 获取电流数据...")
current_data = load_current_data_from_api(csv_path, start_ts, end_ts)
if not current_data:
    print("未获取到电流数据！")
    sys.exit(1)

print(f"获取到 {len(current_data)} 个辊道的数据")

# 查看设备140的数据
if 'R430322G346' in current_data:
    df = current_data['R430322G346']
    print(f"\n[2] 设备140 (R430322G346) 数据:")
    print(f"数据点数: {len(df)}")
    print(f"电流范围: {df['current'].min():.4f} ~ {df['current'].max():.4f}")
    print(f"电流均值: {df['current'].mean():.4f}")
    print(f"前5条数据:\n{df.head()}")
else:
    print("\n[2] 设备140 (R430322G346) 不在数据中！")
    print("可用设备:", list(current_data.keys())[:5], "...")

# 获取转速数据
print("\n[3] 获取转速数据...")
speed_data = load_speed_data_from_api(csv_path, start_ts, end_ts)
if speed_data:
    print(f"获取到 {len(speed_data)} 个组的转速数据")
    for group, df in speed_data.items():
        print(f"  组 {group}: 均值={df['speed'].mean():.2f}")
else:
    print("未获取到转速数据")

# 运行状态聚类
print("\n[4] 运行状态聚类...")
extractor = StateExtractor(current_data, interval=60)
state_info = extractor.classify_states()
print(f"停机比例: {state_info['stop_ratio']:.2f}")
print(f"停机阈值: {CONFIG['stop_state_ratio']}")
if state_info['stop_ratio'] >= CONFIG['stop_state_ratio']:
    print("被判定为停棍状态，跳过检测！")
    sys.exit(0)

# 检测设备140
print("\n[5] 检测设备140...")
if 'R430322G346' in current_data:
    df = current_data['R430322G346']
    # 获取转速
    speed_avg = None
    if speed_data and '1ESP2' in speed_data:
        speed_avg = speed_data['1ESP2']['speed'].mean()
    
    alerts = full_detection(df, 'R430322G346', speed_avg)
    print(f"检测结果: {len(alerts)} 个告警")
    for alert in alerts:
        print(f"  - {alert['alert_type']}: {alert['start_time']} ~ {alert['end_time']}, 持续 {alert['duration']:.1f}秒")
else:
    print("设备140不在数据中，无法检测")
