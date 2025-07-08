# -*- coding: utf-8 -*-
"""
排列五推荐结果验证与奖金计算器
=================================

本脚本旨在自动评估 `pl5_analyzer.py` 生成的推荐号码的实际表现。

工作流程:
1.  读取 `pl5.csv` 文件，获取所有历史开奖数据。
2.  确定最新的一期为"评估期"，倒数第二期为"报告数据截止期"。
3.  根据"报告数据截止期"，在当前目录下查找对应的分析报告文件
    (pl5_analysis_output_*.txt)。
4.  从找到的报告中解析出推荐的排列五号码。
5.  使用"评估期"的实际开奖号码，核对所有推荐投注的中奖情况。
6.  计算总奖金，并将详细的中奖结果追加记录到主报告文件 
    `latest_pl5_calculation.txt` 中。
"""

import os
import re
import glob
import csv
from datetime import datetime
import traceback
from typing import Optional, Tuple, List, Dict

# ==============================================================================
# --- 配置区 ---
# ==============================================================================

# 脚本需要查找的分析报告文件名的模式
REPORT_PATTERN = "pl5_analysis_output_*.txt"
# 开奖数据源CSV文件
CSV_FILE = "pl5.csv"
# 最终生成的主评估报告文件名
MAIN_REPORT_FILE = "latest_pl5_calculation.txt"

# 主报告文件中保留的最大记录数
MAX_NORMAL_RECORDS = 10  # 保留最近10次评估
MAX_ERROR_LOGS = 20      # 保留最近20条错误日志

# 排列五奖金对照表 (元)
PRIZE_VALUES = {
    "直选": 100000,    # 直选奖金：所选号码与中奖号码相同且顺序一致 (10万元)
}

# ==============================================================================
# --- 工具函数 ---
# ==============================================================================

def log_message(message: str, level: str = "INFO"):
    """一个简单的日志打印函数，用于在控制台显示脚本执行状态。"""
    print(f"[{level}] {datetime.now().strftime('%H:%M:%S')} - {message}")

def robust_file_read(file_path: str) -> Optional[str]:
    """
    一个健壮的文件读取函数，能自动尝试多种编码格式。

    Args:
        file_path (str): 待读取文件的路径。

    Returns:
        Optional[str]: 文件内容字符串，如果失败则返回 None。
    """
    if not os.path.exists(file_path):
        log_message(f"文件未找到: {file_path}", "ERROR")
        return None
    encodings = ['utf-8', 'gbk', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, IOError):
            continue
    log_message(f"无法使用任何支持的编码打开文件: {file_path}", "ERROR")
    return None

# ==============================================================================
# --- 数据解析与查找模块 ---
# ==============================================================================

def get_period_data_from_csv(csv_content: str) -> Tuple[Optional[Dict], Optional[List]]:
    """
    从CSV文件内容中解析出所有期号的开奖数据。

    Args:
        csv_content (str): 从CSV文件读取的字符串内容。

    Returns:
        Tuple[Optional[Dict], Optional[List]]:
            - 一个以期号为键，开奖数据为值的字典。
            - 一个按升序排序的期号列表。
            如果解析失败则返回 (None, None)。
    """
    if not csv_content:
        log_message("输入的CSV内容为空。", "WARNING")
        return None, None
    period_map, periods_list = {}, []
    try:
        reader = csv.reader(csv_content.splitlines())
        next(reader)  # 跳过表头
        for i, row in enumerate(reader):
            if len(row) >= 6 and re.match(r'^\d{4,7}$', row[0]):
                try:
                    period, pos_1, pos_2, pos_3, pos_4, pos_5 = row[0], int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5])
                    # 验证数字范围
                    if not all(0 <= num <= 9 for num in [pos_1, pos_2, pos_3, pos_4, pos_5]):
                        continue
                    period_map[period] = {'numbers': [pos_1, pos_2, pos_3, pos_4, pos_5]}
                    periods_list.append(period)
                except (ValueError, IndexError):
                    log_message(f"CSV文件第 {i+2} 行数据格式无效，已跳过: {row}", "WARNING")
    except Exception as e:
        log_message(f"解析CSV数据时发生严重错误: {e}", "ERROR")
        return None, None
    
    if not period_map:
        log_message("未能从CSV中解析到任何有效的开奖数据。", "WARNING")
        return None, None
        
    return period_map, sorted(periods_list, key=int)

