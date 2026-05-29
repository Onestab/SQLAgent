from langchain_core.tools import tool
from database.connection import execute_query_sync, get_table_schema_sync, list_tables_sync
import sqlparse
import sqlglot
from typing import Any
from config import config
from tools.protocol import mcp_success, mcp_error


@tool
def execute_query(sql: str) -> list[dict[str, Any]]:
    """执行SQL查询并返回结果

    Args:
        sql: 要执行的SQL查询语句

    Returns:
        查询结果列表
    """
    try:
        results = execute_query_sync(sql)
        return results
    except Exception as e:
        return [{"error": str(e)}]


@tool
def get_table_schema(table_name: str) -> dict[str, Any]:
    """获取指定表的结构信息

    Args:
        table_name: 表名

    Returns:
        表结构信息，包括列名、类型、是否可空等
    """
    try:
        schema = get_table_schema_sync(table_name)
        return schema
    except Exception as e:
        return {"error": str(e)}


@tool
def list_tables() -> list[str]:
    """列出数据库中所有表名

    Returns:
        表名列表
    """
    try:
        tables = list_tables_sync()
        return tables
    except Exception as e:
        return [f"error: {str(e)}"]


@tool
def validate_sql(sql: str) -> dict[str, Any]:
    """验证SQL语法是否正确

    Args:
        sql: 要验证的SQL语句

    Returns:
        验证结果，包括是否有效和错误信息
    """
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return {"valid": False, "error": "Empty SQL statement"}

        # 基本语法检查
        stmt = parsed[0]
        if stmt.get_type() not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER'):
            return {"valid": False, "error": "Unknown SQL statement type"}

        # 格式化SQL
        formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper')

        return {
            "valid": True,
            "formatted_sql": formatted_sql,
            "statement_type": stmt.get_type()
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def _protocol_dialect() -> str:
    if config.db_type == "postgresql":
        return "postgres"
    return config.db_type


def protocol_list_tables() -> dict[str, Any]:
    """MCP协议兼容：列出所有表。"""
    try:
        return mcp_success({"tables": list_tables_sync()})
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_get_table_schema(table_name: str) -> dict[str, Any]:
    """MCP协议兼容：获取表结构。"""
    try:
        schema = get_table_schema_sync(table_name)
        if isinstance(schema, dict):
            return mcp_success({
                "table_name": table_name,
                "columns": schema.get("columns", []),
            })
        return mcp_success({
            "table_name": table_name,
            "columns": schema,
        })
    except Exception as e:
        return mcp_error("INTERNAL_ERROR", str(e))


def protocol_validate_sql(sql: str, dialect: str | None = None) -> dict[str, Any]:
    """MCP协议兼容：校验SQL。"""
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return mcp_success({
                "valid": False,
                "normalized_sql": "",
                "statement_type": None,
                "warnings": ["Empty SQL statement"],
            })

        stmt = parsed[0]
        formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper')
        return mcp_success({
            "valid": stmt.get_type() in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"),
            "normalized_sql": formatted_sql,
            "statement_type": stmt.get_type(),
            "warnings": [],
            "dialect": dialect or _protocol_dialect(),
        })
    except Exception as e:
        return mcp_error("SQL_VALIDATION_ERROR", str(e))


def protocol_transpile_sql(sql: str, source_dialect: str = "ansi", target_dialect: str | None = None) -> dict[str, Any]:
    """MCP协议兼容：进行方言转译。"""
    try:
        target = target_dialect or _protocol_dialect()
        if target == "postgresql":
            target = "postgres"
        transpiled = sqlglot.transpile(
            sql,
            read=None if source_dialect == "ansi" else source_dialect,
            write=target,
            identity=False,
        )
        return mcp_success({
            "sql": transpiled[0].strip(),
            "source_dialect": source_dialect,
            "target_dialect": target,
        })
    except Exception as e:
        return mcp_error("SQL_VALIDATION_ERROR", str(e))


def protocol_execute_sql(
    sql: str,
    dialect: str | None = None,
    max_rows: int = 100,
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """MCP协议兼容：执行SQL。"""
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
            "dialect": dialect or _protocol_dialect(),
            "timeout_ms": timeout_ms,
        }, truncated=len(results) > max_rows)
    except Exception as e:
        return mcp_error("SQL_EXECUTION_ERROR", str(e))
