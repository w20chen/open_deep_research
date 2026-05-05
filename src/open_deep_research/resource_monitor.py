"""System resource monitoring module.

Monitors CPU, RAM, Disk, and Network usage during agent execution.
Data is recorded into the TraceManager for visualization later.
"""

import asyncio
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from open_deep_research.trace import get_trace_manager


class ResourceMonitor:
    """Monitors system resource usage (CPU, RAM, Disk, Network).
    
    Runs a background thread that periodically samples resource metrics
    and records them into the active TraceManager.
    """

    def __init__(self, interval: float = 0.1):
        """
        Args:
            interval: Sampling interval in seconds (default: 1.0)
        """
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the resource monitoring background thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[ResourceMonitor] Started monitoring (interval={self.interval}s)")

    def stop(self) -> None:
        """Stop the resource monitoring background thread."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        print("[ResourceMonitor] Stopped monitoring")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        import psutil

        # Track network counters for delta calculation
        prev_net = psutil.net_io_counters()
        prev_time = time.time()

        # Per-process CPU measurement (this process only)
        current_process = psutil.Process()

        while not self._stop_event.is_set():
            try:
                # CPU — system-wide
                cpu_percent = psutil.cpu_percent(interval=None)
                cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
                # CPU — this Python process only
                proc_cpu = current_process.cpu_percent(interval=None)

                # RAM
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()

                # Disk — use the current working directory to reflect the
                # actual disk where research data is being written.
                disk = psutil.disk_usage(os.getcwd())

                # Network (delta based)
                curr_net = psutil.net_io_counters()
                curr_time = time.time()
                dt = curr_time - prev_time
                net_sent_mbps = (curr_net.bytes_sent - prev_net.bytes_sent) * 8 / (1024 * 1024 * dt) if dt > 0 else 0
                net_recv_mbps = (curr_net.bytes_recv - prev_net.bytes_recv) * 8 / (1024 * 1024 * dt) if dt > 0 else 0
                prev_net = curr_net
                prev_time = curr_time

                # Number of processes/threads
                process_count = len(psutil.pids())

                snapshot = {
                    "timestamp": time.time(),
                    "datetime": datetime.now().isoformat(),
                    "cpu": {
                        "percent": cpu_percent,
                        "per_core": cpu_per_core,
                        "count": psutil.cpu_count(),
                        "process_percent": proc_cpu,
                    },
                    "memory": {
                        "total_gb": mem.total / (1024**3),
                        "used_gb": mem.used / (1024**3),
                        "available_gb": mem.available / (1024**3),
                        "percent": mem.percent,
                        "swap_total_gb": swap.total / (1024**3),
                        "swap_used_gb": swap.used / (1024**3),
                        "swap_percent": swap.percent,
                    },
                    "disk": {
                        "total_gb": disk.total / (1024**3),
                        "used_gb": disk.used / (1024**3),
                        "free_gb": disk.free / (1024**3),
                        "percent": disk.percent,
                    },
                    "network": {
                        "sent_mbps": net_sent_mbps,
                        "recv_mbps": net_recv_mbps,
                        "total_bytes_sent": curr_net.bytes_sent,
                        "total_bytes_recv": curr_net.bytes_recv,
                    },
                    "processes": process_count,
                }

                # Record into active trace
                trace = get_trace_manager()
                trace.record_resource_snapshot(snapshot)

                # Sleep for the interval (using shorter sleeps for responsiveness)
                self._stop_event.wait(self.interval)

            except Exception as e:
                print(f"[ResourceMonitor] Error: {e}")
                self._stop_event.wait(self.interval)


# Global resource monitor instance
_resource_monitor: Optional[ResourceMonitor] = None


def start_resource_monitoring(interval: float = 0.1) -> ResourceMonitor:
    """Start the global resource monitor.
    
    Args:
        interval: Sampling interval in seconds
        
    Returns:
        The ResourceMonitor instance
    """
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor(interval)
    _resource_monitor.start()
    return _resource_monitor


def stop_resource_monitoring() -> None:
    """Stop the global resource monitor."""
    global _resource_monitor
    if _resource_monitor:
        _resource_monitor.stop()
