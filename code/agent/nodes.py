"""
LangGraph节点实现
每个节点负责工作流中的一个步骤
"""
import re
import sqlparse
from typing import Any
from config import get_llm
from tools import ALL_TOOLS
from agent.state import AgentState
from database.connection import execute_query_sync
from langgraph.config import get_stream_writer
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, trim_messages

def _stream_event(event_type: str, **payload: Any) -> None:
    """向LangGraph流输出自定义事件。"""
    try:
        writer = get_stream_writer()
    except Exception:
        return
    writer({"event": event_type, **payload})


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content)


def _message_reasoning_text(message: Any) -> str:
    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    reasoning = additional_kwargs.get("reasoning_content", "")
    if isinstance(reasoning, str):
        return reasoning
    return str(reasoning)


def _stream_llm_text(llm: Any, messages: list[Any], *, stage: str) -> str:
    """流式消费LLM输出，同时区分思考内容与最终回答。"""
    _stream_event("llm_stage", stage=stage, status="start")
    parts: list[str] = []
    for chunk in llm.stream(messages):
        reasoning_text = _message_reasoning_text(chunk)
        if reasoning_text:
            _stream_event("llm_reasoning_chunk", stage=stage, text=reasoning_text)
        text = _message_text(chunk)
        if not text:
            continue
        parts.append(text)
        _stream_event("llm_answer_chunk", stage=stage, text=text)
    full_text = "".join(parts).strip()
    _stream_event("llm_stage", stage=stage, status="end", text=full_text)
    return full_text


def load_memory_node(state: AgentState) -> dict[str, Any]:
    """加载历史对话记忆"""
    messages = state["llm_messages"]
    max_token_len = 262144
    trimmed = trim_messages(
        messages,
        max_tokens=max_token_len*0.6,
        strategy="last",
        token_counter=len,
        allow_partial=False,
        include_system=True,
        start_on="human"
    )
    return {
        "llm_messages": trimmed
    }


