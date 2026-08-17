#!/usr/bin/env python3
"""
今年报警数据统计分析脚本
连接MySQL数据库，查询并分析今年以来的报警数据
"""
import pymysql
import datetime
import csv

# 数据库配置
DB_CONFIG = {
    'host': '10.51.190.70',
    'port': 3306,
    'user': 'test',
    'password': '1234',
    'database': 'laminar_rt_db',
    'charset': 'utf8mb4',
}

def connect_db():
    """连接数据库"""
    return pymysql.connect(**DB_CONFIG)

def query_yearly_alerts():
    """查询今年以来的报警数据"""
    conn = connect_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 查询今年以来的报警
        sql = """
            SELECT id, instance_name, alert_type, alert_time, 
                   start_time, end_time, duration, description, status
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
            ORDER BY alert_time DESC
        """
        cursor.execute(sql)
        results = cursor.fetchall()
        return results
    finally:
        cursor.close()
        conn.close()

def query_stats():
    """查询统计信息"""
    conn = connect_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 按类型统计
        sql_type = """
            SELECT alert_type, COUNT(*) as count
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
            GROUP BY alert_type
            ORDER BY count DESC
        """
        cursor.execute(sql_type)
        type_stats = cursor.fetchall()
        
        # 按月统计
        sql_month = """
            SELECT DATE_FORMAT(alert_time, '%Y-%m') as month, COUNT(*) as count
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
            GROUP BY month
            ORDER BY month
        """
        cursor.execute(sql_month)
        month_stats = cursor.fetchall()
        
        # 按设备统计TOP10
        sql_device = """
            SELECT instance_name, COUNT(*) as count
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
            GROUP BY instance_name
            ORDER BY count DESC
            LIMIT 10
        """
        cursor.execute(sql_device)
        device_stats = cursor.fetchall()
        
        # 总计
        sql_total = """
            SELECT COUNT(*) as total
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
        """
        cursor.execute(sql_total)
        total = cursor.fetchone()['total']
        
        # 已确认/未确认
        sql_status = """
            SELECT 
                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
                SUM(CASE WHEN status != 'confirmed' OR status IS NULL THEN 1 ELSE 0 END) as unconfirmed
            FROM roller_alerts
            WHERE alert_time >= DATE_FORMAT(CURDATE(), '%Y-01-01')
        """
        cursor.execute(sql_status)
        status_stats = cursor.fetchone()
        
        return {
            'total': total,
            'type_stats': type_stats,
            'month_stats': month_stats,
            'device_stats': device_stats,
            'status_stats': status_stats,
        }
    finally:
        cursor.close()
        conn.close()

def export_to_csv(alerts, filename='yearly_alerts.csv'):
    """导出到CSV"""
    if not alerts:
        print("没有数据可导出")
        return
    
    fieldnames = ['id', 'instance_name', 'alert_type', 'alert_time', 
                  'start_time', 'end_time', 'duration', 'description', 'status']
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for alert in alerts:
            writer.writerow(alert)
    
    print(f"✅ 数据已导出到: {filename}")

def main():
    print("="*60)
    print("层冷辊道报警数据统计分析 - 今年以来")
    print("="*60)
    
    # 查询统计数据
    print("\n📊 正在查询统计数据...")
    stats = query_stats()
    
    print(f"\n{'='*60}")
    print(f"总计报警: {stats['total']} 条")
    print(f"{'='*60}")
    
    # 按状态统计
    print(f"\n状态统计:")
    print(f"  已确认: {stats['status_stats']['confirmed']} 条")
    print(f"  未确认: {stats['status_stats']['unconfirmed']} 条")
    
    # 按类型统计
    print(f"\n按类型统计:")
    for item in stats['type_stats']:
        print(f"  {item['alert_type']}: {item['count']} 条")
    
    # 按月统计
    print(f"\n按月统计:")
    for item in stats['month_stats']:
        print(f"  {item['month']}: {item['count']} 条")
    
    # TOP10设备
    print(f"\n报警次数TOP10设备:")
    for i, item in enumerate(stats['device_stats'], 1):
        print(f"  {i}. {item['instance_name']}: {item['count']} 次")
    
    # 查询详细数据
    print(f"\n{'='*60}")
    print("正在查询详细数据...")
    alerts = query_yearly_alerts()
    print(f"共获取 {len(alerts)} 条记录")
    
    # 导出CSV
    if alerts:
        export_to_csv(alerts)
        
        # 显示最近5条
        print(f"\n最近5条报警:")
        for alert in alerts[:5]:
            print(f"  [{alert['alert_time']}] {alert['instance_name']} - {alert['alert_type']}")
            print(f"    {alert['description'][:60]}...")
    
    print(f"\n{'='*60}")
    print("分析完成")
    print(f"{'='*60}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
