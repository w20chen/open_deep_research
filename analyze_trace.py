"""
analyze_trace.py - 分析 trace JSON 文件中工具调用时间的占比

功能：
- 将所有 tavily API search 相关的时间加起来
- 将所有其他时间加起来（排除 supervisor_tools 父节点）
- 计算 CPU 工具调用时间的占比
"""

import json
import sys
from pathlib import Path


def analyze_trace(trace_path: str) -> dict:
    """
    解析 trace JSON 文件，计算 tavily 搜索时间和其他时间的占比。

    Args:
        trace_path: trace JSON 文件的路径

    Returns:
        包含分析结果的字典
    """
    with open(trace_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    intervals = data["intervals"]

    # 排除的父节点列表（这些节点的时间不纳入统计）
    excluded_nodes = {"supervisor_tools", "researcher_tools", "tavily_search"}

    # 1. 收集 tavily 子节点的时间（tavily_summarization + tavily_api_search）
    #    tavily_search 是父节点，不纳入统计
    tavily_child_nodes = {"tavily_summarization", "tavily_api_search"}
    tavily_intervals = [iv for iv in intervals if iv["node_name"] in tavily_child_nodes]
    tavily_total = sum(iv["duration"] for iv in tavily_intervals)

    # 2. 收集所有其他时间（排除 excluded_nodes 和 tavily 子节点）
    other_intervals = [
        iv
        for iv in intervals
        if iv["node_name"] not in tavily_child_nodes
        and iv["node_name"] not in excluded_nodes
    ]
    other_total = sum(iv["duration"] for iv in other_intervals)

    # 3. 计算占比（基于统计的时间之和，而非 trace 总运行时间）
    stats_total = tavily_total + other_total
    tavily_ratio = (tavily_total / stats_total * 100) if stats_total > 0 else 0.0
    other_ratio = (other_total / stats_total * 100) if stats_total > 0 else 0.0

    # 4. 按 node_name 分组统计（排除 excluded_nodes）
    from collections import defaultdict

    by_node = defaultdict(lambda: {"count": 0, "total_duration": 0.0})
    for iv in intervals:
        name = iv["node_name"]
        if name in excluded_nodes:
            continue
        by_node[name]["count"] += 1
        by_node[name]["total_duration"] += iv["duration"]

    return {
        "run_id": data.get("run_id", ""),
        "start_datetime": data.get("start_datetime", ""),
        "end_datetime": data.get("end_datetime", ""),
        "total_duration": data.get("total_duration", 0),
        "stats_total": round(stats_total, 4),
        "tavily": {
            "count": len(tavily_intervals),
            "total_duration": round(tavily_total, 4),
            "ratio": round(tavily_ratio, 2),
        },
        "other": {
            "count": len(other_intervals),
            "total_duration": round(other_total, 4),
            "ratio": round(other_ratio, 2),
        },
        "by_node": {
            name: {
                "count": info["count"],
                "total_duration": round(info["total_duration"], 4),
            }
            for name, info in sorted(by_node.items(), key=lambda x: x[1]["total_duration"], reverse=True)
        },
    }


def print_analysis(result: dict):
    """打印分析结果"""
    print("=" * 60)
    print("Trace 分析报告")
    print("=" * 60)
    print(f"Run ID:          {result['run_id']}")
    print(f"开始时间:        {result['start_datetime']}")
    print(f"结束时间:        {result['end_datetime']}")
    print(f"总耗时:          {result['total_duration']:.2f}s")
    print()

    print("-" * 60)
    print("Tavily API Search + Tavily Summarization 时间")
    print("-" * 60)
    print(f"  调用次数:       {result['tavily']['count']}")
    print(f"  总耗时:         {result['tavily']['total_duration']:.4f}s")
    print(f"  占比:           {result['tavily']['ratio']:.2f}%")
    print()

    print("-" * 60)
    print("其他时间（排除父节点 supervisor_tools、researcher_tools、tavily_search）")
    print("-" * 60)
    print(f"  节点数:         {result['other']['count']}")
    print(f"  总耗时:         {result['other']['total_duration']:.4f}s")
    print(f"  占比:           {result['other']['ratio']:.2f}%")
    print()

    print("-" * 60)
    print("各节点耗时明细（按总耗时降序，排除父节点 supervisor_tools、researcher_tools、tavily_search）")
    print("-" * 60)
    print(f"{'节点名称':<30s} {'调用次数':<10s} {'总耗时(s)':<15s} {'占比(%)':<10s}")
    print("-" * 65)
    for name, info in result["by_node"].items():
        pct = info["total_duration"] / result["stats_total"] * 100
        print(f"{name:<30s} {info['count']:<10d} {info['total_duration']:<15.4f} {pct:<10.2f}")
    print("-" * 65)
    # 额外统计：tavily_api_search 占所有时间之和的比例
    tavily_api_total = result["by_node"].get("tavily_api_search", {}).get("total_duration", 0)
    tavily_api_pct = tavily_api_total / result["stats_total"] * 100
    print(f"{'tavily_api_search 占总时间比例':<51s} {tavily_api_pct:<10.2f}")


def main():
    # 默认文件路径
    default_path = r"C:\Users\user\Desktop\open_deep_research\trace_20260507_145008_a4e47532.json"

    # 如果命令行提供了参数，使用参数中的路径
    if len(sys.argv) > 1:
        trace_path = sys.argv[1]
    else:
        trace_path = default_path

    if not Path(trace_path).exists():
        print(f"错误：文件不存在 - {trace_path}")
        sys.exit(1)

    result = analyze_trace(trace_path)
    print_analysis(result)


if __name__ == "__main__":
    main()
