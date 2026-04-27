"""Trace visualization tool - generates an interactive HTML page from trace JSON.

Produces a standalone HTML file with:
- Interactive Gantt chart showing agent execution timeline (distinguishing sub-agents)
- Resource usage charts (CPU, RAM, Disk, Network)
- Event log viewer
"""

import json
import os
import webbrowser
from typing import Any, Dict, Optional


# HTML template loaded from an external constant to avoid f-string escaping issues
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deep Research Trace - {run_id}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
h2 {{ font-size: 1.2rem; margin-bottom: 12px; color: #94a3b8; }}
.header {{ margin-bottom: 24px; padding: 16px; background: #1e293b; border-radius: 12px; }}
.header .stats {{ display: flex; gap: 24px; margin-top: 8px; flex-wrap: wrap; }}
.header .stat {{ font-size: 0.9rem; color: #94a3b8; }}
.header .stat strong {{ color: #e2e8f0; }}
.section {{ margin-bottom: 24px; padding: 16px; background: #1e293b; border-radius: 12px; }}
.section-title {{ display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }}
.section-title:hover {{ opacity: 0.8; }}
.section-content {{ margin-top: 16px; }}
.section-toggle {{ font-size: 0.8rem; color: #64748b; }}
.gantt-container {{ overflow-x: auto; position: relative; }}
.gantt-timeline {{ position: relative; height: 40px; border-bottom: 1px solid #334155; margin-bottom: 4px; }}
.gantt-row {{ display: flex; align-items: center; min-height: 36px; margin-bottom: 2px; position: relative; }}
.gantt-label {{ width: 180px; min-width: 180px; font-size: 0.8rem; color: #94a3b8; padding-right: 8px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.gantt-track {{ flex: 1; position: relative; height: 28px; background: #0f172a; border-radius: 4px; }}
.gantt-bar {{ position: absolute; height: 24px; top: 2px; border-radius: 4px; cursor: pointer; transition: opacity 0.2s; display: flex; align-items: center; padding: 0 6px; font-size: 0.7rem; color: white; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; min-width: 4px; }}
.gantt-bar:hover {{ opacity: 0.85; transform: scaleY(1.1); z-index: 10; }}
.gantt-bar .tooltip {{ display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #1e293b; border: 1px solid #475569; padding: 8px 12px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
.gantt-bar:hover .tooltip {{ display: block; }}
.agent-legend {{ display: flex; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }}
.agent-legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.8rem; color: #94a3b8; }}
.agent-legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
.resource-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
@media (max-width: 900px) {{ .resource-grid {{ grid-template-columns: 1fr; }} }}
.chart-container {{ position: relative; height: 200px; }}
canvas {{ width: 100% !important; height: 100% !important; }}
.event-log {{ max-height: 500px; overflow-y: auto; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.78rem; }}
.event-item {{ padding: 4px 8px; border-bottom: 1px solid #1e293b; display: flex; gap: 8px; cursor: pointer; }}
.event-item:hover {{ background: #1e293b; }}
.event-time {{ color: #64748b; white-space: nowrap; }}
.event-type {{ color: #60a5fa; white-space: nowrap; width: 100px; }}
.event-node {{ color: #a78bfa; white-space: nowrap; }}
.event-agent {{ color: #34d399; white-space: nowrap; width: 120px; }}
.event-detail {{ color: #e2e8f0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.modal {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 1000; justify-content: center; align-items: center; }}
.modal-content {{ background: #1e293b; border: 1px solid #475569; border-radius: 12px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 24px; }}
.modal-content h3 {{ margin-bottom: 12px; }}
.modal-content pre {{ background: #0f172a; padding: 12px; border-radius: 6px; font-size: 0.78rem; overflow-x: auto; max-height: 400px; }}
.modal-close {{ float: right; cursor: pointer; font-size: 1.2rem; color: #64748b; }}
.modal-close:hover {{ color: #e2e8f0; }}
</style>
</head>
<body>

<div class="header">
  <h1>🔍 Deep Research Trace</h1>
  <div class="stats">
    <div class="stat">Run ID: <strong>{run_id}</strong></div>
    <div class="stat">Start: <strong>{start_dt}</strong></div>
    <div class="stat">Duration: <strong>{total_duration:.1f}s</strong></div>
    <div class="stat" id="eventCount">Events: <strong>0</strong></div>
    <div class="stat" id="resourceCount">Resource Snapshots: <strong>0</strong></div>
  </div>
</div>

<div class="section" id="ganttSection">
  <div class="section-title" onclick="toggleSection('ganttContent')">
    <h2>📊 Gantt Chart - Agent Execution Timeline</h2>
    <span class="section-toggle" id="ganttToggle">&#9660; collapse</span>
  </div>
  <div class="section-content" id="ganttContent">
    <div class="agent-legend" id="legend"></div>
    <div class="gantt-container" id="ganttContainer"></div>
  </div>
</div>

<div class="section" id="resourceSection">
  <div class="section-title" onclick="toggleSection('resourceContent')">
    <h2>💻 System Resource Usage</h2>
    <span class="section-toggle" id="resourceToggle">&#9660; collapse</span>
  </div>
  <div class="section-content" id="resourceContent">
    <div class="resource-grid">
      <div>
        <h3 style="font-size:0.9rem;color:#94a3b8;margin-bottom:4px;">CPU Usage (%)</h3>
        <div class="chart-container"><canvas id="cpuChart"></canvas></div>
      </div>
      <div>
        <h3 style="font-size:0.9rem;color:#94a3b8;margin-bottom:4px;">Memory Usage (GB)</h3>
        <div class="chart-container"><canvas id="memChart"></canvas></div>
      </div>
      <div>
        <h3 style="font-size:0.9rem;color:#94a3b8;margin-bottom:4px;">Disk Usage (%)</h3>
        <div class="chart-container"><canvas id="diskChart"></canvas></div>
      </div>
      <div>
        <h3 style="font-size:0.9rem;color:#94a3b8;margin-bottom:4px;">Network (Mbps)</h3>
        <div class="chart-container"><canvas id="netChart"></canvas></div>
      </div>
    </div>
  </div>
</div>

<div class="section" id="eventSection">
  <div class="section-title" onclick="toggleSection('eventContent')">
    <h2>📋 Event Log</h2>
    <span class="section-toggle" id="eventToggle">&#9660; collapse</span>
  </div>
  <div class="section-content" id="eventContent">
    <div class="event-log" id="eventLog"></div>
  </div>
</div>

<div class="modal" id="detailModal">
  <div class="modal-content">
    <span class="modal-close" onclick="closeModal()">&times;</span>
    <h3 id="modalTitle">Details</h3>
    <pre id="modalBody"></pre>
  </div>
</div>

<script>
const traceData = {trace_data_json};
const intervals = {intervals_json};
const agentIntervals = {agent_intervals_json};
const resourceUsage = {resource_usage_json};
const events = {events_json};

document.getElementById('eventCount').innerHTML = 'Events: <strong>' + events.length + '</strong>';
document.getElementById('resourceCount').innerHTML = 'Resource Snapshots: <strong>' + resourceUsage.length + '</strong>';

// Agent type colors
const agentColors = {{
  'supervisor': '#8b5cf6',
  'researcher': '#3b82f6',
  'report': '#10b981',
  'system': '#64748b'
}};
const agentLabels = {{
  'supervisor': 'Supervisor',
  'researcher': 'Researcher',
  'report': 'Report Generation',
  'system': 'System'
}};

function renderLegend() {{
  const container = document.getElementById('legend');
  const agentTypeSet = new Set();
  intervals.forEach(function(iv) {{
    agentTypeSet.add(iv.agent_type || 'system');
  }});
  var html = '';
  agentTypeSet.forEach(function(t) {{
    var label = agentLabels[t] || t;
    var color = agentColors[t] || agentColors['system'];
    html += '<div class="agent-legend-item"><div class="agent-legend-color" style="background:' + color + '"></div>' + label + '</div>';
  }});
  Object.keys(agentIntervals).forEach(function(k) {{
    if (k.startsWith('researcher_')) {{
      html += '<div class="agent-legend-item"><div class="agent-legend-color" style="background:#3b82f6"></div>' + k + '</div>';
    }}
  }});
  container.innerHTML = html;
}}

function renderGantt() {{
  const container = document.getElementById('ganttContainer');
  if (intervals.length === 0) {{
    container.innerHTML = '<p style="color:#64748b;text-align:center;padding:20px;">No interval data recorded yet.</p>';
    return;
  }}

  var minTime = Infinity, maxTime = -Infinity;
  intervals.forEach(function(iv) {{
    if (iv.start_time < minTime) minTime = iv.start_time;
    if (iv.end_time > maxTime) maxTime = iv.end_time;
  }});
  var timeRange = maxTime - minTime;
  if (timeRange === 0) return;

  var padding = timeRange * 0.05;
  minTime -= padding;
  maxTime += padding;
  var totalRange = maxTime - minTime;

  var agentGroups = {{}};
  intervals.forEach(function(iv) {{
    var key = iv.researcher_id || iv.agent_type || 'system';
    if (!agentGroups[key]) agentGroups[key] = [];
    agentGroups[key].push(iv);
  }});

  var orderPriority = {{'supervisor': 0, 'report': 999}};
  var orderedKeys = Object.keys(agentGroups).sort(function(a, b) {{
    var pa = (orderPriority[a] !== undefined) ? orderPriority[a] : (a.startsWith('researcher_') ? 100 : 500);
    var pb = (orderPriority[b] !== undefined) ? orderPriority[b] : (b.startsWith('researcher_') ? 100 : 500);
    return pa - pb;
  }});

  var tickCount = Math.min(10, Math.max(3, Math.floor(timeRange)));
  var headerHtml = '<div class="gantt-timeline" style="margin-left:180px;position:relative;">';
  for (var i = 0; i <= tickCount; i++) {{
    var pct = (i / tickCount) * 100;
    var t = minTime + (i / tickCount) * totalRange;
    headerHtml += '<div style="position:absolute;left:' + pct + '%;top:20px;font-size:0.7rem;color:#64748b;transform:translateX(-50%);">' + (t - intervals[0].start_time).toFixed(1) + 's</div>';
    headerHtml += '<div style="position:absolute;left:' + pct + '%;top:0;width:1px;height:30px;background:#334155;"></div>';
  }}
  headerHtml += '</div>';

  var rows = '';
  orderedKeys.forEach(function(key) {{
    var group = agentGroups[key];
    group.sort(function(a, b) {{ return a.start_time - b.start_time; }});

    var displayName = key.startsWith('researcher_') ? key.replace('researcher_', 'R:') : (agentLabels[key] || key);
    rows += '<div class="gantt-row"><div class="gantt-label" title="' + key + '">' + displayName + '</div><div class="gantt-track">';

    group.forEach(function(iv) {{
      var leftPct = ((iv.start_time - minTime) / totalRange) * 100;
      var widthPct = Math.max(0.3, ((iv.duration) / totalRange) * 100);
      if (widthPct < 0.3) return;

      var startRel = (iv.start_time - intervals[0].start_time).toFixed(1);
      var endRel = (iv.end_time - intervals[0].start_time).toFixed(1);

      var color = agentColors[iv.agent_type] || (key.startsWith('researcher_') ? '#3b82f6' : '#64748b');

      rows += '<div class="gantt-bar" style="left:' + leftPct + '%;width:' + widthPct + '%;background:' + color + ';" onclick="showDetail(\'interval\', this)" data-detail=\'' + JSON.stringify(iv).replace(/'/g, '&#39;') + '\'>';
      if (widthPct > 8) {{
        rows += iv.node_name.replace(/_/g, ' ');
      }}
      rows += '<span class="tooltip">';
      rows += '<strong>' + iv.node_name + '</strong><br>';
      rows += 'Start: +' + startRel + 's<br>';
      rows += 'End: +' + endRel + 's<br>';
      rows += 'Duration: ' + iv.duration.toFixed(1) + 's';
      rows += '</span>';
      rows += '</div>';
    }});

    rows += '</div></div>';
  }});

  container.innerHTML = headerHtml + rows;
  renderLegend();
}}

function drawChart(canvasId, dataPoints, color, unit) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = rect.height * 2;
  ctx.scale(2, 2);
  const w = rect.width, h = rect.height;

  var padding = {{top: 20, right: 10, bottom: 30, left: 50}};
  var chartW = w - padding.left - padding.right;
  var chartH = h - padding.top - padding.bottom;
  if (chartW <= 0 || chartH <= 0) return;

  var maxVal = 0;
  dataPoints.forEach(function(v) {{ if (v > maxVal) maxVal = v; }});
  if (maxVal === 0) maxVal = 1;

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#475569';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'right';
  for (var i = 0; i <= 4; i++) {{
    var y = padding.top + (i / 4) * chartH;
    ctx.fillText((maxVal * (1 - i / 4)).toFixed(1) + ' ' + unit, padding.left - 5, y + 3);
    ctx.fillStyle = '#334155';
    ctx.fillRect(padding.left, y, chartW, 1);
    ctx.fillStyle = '#475569';
  }}

  if (dataPoints.length > 1) {{
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    for (var i = 0; i < dataPoints.length; i++) {{
      var x = padding.left + (i / (dataPoints.length - 1)) * chartW;
      var y = padding.top + chartH - (dataPoints[i] / maxVal) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }}
    ctx.stroke();

    ctx.beginPath();
    for (var i = 0; i < dataPoints.length; i++) {{
      var x = padding.left + (i / (dataPoints.length - 1)) * chartW;
      var y = padding.top + chartH - (dataPoints[i] / maxVal) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }}
    ctx.lineTo(padding.left + chartW, padding.top + chartH);
    ctx.lineTo(padding.left, padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = color + '30';
    ctx.fill();
  }}

  for (var i = 0; i < dataPoints.length; i++) {{
    var x = padding.left + (i / Math.max(1, dataPoints.length - 1)) * chartW;
    var y = padding.top + chartH - (dataPoints[i] / maxVal) * chartH;
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }}

  ctx.fillStyle = '#94a3b8';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Time (s)', w / 2, h - 5);
}}

function renderResourceCharts() {{
  if (resourceUsage.length < 2) {{
    var containers = document.querySelectorAll('.chart-container');
    containers.forEach(function(el) {{
      el.innerHTML = '<p style="color:#64748b;text-align:center;padding:40px;">Not enough data points (need 2+, got ' + resourceUsage.length + ')</p>';
    }});
    return;
  }}

  var cpuData = resourceUsage.map(function(r) {{ return r.cpu.percent; }});
  drawChart('cpuChart', cpuData, '#60a5fa', '%');

  var memData = resourceUsage.map(function(r) {{ return r.memory.used_gb; }});
  drawChart('memChart', memData, '#34d399', 'GB');

  var diskData = resourceUsage.map(function(r) {{ return r.disk.percent; }});
  drawChart('diskChart', diskData, '#f59e0b', '%');

  var netData = resourceUsage.map(function(r) {{ return r.network.recv_mbps; }});
  drawChart('netChart', netData, '#f472b6', 'Mbps');
}}

function renderEventLog() {{
  const container = document.getElementById('eventLog');
  if (events.length === 0) {{
    container.innerHTML = '<p style="color:#64748b;text-align:center;padding:20px;">No events recorded.</p>';
    return;
  }}

  var html = '';
  events.forEach(function(ev) {{
    var dt = new Date(ev.timestamp * 1000).toISOString().substr(11, 12);
    var typeIcon = ev.event_type === 'node_start' ? '&#9654;' : (ev.event_type === 'node_end' ? '&#9632;' : (ev.event_type === 'tool_call' ? '&#128295;' : '&#9679;'));
    var detailStr = JSON.stringify(ev.details);
    if (detailStr.length > 80) detailStr = detailStr.substring(0, 80) + '...';
    html += '<div class="event-item" onclick="showDetail(\'event\', this)" data-detail=\'' + JSON.stringify(ev).replace(/'/g, '&#39;') + '\'>';
    html += '<span class="event-time">' + dt + '</span>';
    html += '<span class="event-type">' + typeIcon + ' ' + ev.event_type + '</span>';
    html += '<span class="event-node">' + ev.node_name + '</span>';
    html += '<span class="event-agent">' + (ev.researcher_id || ev.agent_type) + '</span>';
    html += '<span class="event-detail">' + detailStr + '</span>';
    html += '</div>';
  }});
  container.innerHTML = html;
}}

function showDetail(type, el) {{
  var detail = JSON.parse(el.getAttribute('data-detail'));
  document.getElementById('modalTitle').textContent = type === 'interval' ? 'Execution Interval' : 'Event Detail';
  document.getElementById('modalBody').textContent = JSON.stringify(detail, null, 2);
  document.getElementById('detailModal').style.display = 'flex';
}}

function closeModal() {{
  document.getElementById('detailModal').style.display = 'none';
}}

document.getElementById('detailModal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});

function toggleSection(id) {{
  var content = document.getElementById(id);
  var toggle = document.getElementById(id.replace('Content', 'Toggle'));
  if (content.style.display === 'none') {{
    content.style.display = 'block';
    toggle.innerHTML = '&#9660; collapse';
    if (id === 'resourceContent') setTimeout(renderResourceCharts, 100);
  }} else {{
    content.style.display = 'none';
    toggle.innerHTML = '&#9654; expand';
  }}
}}

var resizeTimer;
window.addEventListener('resize', function() {{
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(renderResourceCharts, 300);
}});

// Init
renderGantt();
renderEventLog();
setTimeout(renderResourceCharts, 200);
</script>
</body>
</html>"""


def generate_html(trace_filepath: str, output_filepath: Optional[str] = None) -> str:
    """Generate an interactive HTML visualization from a trace JSON file.

    Args:
        trace_filepath: Path to the trace JSON file
        output_filepath: Path for the output HTML file (auto-generated if None)

    Returns:
        Path to the generated HTML file
    """
    with open(trace_filepath, "r", encoding="utf-8") as f:
        trace_data = json.load(f)

    if output_filepath is None:
        trace_dir = os.path.dirname(trace_filepath)
        basename = os.path.splitext(os.path.basename(trace_filepath))[0]
        output_filepath = os.path.join(trace_dir, f"{basename}.html")

    run_id = trace_data.get("run_id", "unknown")
    start_dt = trace_data.get("start_datetime", "")
    total_duration = trace_data.get("total_duration", 0)
    intervals = trace_data.get("intervals", [])
    agent_intervals = trace_data.get("agent_intervals", {})
    resource_usage = trace_data.get("resource_usage", [])
    events = trace_data.get("events", [])

    html_content = HTML_TEMPLATE.format(
        run_id=run_id,
        start_dt=start_dt,
        total_duration=total_duration,
        trace_data_json=json.dumps(trace_data, indent=2),
        intervals_json=json.dumps(intervals),
        agent_intervals_json=json.dumps(agent_intervals),
        resource_usage_json=json.dumps(resource_usage),
        events_json=json.dumps(events),
    )

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[TraceVisualizer] HTML saved to: {output_filepath}")
    return output_filepath


def open_visualization(trace_filepath: str) -> str:
    """Open the visualization in a web browser.

    Args:
        trace_filepath: Path to the trace JSON file

    Returns:
        Path to the generated HTML file
    """
    html_path = generate_html(trace_filepath)
    webbrowser.open(f"file://{html_path}")
    return html_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        trace_path = sys.argv[1]
        if os.path.exists(trace_path):
            html_path = generate_html(trace_path)
            webbrowser.open(f"file://{html_path}")
            print(f"Visualization opened: {html_path}")
        else:
            print(f"Trace file not found: {trace_path}")
    else:
        print("Usage: python trace_visualizer.py <trace_file.json>")
