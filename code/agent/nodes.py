"""
LangGraph节点实现
每个节点负责工作流中的一个步骤
"""
from agent.state import AgentState
from config import get_llm
from database.connection import list_tables_sync, get_table_schema_sync, execute_query_sync
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import sqlparse
from typing import Any
from tools import ALL_TOOLS
import re
import os

# 从环境变量或配置读取是否显示详细输出
SHOW_AGENTIC_PROCESS = os.getenv("SHOW_AGENTIC_PROCESS", "false").lower() == "true"


def intent_recognition_node(state: AgentState) -> dict[str, Any]:
    """意图识别节点：分析用户查询意图"""
    llm = get_llm()
    user_query = state["user_query"]

    prompt = f"""根据问题判断用户意图。

如果用户需要查询数据库，则简要说明用户的查询意图（1-2句话）

如果判断用户不需要访问数据库，则返回字符串common，其余不要输出任何内容

用户查询: {user_query}

。
"""

    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)

    print("意图的response", response.content)
    if response.content == "common":
        return {
            "chat_mode": "common",
            "llm_messages": [HumanMessage(content=user_query), AIMessage(content=response.content)]
        }
    return {
        "chat_mode": "sql",
        "intent": response.content,
        "llm_messages": [HumanMessage(content=user_query), AIMessage(content=response.content)]
    }


def common_chat_node(state: AgentState) -> dict[str, Any]:
    """普通聊天节点：正常对话，不调用SQL"""
    llm = get_llm()
    user_query = state["user_query"]
    print("进入普通聊天模式")
    prompt = f"""
用户提问: {user_query}

请根据用户提问生成回复。
"""
    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)
    return {
        "llm_messages": [AIMessage(content=response.content)]
    }

def agentic_schema_linking_node(state: AgentState) -> dict[str, Any]:
    """Agentic RAG 方式实现的模式链接节点：识别相关表和列

    通过ReAct Agent自主调用检索工具，多轮交互确保召回所有相关Schema
    """
    user_query = state["user_query"]
    intent = state["intent"]
    llm = get_llm()

    # 创建ReAct Agent，配置元数据检索工具
    from langgraph.prebuilt import create_react_agent

    # 系统提示：指导Agent如何进行Schema检索
    system_prompt = f"""你是一个数据库Schema检索专家。你的任务是根据用户问题找到所有相关的数据库表及其Schema信息。

用户问题: {user_query}
用户意图: {intent}

你需要：
1. 使用search_relevant_tables工具搜索与问题相关的表， 可根据需求适当修改query内容
2. 对于找到的每个表，使用get_related_tables工具查找其关联表
3. 使用get_table_metadata或get_schema_context获取详细的Schema信息
4. 判断是否已经找到回答问题所需的所有表，如果不够完整，继续搜索
5. 当你确认已经找到所有必要的表和Schema信息后，总结你找到的表名列表

重要提示：
- 对于涉及多表关联的查询（如订单和用户、产品和订单等），务必找到所有相关联的表
- 如果问题涉及聚合、统计，确保找到包含相关指标的表
- 必要时使用get_related_tables工具扩展搜索范围，避免遗漏关联表

请开始检索，最后以"找到的相关表: [表1, 表2, ...]"的格式总结。"""

    if SHOW_AGENTIC_PROCESS:
        print("\n" + "="*60)
        print("AgenticRAG Schema检索过程")
        print("="*60)
        print(f"用户问题: {user_query}")
        print(f"用户意图: {intent}")
        print("-"*60)

    # 创建ReAct Agent
    react_agent = create_react_agent(model=llm, tools=ALL_TOOLS)

    # 调用Agent进行多轮检索
    result = react_agent.invoke(input={
        "messages": [SystemMessage(content=system_prompt)],
    },debug=True)
    # 从Agent的响应中提取找到的表名
    agent_messages = result.get("messages", [])

    if SHOW_AGENTIC_PROCESS:
        print("\nAgent检索过程:")
        for i, msg in enumerate(agent_messages):
            if hasattr(msg, 'content') and msg.content:
                print(f"\n[步骤 {i+1}] {msg.__class__.__name__}:")
                print(msg.content[:200] + "..." if len(msg.content) > 200 else msg.content)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    print(f"  → 调用工具: {tool_call.get('name', 'unknown')}")
                    print(f"    参数: {tool_call.get('args', {})}")

    final_message = agent_messages[-1].content if agent_messages else ""

    # 解析Agent找到的表名列表
    relevant_tables = []

    # 尝试从最后的消息中提取表名
    # 匹配 "找到的相关表: [...]" 或类似格式
    table_pattern = r'找到的相关表[：:]\s*\[([^\]]+)\]'
    match = re.search(table_pattern, final_message)

    if match:
        tables_str = match.group(1)
        # 分割表名，去除引号和空格
        relevant_tables = [t.strip().strip('"\'') for t in tables_str.split(',')]
    else:
        # 如果没有找到标准格式，尝试从消息中提取所有提到的表名
        # 这里可以通过分析Agent调用的工具来获取
        for msg in agent_messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get('name') in ['search_relevant_tables', 'get_table_metadata', 'get_related_tables']:
                        args = tool_call.get('args', {})
                        if 'table_name' in args:
                            table = args['table_name']
                            if table not in relevant_tables:
                                relevant_tables.append(table)
                        elif 'table_names' in args:
                            tables = args['table_names']
                            for table in tables:
                                if table not in relevant_tables:
                                    relevant_tables.append(table)

    # 如果Agent没有找到表，回退到传统检索
    if not relevant_tables:
        if SHOW_AGENTIC_PROCESS:
            print("\n⚠️  Agent未找到表，使用传统检索方法")
        from database.metadata import metadata_manager
        relevant_tables = metadata_manager.search_relevant_tables(user_query, top_k=3)

    # 如果仍然没有找到，使用所有表的前几个
    if not relevant_tables:
        from database.connection import list_tables_sync
        relevant_tables = list_tables_sync()[:3]

    # 生成schema上下文
    from database.metadata import metadata_manager
    schema_context = metadata_manager.get_schema_context(relevant_tables, include_examples=True)

    if SHOW_AGENTIC_PROCESS:
        print("\n" + "-"*60)
        print(f"✓ 最终找到的相关表: {relevant_tables}")
        print("="*60 + "\n")

    return {
        "relevant_tables": relevant_tables,
        "schema_context": schema_context,
        "llm_messages": [AIMessage(content=f"通过智能检索找到相关表: {', '.join(relevant_tables)}")]
    }

