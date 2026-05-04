"""元数据检索工具
将元数据管理器的检索功能封装为LangChain工具
"""
from langchain_core.tools import tool
from typing import List, Dict, Any
from database.metadata import metadata_manager


@tool
def search_relevant_tables(query: str, top_k: int = 5) -> List[str]:
    """根据用户查询搜索相关的数据库表

    使用混合检索策略（关键词匹配 + 向量检索 + 关联表扩展）找到最相关的表。

    Args:
        query: 用户的自然语言查询
        top_k: 返回的最相关表数量，默认5

    Returns:
        相关表名列表，按相关性排序
    """
    try:
        tables = metadata_manager.search_relevant_tables(query, top_k=top_k)
        return tables
    except Exception as e:
        return [f"error: {str(e)}"]


@tool
def get_table_metadata(table_name: str) -> Dict[str, Any]:
    """获取指定表的完整元数据信息

    包括表描述、业务上下文、列信息、关联关系、示例查询等。

    Args:
        table_name: 表名

    Returns:
        表的完整元数据字典
    """
    try:
        metadata = metadata_manager.get_table_metadata(table_name)
        if metadata is None:
            return {"error": f"Table '{table_name}' not found in metadata"}
        return metadata
    except Exception as e:
        return {"error": str(e)}


@tool
def get_table_description(table_name: str) -> str:
    """获取表的业务描述

    Args:
        table_name: 表名

    Returns:
        表的业务描述文本
    """
    try:
        description = metadata_manager.get_table_description(table_name)
        if not description:
            return f"No description available for table '{table_name}'"
        return description
    except Exception as e:
        return f"error: {str(e)}"


@tool
def get_related_tables(table_name: str) -> List[str]:
    """获取与指定表直接关联的所有表

    Args:
        table_name: 表名

    Returns:
        关联表名列表
    """
    try:
        related = metadata_manager.get_related_tables(table_name)
        return list(related)
    except Exception as e:
        return [f"error: {str(e)}"]


@tool
def get_schema_context(table_names: List[str], include_examples: bool = True) -> str:
    """获取多个表的Schema上下文信息

    生成格式化的Schema描述，包括表结构、列信息、关联关系等，
    适合作为LLM的上下文输入。

    Args:
        table_names: 表名列表
        include_examples: 是否包含示例查询，默认True

    Returns:
        格式化的Schema上下文文本
    """
    try:
        context = metadata_manager.get_schema_context(table_names, include_examples=include_examples)
        if not context:
            return f"No schema context available for tables: {table_names}"
        return context
    except Exception as e:
        return f"error: {str(e)}"


@tool
def get_example_queries(table_name: str) -> List[Dict[str, str]]:
    """获取表的示例查询

    Args:
        table_name: 表名

    Returns:
        示例查询列表，每个示例包含question和sql字段
    """
    try:
        examples = metadata_manager.get_example_queries(table_name)
        if not examples:
            return [{"info": f"No example queries available for table '{table_name}'"}]
        return examples
    except Exception as e:
        return [{"error": str(e)}]