def find_matching_report(target_period: str) -> Optional[str]:
    """
    在当前目录查找其数据截止期与 `target_period` 匹配的最新分析报告。

    Args:
        target_period (str): 目标报告的数据截止期号。

    Returns:
        Optional[str]: 找到的报告文件的路径，如果未找到则返回 None。
    """
    log_message(f"正在查找数据截止期为 {target_period} 的分析报告...")
    candidates = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for file_path in glob.glob(os.path.join(script_dir, REPORT_PATTERN)):
        content = robust_file_read(file_path)
        if not content: continue
        
        match = re.search(r'分析基于数据:\s*截至\s*(\d+)\s*期', content)
        if match and match.group(1) == target_period:
            try:
                timestamp_str_match = re.search(r'_(\d{8}_\d{6})\.txt$', file_path)
                if timestamp_str_match:
                    timestamp_str = timestamp_str_match.group(1)
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    candidates.append((timestamp, file_path))
            except (AttributeError, ValueError):
                continue
    
    if not candidates:
        log_message(f"未找到数据截止期为 {target_period} 的分析报告。", "WARNING")
        return None
        
    candidates.sort(reverse=True)
    latest_report = candidates[0][1]
    log_message(f"找到匹配的最新报告: {os.path.basename(latest_report)}", "INFO")
    return latest_report

def parse_recommendations_from_report(content: str) -> Dict:
    """
    从分析报告内容中解析出排列五推荐号码（单式和复式）。

    Args:
        content (str): 分析报告的文本内容。

    Returns:
        Dict: 包含单式推荐和复式推荐的字典
        {
            'single': List[List[int]],  # 单式推荐
            'duplex': Dict,             # 复式推荐
            'target_period': str        # 目标期号
        }
    """
    result = {
        'single': [],
        'duplex': {},
        'target_period': ''
    }
    
    # 解析目标期号
    target_match = re.search(r'本次预测目标:\s*第\s*(\d+)\s*期', content)
    if target_match:
        result['target_period'] = target_match.group(1)
    
    # 解析单式推荐号码
    rec_pattern = re.compile(r'注\s*\d+:\s*\[([0-9\s,]+)\]')
    for match in rec_pattern.finditer(content):
        try:
            numbers_str = match.group(1)
            numbers = [int(x.strip()) for x in re.findall(r'\d', numbers_str)]
            if len(numbers) == 5 and all(0 <= num <= 9 for num in numbers):
                result['single'].append(numbers)
        except ValueError:
            continue
    
    # 解析复式推荐号码
    duplex_patterns = {
        'pos1': re.compile(r'第一位推荐:\s*\[([0-9\s,]+)\]'),
        'pos2': re.compile(r'第二位推荐:\s*\[([0-9\s,]+)\]'),
        'pos3': re.compile(r'第三位推荐:\s*\[([0-9\s,]+)\]'),
        'pos4': re.compile(r'第四位推荐:\s*\[([0-9\s,]+)\]'),
        'pos5': re.compile(r'第五位推荐:\s*\[([0-9\s,]+)\]'),
    }
    
    for pos, pattern in duplex_patterns.items():
        match = pattern.search(content)
        if match:
            try:
                numbers_str = match.group(1)
                numbers = [int(x.strip()) for x in re.findall(r'\d', numbers_str)]
                numbers = [num for num in numbers if 0 <= num <= 9]
                if numbers:
                    result['duplex'][pos] = sorted(list(set(numbers)))
            except ValueError:
                continue
    
    return result

