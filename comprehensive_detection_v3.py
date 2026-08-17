"""
综合异常检测 v3（共性问题识别 + 数据库持久化 + 状态聚类 + 自编码器 + 向量化优化）
每5分钟执行一次，监测前5分钟的数据
IQR粗筛 → 残差+波动率检测(向量化) → 0值/高值异常(分级) → 孤立森林复核 → 自编码器补充
→ 时间上下文约束 → 运行状态聚类 → 共性问题分析 → 数据库持久化(断线重连+去重)
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
import datetime
import os
import sys
import pymysql
import logging
import csv
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# PyTorch 自编码器（可选依赖）
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    HAS_PYTORCH = True
except ImportError:
    HAS_PYTORCH = False

# ==================== 可配置阈值 ====================
CONFIG = {
    # IQR 异常检测
    'iqr_factor': 3.0,
    # 残差检测
    'residual_window': 20,
    'residual_percentile': 95,
    # 波动率检测
    'volatility_window': 5,
    'volatility_percentile': 95,
    # 0值异常
    'zero_threshold': 1.0,
    'zero_min_duration': 3,
    'zero_max_duration': None,       # None=不限制上限（修复v2的600秒限制）
    'zero_severe_duration': 600,     # 超过此值为"严重跳闸"
    # 跳闸报警（基于组内平均值）
    'trip_group_avg_threshold': 3.0,   # 组内平均电流 > 3.0A
    'trip_self_threshold': 0.7,      # 该辊子电流 < 0.7A
    'trip_min_duration': 3,          # 持续3秒
    # 高值异常（卡阻辅助）
    'high_threshold': 9.0,
    'high_min_duration': 3,
    # 卡阻报警（基于组内平均值）
    'block_relative_threshold': 1.30,  # 高于组内平均值30%
    'block_diff_threshold': 5.0,       # 差值大于5.0A
    'block_min_duration': 3,           # 持续3秒
    # 孤立森林
    'if_n_estimators': 100,
    'if_percentile': 80,
    # 时间上下文约束
    'context_k': 4,
    # 共性问题（产线停机时大量辊道同时跳闸，时间窗口需放宽到5分钟）
    'common_ratio': 0.6,
    'common_time_diff': 300,        # 秒（5分钟），避免产线停机时误报为非共性问题
    # 停棍状态
    'stop_state_ratio': 0.5,
    'stop_state_current': 1.5,
    'stop_state_low_ratio': 0.8,
    # 自编码器
    'ae_enabled': True,              # 是否启用自编码器
    'ae_epochs': 20,
    'ae_percentile': 95,
    # 数据库
    'db_dedup_minutes': 5,
    # 检测周期
    'interval_seconds': 300,
    'window_minutes': 5,
}

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('comprehensive_detection_v3.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== 数据加载 ====================

def load_current_data_from_api(csv_path, start_time, end_time, clean_outliers=False):
    """加载电流数据（跳过转速点位ZS）"""
    try:
        logger.info(f'从CSV文件加载设备列表: {csv_path}')
        if not os.path.exists(csv_path):
            logger.error(f"CSV文件不存在: {csv_path}")
            return {}

        device_map = {}
        attr_ids = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                instance_name = row.get('instance_name')
                attr_id = row.get('attr_id')
                gdmc = row.get('GDMC', '')
                # 跳过转速点位（GDMC以ZS结尾）和空attr_id
                if instance_name and attr_id and not gdmc.endswith('ZS'):
                    device_map[attr_id] = instance_name
                    attr_ids.append(int(attr_id))

        if not attr_ids:
            logger.error("CSV文件中没有找到有效的设备信息")
            return {}
        logger.info(f'读取到 {len(attr_ids)} 个点位ID')

        api_url = "https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exDataManage/samplingQuery?appKey=240622160158015900001"
        payload = {"attrIds": attr_ids, "startTime": str(start_time), "endTime": str(end_time)}
        logger.info(f'从API获取数据，时间范围: {start_time} - {end_time}')
        response = requests.post(api_url, json=payload, timeout=60)
        if response.status_code != 200:
            logger.error(f"API请求失败: {response.status_code}")
            return {}
        data = response.json()
        if str(data.get('code')) != "0":
            logger.error(f"API错误: {data.get('message')}")
            return {}

        sensor_data = data.get('data', {})
        total_records = sum(len(v) for v in sensor_data.values())
        logger.info(f"成功获取 {len(sensor_data)} 个点位，{total_records} 条记录")

        all_data = []
        for attr_id, values in sensor_data.items():
            instance_name = device_map.get(attr_id)
            if not instance_name:
                continue
            for v in values:
                time_str = v.get('time')
                current_value = v.get(attr_id)
                if time_str and current_value is not None:
                    try:
                        timestamp = int(time_str) if isinstance(time_str, str) else time_str
                        time_dt = pd.to_datetime(timestamp / 1000, unit='s') if timestamp > 1e12 else pd.to_datetime(timestamp, unit='s')
                        time_dt = time_dt + datetime.timedelta(hours=8)
                        current_float = float(str(current_value).strip())
                        all_data.append({'instance_name': instance_name, 'time': time_dt, 'current': current_float})
                    except Exception as e:
                        logger.warning(f"处理数据时出错: {e}")

        if not all_data:
            logger.warning("在时间范围内没有数据")
            return {}

        df = pd.DataFrame(all_data)
        df['current'] = pd.to_numeric(df['current'], errors='coerce')
        df = df.dropna(subset=['current'])
        if len(df) == 0:
            logger.warning("没有有效的电流数据")
            return {}

        roller_data = {}
        for instance_name in df['instance_name'].unique():
            roller_df = df[df['instance_name'] == instance_name].set_index('time').sort_index()
            if 'current' in roller_df.columns:
                roller_df['current'] = pd.to_numeric(roller_df['current'], errors='coerce')
                roller_df = roller_df.dropna(subset=['current'])
                if not roller_df.empty:
                    current_series = roller_df['current']
                    roller_df_resampled = current_series.resample('1s').mean().to_frame()
                    if clean_outliers:
                        Q1, Q3 = roller_df_resampled['current'].quantile(0.25), roller_df_resampled['current'].quantile(0.75)
                        IQR = Q3 - Q1
                        roller_df_resampled = roller_df_resampled[(roller_df_resampled['current'] >= Q1 - 3 * IQR) & (roller_df_resampled['current'] <= Q3 + 3 * IQR)]
                    roller_data[instance_name] = roller_df_resampled

        logger.info(f'成功加载 {len(roller_data)} 个辊道的数据')
        return roller_data
    except Exception as e:
        logger.error(f"数据加载失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

def load_speed_data_from_api(csv_path, start_time, end_time):
    """加载转速数据（组级，GDMC以ZS结尾的点位）"""
    try:
        logger.info(f'从CSV文件加载转速点位: {csv_path}')
        if not os.path.exists(csv_path):
            logger.error(f"CSV文件不存在: {csv_path}")
            return {}

        speed_map = {}  # attr_id -> {instance_name, group_name}
        attr_ids = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                instance_name = row.get('instance_name')
                attr_id = row.get('attr_id')
                gdmc = row.get('GDMC', '')
                # 只取转速点位（GDMC以ZS结尾）且有attr_id
                if instance_name and attr_id and gdmc.endswith('ZS'):
                    # 组名：去掉末尾ZS，如 "1ESP1ZS" -> "1ESP1"
                    group_name = gdmc[:-2] if len(gdmc) > 2 else gdmc
                    speed_map[int(attr_id)] = {'instance_name': instance_name, 'group_name': group_name}
                    attr_ids.append(int(attr_id))

        if not attr_ids:
            logger.warning("CSV文件中未找到转速点位（GDMC以ZS结尾且attr_id不为空）")
            return {}
        logger.info(f'读取到 {len(attr_ids)} 个转速点位: {list(speed_map.keys())}')

        api_url = "https://iip.rizhaosteel.com/di-api/dacoo-api/openApi/exDataManage/samplingQuery?appKey=240622160158015900001"
        payload = {"attrIds": attr_ids, "startTime": str(start_time), "endTime": str(end_time)}
        logger.info(f'从API获取转速数据，时间范围: {start_time} - {end_time}')
        response = requests.post(api_url, json=payload, timeout=60)
        if response.status_code != 200:
            logger.error(f"API请求失败: {response.status_code}")
            return {}
        data = response.json()
        if str(data.get('code')) != "0":
            logger.error(f"API错误: {data.get('message')}")
            return {}

        sensor_data = data.get('data', {})
        total_records = sum(len(v) for v in sensor_data.values())
        logger.info(f"成功获取 {len(sensor_data)} 个转速点位，{total_records} 条记录")

        # 解析转速数据：group_name -> DataFrame(speed)
        speed_data = {}
        for attr_id_str, values in sensor_data.items():
            attr_id = int(attr_id_str)
            info = speed_map.get(attr_id)
            if not info:
                continue
            group_name = info['group_name']
            all_data = []
            for v in values:
                time_str = v.get('time')
                speed_value = v.get(attr_id_str)
                if time_str and speed_value is not None:
                    try:
                        timestamp = int(time_str) if isinstance(time_str, str) else time_str
                        time_dt = pd.to_datetime(timestamp / 1000, unit='s') if timestamp > 1e12 else pd.to_datetime(timestamp, unit='s')
                        time_dt = time_dt + datetime.timedelta(hours=8)
                        speed_float = float(str(speed_value).strip())
                        all_data.append({'time': time_dt, 'speed': speed_float})
                    except Exception as e:
                        logger.warning(f"处理转速数据时出错: {e}")

            if all_data:
                df = pd.DataFrame(all_data)
                df = df.set_index('time').sort_index()
                df['speed'] = pd.to_numeric(df['speed'], errors='coerce')
                df = df.dropna(subset=['speed'])
                if not df.empty:
                    speed_data[group_name] = df
                    logger.info(f"组 {group_name} 转速数据点数: {len(df)}, 均值: {df['speed'].mean():.2f}")

        logger.info(f'成功加载 {len(speed_data)} 个组的转速数据')
        return speed_data
    except Exception as e:
        logger.error(f"转速数据加载失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

# ==================== 向量化检测函数 ====================

def detect_anomalies_iqr(data, factor=None):
    """使用 IQR 方法检测异常"""
    factor = factor or CONFIG['iqr_factor']
    Q1, Q3 = np.percentile(data, 25), np.percentile(data, 75)
    IQR = Q3 - Q1
    lower_bound, upper_bound = Q1 - factor * IQR, Q3 + factor * IQR
    return (data < lower_bound) | (data > upper_bound), lower_bound, upper_bound

def detect_anomalies_residual(data, window_size=None, percentile=None):
    """使用移动窗口残差检测异常（向量化版本）"""
    window_size = window_size or CONFIG['residual_window']
    percentile = percentile or CONFIG['residual_percentile']
    n = len(data)
    # 使用 cumsum 技巧向量化计算移动均值
    cumsum = np.concatenate([[0], np.cumsum(data)])
    starts = np.maximum(0, np.arange(n) - window_size // 2)
    ends = np.minimum(n, np.arange(n) + window_size // 2 + 1)
    window_sums = cumsum[ends] - cumsum[starts]
    window_counts = ends - starts
    means = window_sums / window_counts
    residuals = np.abs(data - means)
    threshold = np.percentile(residuals, percentile)
    return residuals > threshold, residuals, threshold

def detect_anomalies_volatility(data, window_size=None, percentile=None):
    """使用局部窗口波动率检测异常（向量化版本）"""
    window_size = window_size or CONFIG['volatility_window']
    percentile = percentile or CONFIG['volatility_percentile']
    n = len(data)
    # 使用 cumsum 和 cumsum of squares 向量化计算移动标准差
    cumsum = np.concatenate([[0], np.cumsum(data)])
    cumsum2 = np.concatenate([[0], np.cumsum(data ** 2)])
    starts = np.maximum(0, np.arange(n) - window_size // 2)
    ends = np.minimum(n, np.arange(n) + window_size // 2 + 1)
    counts = ends - starts
    sums = cumsum[ends] - cumsum[starts]
    sum2s = cumsum2[ends] - cumsum2[starts]
    means = sums / counts
    variances = np.maximum(0, sum2s / counts - means ** 2)
    volatilities = np.sqrt(variances)
    volatilities[counts <= 1] = 0
    threshold = np.percentile(volatilities, percentile)
    return volatilities > threshold, volatilities, threshold

def detect_anomalies_zero(data, zero_threshold=None, min_duration=None, max_duration=None):
    """检测数据降至0的异常（修复：不再限制max_duration上限，分级处理）"""
    zero_threshold = zero_threshold or CONFIG['zero_threshold']
    min_duration = min_duration or CONFIG['zero_min_duration']
    max_duration = max_duration or CONFIG['zero_max_duration']
    anomalies = np.zeros(len(data), dtype=bool)
    zero_points = data < zero_threshold
    i = 0
    while i < len(zero_points):
        if zero_points[i]:
            j = i
            while j < len(zero_points) and zero_points[j]:
                j += 1
            duration = j - i
            if duration >= min_duration:
                if max_duration is None or duration <= max_duration:
                    anomalies[i:j] = True
                # 修复：超过max_duration也标记（不再忽略长时间0值）
                elif max_duration is not None and duration > max_duration:
                    anomalies[i:j] = True
            i = j
        else:
            i += 1
    return anomalies

def apply_time_context_constraint(anomalies, k=None):
    """应用时间上下文约束"""
    k = k or CONFIG['context_k']
    constrained_anomalies = np.copy(anomalies)
    n = len(anomalies)
    for i in range(n):
        if anomalies[i]:
            start, end = max(0, i - k + 1), min(n, i + k)
            if sum(anomalies[start:end]) < k:
                constrained_anomalies[i] = False
    return constrained_anomalies

# ==================== 自编码器（PyTorch 轻量级） ====================

if HAS_PYTORCH:
    class RollerAutoencoder(nn.Module):
        def __init__(self, input_dim):
            super().__init__()
            mid = max(input_dim // 4, 16)
            self.encoder = nn.Sequential(nn.Linear(input_dim, mid), nn.ReLU(), nn.Linear(mid, mid // 2), nn.ReLU())
            self.decoder = nn.Sequential(nn.Linear(mid // 2, mid), nn.ReLU(), nn.Linear(mid, input_dim))

        def forward(self, x):
            return self.decoder(self.encoder(x))


def autoencoder_detect(current_values, epochs=None, percentile=None):
    """自编码器异常检测，返回异常布尔数组和MSE分数"""
    if not HAS_PYTORCH or not CONFIG['ae_enabled']:
        return np.zeros(len(current_values), dtype=bool), np.zeros(len(current_values))
    epochs = epochs or CONFIG['ae_epochs']
    percentile_val = percentile or CONFIG['ae_percentile']

    # 使用滑动窗口构建训练样本
    window_size = 30
    step = 10
    n = len(current_values)
    windows = []
    for i in range(0, n - window_size + 1, step):
        windows.append(current_values[i:i + window_size])
    if len(windows) < 5:
        return np.zeros(n, dtype=bool), np.zeros(n)

    X = np.array(windows, dtype=np.float32)
    # 归一化
    x_min, x_max = X.min(), X.max()
    if x_max - x_min < 1e-6:
        return np.zeros(n, dtype=bool), np.zeros(n)
    X_norm = (X - x_min) / (x_max - x_min + 1e-8)

    model = RollerAutoencoder(window_size)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    X_tensor = torch.tensor(X_norm)

    model.train()
    for _ in range(epochs):
        pred = model(X_tensor)
        loss = criterion(pred, X_tensor)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        pred = model(X_tensor)
        mse_per_window = torch.mean((pred - X_tensor) ** 2, dim=1).numpy()

    threshold = np.percentile(mse_per_window, percentile_val)

    # 将窗口级MSE映射回原始时间点
    point_mse = np.zeros(n)
    point_count = np.zeros(n)
    for idx, i in enumerate(range(0, n - window_size + 1, step)):
        point_mse[i:i + window_size] += mse_per_window[idx]
        point_count[i:i + window_size] += 1
    point_count[point_count == 0] = 1
    point_mse /= point_count

    point_threshold = np.percentile(point_mse[point_mse > 0], percentile_val) if np.any(point_mse > 0) else threshold
    return point_mse > point_threshold, point_mse

# ==================== 运行状态聚类（来自 projectrg） ====================

class StateExtractor:
    """基于 KMeans 的运行状态识别，替代硬编码的停机判断"""

    def __init__(self, roller_data, interval=60):
        """
        roller_data: dict[instance_name -> DataFrame]
        interval: 状态切分间隔（秒）
        """
        self.roller_data = roller_data
        self.interval = interval
        self.states = None
        self.kmeans = None

    def extract_features(self):
        """从所有辊道数据中提取运行状态特征"""
        features = []
        labels = []
        for instance_name, df in self.roller_data.items():
            values = df['current'].values
            if len(values) < self.interval:
                continue
            # 按interval秒切段
            for i in range(0, len(values) - self.interval + 1, self.interval):
                segment = values[i:i + self.interval]
                feat = [
                    np.mean(segment),
                    np.std(segment),
                    np.percentile(segment, 10),
                    np.percentile(segment, 90),
                    np.mean(np.abs(np.diff(segment))),  # 变化率
                ]
                features.append(feat)
                labels.append(instance_name)
        return np.array(features), labels

    def classify_states(self, n_clusters=3):
        """聚类为 n_clusters 种运行状态，返回每种状态的信息"""
        features, labels = self.extract_features()
        if len(features) < n_clusters:
            return {'stopped': 0, 'running': 1, 'total': len(features), 'stop_ratio': 0.0}

        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=5)
        cluster_labels = self.kmeans.fit_predict(features)

        # 均值最低的聚类为候选停机状态
        cluster_means = []
        for c in range(n_clusters):
            mask = cluster_labels == c
            cluster_means.append(np.mean(features[mask, 0]))  # mean current
        stopped_cluster = np.argmin(cluster_means)
        min_cluster_mean = cluster_means[stopped_cluster]

        # 修复：如果最低均值簇的电流仍高于停机阈值，说明没有真正的停机段
        stopped_count = 0
        total_count = len(cluster_labels)
        if min_cluster_mean < CONFIG['stop_state_current']:
            stopped_count = int(np.sum(cluster_labels == stopped_cluster))
        stop_ratio = stopped_count / total_count if total_count > 0 else 0

        state_info = {
            'stopped': int(stopped_count),
            'running': int(total_count - stopped_count),
            'total': int(total_count),
            'stop_ratio': float(stop_ratio),
            'cluster_means': cluster_means,
            'min_cluster_mean': float(min_cluster_mean),
            'stopped_cluster_id': int(stopped_cluster),
        }
        logger.info(f'运行状态聚类: 停机段={stopped_count}, 运行段={total_count - stopped_count}, '
                     f'停机比例={stop_ratio:.2f}, 各簇均值={[f"{m:.2f}" for m in cluster_means]}, '
                     f'最低簇均值={min_cluster_mean:.2f}A, 停机阈值={CONFIG["stop_state_current"]}A')
        return state_info

# ==================== 完整检测函数 ====================

def full_detection(df, instance_name, speed_avg=None, group_avg_values=None):
    """对单个辊道的5分钟窗口进行完整异常检测"""
    detection_results = []
    time_index = df.index
    current_values = df['current'].values

    # 1. IQR 粗筛
    iqr_anomalies, _, _ = detect_anomalies_iqr(current_values)

    # 2. 残差检测（向量化）
    residual_anomalies, _, _ = detect_anomalies_residual(current_values)

    # 3. 波动率检测（向量化）
    volatility_anomalies, _, _ = detect_anomalies_volatility(current_values)

    # 4. 0值异常检测（修复：不再限制max_duration上限）
    zero_anomalies = detect_anomalies_zero(current_values)

    # 5. 高值异常检测
    high_value_anomalies = np.zeros(len(current_values), dtype=bool)
    high_threshold = CONFIG['high_threshold']
    high_min = CONFIG['high_min_duration']
    i = 0
    while i < len(current_values):
        if current_values[i] > high_threshold:
            j = i
            while j < len(current_values) and current_values[j] > high_threshold:
                j += 1
            if (j - i) >= high_min:
                high_value_anomalies[i:j] = True
            i = j
        else:
            i += 1

    # 合并
    if np.sum(zero_anomalies) > 0:
        combined = (iqr_anomalies & residual_anomalies & volatility_anomalies) | zero_anomalies | high_value_anomalies
    else:
        combined = (iqr_anomalies & residual_anomalies & volatility_anomalies) | high_value_anomalies

    # 6. 孤立森林复核
    data_reshaped = current_values.reshape(-1, 1)
    if_model = IsolationForest(n_estimators=CONFIG['if_n_estimators'], contamination='auto', random_state=42)
    if_model.fit(data_reshaped)
    if_scores = -if_model.score_samples(data_reshaped)
    if_threshold = np.percentile(if_scores, CONFIG['if_percentile'])
    if_anomalies = if_scores > if_threshold

    # 7. 综合最终结果
    final_anomalies = np.zeros(len(current_values), dtype=bool)
    for i in range(len(current_values)):
        if zero_anomalies[i]:
            final_anomalies[i] = True
        elif combined[i]:
            final_anomalies[i] = if_anomalies[i]

    # 8. 自编码器补充检测
    if CONFIG['ae_enabled'] and HAS_PYTORCH:
        try:
            ae_anomalies, ae_mse = autoencoder_detect(current_values)
            # 自编码器检测到的异常作为补充信号
            final_anomalies = final_anomalies | ae_anomalies
        except Exception as e:
            logger.warning(f"{instance_name} 自编码器检测失败: {e}")

    zero_positions = np.where(zero_anomalies)[0]
    final_anomalies = apply_time_context_constraint(final_anomalies)
    final_anomalies[zero_positions] = True

    # 9. 跳闸报警（基于组内平均值 + 分级告警）
    if group_avg_values is not None and len(group_avg_values) == len(current_values):
        # 新规则：组内平均 > 3.0A 且 该辊子 < 0.7A，持续3秒
        i = 0
        while i < len(current_values):
            if (group_avg_values[i] > CONFIG['trip_group_avg_threshold'] and
                current_values[i] < CONFIG['trip_self_threshold']):
                j = i
                while (j < len(current_values) and
                       group_avg_values[j] > CONFIG['trip_group_avg_threshold'] and
                       current_values[j] < CONFIG['trip_self_threshold']):
                    j += 1
                duration = j - i
                if duration >= CONFIG['trip_min_duration']:
                    alert_type = '严重跳闸报警' if duration >= CONFIG['zero_severe_duration'] else '跳闸报警'
                    detection_results.append({
                        'start_idx': i, 'end_idx': j - 1,
                        'start_time': time_index[i], 'end_time': time_index[j - 1],
                        'duration': (time_index[j - 1] - time_index[i]).total_seconds(),
                        'alert_type': alert_type,
                    })
                i = j
            else:
                i += 1
    else:
        # 旧规则：仅基于单辊电流
        i = 0
        while i < len(current_values):
            if zero_anomalies[i] and final_anomalies[i]:
                j = i
                while j < len(current_values) and zero_anomalies[j] and final_anomalies[j]:
                    j += 1
                duration = j - i
                if duration >= CONFIG['zero_min_duration']:
                    alert_type = '严重跳闸报警' if duration >= CONFIG['zero_severe_duration'] else '跳闸报警'
                    detection_results.append({
                        'start_idx': i, 'end_idx': j - 1,
                        'start_time': time_index[i], 'end_time': time_index[j - 1],
                        'duration': (time_index[j - 1] - time_index[i]).total_seconds(),
                        'alert_type': alert_type,
                    })
                i = j
            else:
                i += 1

    # 10. 卡阻报警（加入转速辅助判断 + 基于组内平均值的相对阈值）
    # 如果有转速数据且转速极低，可能是产线减速而非卡阻，降低误报
    skip_block = False
    if speed_avg is not None and speed_avg < 1.0:
        logger.info(f"{instance_name} 转速较低({speed_avg:.2f})，降低卡阻检测灵敏度")
        skip_block = True

    # 10.1 基于组内平均值的卡阻检测（新规则）
    if group_avg_values is not None and len(group_avg_values) == len(current_values):
        i = 0
        while i < len(current_values):
            # 检查是否满足：电流 > 组均值*1.30 且 电流 - 组均值 > 5.0A
            if (current_values[i] > group_avg_values[i] * CONFIG['block_relative_threshold'] and
                current_values[i] - group_avg_values[i] > CONFIG['block_diff_threshold']):
                j = i
                while (j < len(current_values) and
                       current_values[j] > group_avg_values[j] * CONFIG['block_relative_threshold'] and
                       current_values[j] - group_avg_values[j] > CONFIG['block_diff_threshold']):
                    j += 1
                if (j - i) >= CONFIG['block_min_duration']:
                    if skip_block:
                        logger.info(f"{instance_name} 检测到相对卡阻但转速低({speed_avg:.2f})，跳过")
                    else:
                        detection_results.append({
                            'start_idx': i, 'end_idx': j - 1,
                            'start_time': time_index[i], 'end_time': time_index[j - 1],
                            'duration': (time_index[j - 1] - time_index[i]).total_seconds(),
                            'alert_type': '卡阻报警',
                        })
                i = j
            else:
                i += 1
    else:
        # 10.2 基于绝对阈值的卡阻检测（旧规则，作为补充）
        i = 0
        while i < len(current_values):
            if high_value_anomalies[i] and final_anomalies[i]:
                j = i
                while j < len(current_values) and high_value_anomalies[j] and final_anomalies[j]:
                    j += 1
                if (j - i) >= CONFIG['block_min_duration']:
                    # 转速极低时跳过卡阻报警（避免产线减速误报）
                    if skip_block:
                        logger.info(f"{instance_name} 检测到高电流但转速低({speed_avg:.2f})，跳过卡阻报警")
                    else:
                        detection_results.append({
                            'start_idx': i, 'end_idx': j - 1,
                            'start_time': time_index[i], 'end_time': time_index[j - 1],
                            'duration': (time_index[j - 1] - time_index[i]).total_seconds(),
                            'alert_type': '卡阻报警',
                        })
                i = j
            else:
                i += 1

    return detection_results

# ==================== 共性问题分析（修复：支持多种类型） ====================

def analyze_common_issues(detection_results, total_rollers):
    """分析共性问题，返回 list（修复：不再只返回一种类型）"""
    common_issues_list = []
    alerts_by_type = {}
    for instance_name, alerts in detection_results.items():
        for alert in alerts:
            alert_type = alert['alert_type']
            if alert_type not in alerts_by_type:
                alerts_by_type[alert_type] = []
            alerts_by_type[alert_type].append({
                'instance': instance_name,
                'start_time': alert['start_time'],
                'end_time': alert['end_time'],
                'duration': alert['duration']
            })

    for alert_type, alerts in alerts_by_type.items():
        affected_ratio = len(alerts) / total_rollers
        if affected_ratio >= CONFIG['common_ratio']:
            start_times = [a['start_time'] for a in alerts]
            end_times = [a['end_time'] for a in alerts]
            min_start, max_start = min(start_times), max(start_times)
            max_end = max(end_times)
            time_diff = (max_start - min_start).total_seconds()
            if time_diff <= CONFIG['common_time_diff']:
                issue = {
                    'issue_type': alert_type,
                    'affected_rollers': len(alerts),
                    'affected_ratio': affected_ratio,
                    'start_time': min_start,
                    'end_time': max_end,
                    'duration': (max_end - min_start).total_seconds(),
                }
                common_issues_list.append(issue)
                logger.info(f"检测到共性问题: {alert_type}，影响 {len(alerts)}/{total_rollers}，比例: {affected_ratio:.2f}")
    return common_issues_list

# ==================== 数据库操作（带断线重连+超时控制） ====================

class DBConnector:
    """数据库连接器，支持断线重连和超时控制"""

    def __init__(self, db_config):
        self.config = db_config
        self.connection = None

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=self.config['host'], port=self.config['port'],
                user=self.config['user'], password=self.config['password'],
                database=self.config['database'], charset=self.config.get('charset', 'utf8mb4'),
                connect_timeout=30, read_timeout=120, write_timeout=120
            )
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            self.connection = None

    def ensure_connected(self):
        """确保连接可用，断线自动重连"""
        if self.connection is None:
            self.connect()
            return
        try:
            self.connection.ping(reconnect=True)
        except Exception:
            logger.warning("数据库连接断开，正在重连...")
            self.connect()

    def insert_alert(self, instance_name, alert_type, alert_time, start_time, end_time, duration, description):
        self.ensure_connected()
        if not self.connection:
            return None
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO roller_alerts (instance_name, alert_type, alert_time, start_time, end_time, duration, description) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (instance_name, alert_type, alert_time, start_time, end_time, duration, description))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入告警失败: {e}")
            try:
                self.connection.rollback()
            except Exception:
                self.connect()
            return None

    def check_recent_alert(self, instance_name, alert_type, minutes=None):
        """检查近期是否已有同类告警（修复：异常时返回True更安全）"""
        minutes = minutes or CONFIG['db_dedup_minutes']
        self.ensure_connected()
        if not self.connection:
            return True  # 连接不可用时保守跳过
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT id FROM roller_alerts WHERE instance_name = %s AND alert_type = %s "
                "AND alert_time > DATE_SUB(NOW(), INTERVAL %s MINUTE) LIMIT 1",
                (instance_name, alert_type, minutes))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.warning(f"检查近期告警失败: {e}")
            return True  # 查询失败时保守跳过，避免重复写入

    def close(self):
        if self.connection:
            try:
                self.connection.close()
                logger.info("数据库连接已关闭")
            except Exception:
                pass
            self.connection = None

# ==================== 主检测函数 ====================

def run_detection(db_connector=None):
    """执行一次异常检测"""
    try:
        logger.info("=" * 60)
        logger.info("开始执行异常检测 v3")
        logger.info("=" * 60)

        end_dt = datetime.datetime.now()
        start_dt = end_dt - datetime.timedelta(minutes=CONFIG['window_minutes'])
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f'监测时间范围: {start_dt} 到 {end_dt}')

        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, 'meter_ledger.csv')
        if not os.path.exists(csv_path):
            csv_path = os.path.join(current_dir, 'CLGD', 'meter_ledger.csv')

        current_data = load_current_data_from_api(csv_path, start_ts, end_ts)
        if not current_data:
            logger.warning('未获取到任何数据')
            return

        logger.info(f'成功获取 {len(current_data)} 个辊道的数据')

        # 读取CSV建立 instance_name -> group_name 映射
        instance_group_map = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                instance_name = row.get('instance_name')
                gdmc = row.get('GDMC', '')
                if instance_name and gdmc and not gdmc.endswith('ZS'):
                    instance_group_map[instance_name] = gdmc

        # 获取转速数据（组级）
        speed_data = load_speed_data_from_api(csv_path, start_ts, end_ts)
        if speed_data:
            logger.info(f'成功获取 {len(speed_data)} 个组的转速数据')
            # 计算各组平均转速
            for group_name, df in speed_data.items():
                avg_speed = df['speed'].mean()
                logger.info(f'组 {group_name} 平均转速: {avg_speed:.2f}')
                # 如果转速≈0（<0.5），过滤掉该组所有辊道
                if avg_speed < 0.5:
                    logger.info(f'组 {group_name} 转速≈0，判定为停机状态')
        else:
            logger.warning('未获取到转速数据，将仅使用电流数据检测')

        # 运行状态聚类（替代硬编码停机判断）
        extractor = StateExtractor(current_data, interval=60)
        state_info = extractor.classify_states()
        if state_info['stop_ratio'] >= CONFIG['stop_state_ratio']:
            logger.info(f'检测到停棍状态（停机比例 {state_info["stop_ratio"]:.2f} >= {CONFIG["stop_state_ratio"]}），跳过检测')
            return

        # 并行检测（带转速信息 + 组内平均值）
        # 先计算各组的组内平均电流（按时间点）
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
                # 合并所有series并取平均值
                combined = pd.concat(series_list, axis=1)
                group_avg_current[group_name] = combined.mean(axis=1)
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
                    logger.info(f'{name} 所属组 {group_name} 转速≈0({speed_avg:.2f})，跳过检测（正常停机）')
                    return name, []
            
            # 获取组内平均电流序列
            group_avg_values = None
            if group_name and group_name in group_avg_current and group_avg_current[group_name] is not None:
                # 对齐时间索引
                group_avg_series = group_avg_current[group_name]
                # 取交集时间点的平均值
                common_index = df.index.intersection(group_avg_series.index)
                if len(common_index) > 0:
                    group_avg_values = group_avg_series.reindex(df.index, method='nearest').values
            
            alerts = full_detection(df, name, speed_avg, group_avg_values)
            if alerts:
                logger.info(f'{name} 检测到 {len(alerts)} 个告警')
            return name, alerts

        all_results = {}
        max_workers = min(8, len(current_data))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_roller, n, df): n for n, df in current_data.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    n, alerts = future.result()
                    all_results[n] = alerts
                except Exception as e:
                    logger.error(f'处理 {name} 时出错: {e}')
                    all_results[name] = []

        # 共性问题分析（支持多种类型）
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

        logger.info(f'总告警: {total_alerts} | 跳闸: {total_trip} | 严重跳闸: {total_severe_trip} | 卡阻: {total_block}')
        if common_issues_list:
            for ci in common_issues_list:
                logger.info(f'共性问题: {ci["issue_type"]}，影响 {ci["affected_rollers"]} 个辊道，持续 {ci["duration"]:.1f}s')

        # 数据库写入
        if db_connector:
            logger.info('正在将非共性问题告警写入数据库...')
            inserted = skipped = 0
            for instance_name, alerts in all_results.items():
                for alert in alerts:
                    # 检查是否属于任何共性问题（时间重叠即过滤）
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
                        desc = f"{instance_name} 检测到{alert['alert_type']}，电流小于{CONFIG['zero_threshold']}A，持续 {alert['duration']:.1f} 秒"
                    else:
                        desc = f"{instance_name} 检测到{alert['alert_type']}，电流大于{CONFIG['high_threshold']}A，持续 {alert['duration']:.1f} 秒"

                    aid = db_connector.insert_alert(instance_name, alert['alert_type'], alert_time,
                                                     alert['start_time'], alert['end_time'], alert['duration'], desc)
                    if aid:
                        inserted += 1
                        logger.info(f"已写入: {instance_name} [{alert['alert_type']}], 持续 {alert['duration']:.1f}s")

            logger.info(f'数据库写入: 新增 {inserted} 条, 去重跳过 {skipped} 条')

    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

# ==================== 主函数 ====================

def main():
    logger.info("=" * 60)
    logger.info("启动异常检测 v3（状态聚类 + 自编码器 + 数据库持久化）")
    logger.info(f"执行周期: 每{CONFIG['interval_seconds']}秒 | 窗口: {CONFIG['window_minutes']}分钟")
    logger.info(f"自编码器: {'启用' if CONFIG['ae_enabled'] and HAS_PYTORCH else '未启用/PyTorch不可用'}")
    logger.info("=" * 60)

    db_config = {
        'host': '10.51.190.70', 'port': 3306,
        'user': 'test', 'password': '1234',
        'database': 'laminar_rt_db', 'charset': 'utf8mb4'
    }
    db = DBConnector(db_config)
    db.connect()

    while True:
        try:
            run_detection(db)
        except Exception as e:
            logger.error(f"检测执行出错: {e}")
        logger.info(f"等待 {CONFIG['interval_seconds']} 秒后执行下一次检测...")
        time.sleep(CONFIG['interval_seconds'])

if __name__ == '__main__':
    main()
