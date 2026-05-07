"""Trace visualization tool - generates an interactive HTML page from trace JSON.

Produces a standalone HTML file with:
- Unified timeline chart (canvas) combining Gantt bars and resource usage lines
- Event log viewer
"""

import json
import os
import webbrowser
from typing import Any, Dict, Optional


# HTML template — uses a single canvas to draw both Gantt bars and resource
# lines on the same time axis for perfect alignment.
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

/* Unified timeline canvas */
.timeline-wrapper {{ overflow-x: auto; }}
#timelineCanvas {{ display: block; width: 100%; }}

/* Legend */
.legend {{ display: flex; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.8rem; color: #94a3b8; }}
.legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}

/* Event log */
.event-log {{ max-height: 500px; overflow-y: auto; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.78rem; }}
.event-item {{ padding: 4px 8px; border-bottom: 1px solid #1e293b; display: flex; gap: 8px; cursor: pointer; }}
.event-item:hover {{ background: #1e293b; }}
.event-time {{ color: #64748b; white-space: nowrap; }}
.event-type {{ color: #60a5fa; white-space: nowrap; width: 100px; }}
.event-node {{ color: #a78bfa; white-space: nowrap; }}
.event-agent {{ color: #34d399; white-space: nowrap; width: 120px; }}
.event-detail {{ color: #e2e8f0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

/* Modal */
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

<div class="section" id="timelineSection">
  <div class="section-title" onclick="toggleSection('timelineContent')">
    <h2>📊 Timeline - Agent Execution & Resource Usage</h2>
    <span class="section-toggle" id="timelineToggle">&#9660; collapse</span>
  </div>
  <div class="section-content" id="timelineContent">
    <div class="legend" id="legend"></div>
    <div class="timeline-wrapper"><canvas id="timelineCanvas"></canvas></div>
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
// Data from Python
var intervals = {intervals_json};
var agentIntervals = {agent_intervals_json};
var resourceUsage = {resource_usage_json};
var events = {events_json};

document.getElementById('eventCount').innerHTML = 'Events: <strong>' + events.length + '</strong>';
document.getElementById('resourceCount').innerHTML = 'Resource Snapshots: <strong>' + resourceUsage.length + '</strong>';

// Agent-level colors (base hue per agent type)
var agentBaseColors = {{
  'supervisor': '#8b5cf6',
  'researcher': '#3b82f6',
  'report': '#10b981',
  'system': '#64748b'
}};
var agentLabels = {{
  'supervisor': 'Supervisor',
  'researcher': 'Researcher',
  'report': 'Report Generation',
  'system': 'System'
}};

// Phase-specific color shades within each agent type.
var phaseShades = {{
  'supervisor': '#8b5cf6',
  'supervisor_tools': '#a78bfa',
  'researcher': '#3b82f6',
  'researcher_tools': '#60a5fa',
  'compress_research': '#93c5fd',
  'final_report_generation': '#10b981',
  'clarify_with_user': '#64748b',
  'write_research_brief': '#94a3b8',
  'research_supervisor': '#475569',
  // Tool-level event colors (for tool_call/tool_result intervals)
  'tavily_search': '#f59e0b',
  'tavily_api_search': '#f97316',
  'tavily_summarization': '#fb923c',
  'think_tool': '#a78bfa',
  'web_search': '#f59e0b',
  'arxiv_search': '#14b8a6',
}};


// Resource line colors
var resourceColors = {{
  cpu: '#60a5fa',
  mem: '#34d399',
  disk: '#f59e0b',
  net: '#f472b6',
  procCpu: '#fbbf24'
}};

function getBarColor(iv, groupKey) {{
  if (phaseShades[iv.node_name]) return phaseShades[iv.node_name];
  if (agentBaseColors[iv.agent_type]) return agentBaseColors[iv.agent_type];
  return '#64748b';
}}

function renderLegend() {{
  var container = document.getElementById('legend');
  var seen = {{}};
  var html = '';
  // Agent interval legend items
  intervals.forEach(function(iv) {{
    var color = getBarColor(iv);
    var label = iv.node_name.replace(/_/g, ' ');
    if (!seen[label]) {{
      seen[label] = true;
      html += '<div class="legend-item"><div class="legend-color" style="background:' + color + '"></div>' + label + '</div>';
    }}
  }});
  // Resource legend items
  html += '<div class="legend-item"><div class="legend-color" style="background:' + resourceColors.cpu + '"></div>CPU (system)</div>';
  html += '<div class="legend-item"><div class="legend-color" style="background:' + resourceColors.procCpu + '"></div>CPU (process)</div>';
  html += '<div class="legend-item"><div class="legend-color" style="background:' + resourceColors.mem + '"></div>Memory</div>';
  html += '<div class="legend-item"><div class="legend-color" style="background:' + resourceColors.disk + '"></div>Disk</div>';
  html += '<div class="legend-item"><div class="legend-color" style="background:' + resourceColors.net + '"></div>Network</div>';
  container.innerHTML = html;
}}

// Time range (shared by all drawing)
var chartMinTime = null;
var chartMaxTime = null;
var chartRefTime = null;

// Layout constants
var LABEL_W = 160;       // width for agent labels on the left
var ROW_H = 28;          // height per agent row
var RESOURCE_H = 80;     // height per resource chart
var RESOURCE_GAP = 32;   // gap between resource charts (avoid y-axis label overlap)
var X_TICK_H = 24;       // height for x-axis labels at bottom
var Y_PAD = 16;          // padding between sections

// Hit regions for Gantt bar clicks
var ganttHitRegions = [];

function drawTimeline() {{
  var canvas = document.getElementById('timelineCanvas');
  if (!canvas) return;

  // Compute time range from intervals
  if (intervals.length === 0) {{
    canvas.parentElement.innerHTML = '<p style="color:#64748b;text-align:center;padding:20px;">No interval data recorded yet.</p>';
    return;
  }}

  var minTime = Infinity, maxTime = -Infinity;
  intervals.forEach(function(iv) {{
    if (iv.start_time < minTime) minTime = iv.start_time;
    if (iv.end_time > maxTime) maxTime = iv.end_time;
  }});
  // Also consider resource timestamps
  resourceUsage.forEach(function(r) {{
    if (r.timestamp < minTime) minTime = r.timestamp;
    if (r.timestamp > maxTime) maxTime = r.timestamp;
  }});

  var timeRange = maxTime - minTime;
  if (timeRange === 0) timeRange = 1;
  var padding = timeRange * 0.05;
  minTime -= padding;
  maxTime += padding;
  var totalRange = maxTime - minTime;

  chartMinTime = minTime;
  chartMaxTime = maxTime;
  chartRefTime = intervals[0].start_time;

  // Group intervals by agent
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

  // Compute canvas dimensions
  var parent = canvas.parentElement;
  var availW = parent.clientWidth;
  if (availW <= 0) availW = 900;

  var nAgentRows = orderedKeys.length;
  var hasResources = resourceUsage.length > 0;
  var nResourceRows = hasResources ? 5 : 0;

  var chartW = availW - LABEL_W;
  if (chartW < 200) chartW = 200;

  var agentSectionH = nAgentRows * ROW_H;
  var resourceSectionH = nResourceRows * (RESOURCE_H + RESOURCE_GAP) - (hasResources ? RESOURCE_GAP : 0);
  var totalH = Y_PAD + agentSectionH + Y_PAD + resourceSectionH + X_TICK_H + Y_PAD;

  // Set canvas size
  canvas.setAttribute('width', availW);
  canvas.setAttribute('height', totalH);
  canvas.style.width = '';
  canvas.style.height = '';

  var ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, availW, totalH);

  // ---- Draw x-axis ticks (shared time axis at the bottom) ----
  var tickCount = Math.max(5, Math.min(20, Math.floor(timeRange * 2)));
  ctx.fillStyle = '#64748b';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';

  var xAxisY = Y_PAD + agentSectionH + Y_PAD + resourceSectionH;
  // Draw tick labels
  for (var i = 0; i <= tickCount; i++) {{
    var t = minTime + (i / tickCount) * totalRange;
    var x = LABEL_W + (i / tickCount) * chartW;
    ctx.fillText('+' + (t - chartRefTime).toFixed(1) + 's', x, xAxisY + 4);
    // Tick line
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, xAxisY);
    ctx.lineTo(x, xAxisY + 6);
    ctx.stroke();
  }}

  // ---- Draw agent Gantt rows ----
  ganttHitRegions = [];
  var agentY = Y_PAD;
  orderedKeys.forEach(function(key) {{
    var group = agentGroups[key];
    group.sort(function(a, b) {{ return a.start_time - b.start_time; }});

    // Agent label
    var displayName = key.startsWith('researcher_') ? key.replace('researcher_', 'R:') : (agentLabels[key] || key);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(displayName, LABEL_W - 8, agentY + ROW_H / 2);

    // Track background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(LABEL_W, agentY, chartW, ROW_H);

    // Draw Gantt bars
    group.forEach(function(iv) {{
      var leftPx = ((iv.start_time - minTime) / totalRange) * chartW;
      var widthPx = Math.max(2, ((iv.duration) / totalRange) * chartW);
      var color = getBarColor(iv, key);
      ctx.fillStyle = color;
      var barY = agentY + 2;
      var barH = ROW_H - 4;
      // Draw rounded rect manually (compatible with all browsers)
      var rx = LABEL_W + leftPx, ry = barY, rw = widthPx, rh = barH, rr = 4;
      ctx.beginPath();
      ctx.moveTo(rx + rr, ry);
      ctx.lineTo(rx + rw - rr, ry);
      ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + rr);
      ctx.lineTo(rx + rw, ry + rh - rr);
      ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - rr, ry + rh);
      ctx.lineTo(rx + rr, ry + rh);
      ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - rr);
      ctx.lineTo(rx, ry + rr);
      ctx.quadraticCurveTo(rx, ry, rx + rr, ry);
      ctx.closePath();
      ctx.fill();

      // Record hit region for click detection
      ganttHitRegions.push({{
        x: LABEL_W + leftPx,
        y: barY,
        w: widthPx,
        h: barH,
        data: iv
      }});

      // Bar label if wide enough
      if (widthPx > 40) {{
        ctx.fillStyle = '#ffffff';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(iv.node_name.replace(/_/g, ' '), LABEL_W + leftPx + 4, barY + barH / 2);
      }}
    }});

    agentY += ROW_H;
  }});

  // ---- Draw resource charts ----
  if (hasResources) {{
    var resourceY = Y_PAD + agentSectionH + Y_PAD;
    var timestamps = resourceUsage.map(function(r) {{ return r.timestamp; }});

    var resources = [
      {{ label: 'CPU (%)', key: 'cpu', field: function(r) {{ return (r.cpu && r.cpu.percent != null) ? r.cpu.percent : 0; }}, color: resourceColors.cpu }},
      {{ label: 'Proc CPU (%)', key: 'procCpu', field: function(r) {{ return (r.cpu && r.cpu.process_percent != null) ? r.cpu.process_percent : 0; }}, color: resourceColors.procCpu }},
      {{ label: 'Memory (GB)', key: 'mem', field: function(r) {{ return (r.memory && r.memory.used_gb != null) ? r.memory.used_gb : 0; }}, color: resourceColors.mem }},
      {{ label: 'Disk (%)', key: 'disk', field: function(r) {{ return (r.disk && r.disk.percent != null) ? r.disk.percent : 0; }}, color: resourceColors.disk }},
      {{ label: 'Network (Mbps)', key: 'net', field: function(r) {{ return (r.network && r.network.recv_mbps != null) ? r.network.recv_mbps : 0; }}, color: resourceColors.net }}
    ];

    resources.forEach(function(res) {{
      var dataPoints = resourceUsage.map(res.field);
      var maxVal = 0;
      dataPoints.forEach(function(v) {{ if (v > maxVal) maxVal = v; }});
      if (maxVal <= 0) maxVal = 1;

      var chartTop = resourceY;
      var chartH = RESOURCE_H;

      // Add gap before this chart (except first)
      if (resourceY > Y_PAD + agentSectionH + Y_PAD) {{
        chartTop += RESOURCE_GAP;
      }}

      // Background
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(LABEL_W, chartTop, chartW, chartH);

      // Y-axis label
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      // Y-axis grid lines and labels
      for (var gi = 0; gi <= 3; gi++) {{
        var y = chartTop + (gi / 3) * chartH;
        var val = maxVal * (1 - gi / 3);
        ctx.fillText(val.toFixed(val < 10 ? 1 : 0), LABEL_W - 6, y);
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(LABEL_W, y);
        ctx.lineTo(LABEL_W + chartW, y);
        ctx.stroke();
      }}

      // Resource label on the left
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'top';
      ctx.fillText(res.label, LABEL_W - 8, chartTop + 2);

      // Fill area under line
      if (dataPoints.length > 1) {{
        ctx.beginPath();
        for (var di = 0; di < dataPoints.length; di++) {{
          var x = LABEL_W + ((timestamps[di] - minTime) / totalRange) * chartW;
          var y = chartTop + chartH - (dataPoints[di] / maxVal) * chartH;
          if (di === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }}
        ctx.lineTo(LABEL_W + chartW, chartTop + chartH);
        ctx.lineTo(LABEL_W, chartTop + chartH);
        ctx.closePath();
        ctx.fillStyle = res.color + '25';
        ctx.fill();
      }}

      // Draw line
      ctx.beginPath();
      ctx.strokeStyle = res.color;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      for (var di = 0; di < dataPoints.length; di++) {{
        var x = LABEL_W + ((timestamps[di] - minTime) / totalRange) * chartW;
        var y = chartTop + chartH - (dataPoints[di] / maxVal) * chartH;
        if (di === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }}
      ctx.stroke();

      resourceY += chartH;
    }});
  }}

  // ---- Draw vertical grid lines (aligned with x-axis ticks) ----
  for (var i = 0; i <= tickCount; i++) {{
    var x = LABEL_W + (i / tickCount) * chartW;
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, Y_PAD);
    ctx.lineTo(x, Y_PAD + agentSectionH + Y_PAD + resourceSectionH);
    ctx.stroke();
  }}

  renderLegend();
}}

function renderEventLog() {{
  var container = document.getElementById('eventLog');
  if (events.length === 0) {{
    container.innerHTML = '<p style="color:#64748b;text-align:center;padding:20px;">No events recorded.</p>';
    return;
  }}

  var html = '';
  events.forEach(function(ev) {{
    var dt = new Date(ev.timestamp * 1000).toISOString().substr(11, 12);
    var typeIcon = ev.event_type === 'node_start' ? '&#9654;' : (ev.event_type === 'node_end' ? '&#9632;' : (ev.event_type === 'tool_call' ? '&#128295;' : (ev.event_type === 'tool_result' ? '&#9989;' : '&#9679;')));

    var detailStr = JSON.stringify(ev.details);
    if (detailStr.length > 80) detailStr = detailStr.substring(0, 80) + '...';
    var escaped = encodeURIComponent(JSON.stringify(ev));
    html += '<div class="event-item" data-detail="' + escaped + '">';
    html += '<span class="event-time">' + dt + '</span>';
    html += '<span class="event-type">' + typeIcon + ' ' + ev.event_type + '</span>';
    html += '<span class="event-node">' + ev.node_name + '</span>';
    html += '<span class="event-agent">' + (ev.researcher_id || ev.agent_type || '') + '</span>';
    html += '<span class="event-detail">' + detailStr + '</span>';
    html += '</div>';
  }});
  container.innerHTML = html;
}}

function showDetail(type, el) {{
  try {{
    var detail;
    if (type === 'interval' && el.data) {{
      // Called from canvas hit region
      detail = el.data;
    }} else {{
      // Called from DOM element
      var raw = el.getAttribute('data-detail');
      detail = JSON.parse(decodeURIComponent(raw));
    }}
    document.getElementById('modalTitle').textContent = type === 'interval' ? 'Execution Interval' : 'Event Detail';
    document.getElementById('modalBody').textContent = JSON.stringify(detail, null, 2);
    document.getElementById('detailModal').style.display = 'flex';
  }} catch(e) {{
    console.error('Error showing detail:', e);
  }}
}}

function closeModal() {{
  document.getElementById('detailModal').style.display = 'none';
}}

document.getElementById('detailModal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});

function toggleSection(id) {{
  var content = document.getElementById(id);
  var toggleId = id.replace('Content', 'Toggle');
  var toggle = document.getElementById(toggleId);
  if (content.style.display === 'none') {{
    content.style.display = 'block';
    toggle.innerHTML = '&#9660; collapse';
    if (id === 'timelineContent') {{
      setTimeout(drawTimeline, 50);
    }}
  }} else {{
    content.style.display = 'none';
    toggle.innerHTML = '&#9654; expand';
  }}
}}

var resizeTimer;
window.addEventListener('resize', function() {{
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(drawTimeline, 300);
}});

// Canvas click handler for Gantt bar clicks
document.getElementById('timelineCanvas').addEventListener('click', function(e) {{
  var rect = this.getBoundingClientRect();
  var scaleX = this.width / rect.width;
  var mx = (e.clientX - rect.left) * scaleX;
  var my = (e.clientY - rect.top) * scaleX;
  // Check hit regions in reverse order (topmost drawn last)
  for (var i = ganttHitRegions.length - 1; i >= 0; i--) {{
    var r = ganttHitRegions[i];
    if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {{
      showDetail('interval', r);
      return;
    }}
  }}
}});

// Event delegation for event log clicks
document.getElementById('eventLog').addEventListener('click', function(e) {{
  var item = e.target.closest('.event-item');
  if (item) {{
    showDetail('event', item);
  }}
}});

// Init
drawTimeline();
renderEventLog();
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
