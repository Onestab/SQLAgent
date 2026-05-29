"""元数据检索工具
将元数据管理器的检索功能封装为LangChain工具
"""
from langchain_core.tools import tool
from typing import List, Dict, Any
from database.metadata import metadata_manager
from tools.protocol import mcp_success, mcp_error


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
        # print("***************** search_relevant_tables ********************")
        # print(tables)
        # print("*************************************************************")
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
        # print("***************** get_table_metadata ********************")
        # print(metadata)
        # print("*********************************************************")
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
        # print("***************** get_table_description ********************")
        # print(description)
        # print("************************************************************")
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
        # print("***************** get_related_tables ********************")
        # print(related)
        # print("*********************************************************")
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


def protocol_describe_database() -> dict[str, Any]:
    """MCP协议兼容：描述数据库元数据概况。"""
    try:
        db_info, table_cnt = metadata_manager.get_database_info()
        return mcp_success({
            "database_name": "default",
            "table_count": table_cnt,
            "tables": db_info,
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_search_tables(query: str, top_k: int = 5, include_scores: bool = False) -> dict[str, Any]:
    """MCP协议兼容：搜索相关表。"""
    try:
        tables = metadata_manager.search_relevant_tables(query, top_k=top_k)
        source = "local"
    except Exception:
        try:
            keyword_scores = []
            for table_name in metadata_manager.metadata_cache.keys():
                score = metadata_manager._keyword_match_score(query, table_name)
                keyword_scores.append((table_name, score))
            keyword_scores.sort(key=lambda item: item[1], reverse=True)
            tables = [table for table, _ in keyword_scores[:top_k]]
            source = "local-fallback"
        except Exception as e:
            return mcp_error("INTERNAL_ERROR", str(e))
    try:
        data = {
            "tables": [
                {"table_name": table, "score": None, "reason": None}
                for table in tables
            ]
        }
        if not include_scores:
            for item in data["tables"]:
                item.pop("score")
        return mcp_success(data, source=source)
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_get_table(table_name: str) -> dict[str, Any]:
    """MCP协议兼容：获取表元数据。"""
    try:
        metadata = metadata_manager.get_table_metadata(table_name)
        if metadata is None:
            return mcp_error("NOT_FOUND", f"Table '{table_name}' not found")
        return mcp_success({
            "table_name": table_name,
            "description": metadata.get("description", ""),
            "business_context": metadata.get("business_context", ""),
            "columns": metadata.get("columns", []),
            "relations": metadata.get("relationships", []),
            "examples": metadata.get("example_queries", []),
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_get_related_tables(table_name: str, max_depth: int = 1) -> dict[str, Any]:
    """MCP协议兼容：获取关联表。"""
    try:
        related = metadata_manager.get_related_tables(table_name)
        return mcp_success({
            "table_name": table_name,
            "related_tables": [
                {"table_name": name, "relation_type": None, "max_depth": max_depth}
                for name in sorted(related)
            ],
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_get_schema_context(
    table_names: List[str],
    include_examples: bool = True,
    include_relations: bool = True,
) -> dict[str, Any]:
    """MCP协议兼容：获取schema上下文。"""
    try:
        schema_context = metadata_manager.get_schema_context(
            table_names,
            include_examples=include_examples,
            include_relationships=include_relations,
        )
        tables = []
        for table_name in table_names:
            metadata = metadata_manager.get_table_metadata(table_name) or {}
            tables.append({
                "table_name": table_name,
                "description": metadata.get("description", ""),
                "columns": metadata.get("columns", []),
                "relations": metadata.get("relationships", []),
                "examples": metadata.get("example_queries", []) if include_examples else [],
            })
        return mcp_success({
            "schema_context": schema_context,
            "tables": tables,
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_get_examples(table_name: str, limit: int = 5) -> dict[str, Any]:
    """MCP协议兼容：获取示例SQL。"""
    try:
        examples = metadata_manager.get_example_queries(table_name)[:limit]
        return mcp_success({"examples": examples})
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))
