import pandas as pd
import requests
import json
import pymysql
import time
import logging
import os
from datetime import datetime, timedelta

class ESPLayerCoolingData:
    def __init__(self):
        # 配置信息
        self.config = {
            'excel_file': r"c:\Users\DBGBG\Desktop\CLGD\层冷辊道点位对应表.xlsx",
            'api_url': "https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exDataManage/samplingQuery?appKey=240622160158015900001 ",
            'db_config': {
                'host': '10.51.190.70',
                'port': 3306,
                'user': 'test',
                'password': '1234',
                'database': 'laminar_rt_db',
                'charset': 'utf8mb4',
                # 🚀 新增优化参数
                'autocommit': False,      # 手动控制事务
                'connect_timeout': 600,
                'read_timeout': 600,
                'write_timeout': 600,
                'max_allowed_packet': 128*1024*1024,  # 128MB
            },
            'time_range': {
                'start_time': "1769731200000",
                'end_time': "1769731500000"
            },
            'retry_config': {
                'max_retries': 3,
                'retry_interval': 5  # 秒
            },
            'scheduling': {
                'init_start_date': "2025-12-15",
                'interval_minutes': 30
            }
        }
        
        # 初始化日志
        self.setup_logging()
        
        # 初始化标志
        self.initialized = False
        
        # 上次成功获取数据的时间
        self.last_success_time = None

    def setup_logging(self):
        """设置日志配置"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, f"esp_layer_cooling_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def get_attr_ids_from_db(self):
        """从数据库读取attr_id"""
        self.logger.info("正在从数据库读取attr_id...")
        try:
            # 连接数据库
            connection = pymysql.connect(**self.config['db_config'])
            cursor = connection.cursor()
            
            # 查询所有attr_id
            cursor.execute("SELECT attr_id FROM meter_ledger ORDER BY attr_id ASC")
            
            attr_ids = [row[0] for row in cursor.fetchall()]
            
            self.logger.info(f"共从数据库获取到 {len(attr_ids)} 个点位ID")
            self.logger.info(f"点位ID列表: {attr_ids[:10]}...")
            
            return attr_ids
            
        except Exception as e:
            self.logger.error(f"从数据库读取attr_id失败: {str(e)}")
            return []
        finally:
            if 'connection' in locals():
                connection.close()
    
    def read_excel_ledger(self):
        """读取Excel台账文件获取点位信息"""
        self.logger.info("正在读取Excel台账文件...")
        try:
            # 检查文件是否存在
            if not os.path.exists(self.config['excel_file']):
                self.logger.warning("Excel台账文件不存在，跳过读取")
                return [], []
                
            df = pd.read_excel(self.config['excel_file'])
            self.logger.info(f"成功读取Excel文件，共 {len(df)} 行数据")
            
            # 提取点位信息
            ledger_data = []
            attr_ids = []
            
            for _, row in df.iterrows():
                instance_name = row['实例名称(必填)']
                attr_id = row['点位ID(选填)']
                if pd.notna(attr_id):  # 过滤掉空值
                    attr_id_int = int(attr_id)
                    ledger_data.append((instance_name, attr_id_int))
                    attr_ids.append(attr_id_int)
            
            self.logger.info(f"共获取到 {len(attr_ids)} 个点位ID")
            self.logger.info(f"点位ID列表: {attr_ids[:10]}...")
            
            return ledger_data, attr_ids
            
        except Exception as e:
            self.logger.error(f"读取Excel文件失败: {str(e)}")
            return [], []
    
    def create_tables(self):
        """创建数据库表结构（已禁用）"""
        self.logger.info("表结构已存在，跳过创建步骤...")
        return True
    
    def import_ledger_data(self, ledger_data):
        """导入台账数据到数据库"""
        if not ledger_data:
            self.logger.info("没有台账数据需要导入")
            return
        
        self.logger.info(f"正在导入 {len(ledger_data)} 条台账数据...")
        
        try:
            # 连接数据库
            connection = pymysql.connect(**self.config['db_config'])
            cursor = connection.cursor()
            
            # 插入数据
            insert_sql = """
            INSERT INTO meter_ledger (instance_name, attr_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            instance_name = VALUES(instance_name)
            """
            
            cursor.executemany(insert_sql, ledger_data)
            connection.commit()
            
            self.logger.info(f"成功插入/更新 {len(ledger_data)} 条台账记录")
            
            return True
            
        except Exception as e:
            self.logger.error(f"导入台账数据失败: {str(e)}")
            return False
        finally:
            if 'connection' in locals():
                connection.close()
    
    def calculate_time_ranges(self, start_datetime, end_datetime):
        """计算两个时间之间的半小时时间范围
        
        Args:
            start_datetime: 开始时间，datetime对象
            end_datetime: 结束时间，datetime对象
            
        Returns:
            list: 时间范围列表，每个元素为(start_ms, end_ms, start_time_str, end_time_str)
        """
        self.logger.info(f"计算时间范围: {start_datetime} 到 {end_datetime}")
        
        # 转换为秒级时间戳
        start_sec = int(start_datetime.timestamp())
        end_sec = int(end_datetime.timestamp())
        
        # 计算每半个小时的时间范围
        half_hour_ranges = []
        current_sec = start_sec
        
        # 调整到最近的半小时开始（向下取整）
        minutes = start_datetime.minute
        seconds = start_datetime.second
        
        # 计算当前分钟数对30的余数
        remainder = minutes % 30
        if remainder > 0 or seconds > 0:
            # 向下调整到最近的半小时整点
            current_sec -= remainder * 60 + seconds
        
        while current_sec <= end_sec:
            # 半小时结束时间
            next_sec = current_sec + (30 * 60)
            
            # 确保不超过结束时间
            actual_end_sec = min(next_sec - 1, end_sec)
            
            # 转换为毫秒
            start_ms = current_sec * 1000
            end_ms = actual_end_sec * 1000
            
            # 格式化时间
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_sec))
            end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(actual_end_sec))
            
            half_hour_ranges.append((start_ms, end_ms, start_time_str, end_time_str))
            
            # 移动到下半个小时
            current_sec = next_sec
        
        self.logger.info(f"共计算出 {len(half_hour_ranges)} 个半小时的时间范围")
        if half_hour_ranges:
            self.logger.info(f"第一个时间范围: {half_hour_ranges[0][2]} 到 {half_hour_ranges[0][3]}")
            self.logger.info(f"最后一个时间范围: {half_hour_ranges[-1][2]} 到 {half_hour_ranges[-1][3]}")
        
        return half_hour_ranges
    
    def get_initial_time_ranges(self):
        """获取初始化阶段的时间范围
        
        Returns:
            list: 从2025年12月15日到当前时间的半小时时间范围列表
        """
        # 初始化开始时间（修改为2025年12月15日）
        init_start = datetime(2025, 12, 15, 0, 0, 0)
        # 结束时间（2025年12月17日，包含16日整天）
        end_time = datetime(2025, 12, 17, 0, 0, 0)
        
        return self.calculate_time_ranges(init_start, end_time)
    
    def get_latest_time_range(self):
        """获取最近30分钟的时间范围
        
        Returns:
            tuple: (start_ms, end_ms, start_time_str, end_time_str)
        """
        # 当前时间
        current_time = datetime.now()
        # 30分钟前
        start_time = current_time - timedelta(minutes=30)
        
        # 计算时间范围
        ranges = self.calculate_time_ranges(start_time, current_time)
        
        if ranges:
            return ranges[-1] if len(ranges) == 1 else ranges
        return []
    
    def fetch_api_data(self, attr_ids, start_time, end_time):
        """从API获取数据
        
        Args:
            attr_ids: 点位ID列表
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            
        Returns:
            dict: API返回的数据，失败返回None
        """
        if not attr_ids:
            self.logger.warning("没有点位ID，无法获取API数据")
            return None
        
        max_retries = self.config['retry_config']['max_retries']
        retry_interval = self.config['retry_config']['retry_interval']
        
        for retry in range(max_retries):
            self.logger.info(f"正在从API获取 {len(attr_ids)} 个点位的数据... (尝试 {retry+1}/{max_retries})")
            
            # 构建请求体
            payload = {
                "attrIds": attr_ids,
                "startTime": str(start_time),
                "endTime": str(end_time)
            }
            
            try:
                # 发送请求
                response = requests.post(self.config['api_url'], json=payload, timeout=30)
                self.logger.info(f"API响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.logger.info(f"API返回的code: {data.get('code')}")
                        
                        if str(data.get('code')) == "0":
                            self.logger.info("API数据获取成功")
                            return data
                        else:
                            self.logger.warning(f"API返回失败，code: {data.get('code')}")
                            if retry < max_retries - 1:
                                self.logger.info(f"等待 {retry_interval} 秒后重试...")
                                time.sleep(retry_interval)
                                continue
                            return None
                            
                    except json.JSONDecodeError:
                        self.logger.error("API返回的数据格式错误")
                        if retry < max_retries - 1:
                            self.logger.info(f"等待 {retry_interval} 秒后重试...")
                            time.sleep(retry_interval)
                            continue
                        return None
                else:
                    self.logger.error(f"API请求失败，状态码: {response.status_code}")
                    self.logger.error(f"响应内容: {response.text[:500]}...")
                    if retry < max_retries - 1:
                        self.logger.info(f"等待 {retry_interval} 秒后重试...")
                        time.sleep(retry_interval)
                        continue
                    return None
                    
            except Exception as e:
                self.logger.error(f"获取API数据失败: {str(e)}")
                if retry < max_retries - 1:
                    self.logger.info(f"等待 {retry_interval} 秒后重试...")
                    time.sleep(retry_interval)
                    continue
                return None
        
        self.logger.error(f"达到最大重试次数 ({max_retries})，API数据获取失败")
        return None
    
    def store_sensor_data(self, api_data):
        """将传感器数据存储到数据库 - 优化版：真正的批量INSERT"""
        if not api_data or str(api_data.get('code')) != "0":
            self.logger.warning("API数据格式错误或返回失败")
            return
        
        sensor_data = api_data.get('data', {})
        if not sensor_data:
            self.logger.info("没有传感器数据需要存储")
            return
        
        self.logger.info("正在处理传感器数据...")
        
        # 准备数据 - 只需要3个字段：timestamp_ms, attr_id, attr_value
        data_to_insert = []
        total_records = 0
        
        for attr_id, values in sensor_data.items():
            for item in values:
                ts = item.get('time')
                value = item.get(attr_id)
                if ts and value is not None:
                    ts_int = int(ts)
                    data_to_insert.append((ts_int, int(attr_id), float(value), ts_int))
                    total_records += 1
        
        if not data_to_insert:
            self.logger.info("没有数据需要插入")
            return
        
        self.logger.info(f"共获取到 {total_records} 条传感器记录")
        
        try:
            # 连接数据库
            connection = pymysql.connect(**self.config['db_config'])
            cursor = connection.cursor()
            
            # 🚀 优化：真正的批量INSERT，每批5000条
            batch_size = 10000
            inserted_count = 0
            
            for i in range(0, len(data_to_insert), batch_size):
                batch = data_to_insert[i:i+batch_size]
                
                # 构建多值INSERT语句：INSERT INTO t VALUES (1,2,3), (4,5,6), ...
                placeholders = ','.join(['(%s,%s,%s,FROM_UNIXTIME(%s/1000))'] * len(batch))
                sql = f"""
                INSERT INTO sensor_data (timestamp_ms, attr_id, attr_value, record_time) 
                VALUES {placeholders}
                ON DUPLICATE KEY UPDATE 
                record_time = FROM_UNIXTIME(VALUES(timestamp_ms)/1000),
                attr_value = VALUES(attr_value)
                """
                
                # 展平数据 [(1,2,3), (4,5,6)] -> [1,2,3,4,5,6]
                flat_data = [item for sublist in batch for item in sublist]
                
                cursor.execute(sql, flat_data)
                inserted_count += len(batch)
                self.logger.info(f"已插入 {inserted_count}/{total_records} 条记录")
            
            # 🚀 优化：最后统一commit，减少磁盘IO
            connection.commit()
            self.logger.info(f"✅ 成功插入/更新 {total_records} 条传感器记录")
            self.last_success_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"存储传感器数据失败: {str(e)}")
            if 'connection' in locals():
                connection.rollback()
        finally:
            if 'connection' in locals():
                connection.close()
    
    def run_initialization(self):
        """执行初始化数据获取（从2026年2月1日开始）"""
        self.logger.info("=" * 60)
        self.logger.info("1#ESP层冷辊道数据采集项目 - 初始化模式")
        self.logger.info("=" * 60)
        
        # 1. 从数据库读取attr_id
        attr_ids = self.get_attr_ids_from_db()
        
        if not attr_ids:
            self.logger.error("没有获取到attr_id，初始化失败")
            return False
        
        # 2. 获取初始化时间范围
        time_ranges = self.get_initial_time_ranges()
        
        if not time_ranges:
            self.logger.error("没有计算出初始化时间范围，初始化失败")
            return False
        
        # 3. 按半小时分批获取数据
        total_ranges = len(time_ranges)
        success_ranges = 0
        
        self.logger.info(f"开始初始化数据获取，共 {total_ranges} 个时间段")
        
        for i, (start_time, end_time, start_time_str, end_time_str) in enumerate(time_ranges):
            self.logger.info(f"-" * 60)
            self.logger.info(f"处理第 {i+1}/{total_ranges} 个时间段")
            self.logger.info(f"时间范围: {start_time_str} 到 {end_time_str}")
            self.logger.info("-" * 60)
            
            try:
                # 获取API数据
                api_data = self.fetch_api_data(attr_ids, start_time, end_time)
                
                if not api_data:
                    self.logger.warning(f"获取 {start_time_str} 的数据失败，跳过")
                    continue
                
                # 存储传感器数据
                self.store_sensor_data(api_data)
                
                success_ranges += 1
                self.logger.info(f"✅ {start_time_str} 的数据处理成功")
                
                # 每处理完一个时间段，休息1秒，避免请求过于频繁
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"❌ 处理 {start_time_str} 的数据时出错: {str(e)}")
                continue
        
        self.logger.info("=" * 60)
        self.logger.info(f"初始化数据采集完成！")
        self.logger.info(f"共处理 {total_ranges} 个时间段，成功 {success_ranges} 个")
        self.logger.info("=" * 60)
        
        if success_ranges > 0:
            self.initialized = True
            return True
        return False
    
    def run_latest_data(self):
        """获取最近30分钟的数据"""
        self.logger.info("=" * 60)
        self.logger.info("1#ESP层冷辊道数据采集项目 - 定时获取模式")
        self.logger.info("=" * 60)
        
        # 1. 从数据库读取attr_id
        attr_ids = self.get_attr_ids_from_db()
        
        if not attr_ids:
            self.logger.error("没有获取到attr_id，数据获取失败")
            return False
        
        # 2. 获取最近30分钟的时间范围
        time_range = self.get_latest_time_range()
        
        if not time_range:
            self.logger.error("没有计算出时间范围，数据获取失败")
            return False
        
        # 处理时间范围
        if isinstance(time_range, list):
            # 可能返回多个时间范围（跨半小时边界）
            for i, (start_time, end_time, start_time_str, end_time_str) in enumerate(time_range):
                self.logger.info(f"处理第 {i+1}/{len(time_range)} 个时间段")
                self.logger.info(f"时间范围: {start_time_str} 到 {end_time_str}")
                
                try:
                    # 获取API数据
                    api_data = self.fetch_api_data(attr_ids, start_time, end_time)
                    
                    if not api_data:
                        self.logger.warning(f"获取 {start_time_str} 的数据失败，跳过")
                        continue
                    
                    # 存储传感器数据
                    self.store_sensor_data(api_data)
                    
                    self.logger.info(f"✅ {start_time_str} 的数据处理成功")
                    
                except Exception as e:
                    self.logger.error(f"❌ 处理 {start_time_str} 的数据时出错: {str(e)}")
                    continue
        else:
            # 单个时间范围
            start_time, end_time, start_time_str, end_time_str = time_range
            self.logger.info(f"时间范围: {start_time_str} 到 {end_time_str}")
            
            try:
                # 获取API数据
                api_data = self.fetch_api_data(attr_ids, start_time, end_time)
                
                if not api_data:
                    self.logger.warning(f"获取 {start_time_str} 的数据失败")
                    return False
                
                # 存储传感器数据
                self.store_sensor_data(api_data)
                
                self.logger.info(f"✅ {start_time_str} 的数据处理成功")
                
            except Exception as e:
                self.logger.error(f"❌ 处理数据时出错: {str(e)}")
                return False
        
        self.logger.info("=" * 60)
        self.logger.info("最近30分钟数据获取完成！")
        self.logger.info("=" * 60)
        return True
    
    def run_periodically(self):
        """每30分钟执行一次数据采集"""
        self.logger.info("=" * 70)
        self.logger.info("1#ESP层冷辊道数据采集项目 - 定时执行模式")
        self.logger.info("=" * 70)
        self.logger.info("程序将每30分钟执行一次数据采集")
        self.logger.info("按 Ctrl+C 退出程序")
        self.logger.info("=" * 70)
        
        try:
            # 首先执行初始化（仅一次）
            if not self.initialized:
                self.logger.info("执行初始化数据获取...")
                self.run_initialization()
                self.initialized = True
            
            while True:
                # 执行一次最新数据获取
                self.run_latest_data()
                
                # 等待30分钟
                wait_time = 30 * 60
                self.logger.info(f"等待 {wait_time} 秒后执行下一次采集...")
                
                for i in range(wait_time, 0, -1):
                    time.sleep(1)
                    if i % 60 == 0:  # 每分钟打印一次
                        self.logger.info(f"剩余 {i//60} 分钟...")
                
        except KeyboardInterrupt:
            self.logger.info("程序已手动退出")
        except Exception as e:
            self.logger.error(f"程序运行出错: {str(e)}")
            # 继续运行，确保服务不中断
            self.logger.error(f"程序运行出错: {str(e)}")
            self.logger.info("程序将在5秒后重启...")
            time.sleep(5)
            self.run_periodically()

if __name__ == "__main__":
    # 运行程序 - 定时执行模式（初始化后每30分钟获取数据）
    app = ESPLayerCoolingData()
    app.run_periodically()