#!/usr/bin/env python3
"""
调试脚本 - 检测单个时间窗口的报警（带详细日志）
可以查看每个检测步骤的结果
"""
import datetime
import os
import sys
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from comprehensive_detection_v3 import (
    load_current_data_from_api,
    load_speed_data_from_api,
    full_detection,
    CONFIG,
    logger,
)

# 根据图表分析，假设报警时间是 2026-08-06 10:05 左右
target_time = datetime.datetime(2026, 5, 7, 20, 15, 0)
start_time = target_time - datetime.timedelta(minutes=5)
end_time = target_time + datetime.timedelta(minutes=5)

start_ts = int(start_time.timestamp() * 1000)
end_ts = int(end_time.timestamp() * 1000)

csv_path = os.path.join(SCRIPT_DIR, 'meter_ledger.csv')

print("=" * 60)
print(f"调试窗口: {start_time} ~ {end_time}")
print("=" * 60)

# 获取电流数据
current_data = load_current_data_from_api(csv_path, start_ts, end_ts)
if not current_data:
    print("未获取到电流数据！")
    sys.exit(1)

print(f"获取到 {len(current_data)} 个辊道的数据")

# 打印所有辊道的电流统计
print("\n各辊道电流统计:")
for name, df in current_data.items():
    print(f"  {name}: min={df['current'].min():.2f}, max={df['current'].max():.2f}, mean={df['current'].mean():.2f}")

# 找出电流最高的辊道
max_name = max(current_data.keys(), key=lambda n: current_data[n]['current'].max())
max_df = current_data[max_name]
print(f"\n电流最高的辊道: {max_name}")
print(f"  max={max_df['current'].max():.2f}, mean={max_df['current'].mean():.2f}")

# 手动检测这个辊道
print(f"\n手动检测 {max_name}:")
df = max_df
current_values = df['current'].values
time_index = df.index

# 检查是否有超过绝对阈值9A的数据
high_count = np.sum(current_values > 9.0)
print(f"  电流>9A的数据点数: {high_count}")

# 检查是否有超过相对阈值的数据（假设组均值约3.37A）
group_avg = 3.37
relative_threshold = group_avg * 1.30
diff_threshold = 5.0
print(f"  组均值假设: {group_avg:.2f}A")
print(f"  相对阈值: {relative_threshold:.2f}A")
print(f"  差值阈值: {diff_threshold:.2f}A")

# 检查满足条件的数据点
relative_condition = (current_values > relative_threshold) & (current_values - group_avg > diff_threshold)
print(f"  满足相对卡阻条件的数据点数: {np.sum(relative_condition)}")

# 检查连续满足条件的最大持续时间
max_duration = 0
current_duration = 0
for i in range(len(relative_condition)):
    if relative_condition[i]:
        current_duration += 1
        max_duration = max(max_duration, current_duration)
    else:
        current_duration = 0
print(f"  最大连续满足条件时长: {max_duration} 秒")

# 获取转速数据
speed_data = load_speed_data_from_api(csv_path, start_ts, end_ts)
if speed_data:
    print(f"\n转速数据: {len(speed_data)} 个组")
    for group_name, df in speed_data.items():
        print(f"  {group_name}: mean={df['speed'].mean():.2f}")
else:
    print("\n未获取到转速数据")

# 运行完整检测
print(f"\n运行完整检测 ({max_name})...")
alerts = full_detection(max_df, max_name)
print(f"检测结果: {len(alerts)} 个告警")
for alert in alerts:
    print(f"  - {alert['alert_type']}: {alert['start_time']} ~ {alert['end_time']}, 持续 {alert['duration']:.1f}秒")
