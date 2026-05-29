"""
工具函数模块
"""
from typing import Any


def format_results(results: list[dict[str, Any]], max_rows: int = 10) -> str:
    """格式化查询结果为可读字符串"""
    if not results:
        return "查询结果为空"

    if len(results) > max_rows:
        display_results = results[:max_rows]
        suffix = f"\n... (共 {len(results)} 条记录，仅显示前 {max_rows} 条)"
    else:
        display_results = results
        suffix = ""

    # 简单的表格格式
    if display_results:
        keys = list(display_results[0].keys())
        lines = [" | ".join(str(k) for k in keys)]
        lines.append("-" * len(lines[0]))
        for row in display_results:
            lines.append(" | ".join(str(row.get(k, "")) for k in keys))
        return "\n".join(lines) + suffix

    return "查询结果为空"


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
