# Trace & Visualization 模块使用指南

## 概述

新增的三个模块为 agent 运行提供了完整的可观测性：

- **trace.py** — 录制每一步的起止时间、agent 类型、详细内容
- **resource_monitor.py** — 监控 CPU / RAM / Disk / Network 资源
- **trace_visualizer.py** — 生成交互式 HTML 可视化页面

## 快速使用

### 方式一：包装 graph（推荐，只需一行）

```python
from open_deep_research.deep_researcher import deep_researcher, wrap_graph_with_tracing

# 包装 graph — 之后每次 ainvoke 都会自动录制 trace
deep_researcher = wrap_graph_with_tracing(deep_researcher)

# 正常调用即可，结束后自动生成 JSON + HTML
result = await deep_researcher.ainvoke(input_data, config)
```

输出示例：

```
[ResourceMonitor] Started monitoring (interval=1.0s)
[Trace] Saved trace to: traces/trace_20260427_193535_58c3f3e6.json
[Trace] Visualization saved to: traces/trace_20260427_193535_58c3f3e6.html
```

### 方式二：run_with_tracing 函数

```python
from open_deep_research.deep_researcher import deep_researcher, run_with_tracing

result = await run_with_tracing(deep_researcher, input_data, config)
```

### 方式三：单独可视化已有的 trace 文件

```python
from open_deep_research.trace_visualizer import generate_html, open_visualization

# 生成 HTML
html_path = generate_html("traces/trace_xxx.json")

# 生成并在浏览器中打开
open_visualization("traces/trace_xxx.json")
```

## 可视化页面功能

生成的 HTML 是**纯前端、无外部依赖**的交互式页面，包含三个部分：

### 📊 甘特图 — Agent 执行时间线

- 每一行代表一个 agent（supervisor、各 researcher、report generation）
- **颜色区分**：紫色 = supervisor，蓝色 = researcher，绿色 = report，灰色 = system
- 鼠标悬停显示节点名、起止时间、耗时
- 点击任意条块可查看完整 JSON 详情
- 图例标注了所有参与的子 agent

### 💻 系统资源使用

- 四个实时的 Canvas 折线图：CPU(%)、内存(GB)、磁盘(%)、网络(Mbps)
- 首次打开或展开时自动渲染

### 📋 事件日志

- 按时间顺序列出所有 node_start / node_end / tool_call 事件
- 点击任意事件可查看完整 JSON 详情

## 输出文件

| 文件 | 位置 | 说明 |
|------|------|------|
| `trace_xxx.json` | `traces/` | 完整 trace 数据，包含 intervals、events、resource_usage |
| `trace_xxx.html` | `traces/` | 交互式可视化页面，可直接在浏览器打开 |

## sub-agent 区分机制

每个 researcher 子图调用时都会被分配唯一的 `researcher_id` (格式 `researcher_3e4dd688`)，该 ID 自动注入到 config 中。TraceManager 通过这个 ID 区分不同 researcher 的执行区间，甘特图中会单独成行显示。
