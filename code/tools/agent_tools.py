"""当前 Agent 使用的最小工具集合。"""
from typing import Any, Dict, List

from langchain_core.tools import tool

from database.metadata import metadata_manager


@tool
def search_relevant_tables(query: str, top_k: int = 5) -> List[str]:
    """根据用户查询搜索相关的数据库表。"""
    try:
        return metadata_manager.search_relevant_tables(query, top_k=top_k)
    except Exception as e:
        return [f"error: {str(e)}"]


@tool
def get_table_metadata(table_name: str) -> Dict[str, Any]:
    """获取指定表的完整元数据信息。"""
    try:
        metadata = metadata_manager.get_table_metadata(table_name)
        if metadata is None:
            return {"error": f"Table '{table_name}' not found in metadata"}
        return metadata
    except Exception as e:
        return {"error": str(e)}


@tool
def get_related_tables(table_name: str) -> List[str]:
    """获取与指定表直接关联的所有表。"""
    try:
        return list(metadata_manager.get_related_tables(table_name))
    except Exception as e:
        return [f"error: {str(e)}"]


@tool
def get_schema_context(table_names: List[str], include_examples: bool = True) -> str:
    """获取多个表的 Schema 上下文信息。"""
    try:
        context = metadata_manager.get_schema_context(table_names, include_examples=include_examples)
        if not context:
            return f"No schema context available for tables: {table_names}"
        return context
    except Exception as e:
        return f"error: {str(e)}"


ALL_TOOLS = [
    search_relevant_tables,
    get_table_metadata,
    get_related_tables,
    get_schema_context,
]
