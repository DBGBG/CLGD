package com.rizhao.esp.service;

import com.rizhao.esp.entity.*;
import com.rizhao.esp.utils.CsvUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * 辊道业务服务类
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
@Service
public class RollerService {

    private static final Logger logger = LoggerFactory.getLogger(RollerService.class);

    @Value("${esp.csv.path:meter_ledger.csv}")
    private String csvPath;

    @Value("${esp.current.threshold:6.0}")
    private double currentThreshold;

    @Value("${esp.api.url:}")
    private String apiUrl;

    private final RestTemplate restTemplate;

    @Autowired
    public RollerService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    private List<MeterLedger> ledgerCache = null;
    private final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private volatile long lastApiFailTime = 0;
    private static final long API_FAIL_COOLDOWN_MS = 60000;
    private Map<Integer, Double> lastKnownCurrentMap = new HashMap<>();

    /**
     * 获取辊道台账数据（带缓存）
     */
    public List<MeterLedger> getLedgerData() {
        if (ledgerCache == null) {
            ledgerCache = CsvUtils.readCsv(csvPath);
        }
        return ledgerCache;
    }

    /**
     * 获取所有辊道信息（按组）
     */
    public Map<String, List<MeterLedger>> getRollersByGroup() {
        List<MeterLedger> data = getLedgerData();
        return CsvUtils.groupByGdmc(data);
    }

    /**
     * 获取辊道电流数据（从外部 API 获取实时数据）
     */
    public Map<String, RollerCurrent> getCurrentData() {
        List<MeterLedger> ledgers = getLedgerData();
        Map<String, RollerCurrent> result = new LinkedHashMap<>();
        String now = LocalDateTime.now().format(formatter);

        // 获取实时电流数据（从 API）
        Map<Integer, Double> currentMap = fetchCurrentDataFromApi(ledgers);

        for (MeterLedger ledger : ledgers) {
            // 只使用 API 返回的真实数据，没有数据时电流为 null
            Double current = currentMap.get(ledger.getAttrId());

            RollerCurrent rc = new RollerCurrent(
                    ledger.getId(),
                    ledger.getInstanceName(),
                    ledger.getAttrId(),
                    current != null ? current : 0.0,
                    ledger.getGdmc(),
                    now
            );
            result.put(String.valueOf(ledger.getAttrId()), rc);
        }

        return result;
    }

