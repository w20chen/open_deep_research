"""调试配置和工具"""

import os
from typing import Any, Dict, Optional
from functools import wraps
import datetime
import json

# Import tracing (lazy import to avoid circular dependencies)
_trace_manager = None

def _get_trace():
    """Lazy import of trace module to avoid circular dependencies."""
    global _trace_manager
    if _trace_manager is None:
        from open_deep_research.trace import get_trace_manager
        _trace_manager = get_trace_manager()
    return _trace_manager


class DebugConfig:
    """调试配置类，通过环境变量控制调试输出"""
    
    DEBUG_ENABLED = True
    DEBUG_NODE_START = True
    DEBUG_NODE_END = True
    DEBUG_STATE_TRANSITION = True
    DEBUG_LLM_CALLS = True
    DEBUG_TOOL_CALLS = True
    TRACE_ENABLED = True  # Whether to record trace events
    
    # 日志文件相关
    _log_file_path = None
    _log_file = None
    
    @classmethod
    def _init_log_file(cls):
        """初始化日志文件"""
        if cls._log_file is None:
            # 创建 logs 目录
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # 生成基于开始运行时间的文件名
            start_time = datetime.datetime.now()
            log_filename = f"debug_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
            cls._log_file_path = os.path.join(log_dir, log_filename)
            
            # 打开日志文件
            cls._log_file = open(cls._log_file_path, "a", encoding="utf-8")
            
            # 写入日志文件头
            cls._write_log(f"[DEBUG] 日志文件创建于: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @classmethod
    def _write_log(cls, message: str):
        """写入日志信息"""
        cls._init_log_file()
        if cls._log_file:
            cls._log_file.write(message + "\n")
            cls._log_file.flush()  # 立即刷新，确保信息被写入
    
    @classmethod
    def get_log_file_path(cls) -> Optional[str]:
        """获取日志文件路径"""
        cls._init_log_file()
        return cls._log_file_path
    
    @classmethod
    def close_log_file(cls):
        """关闭日志文件"""
        if cls._log_file:
            cls._log_file.close()
            cls._log_file = None
    
    @classmethod
    def is_debug_enabled(cls) -> bool:
        """检查是否启用调试"""
        return cls.DEBUG_ENABLED
    
    @classmethod
    def should_print_node_start(cls) -> bool:
        """检查是否打印节点开始信息"""
        return cls.DEBUG_ENABLED and cls.DEBUG_NODE_START
    
    @classmethod
    def should_print_node_end(cls) -> bool:
        """检查是否打印节点结束信息"""
        return cls.DEBUG_ENABLED and cls.DEBUG_NODE_END
    
    @classmethod
    def should_print_state_transition(cls) -> bool:
        """检查是否打印状态转换信息"""
        return cls.DEBUG_ENABLED and cls.DEBUG_STATE_TRANSITION
    
    @classmethod
    def should_print_llm_calls(cls) -> bool:
        """检查是否打印 LLM 调用信息"""
        return cls.DEBUG_ENABLED and cls.DEBUG_LLM_CALLS
    
    @classmethod
    def should_print_tool_calls(cls) -> bool:
        """检查是否打印工具调用信息"""
        return cls.DEBUG_ENABLED and cls.DEBUG_TOOL_CALLS


def debug_node(node_name: str):
    """节点调试装饰器 - also records trace events.
    
    使用方法:
        @debug_node("my_node")
        async def my_node(state, config):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(state, config):
            # 获取唯一标识
            # 在 config.configurable.researcher_id 中设置 unique_id，则会被记录
            unique_id = None
            agent_type = "system"
            if config:
                configurable = config.get("configurable", {})
                if configurable:
                    unique_id = configurable.get("researcher_id", "invalid")
            
            # Determine agent type based on node name and researcher_id
            if node_name in ("clarify_with_user", "write_research_brief"):
                agent_type = "system"
            elif node_name in ("supervisor", "supervisor_tools"):
                agent_type = "supervisor"
            elif node_name in ("researcher", "researcher_tools", "compress_research"):
                agent_type = "researcher"
            elif node_name == "final_report_generation":
                agent_type = "report"
            
            # Record trace: node start
            if DebugConfig.TRACE_ENABLED:
                try:
                    trace = _get_trace()
                    trace.record_event(
                        event_type="node_start",
                        node_name=node_name,
                        agent_type=agent_type,
                        researcher_id=unique_id if unique_id and unique_id != "invalid" else None,
                        details={
                            "state_keys": list(state.keys()) if isinstance(state, dict) else [],
                        }
                    )
                except Exception:
                    pass  # Don't let tracing errors affect execution
            
            # 打印节点开始信息
            if DebugConfig.should_print_node_start():
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_messages = [
                    f"{'='*70}",
                    f"[DEBUG] node start: {node_name}",
                    f"[DEBUG] node id: {unique_id if unique_id else 'invalid'}",
                    f"[DEBUG] timestamp: {timestamp}",
                    f"{'='*70}"
                ]
                
                # 输出到控制台
                for msg in start_messages:
                    print(f"\n{msg}")
                
                # 写入日志文件
                for msg in start_messages:
                    DebugConfig._write_log(msg)
            
            # 执行节点函数
            result = await func(state, config)
            
            # Record trace: node end
            if DebugConfig.TRACE_ENABLED:
                try:
                    trace = _get_trace()
                    end_details = {}
                    if hasattr(result, 'goto'):
                        end_details["next_node"] = result.goto
                    trace.record_event(
                        event_type="node_end",
                        node_name=node_name,
                        agent_type=agent_type,
                        researcher_id=unique_id if unique_id and unique_id != "invalid" else None,
                        details=end_details,
                    )
                except Exception:
                    pass
            
            # 打印节点结束信息
            if DebugConfig.should_print_node_end():
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                end_messages = [
                    f"{'='*70}",
                    f"[DEBUG] node complete: {node_name}",
                    f"[DEBUG] node id: {unique_id if unique_id else 'invalid'}",
                    f"[DEBUG] timestamp: {timestamp}"
                ]
                
                try:
                    if hasattr(result, 'goto'):
                        end_messages.append(f"[DEBUG] next node: {result.goto}")
                except:
                    pass
                
                end_messages.append(f"{'='*70}")
                
                # 输出到控制台
                for msg in end_messages:
                    print(f"\n{msg}")
                
                # 写入日志文件
                for msg in end_messages:
                    DebugConfig._write_log(msg)
            
            return result
        return wrapper
    return decorator


def print_debug(message: str, category: str = "INFO"):
    """打印调试信息
    
    Args:
        message: 调试消息
        category: 消息类别 (INFO, WARNING, ERROR)
    """
    if not DebugConfig.is_debug_enabled():
        return
    
    icons = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "SUCCESS": "✅",
        "DEBUG": "🔍"
    }
    
    icon = icons.get(category, "ℹ️")
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {icon} [{category}] {message}"
    
    # 输出到控制台
    print(f"\n{log_message}")
    
    # 写入日志文件
    DebugConfig._write_log(log_message)


def print_state_summary(state: dict, title: str = "状态摘要"):
    """打印状态摘要
    
    Args:
        state: 状态字典
        title: 标题
    """
    if not DebugConfig.is_debug_enabled():
        return
    
    summary_messages = [
        f"{'='*70}",
        f"[DEBUG] {title}",
        f"{'='*70}"
    ]
    
    for key, value in state.items():
        if isinstance(value, list):
            summary_messages.append(f"  {key}: list with {len(value)} items")
        elif isinstance(value, dict):
            summary_messages.append(f"  {key}: dict with {len(value)} keys")
        elif isinstance(value, str) and len(value) > 100:
            summary_messages.append(f"  {key}: {value[:100]}...")
        else:
            summary_messages.append(f"  {key}: {value}")
    
    summary_messages.append(f"{'='*70}")
    
    # 输出到控制台
    for msg in summary_messages:
        print(f"\n{msg}")
    
    # 写入日志文件
    for msg in summary_messages:
        DebugConfig._write_log(msg)


def print_tool_calls(tool_calls, unique_id=None):
    """打印工具调用信息

    Args:
        tool_calls: 工具调用列表
        unique_id: 唯一标识（可选）
    """
    if not DebugConfig.is_debug_enabled() or not tool_calls:
        return

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tool_messages = [
        f"{'='*70}",
        f"[DEBUG] tool call",
        f"[DEBUG] node id: {unique_id}" if unique_id else None,
        f"[DEBUG] timestamp: {timestamp}",
        f"[DEBUG] #tools: {len(tool_calls)}"
    ]
    
    # 过滤掉 None 值
    tool_messages = [msg for msg in tool_messages if msg is not None]
    
    # 添加工具名称
    tool_names = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "unknown")
        tool_names.append(tool_name)
    tool_messages.append(" ".join(tool_names))
    tool_messages.append(f"{'='*70}")
    
    # 输出到控制台
    for msg in tool_messages:
        if msg == tool_messages[-2]:  # 工具名称行
            print(f"{msg} ")
        else:
            print(f"\n{msg}")
    
    # 写入日志文件
    for msg in tool_messages:
        DebugConfig._write_log(msg)