def calculate_prize(recommendations: List[List[int]], prize_numbers: List[int]) -> Tuple[int, Dict, List]:
    """
    计算推荐号码的中奖情况和奖金。

    Args:
        recommendations (List[List[int]]): 推荐的号码组合列表
        prize_numbers (List[int]): 实际开奖号码

    Returns:
        Tuple[int, Dict, List]: 总奖金、中奖统计、中奖详情
    """
    if not recommendations or not prize_numbers or len(prize_numbers) != 5:
        return 0, {}, []

    total_prize = 0
    prize_stats = {"直选": 0}
    winning_details = []

    for i, recommendation in enumerate(recommendations):
        if len(recommendation) != 5:
            continue

        # 检查直选中奖（五个位置完全匹配）
        if recommendation == prize_numbers:
            prize_amount = PRIZE_VALUES["直选"]
            total_prize += prize_amount
            prize_stats["直选"] += 1
            
            winning_details.append({
                'index': i + 1,
                'numbers': recommendation,
                'prize_type': '直选',
                'prize_amount': prize_amount
            })

    return total_prize, prize_stats, winning_details

def format_winning_details(winning_details: List[Dict], prize_numbers: List[int], duplex_data: Dict = None, target_period: str = "") -> List[str]:
    """
    格式化中奖详情为可读的文本列表。

    Args:
        winning_details (List[Dict]): 中奖详情列表
        prize_numbers (List[int]): 开奖号码
        duplex_data (Dict): 复式数据
        target_period (str): 目标期号

    Returns:
        List[str]: 格式化的详情文本列表
    """
    lines = []
    
    if target_period:
        lines.append(f"预测期号: 第{target_period}期")
    
    # 格式化开奖号码
    numbers_str = ''.join(map(str, prize_numbers))
    lines.append(f"开奖号码: {numbers_str}")
    
    if not winning_details:
        lines.append("遗憾：所有推荐号码均未中奖")
    else:
        lines.append(f"恭喜：共有 {len(winning_details)} 注中奖")
        for detail in winning_details:
            numbers_str = ''.join(map(str, detail['numbers']))
            lines.append(f"  第{detail['index']}注: {numbers_str} - {detail['prize_type']} - {detail['prize_amount']}元")
    
    # 如果有复式数据，显示复式参考
    if duplex_data:
        lines.append("\n复式推荐参考:")
        for pos, numbers in duplex_data.items():
            pos_name = {'pos1': '第一位', 'pos2': '第二位', 'pos3': '第三位', 'pos4': '第四位', 'pos5': '第五位'}.get(pos, pos)
            numbers_str = ','.join(map(str, numbers))
            lines.append(f"  {pos_name}: [{numbers_str}]")
    
    return lines