    /**
     * 从外部 API 获取实时电流数据（带熔断机制）
     */
    private Map<Integer, Double> fetchCurrentDataFromApi(List<MeterLedger> ledgers) {
        Map<Integer, Double> result = new HashMap<>();

        if (apiUrl == null || apiUrl.isEmpty()) {
            logger.warn("API URL 未配置");
            return result;
        }

        long now = System.currentTimeMillis();
        if (now - lastApiFailTime < API_FAIL_COOLDOWN_MS) {
            if (!lastKnownCurrentMap.isEmpty()) {
                logger.debug("API 熔断中，使用缓存数据");
                return new HashMap<>(lastKnownCurrentMap);
            }
            logger.debug("API 熔断中，无缓存数据");
            return result;
        }

        try {
            List<Integer> attrIds = new ArrayList<>();
            for (MeterLedger ledger : ledgers) {
                attrIds.add(ledger.getAttrId());
            }

            long endTime = System.currentTimeMillis();
            long startTime = endTime - (30 * 60 * 1000);

            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("attrIds", attrIds);
            requestBody.put("startTime", String.valueOf(startTime));
            requestBody.put("endTime", String.valueOf(endTime));

            logger.info("正在请求 API: {}, attrIds数量: {}, 时间范围: {}-{}", 
                apiUrl, attrIds.size(), startTime, endTime);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

            ApiDataResponse response = restTemplate.postForObject(apiUrl, request, ApiDataResponse.class);

            if (response == null) {
                logger.error("API 返回空响应");
                lastApiFailTime = now;
                return result;
            }

            logger.info("API 响应: code={}, message={}", response.getCode(), response.getMessage());

            if ("0".equals(response.getCode())) {
                Map<String, List<Map<String, Object>>> data = response.getData();
                if (data != null) {
                    int successCount = 0;
                    for (Map.Entry<String, List<Map<String, Object>>> entry : data.entrySet()) {
                        String attrIdStr = entry.getKey();
                        List<Map<String, Object>> values = entry.getValue();
                        if (values != null && !values.isEmpty()) {
                            Map<String, Object> latest = values.get(values.size() - 1);
                            Object value = latest.get(attrIdStr);
                            if (value == null) {
                                for (Map.Entry<String, Object> item : latest.entrySet()) {
                                    if (!"time".equals(item.getKey())) {
                                        value = item.getValue();
                                        break;
                                    }
                                }
                            }
                            if (value != null) {
                                try {
                                    double current = Double.parseDouble(value.toString());
                                    result.put(Integer.parseInt(attrIdStr), current);
                                    successCount++;
                                } catch (NumberFormatException e) {
                                    logger.warn("解析电流值失败: attrId={}, value={}", attrIdStr, value);
                                }
                            }
                        }
                    }
                    logger.info("API 数据获取成功，共解析 {}/{} 条电流数据", successCount, attrIds.size());
                    lastKnownCurrentMap = new HashMap<>(result);
                } else {
                    logger.warn("API 返回数据为空");
                }
            } else {
                logger.warn("API 返回错误: code={}, message={}", response.getCode(), response.getMessage());
                lastApiFailTime = now;
            }

        } catch (Exception e) {
            logger.error("API 请求异常: {}", e.getMessage());
            lastApiFailTime = now;
            if (!lastKnownCurrentMap.isEmpty()) {
                logger.info("使用缓存数据作为降级");
                return new HashMap<>(lastKnownCurrentMap);
            }
        }

        return result;
    }

    /**
     * 获取设备统计（基于 API 真实数据）
     */
    public EquipmentStats getEquipmentStats() {
        List<MeterLedger> ledgers = getLedgerData();
        Map<String, List<MeterLedger>> groups = CsvUtils.groupByGdmc(ledgers);
        Map<Integer, Double> currentMap = fetchCurrentDataFromApi(ledgers);

        int totalGroups = groups.size();
        int totalRollers = ledgers.size();

        // 统计故障辊道（电流 > 阈值的辊道，仅基于真实数据）
        int faultRollers = 0;
        for (MeterLedger ledger : ledgers) {
            Double current = currentMap.get(ledger.getAttrId());
            if (current != null && current > currentThreshold) {
                faultRollers++;
            }
        }

        // 统计故障组（如果组内有故障辊道，则该组为故障组）
        int faultGroups = 0;
        for (Map.Entry<String, List<MeterLedger>> entry : groups.entrySet()) {
            boolean hasFault = false;
            for (MeterLedger ledger : entry.getValue()) {
                Double current = currentMap.get(ledger.getAttrId());
                if (current != null && current > currentThreshold) {
                    hasFault = true;
                    break;
                }
            }
            if (hasFault) {
                faultGroups++;
            }
        }

        return new EquipmentStats(
                totalGroups,
                faultGroups,
                totalGroups - faultGroups,
                totalRollers,
                faultRollers,
                totalRollers - faultRollers
        );
    }

    /**
     * 获取报警统计（无数据时返回空统计）
     */
    public AlarmStats getAlarmStats() {
        // 报警数据应从数据库查询，暂返回空统计
        return new AlarmStats(0, 0, 0, 0);
    }

    /**
     * 获取更换统计（无数据时返回空统计）
     */
    public ReplaceStats getReplaceStats() {
        // 更换数据应从数据库查询，暂返回空统计
        return new ReplaceStats(0, 0);
    }
}
