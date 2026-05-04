from typing import TypedDict, Annotated, Optional, Any
import operator


class AgentState(TypedDict):
    user_query: str
    session_id: str
    intent: str
    chat_mode: str
    relevant_tables: list[str]
    schema_context: str
    generated_sql: str
    sql_validation_result: str
    retry_count: int
    query_results: list[dict]
    execution_error: Optional[str]
    final_answer: str
    error_message: Optional[str]
    llm_messages: Annotated[list[Any], operator.add]
