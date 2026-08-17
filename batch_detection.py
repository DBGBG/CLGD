#!/usr/bin/env python3
"""
批量检测脚本 - 对指定时间范围内的历史数据进行批量异常检测
调用 comprehensive_detection_v3.py 的检测逻辑，支持指定时间范围
"""
import datetime
import time
import os
import sys

# 将脚本所在目录加入路径，以便导入模型
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from comprehensive_detection_v3 import (
    load_current_data_from_api,
    load_speed_data_from_api,
    full_detection,
    analyze_common_issues,
    DBConnector,
    StateExtractor,
    CONFIG,
    logger,
)
import csv
import concurrent.futures

# ==================== 批量检测配置 ====================
BATCH_CONFIG = {
    # 时间范围（2026-05-07 20:00:00 至今）
    'start_date': datetime.datetime(2026, 5, 20, 0, 0, 0),
    'end_date':  datetime.datetime.now(),
    # 检测窗口（分钟）
    'window_minutes': 5,
    # 批次间隔（秒），避免请求过于频繁
    'batch_interval': 2,
    # CSV文件路径
    'csv_path': os.path.join(SCRIPT_DIR, 'meter_ledger.csv'),
}


def run_batch_detection(start_time, end_time, db_connector=None):
    """对单个时间窗口执行检测"""
    try:
        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        logger.info(f"[{start_time.strftime('%Y-%m-%d %H:%M')}~{end_time.strftime('%H:%M')}] 窗口开始检测")

        # 获取电流数据
        current_data = load_current_data_from_api(BATCH_CONFIG['csv_path'], start_ts, end_ts)
        if not current_data:
            logger.warning(f"窗口 {start_time}~{end_time} 未获取到数据")
            return

        logger.info(f"成功获取 {len(current_data)} 个辊道的数据")

        # 读取CSV建立 instance_name -> group_name 映射
        instance_group_map = {}
        with open(BATCH_CONFIG['csv_path'], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                instance_name = row.get('instance_name')
                gdmc = row.get('GDMC', '')
                if instance_name and gdmc and not gdmc.endswith('ZS'):
                    instance_group_map[instance_name] = gdmc

        # 获取转速数据（组级）
        speed_data = load_speed_data_from_api(BATCH_CONFIG['csv_path'], start_ts, end_ts)
        if speed_data:
            logger.info(f"成功获取 {len(speed_data)} 个组的转速数据")
            # 只打印转速异常的组
            for group_name, df in speed_data.items():
                avg_speed = df['speed'].mean()
                if avg_speed < 0.5:
                    logger.info(f'组 {group_name} 平均转速: {avg_speed:.2f} (已停机)')
        else:
            logger.warning('未获取到转速数据，将仅使用电流数据检测')

        # 运行状态聚类
        extractor = StateExtractor(current_data, interval=60)
        state_info = extractor.classify_states()
        if state_info['stop_ratio'] >= CONFIG['stop_state_ratio']:
            logger.info(f"检测到停棍状态（比例 {state_info['stop_ratio']:.2f}），跳过")
            return

        # 并行检测（带转速信息 + 组内平均值）
        # 先计算各组的组内平均电流（按时间点）
        import pandas as pd
        group_avg_current = {}
        for name, df in current_data.items():
            group_name = instance_group_map.get(name, '')
            if group_name:
                if group_name not in group_avg_current:
                    group_avg_current[group_name] = []
                group_avg_current[group_name].append(df['current'])
        
        # 合并同组所有辊道的电流数据，计算每个时间点的平均值
        for group_name, series_list in group_avg_current.items():
            if len(series_list) > 0:
                # 使用join='inner'确保只保留共同的时间点
                combined = pd.concat(series_list, axis=1)
                # 计算每行的平均值，忽略NaN
                group_avg_current[group_name] = combined.mean(axis=1, skipna=True).dropna()
                avg_mean = group_avg_current[group_name].mean()
                logger.info(f"组 {group_name} 平均电流: {avg_mean:.2f}A, 数据点数={len(group_avg_current[group_name])}")
            else:
                group_avg_current[group_name] = None

        def process_roller(name, df):
            # 获取该辊道所属组的转速均值
            group_name = instance_group_map.get(name, '')
            speed_avg = None
            if group_name and group_name in speed_data:
                speed_avg = speed_data[group_name]['speed'].mean()
                # 如果转速≈0（<0.5），跳过该辊道（正常停机）
                if speed_avg < 0.5:
                    logger.debug(f'{name} 所属组 {group_name} 转速≈0({speed_avg:.2f})，跳过检测（正常停机）')
                    return name, []
            
            # 获取组内平均电流序列
            group_avg_values = None
            if group_name and group_name in group_avg_current and group_avg_current[group_name] is not None:
                group_avg_series = group_avg_current[group_name]
                common_index = df.index.intersection(group_avg_series.index)
                if len(common_index) > 0:
                    group_avg_values = group_avg_series.reindex(df.index, method='nearest').values
                    # 检查是否有NaN
                    nan_count = sum(1 for v in group_avg_values if pd.isna(v))
                    if nan_count > 0:
                        logger.warning(f'{name} 组内平均值包含 {nan_count} 个NaN，将使用旧规则')
                        group_avg_values = None
                else:
                    logger.warning(f'{name} 无共同时间点，组内平均值为空')
            
            alerts = full_detection(df, name, speed_avg, group_avg_values)
            if name == 'LcRt140':
                has_avg = '有' if group_avg_values is not None else '无'
                logger.info(f"【调试】{name} 检测完成: {len(alerts)} 个告警, speed_avg={speed_avg:.2f}, group_avg_values={has_avg}")
            if alerts:
                logger.info(f'{name} 检测到 {len(alerts)} 个告警')
            return name, alerts

        all_results = {}
        max_workers = min(8, len(current_data))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_roller, n, df): n for n, df in current_data.items()}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    n, alerts = future.result()
                    all_results[n] = alerts
                except Exception as e:
                    logger.error(f'处理 {name} 时出错: {e}')
                    all_results[name] = []

        # 共性问题分析
        common_issues_list = analyze_common_issues(all_results, len(current_data))
        
        # 汇总
        total_alerts = total_trip = total_severe_trip = total_block = 0
        for alerts in all_results.values():
            total_alerts += len(alerts)
            for a in alerts:
                if a['alert_type'] == '跳闸报警':
                    total_trip += 1
                elif a['alert_type'] == '严重跳闸报警':
                    total_severe_trip += 1
                elif a['alert_type'] == '卡阻报警':
                    total_block += 1
        
        logger.info(f'窗口检测完成: 总告警 {total_alerts} | 跳闸 {total_trip} | 严重跳闸 {total_severe_trip} | 卡阻 {total_block}')
        
        # 数据库写入
        if db_connector:
            inserted = skipped = 0
            for instance_name, alerts in all_results.items():
                for alert in alerts:
                    # 检查是否属于共性问题
                    is_common = False
                    for ci in common_issues_list:
                        if (alert['alert_type'] == ci['issue_type'] and
                            alert['start_time'] <= ci['end_time'] and
                            alert['end_time'] >= ci['start_time']):
                            is_common = True
                            break
                    if is_common:
                        continue
                    
                    if db_connector.check_recent_alert(instance_name, alert['alert_type']):
                        skipped += 1
                        continue
                    
                    alert_time = datetime.datetime.now()
                    if '跳闸' in alert['alert_type']:
                        desc = f"{instance_name} 检测到{alert['alert_type']}，持续 {alert['duration']:.1f} 秒"
                    else:
                        desc = f"{instance_name} 检测到{alert['alert_type']}，持续 {alert['duration']:.1f} 秒"
                    
                    aid = db_connector.insert_alert(
                        instance_name, alert['alert_type'], alert_time,
                        alert['start_time'], alert['end_time'], alert['duration'], desc
                    )
                    if aid:
                        inserted += 1
            
            logger.info(f'数据库写入: 新增 {inserted} 条, 去重跳过 {skipped} 条')
        
    except Exception as e:
        logger.error(f"窗口检测出错: {e}")
        import traceback
        logger.error(traceback.format_exc())


