"""
LangGraph工作流图定义
实现Text-to-SQL的完整流程
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import AgentState
from agent.nodes import (
    intent_recognition_node,
    common_chat_node,
    schema_linking_node,
    sql_generation_node,
    sql_validation_node,
    sql_execution_node,
    result_interpretation_node,
    error_handler_node
)


def should_retry(state: AgentState) -> Literal["sql_generation", "error_handler"]:
    """判断是否需要重试SQL生成"""
    if state.get("execution_error") and state.get("retry_count", 0) < 3:
        return "sql_generation"
    elif state.get("execution_error"):
        return "error_handler"
    return "result_interpretation"


def need_sql_chat(state: AgentState) -> Literal["schema_linking", "common_chat"]:
    """判断对话是普通对话还是SQL问答"""
    if state.get("chat_mode") == "common":
        return "common_chat"
    return "schema_linking"

def build_graph() -> StateGraph:
    """构建LangGraph工作流"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("common_chat", common_chat_node)
    workflow.add_node("schema_linking", schema_linking_node)
    workflow.add_node("sql_generation", sql_generation_node)
    workflow.add_node("sql_validation", sql_validation_node)
    workflow.add_node("sql_execution", sql_execution_node)
    workflow.add_node("result_interpretation", result_interpretation_node)
    workflow.add_node("error_handler", error_handler_node)

    # 设置入口点
    workflow.set_entry_point("intent_recognition")

    # 添加边
    # workflow.add_edge("intent_recognition", "schema_linking")
    workflow.add_conditional_edges(
        "intent_recognition",
        need_sql_chat,
        {
            "schema_linking": "schema_linking",
            "common_chat": "common_chat"
        }
    )
    workflow.add_edge("schema_linking", "sql_generation")
    workflow.add_edge("sql_generation", "sql_validation")
    workflow.add_edge("sql_validation", "sql_execution")

    # 条件边：根据执行结果决定是重试还是继续
    workflow.add_conditional_edges(
        "sql_execution",
        should_retry,
        {
            "sql_generation": "sql_generation",
            "error_handler": "error_handler",
            "result_interpretation": "result_interpretation"
        }
    )

    workflow.add_edge("common_chat", END)
    workflow.add_edge("result_interpretation", END)
    workflow.add_edge("error_handler", END)

    return workflow.compile()


# 编译图
compiled_graph = build_graph()
