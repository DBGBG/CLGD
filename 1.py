import csv
import requests
import sys
import os

API_URL = "https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exRedisManage/recentVal/single?appKey=240622160158015900001"
CSV_FILE = os.path.join(os.path.dirname(__file__), 'meter_ledger.csv')


def read_attr_ids_from_csv():
    """从CSV文件读取点位信息，过滤ZS组"""
    attr_ids = []
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('GDMC') != 'ZS':
                    attr_ids.append({
                        'id': row['id'],
                        'instance_name': row['instance_name'],
                        'attr_id': int(row['attr_id']),
                        'group': row['GDMC']
                    })
        print(f"从CSV读取到 {len(attr_ids)} 个非ZS点位")
        return attr_ids
    except Exception as e:
        print(f"读取CSV失败: {str(e)}")
        return []


def fetch_latest_value(item):
    """获取单个点位的最新数据"""
    attr_id = item['attr_id']
    payload = {"attrId": attr_id}
    
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if str(data.get('code')) == "0":
                result = data.get('data')
                if result:
                    return result
                else:
                    return None
            else:
                return None
        else:
            return None
    except Exception as e:
        return None


def main():
    items = read_attr_ids_from_csv()
    if not items:
        print("没有获取到点位信息")
        return
    
    print(f"\n开始查询 {len(items)} 个点位的最新数据...\n")
    
    success_count = 0
    null_count = 0
    
    for i, item in enumerate(items):
        result = fetch_latest_value(item)
        status = ""
        if result:
            success_count += 1
            status = f"值={result}"
        else:
            null_count += 1
            status = "无数据"
        
        print(f"[{i+1}/{len(items)}] {item['group']} {item['instance_name']} (attr_id={item['attr_id']}) => {status}")
    
    print(f"\n{'='*60}")
    print(f"查询完成: 成功 {success_count} 个, 无数据 {null_count} 个")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