def sql_generation_node(state: AgentState) -> dict[str, Any]:
    """SQL生成节点：基于意图和schema生成SQL"""
    llm = get_llm()
    user_query = state["user_query"]
    schema_context = state["schema_context"]
    retry_count = state.get("retry_count", 0)
    execution_error = state.get("execution_error")

    prompt = f"""你是一个SQL专家。根据用户查询和数据库schema，生成正确的SQL查询语句。

用户查询: {user_query}

数据库Schema:
{schema_context}

要求:
1. 只返回SQL语句，不要有任何解释
2. 使用标准SQL语法
3. 确保表名和列名正确
4. 如果需要JOIN，确保JOIN条件正确
5. 对于聚合查询，使用适当的GROUP BY
"""

    if execution_error:
        prompt += f"""

上一次执行出错了，错误信息: {execution_error}
请修正SQL语句。
"""

    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)

    # 提取SQL语句
    sql = response.content.strip()
    # 移除可能的markdown代码块标记
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    sql = sql.strip()

    return {
        "generated_sql": sql,
        "retry_count": retry_count + 1 if execution_error else retry_count,
        "execution_error": None,  # 清除之前的错误
        "llm_messages": [AIMessage(content=f"生成的SQL:\n{sql}")]
    }


def sql_validation_node(state: AgentState) -> dict[str, Any]:
    """SQL验证节点：验证SQL语法"""
    sql = state["generated_sql"]

    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return {"sql_validation_result": "invalid", "execution_error": "Empty SQL statement"}

        stmt = parsed[0]
        stmt_type = stmt.get_type()

        if stmt_type not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            return {"sql_validation_result": "invalid", "execution_error": f"Unsupported statement type: {stmt_type}"}

        # 格式化SQL
        formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper')

        return {
            "sql_validation_result": "valid",
            "generated_sql": formatted_sql
        }
    except Exception as e:
        return {
            "sql_validation_result": "invalid",
            "execution_error": f"SQL validation error: {str(e)}"
        }


def sql_execution_node(state: AgentState) -> dict[str, Any]:
    """SQL执行节点：执行SQL查询"""
    sql = state["generated_sql"]

    try:
        results = execute_query_sync(sql)
        return {
            "query_results": results,
            "execution_error": None
        }
    except Exception as e:
        return {
            "query_results": [],
            "execution_error": f"SQL execution error: {str(e)}"
        }


def result_interpretation_node(state: AgentState) -> dict[str, Any]:
    """结果解释节点：将查询结果转换为自然语言"""
    llm = get_llm()
    user_query = state["user_query"]
    sql = state["generated_sql"]
    results = state["query_results"]

    # 限制结果数量以避免token过多
    display_results = results[:10] if len(results) > 10 else results
    result_summary = f"查询返回了 {len(results)} 条记录"
    if len(results) > 10:
        result_summary += f"，以下是前10条:\n{display_results}"
    else:
        result_summary += f":\n{display_results}"

    prompt = f"""根据用户查询和SQL执行结果，用自然语言回答用户的问题。

用户查询: {user_query}

执行的SQL: {sql}

查询结果: {result_summary}

请用简洁、清晰的中文回答用户的问题。如果结果为空，请说明没有找到相关数据。
"""

    messages = [SystemMessage(content=prompt)]
    response = llm.invoke(messages)

    return {
        "final_answer": response.content,
        "llm_messages": [AIMessage(content=response.content)]
    }


def error_handler_node(state: AgentState) -> dict[str, Any]:
    """错误处理节点：处理无法恢复的错误"""
    error = state.get("execution_error", "Unknown error")
    user_query = state["user_query"]

    error_message = f"""抱歉，在处理您的查询时遇到了问题。

您的查询: {user_query}

错误信息: {error}

建议:
1. 请尝试用不同的方式描述您的问题
2. 确保您询问的数据在数据库中存在
3. 如果问题持续，请联系管理员
"""

    return {
        "final_answer": error_message,
        "error_message": error,
        "llm_messages": [AIMessage(content=error_message)]
    }