def intent_recognition_node(state: AgentState) -> dict[str, Any]:
    """意图识别节点：分析用户查询意图"""
    from database.metadata import metadata_manager
    llm = get_llm()
    db_info, table_cnt = metadata_manager.get_database_info()
    user_query = state["user_query"]
    history = state.get("llm_messages", [])
    prompt = f"""根据当前问题及历史对话判断用户意图。

如果回答用户当前问题必须查询数据库，则返回字符串sql，并简要说明用户的查询意图（1-2句话，如有指代关系需要替换成实际名称）

如果判断用户不需要访问数据库，则返回字符串common，并直接回答用户问题。

输出格式：
- 需要查询数据库情况：sql 用户查询意图
- 无需查询数据库情况：common 你的回答

当前数据库包含的表：
{"\n".join(db_info)}

当前数据库包含表的总数：
{table_cnt}
"""
    messages = history + [HumanMessage(content=prompt), HumanMessage(content=user_query)]
    response_text = _stream_llm_text(llm, messages, stage="intent_recognition")
    if response_text.startswith("common"):
        _stream_event("decision", node="intent_recognition", route="common_chat")
        return {
            "chat_mode": "common",
            "llm_messages": [HumanMessage(content=user_query), AIMessage(content=response_text.strip().removeprefix("common").strip())]
        }
    _stream_event("decision", node="intent_recognition", route="sql")
    return {
        "chat_mode": "sql",
        "intent": response_text.strip().removeprefix("sql").strip(),
        "llm_messages": [HumanMessage(content=user_query), AIMessage(content=response_text)]
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
    system_prompt = f"""你是一个数据库Schema检索专家。你的任务是根据用户意图找到所有相关的数据库表及其Schema信息。
你需要：
1. 使用search_relevant_tables工具搜索与问题相关的表， 可根据需求适当修改query内容
2. 对于找到的每个表，使用get_related_tables工具查找其关联表
3. 使用get_schema_context获取详细的Schema信息
4. 判断是否已经找到回答问题所需的所有表，如果不够完整，继续搜索
5. 当你确认已经找到所有必要的表和Schema信息后，总结你找到的表名列表

重要提示：
- 对于涉及多表关联的查询（如订单和用户、产品和订单等），务必找到所有相关联的表
- 如果问题涉及聚合、统计，确保找到包含相关指标的表
- 必要时使用get_related_tables工具扩展搜索范围，避免遗漏关联表

请开始检索，最后结果以"相关表: [表1, 表2, ...]"的格式总结。"""

    user_input = f"""
用户问题: {user_query}
用户意图: {intent}
"""
    _stream_event("schema_linking_context", user_query=user_query, intent=intent)

    # 创建ReAct Agent
    react_agent = create_react_agent(model=llm, tools=ALL_TOOLS)

    # 调用Agent进行多轮检索
    agent_messages: list[Any] = []
    for event in react_agent.stream(
        input={"messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_input)]},
        stream_mode=["values", "updates", "messages", "tasks", "custom"],
        version="v2",
    ):
        event_type = event.get("type")
        data = event.get("data")
        if event_type == "messages":
            chunk, metadata = data
            text = _message_text(chunk)
            if text:
                _stream_event(
                    "agent_message_chunk",
                    node="agentic_schema_linking",
                    text=text,
                    source=metadata.get("langgraph_node"),
                    model=metadata.get("ls_provider"),
                )
        elif event_type == "tasks":
            task_name = data.get("name")
            if "input" in data:
                _stream_event("agent_task_start", node="agentic_schema_linking", task=task_name)
            else:
                _stream_event(
                    "agent_task_end",
                    node="agentic_schema_linking",
                    task=task_name,
                    error=data.get("error"),
                )
        elif event_type == "updates":
            for update_node, update_payload in data.items():
                if update_node == "tools":
                    messages = update_payload.get("messages", [])
                    for msg in messages:
                        tool_name = getattr(msg, "name", None)
                        if tool_name:
                            _stream_event(
                                "tool_result",
                                node="agentic_schema_linking",
                                tool=tool_name,
                                output=_message_text(msg)[:400],
                            )
                elif update_node == "agent":
                    messages = update_payload.get("messages", [])
                    if messages:
                        agent_messages = messages
        elif event_type == "values":
            value_messages = data.get("messages", [])
            if value_messages:
                agent_messages = value_messages

    final_message = agent_messages[-1].content if agent_messages else ""

    # 解析Agent找到的表名列表
    relevant_tables = []

    # 尝试从最后的消息中提取表名
    # 匹配 "找到的相关表: [...]" 或类似格式
    table_pattern = r'相关表[：:]\s*\[([^\]]+)\]'
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
        from database.metadata import metadata_manager
        _stream_event("schema_linking_fallback", method="metadata_search")
        relevant_tables = metadata_manager.search_relevant_tables(user_query, top_k=5)

    # 如果仍然没有找到，使用所有表的前几个
    if not relevant_tables:
        from database.connection import list_tables_sync
        _stream_event("schema_linking_fallback", method="list_tables")
        relevant_tables = list_tables_sync()[:3]

    # 生成schema上下文
    from database.metadata import metadata_manager
    schema_context = metadata_manager.get_schema_context(relevant_tables, include_examples=True)
    _stream_event("schema_linking_result", tables=relevant_tables)

    return {
        "relevant_tables": relevant_tables,
        "schema_context": schema_context,
        "llm_messages": [AIMessage(content=f"通过智能检索找到相关表: {', '.join(relevant_tables)}")]
    }


def sql_generation_node(state: AgentState) -> dict[str, Any]:
    """SQL生成节点：基于意图和schema生成SQL"""
    from config import config
    llm = get_llm()
    user_query = state["user_query"]
    user_intent = state["intent"]
    schema_context = state["schema_context"]
    retry_count = state.get("retry_count", 0)
    execution_error = state.get("execution_error")

    # 数据库类型特定的语法提示
    db_hints = {
        "sqlite": "使用SQLite语法，日期函数用date()、datetime()，字符串拼接用||",
        "mysql": "使用MySQL语法，日期函数用DATE()、NOW()，字符串拼接用CONCAT()",
        "postgresql": "使用PostgreSQL语法，日期函数用CURRENT_DATE、NOW()，字符串拼接用||"
    }
    db_hint = db_hints.get(config.db_type, "使用标准SQL语法")

    prompt = f"""你是一个SQL专家。根据用户查询和数据库schema，生成正确的SQL查询语句。

数据库类型: {config.db_type.upper()}
{db_hint}

用户查询: {user_query}
用户意图：{user_intent}

数据库Schema:
{schema_context}

要求:
1. 只返回SQL语句，不要有任何解释
2. 根据数据库类型使用正确的语法
3. 确保表名和列名正确
4. 如果需要JOIN，确保JOIN条件正确
5. 对于聚合查询，使用适当的GROUP BY
6. 所给schema都是回答问题所必须的，充分思考所给的schema之间的关联后再生成SQL
"""

    if execution_error:
        prompt += f"""

上一次执行出错了，错误信息: {execution_error}
请修正SQL语句。
"""
        _stream_event("retry", node="sql_generation", retry_count=retry_count, error=execution_error)

    messages = [HumanMessage(content=prompt)]
    response_text = _stream_llm_text(llm, messages, stage="sql_generation")
    # 提取SQL语句
    sql = response_text.strip()
    # 移除可能的markdown代码块标记
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    sql = sql.strip()
    _stream_event("sql_generated", sql=sql)

    return {
        "generated_sql": sql,
        "retry_count": retry_count + 1 if execution_error else retry_count,
        "execution_error": None,  # 清除之前的错误
        "llm_messages": [AIMessage(content=f"生成的SQL:\n{sql}")]
    }


def sql_validation_node(state: AgentState) -> dict[str, Any]:
    """SQL验证节点：验证SQL语法"""
    sql = state["generated_sql"]
    _stream_event("sql_validation_start")

    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            _stream_event("sql_validation_end", status="invalid", error="Empty SQL statement")
            return {"sql_validation_result": "invalid", "execution_error": "Empty SQL statement"}

        stmt = parsed[0]
        stmt_type = stmt.get_type()

        if stmt_type not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            _stream_event("sql_validation_end", status="invalid", error=f"Unsupported statement type: {stmt_type}")
            return {"sql_validation_result": "invalid", "execution_error": f"Unsupported statement type: {stmt_type}"}

        # 格式化SQL
        formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper')
        _stream_event("sql_validation_end", status="valid", statement_type=stmt_type)

        return {
            "sql_validation_result": "valid",
            "generated_sql": formatted_sql
        }
    except Exception as e:
        _stream_event("sql_validation_end", status="invalid", error=str(e))
        return {
            "sql_validation_result": "invalid",
            "execution_error": f"SQL validation error: {str(e)}"
        }


def sql_execution_node(state: AgentState) -> dict[str, Any]:
    """SQL执行节点：执行SQL查询"""
    sql = state["generated_sql"]
    _stream_event("sql_execution_start", sql=sql)

    try:
        results = execute_query_sync(sql)
        _stream_event("sql_execution_end", row_count=len(results))
        return {
            "query_results": results,
            "execution_error": None
        }
    except Exception as e:
        _stream_event("sql_execution_end", error=str(e))
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

    messages = [HumanMessage(content=prompt)]
    response_text = _stream_llm_text(llm, messages, stage="result_interpretation")

    return {
        "final_answer": response_text,
        "llm_messages": [AIMessage(content=response_text)]
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