def main():
    start_time = BATCH_CONFIG['start_date']
    end_time = BATCH_CONFIG['end_date']
    window = datetime.timedelta(minutes=BATCH_CONFIG['window_minutes'])
    
    logger.info(f"批量异常检测: {start_time} ~ {end_time}, 窗口={BATCH_CONFIG['window_minutes']}分钟")
    
    # 计算总窗口数
    total_seconds = (end_time - start_time).total_seconds()
    total_windows = int(total_seconds / (BATCH_CONFIG['window_minutes'] * 60))
    logger.info(f"预计检测 {total_windows} 个窗口")
    
    # 初始化数据库连接
    db_config = {
        'host': '10.51.190.70', 'port': 3306,
        'user': 'test', 'password': '1234',
        'database': 'laminar_rt_db', 'charset': 'utf8mb4'
    }
    db = DBConnector(db_config)
    db.connect()
    
    # 批量检测循环
    current = start_time
    window_count = 0
    
    try:
        while current < end_time:
            window_start = current
            window_end = min(current + window, end_time)
            
            window_count += 1
            logger.info(f"批次 {window_count}/{total_windows}: {window_start.strftime('%Y-%m-%d %H:%M')}~{window_end.strftime('%H:%M')}")
            
            # 执行检测
            run_batch_detection(window_start, window_end, db)
            
            # 前进到下一个窗口
            current = window_end
            
            # 避免请求过于频繁
            if current < end_time:
                time.sleep(BATCH_CONFIG['batch_interval'])
                
                # 每10个窗口暂停一下，避免API限流
                if window_count % 10 == 0:
                    logger.info(f"已处理 {window_count} 个窗口，暂停 5 秒...")
                    time.sleep(5)
    
    except KeyboardInterrupt:
        logger.info("用户中断，停止检测")
    
    finally:
        db.close()
        logger.info(f"批量检测完成，共处理 {window_count} 个窗口")


if __name__ == '__main__':
    main()
