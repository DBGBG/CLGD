package com.rizhao.esp.utils;

import com.rizhao.esp.entity.MeterLedger;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * CSV 工具类 - 读取辊道台账数据
 *
 * <p>读取 meter_ledger.csv 文件，解析辊道台账信息。</p>
 *
 * <p>CSV 文件格式：</p>
 * <pre>
 * id,instance_name,attr_id,GDMC
 * 1,LcRt1,133,1ESP1
 * 2,LcRt2,134,1ESP1
 * ...
 * </pre>
 *
 * @author 日照钢铁
 * @version 1.0.0
 */
public class CsvUtils {

    /**
     * 读取 CSV 文件，返回辊道台账列表
     *
     * @param filePath CSV 文件路径（支持绝对路径或相对路径）
     * @return 辊道台账列表
     */
    public static List<MeterLedger> readCsv(String filePath) {
        List<MeterLedger> result = new ArrayList<>();

        // 尝试多个路径查找 CSV 文件
        File file = resolveCsvFile(filePath);

        if (file == null || !file.exists()) {
            System.err.println("[警告] CSV 文件不存在: " + filePath);
            System.err.println("[提示] 请确保 meter_ledger.csv 文件在项目根目录");
            return result;
        }

        System.out.println("[INFO] 正在读取 CSV 文件: " + file.getAbsolutePath());

        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {

            String line;
            boolean isFirstLine = true;
            int lineCount = 0;

            while ((line = br.readLine()) != null) {
                lineCount++;

                // 跳过标题行
                if (isFirstLine) {
                    isFirstLine = false;
                    continue;
                }

                // 跳过空行
                if (line.trim().isEmpty()) {
                    continue;
                }

                // 解析 CSV 行
                MeterLedger ledger = parseLine(line, lineCount);
                if (ledger != null) {
                    result.add(ledger);
                }
            }

            System.out.println("[INFO] CSV 读取完成，共 " + result.size() + " 条记录");

        } catch (IOException e) {
            System.err.println("[错误] 读取 CSV 文件失败: " + e.getMessage());
        }

        return result;
    }

    /**
     * 解析单行 CSV 数据
     */
    private static MeterLedger parseLine(String line, int lineNumber) {
        String[] parts = line.split(",");

        if (parts.length < 4) {
            System.err.println("[警告] 第 " + lineNumber + " 行数据不完整，跳过: " + line);
            return null;
        }

        try {
            int id = Integer.parseInt(parts[0].trim());
            String instanceName = parts[1].trim();
            int attrId = Integer.parseInt(parts[2].trim());
            String gdmc = parts[3].trim();

            return new MeterLedger(id, instanceName, attrId, gdmc);
        } catch (NumberFormatException e) {
            System.err.println("[错误] 第 " + lineNumber + " 行解析失败: " + line);
            return null;
        }
    }

    /**
     * 解析 CSV 文件中的多行文本值（处理包含逗号的字段）
     */
    private static String[] parseCsvLine(String line) {
        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inQuotes = false;

        for (char c : line.toCharArray()) {
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ',' && !inQuotes) {
                result.add(current.toString().trim());
                current = new StringBuilder();
            } else {
                current.append(c);
            }
        }
        result.add(current.toString().trim());

        return result.toArray(new String[0]);
    }

    /**
     * 按工段分组
     *
     * @param list 辊道台账列表
     * @return 按工段分组的 Map
     */
    public static Map<String, List<MeterLedger>> groupByGdmc(List<MeterLedger> list) {
        Map<String, List<MeterLedger>> map = new LinkedHashMap<>();
        for (MeterLedger ledger : list) {
            String gdmc = ledger.getGdmc();
            if (!map.containsKey(gdmc)) {
                map.put(gdmc, new ArrayList<>());
            }
            map.get(gdmc).add(ledger);
        }
        return map;
    }

    /**
     * 解析文件路径，尝试多个位置查找 CSV 文件
     */
    private static File resolveCsvFile(String filePath) {
        // 1. 直接使用给定路径
        File file = new File(filePath);
        if (file.exists()) {
            return file;
        }

        // 2. 从用户工作目录查找
        file = new File(System.getProperty("user.dir"), filePath);
        if (file.exists()) {
            return file;
        }

        // 3. 从项目根目录查找（向上多级到项目根目录）
        String projectRoot = System.getProperty("user.dir");
        File parentDir = new File(projectRoot).getParentFile();
        while (parentDir != null) {
            file = new File(parentDir, filePath);
            if (file.exists()) {
                return file;
            }
            // 尝试在父目录中查找 meter_ledger.csv
            if (filePath.equals("meter_ledger.csv")) {
                File alt = new File(parentDir, "meter_ledger.csv");
                if (alt.exists()) {
                    return alt;
                }
            }
            parentDir = parentDir.getParentFile();
        }

        // 4. 尝试从 classpath 查找
        ClassLoader classLoader = CsvUtils.class.getClassLoader();
        if (classLoader.getResource(filePath) != null) {
            return new File(classLoader.getResource(filePath).getFile());
        }

        return null;
    }
}