def manage_report(new_entry: Optional[Dict] = None, new_error: Optional[str] = None):
    """
    管理主报告文件，维护记录数量限制。

    Args:
        new_entry (Optional[Dict]): 新的评估记录
        new_error (Optional[str]): 新的错误信息
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(script_dir, MAIN_REPORT_FILE)
    
    # 读取现有内容
    existing_content = ""
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except Exception as e:
            log_message(f"读取现有报告失败: {e}", "WARNING")
    
    # 分离正常记录和错误日志
    sections = existing_content.split("\n" + "="*80 + "\n")
    normal_records = []
    error_logs = []
    
    for section in sections:
        if section.strip():
            if "ERROR" in section or "错误" in section:
                error_logs.append(section)
            elif "评估时间:" in section:
                normal_records.append(section)
    
    # 添加新记录
    if new_entry:
        entry_lines = [
            f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"评估期号: {new_entry.get('period', '未知')}",
            f"开奖号码: {''.join(map(str, new_entry.get('prize_numbers', [])))}",
            f"推荐数量: {new_entry.get('recommendation_count', 0)}注",
            f"中奖数量: {new_entry.get('winning_count', 0)}注",
            f"总奖金: {new_entry.get('total_prize', 0):,}元",
            ""
        ]
        
        if new_entry.get('winning_details'):
            entry_lines.append("中奖详情:")
            for detail in new_entry['winning_details']:
                numbers_str = ''.join(map(str, detail['numbers']))
                entry_lines.append(f"  第{detail['index']}注: {numbers_str} - {detail['prize_type']} - {detail['prize_amount']:,}元")
            entry_lines.append("")
        
        normal_records.insert(0, "\n".join(entry_lines))
    
    if new_error:
        error_entry = f"错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n错误信息: {new_error}\n"
        error_logs.insert(0, error_entry)
    
    # 限制记录数量
    normal_records = normal_records[:MAX_NORMAL_RECORDS]
    error_logs = error_logs[:MAX_ERROR_LOGS]
    
    # 重新组合内容
    new_content_parts = []
    
    if normal_records:
        new_content_parts.extend(normal_records)
    
    if error_logs:
        if new_content_parts:
            new_content_parts.append("")
        new_content_parts.append("错误日志:")
        new_content_parts.extend(error_logs)
    
    # 写入文件
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(("\n" + "="*80 + "\n").join(new_content_parts))
        log_message(f"报告已更新: {report_path}", "INFO")
    except Exception as e:
        log_message(f"写入报告失败: {e}", "ERROR")

def main_process():
    """
    主处理函数
    """
    try:
        # 读取CSV数据
        csv_content = robust_file_read(CSV_FILE)
        if not csv_content:
            raise Exception(f"无法读取CSV文件: {CSV_FILE}")
        
        # 解析期号数据
        period_map, periods_list = get_period_data_from_csv(csv_content)
        if not period_map or not periods_list:
            raise Exception("CSV数据解析失败")
        
        if len(periods_list) < 2:
            raise Exception("数据不足，至少需要2期数据")
        
        # 确定评估期和数据截止期
        eval_period = periods_list[-1]
        data_cutoff_period = periods_list[-2]
        
        log_message(f"评估期: {eval_period}, 数据截止期: {data_cutoff_period}")
        
        # 查找对应的分析报告
        report_path = find_matching_report(data_cutoff_period)
        if not report_path:
            raise Exception(f"未找到数据截止期为 {data_cutoff_period} 的分析报告")
        
        # 解析报告中的推荐号码
        report_content = robust_file_read(report_path)
        if not report_content:
            raise Exception(f"无法读取报告文件: {report_path}")
        
        recommendations_data = parse_recommendations_from_report(report_content)
        recommendations = recommendations_data['single']
        
        if not recommendations:
            raise Exception("报告中未找到有效的推荐号码")
        
        # 获取开奖号码
        prize_numbers = period_map[eval_period]['numbers']
        
        # 计算中奖情况
        total_prize, prize_stats, winning_details = calculate_prize(recommendations, prize_numbers)
        
        # 生成报告
        entry_data = {
            'period': eval_period,
            'prize_numbers': prize_numbers,
            'recommendation_count': len(recommendations),
            'winning_count': len(winning_details),
            'total_prize': total_prize,
            'winning_details': winning_details
        }
        
        manage_report(new_entry=entry_data)
        
        # 输出结果
        log_message(f"评估完成: 期号 {eval_period}", "INFO")
        log_message(f"开奖号码: {''.join(map(str, prize_numbers))}", "INFO")
        log_message(f"推荐数量: {len(recommendations)}注", "INFO")
        log_message(f"中奖数量: {len(winning_details)}注", "INFO")
        log_message(f"总奖金: {total_prize:,}元", "INFO")
        
        if winning_details:
            log_message("中奖详情:", "INFO")
            for detail in winning_details:
                numbers_str = ''.join(map(str, detail['numbers']))
                log_message(f"  第{detail['index']}注: {numbers_str} - {detail['prize_type']} - {detail['prize_amount']:,}元", "INFO")
    
    except Exception as e:
        error_msg = f"处理过程中发生错误: {str(e)}"
        log_message(error_msg, "ERROR")
        log_message("错误详情:", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        manage_report(new_error=error_msg)

if __name__ == "__main__":
    log_message("排列五推荐结果验证器启动", "INFO")
    main_process()
    log_message("验证完成", "INFO")