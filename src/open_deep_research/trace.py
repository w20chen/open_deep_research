"""Trace recording module for the Deep Research agent.

Records every step of the agent run with timing, details, and agent hierarchy.
Supports supervisor, researchers (with unique IDs), and report generation phases.
"""

import json
import os
import time
import uuid
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class TraceEvent:
    """A single trace event in the agent execution timeline."""

    def __init__(
        self,
        event_type: str,
        node_name: str,
        agent_type: str = "system",
        researcher_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.event_type = event_type  # node_start, node_end, tool_call, tool_result, llm_call
        self.node_name = node_name
        self.agent_type = agent_type  # supervisor, researcher, report_generation, system
        self.researcher_id = researcher_id
        self.timestamp = time.time()
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "node_name": self.node_name,
            "agent_type": self.agent_type,
            "researcher_id": self.researcher_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            f"TraceEvent({self.event_type}, {self.node_name}, "
            f"agent={self.agent_type}, rid={self.researcher_id})"
        )


class TraceManager:
    """Manages trace recording for a single agent run.
    
    This is a singleton per run. Use get_trace_manager() to access.
    """

    _instance_lock = threading.Lock()
    _instance: Optional["TraceManager"] = None

    def __init__(self):
        self.events: List[TraceEvent] = []
        self.start_time = time.time()
        self.run_id = str(uuid.uuid4())[:8]
        self.resource_data: List[Dict[str, Any]] = []

    @classmethod
    def reset(cls) -> "TraceManager":
        """Reset and create a new trace manager for a new run."""
        with cls._instance_lock:
            cls._instance = TraceManager()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "TraceManager":
        """Get the current trace manager instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = TraceManager()
            return cls._instance

    def record_event(
        self,
        event_type: str,
        node_name: str,
        agent_type: str = "system",
        researcher_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Record a trace event."""
        event = TraceEvent(event_type, node_name, agent_type, researcher_id, details)
        self.events.append(event)
        return event

    def record_resource_snapshot(self, data: Dict[str, Any]) -> None:
        """Record a resource usage snapshot."""
        self.resource_data.append(data)

    def compute_execution_intervals(self) -> List[Dict[str, Any]]:
        """Compute execution intervals from node_start/node_end and tool_call/tool_result events.
        
        Returns a list of intervals with: node_name, agent_type, researcher_id,
        start_time, end_time, duration, and all details.
        """
        # Gather all start events (both node_start and tool_call)
        start_events: Dict[str, TraceEvent] = {}
        intervals: List[Dict[str, Any]] = []

        for event in self.events:
            if event.event_type in ("node_start", "tool_call"):
                key = f"{event.event_type}_{event.node_name}_{event.researcher_id or ''}_{event.id}"
                start_events[key] = event
            elif event.event_type in ("node_end", "tool_result"):
                # Match to the corresponding start event
                # node_end matches node_start, tool_result matches tool_call
                expected_start_type = "node_start" if event.event_type == "node_end" else "tool_call"
                
                # For tool_call/tool_result pairs, try to match by call_id first
                # (to correctly handle parallel execution of identical tools)
                event_call_id = event.details.get("call_id") if event.details else None
                
                matched_key = None
                if event_call_id and expected_start_type == "tool_call":
                    # Try to match by call_id for parallel tool calls
                    for key in reversed(list(start_events.keys())):
                        se = start_events[key]
                        se_call_id = se.details.get("call_id") if se.details else None
                        if (se.event_type == expected_start_type and 
                            se.node_name == event.node_name and 
                            se.researcher_id == event.researcher_id and
                            se_call_id == event_call_id):
                            matched_key = key
                            break
                
                # Fallback: match by (node_name, researcher_id) for node events
                # or tool events without call_id
                if matched_key is None:
                    for key in reversed(list(start_events.keys())):
                        se = start_events[key]
                        if (se.event_type == expected_start_type and 
                            se.node_name == event.node_name and 
                            se.researcher_id == event.researcher_id):
                            matched_key = key
                            break
                
                if matched_key:
                    se = start_events.pop(matched_key)
                    interval = {
                        "node_name": event.node_name,
                        "agent_type": event.agent_type,
                        "researcher_id": event.researcher_id,
                        "start_time": se.timestamp,
                        "end_time": event.timestamp,
                        "duration": event.timestamp - se.timestamp,
                        "start_details": se.details,
                        "end_details": event.details,
                        "interval_type": se.event_type,  # "node_start" or "tool_call"
                    }
                    intervals.append(interval)

        return intervals


    def compute_agent_intervals(self) -> Dict[str, List[Dict[str, Any]]]:
        """Compute intervals grouped by agent (researcher_id or main agent type)."""
        intervals = self.compute_execution_intervals()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for interval in intervals:
            agent_key = interval.get("researcher_id") or interval["agent_type"]
            if agent_key not in grouped:
                grouped[agent_key] = []
            grouped[agent_key].append(interval)
        return grouped

    def to_run_summary(self) -> Dict[str, Any]:
        """Build a complete run summary with all trace information."""
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "start_datetime": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": time.time(),
            "end_datetime": datetime.fromtimestamp(time.time()).isoformat(),
            "total_duration": time.time() - self.start_time,
            "events": [e.to_dict() for e in self.events],
            "intervals": self.compute_execution_intervals(),
            "agent_intervals": self.compute_agent_intervals(),
            "resource_usage": self.resource_data,
        }

    def save_to_file(self) -> str:
        """Save the complete trace to a JSON file.
        
        Returns:
            The file path of the saved trace.
        """
        trace_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "traces"
        )
        os.makedirs(trace_dir, exist_ok=True)

        run_summary = self.to_run_summary()
        timestamp = datetime.fromtimestamp(self.start_time).strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{timestamp}_{self.run_id}.json"
        filepath = os.path.join(trace_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        print(f"\n[Trace] Trace saved to: {filepath}")
        return filepath


def get_trace_manager() -> TraceManager:
    """Get the current trace manager instance."""
    return TraceManager.get_instance()


def reset_trace() -> TraceManager:
    """Reset the trace manager for a new run."""
    return TraceManager.reset()
