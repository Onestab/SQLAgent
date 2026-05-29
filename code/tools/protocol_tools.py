"""面向未来 MCP 迁移的最小协议兼容工具集合。"""
from __future__ import annotations

from typing import Any, List

from database.connection import execute_query_sync, list_tables_sync
from database.metadata import metadata_manager
from tools.protocol import mcp_error, mcp_success


def protocol_get_database_info() -> dict[str, Any]:
    """MCP协议兼容：获取数据库元数据概况。"""
    try:
        db_info, table_cnt = metadata_manager.get_database_info()
        return mcp_success({
            "database_name": "default",
            "table_count": table_cnt,
            "tables": db_info,
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_search_relevant_tables(query: str, top_k: int = 5, include_scores: bool = False) -> dict[str, Any]:
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


def protocol_get_table_metadata(table_name: str) -> dict[str, Any]:
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


def protocol_list_tables() -> dict[str, Any]:
    """MCP协议兼容：列出所有表。"""
    try:
        return mcp_success({"tables": list_tables_sync()})
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_execute_query(
    sql: str,
    max_rows: int = 100,
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """MCP协议兼容：执行查询SQL。"""
    try:
        results = execute_query_sync(sql)
        limited_rows = results[:max_rows]
        columns: list[dict[str, Any]] = []
        rows: list[list[Any]] = []
        if limited_rows:
            first = limited_rows[0]
            columns = [{"name": key, "type": None} for key in first.keys()]
            rows = [list(row.values()) for row in limited_rows]
        return mcp_success({
            "columns": columns,
            "rows": rows,
            "row_count": len(results),
            "timeout_ms": timeout_ms,
        }, truncated=len(results) > max_rows)
    except Exception as e:
        return mcp_error("SQL_EXECUTION_ERROR", str(e))
