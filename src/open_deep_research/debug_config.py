"""调试配置和工具"""

import os
from typing import Any, Dict, Optional
from functools import wraps


class DebugConfig:
    """调试配置类，通过环境变量控制调试输出"""
    
    # # 从环境变量读取调试设置
    # DEBUG_ENABLED = os.getenv("DEBUG_ENABLED", "false").lower() == "true"
    # DEBUG_NODE_START = os.getenv("DEBUG_NODE_START", "true").lower() == "true"
    # DEBUG_NODE_END = os.getenv("DEBUG_NODE_END", "true").lower() == "true"
    # DEBUG_STATE_TRANSITION = os.getenv("DEBUG_STATE_TRANSITION", "true").lower() == "true"
    # DEBUG_LLM_CALLS = os.getenv("DEBUG_LLM_CALLS", "true").lower() == "true"
    # DEBUG_TOOL_CALLS = os.getenv("DEBUG_TOOL_CALLS", "true").lower() == "true"

    DEBUG_ENABLED = True
    DEBUG_NODE_START = True
    DEBUG_NODE_END = True
    DEBUG_STATE_TRANSITION = True
    DEBUG_LLM_CALLS = True
    DEBUG_TOOL_CALLS = True
    
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
    """节点调试装饰器
    
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
            if config:
                configurable = config.get("configurable", {})
                if configurable:
                    unique_id = configurable.get("researcher_id", "invalid")
            
            # 打印节点开始信息
            if DebugConfig.should_print_node_start():
                print(f"\n{'='*70}")
                print(f"[DEBUG] node start: {node_name}")
                if unique_id:
                    print(f"[DEBUG] node id: {unique_id}")
                else:
                    print(f"[DEBUG] node id: invalid")
                print(f"[DEBUG] timestamp: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                # print(f"[DEBUG] 状态键: {list(state.keys())}")
                print(f"{'='*70}")
            
            # 执行节点函数
            result = await func(state, config)
            
            # 打印节点结束信息
            if DebugConfig.should_print_node_end():
                print(f"\n{'='*70}")
                print(f"[DEBUG] node complete: {node_name}")
                if unique_id:
                    print(f"[DEBUG] node id: {unique_id}")
                print(f"[DEBUG] timestamp: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                try:
                    if hasattr(result, 'goto'):
                        print(f"[DEBUG] next node: {result.goto}")
                    # if hasattr(result, 'update'):
                    #     update_keys = list(result.update.keys()) if result.update else []
                    #     print(f"[DEBUG] 更新的状态键: {update_keys}")
                except:
                    pass

                print(f"{'='*70}")
            
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
    timestamp = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{timestamp}] {icon} [{category}] {message}")


def print_state_summary(state: dict, title: str = "状态摘要"):
    """打印状态摘要
    
    Args:
        state: 状态字典
        title: 标题
    """
    if not DebugConfig.is_debug_enabled():
        return
    
    print(f"\n{'='*70}")
    print(f"[DEBUG] {title}")
    print(f"{'='*70}")
    
    for key, value in state.items():
        if isinstance(value, list):
            print(f"  {key}: list with {len(value)} items")
        elif isinstance(value, dict):
            print(f"  {key}: dict with {len(value)} keys")
        elif isinstance(value, str) and len(value) > 100:
            print(f"  {key}: {value[:100]}...")
        else:
            print(f"  {key}: {value}")
    
    print(f"{'='*70}")


def print_tool_calls(tool_calls, unique_id=None):
    """打印工具调用信息

    Args:
        tool_calls: 工具调用列表
        unique_id: 唯一标识（可选）
    """
    if not DebugConfig.is_debug_enabled() or not tool_calls:
        return

    print(f"\n{'='*70}")
    print(f"[DEBUG] tool call")
    if unique_id:
        print(f"[DEBUG] node id: {unique_id}")
    print(f"[DEBUG] timestamp: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[DEBUG] #tools: {len(tool_calls)}")

    # for i, tool_call in enumerate(tool_calls, 1):
    #     tool_name = tool_call.get("name", "unknown")
    #     tool_id = tool_call.get("id", "unknown")
    #     tool_args = tool_call.get("args", {})

    #     print(f"\n[DEBUG] 工具 #{i}:")
    #     print(f"  名称: {tool_name}")
    #     print(f"  ID: {tool_id}")
    #     print(f"  参数:")

    #     for key, value in tool_args.items():
    #         if isinstance(value, str) and len(value) > 150:
    #             print(f"    {key}: {value[:150]}...")
    #         else:
    #             print(f"    {key}: {value}")

    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "unknown")
        print(f"{tool_name} ", end=' ')

    print("")
    print(f"{'='*70}")
