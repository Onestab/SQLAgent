from langchain_core.tools import tool
from database.connection import execute_query_sync, get_table_schema_sync, list_tables_sync
import sqlparse
from typing import Any


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
