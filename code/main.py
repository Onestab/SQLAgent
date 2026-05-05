"""
SQLAgent主程序
基于LangGraph的智能问数系统
"""
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from agent.graph import compiled_graph
from agent.state import AgentState
from agent.nodes import set_verbose_config
from database.connection import initialize_demo_db
from config import config

console = Console()

# 全局配置
VERBOSE_CONFIG = {
    "show_intent": False,
    "show_schema_linking": False,
    "show_agentic_process": False,
    "show_validation": False,
    "show_retry": False,
    "show_execution_details": False
}


def run_query(user_query: str, session_id: str = None, verbose: bool = False) -> dict:
    """运行单个查询

    Args:
        user_query: 用户查询
        session_id: 会话ID
        verbose: 是否显示详细的中间过程
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    # 初始化状态
    initial_state: AgentState = {
        "user_query": user_query,
        "session_id": session_id,
        "intent": "",
        "relevant_tables": [],
        "schema_context": "",
        "generated_sql": "",
        "sql_validation_result": "",
        "retry_count": 0,
        "query_results": [],
        "execution_error": None,
        "final_answer": "",
        "error_message": None,
        "llm_messages": []
    }

    if verbose or VERBOSE_CONFIG["show_agentic_process"]:
        console.print("[dim]开始执行查询流程...[/dim]")

    # 执行图
    result = compiled_graph.invoke(initial_state)

    # 显示中间过程
    if verbose or VERBOSE_CONFIG["show_intent"]:
        if result.get("intent"):
            console.print(Panel(
                result["intent"],
                title="[bold cyan]意图识别[/bold cyan]",
                border_style="cyan"
            ))

    if verbose or VERBOSE_CONFIG["show_schema_linking"]:
        if result.get("relevant_tables"):
            table = Table(title="相关表识别", show_header=True, header_style="bold magenta")
            table.add_column("表名", style="cyan")
            for tbl in result["relevant_tables"]:
                table.add_row(tbl)
            console.print(table)

    if verbose or VERBOSE_CONFIG["show_validation"]:
        if result.get("sql_validation_result"):
            console.print(f"[dim]SQL验证: {result['sql_validation_result']}[/dim]")

    if verbose or VERBOSE_CONFIG["show_retry"]:
        if result.get("retry_count", 0) > 0:
            console.print(f"[yellow]重试次数: {result['retry_count']}[/yellow]")
            if result.get("execution_error"):
                console.print(f"[yellow]错误信息: {result['execution_error']}[/yellow]")

    if verbose or VERBOSE_CONFIG["show_execution_details"]:
        if result.get("query_results"):
            console.print(f"[dim]执行成功，返回 {len(result['query_results'])} 条记录[/dim]")

    return result


def interactive_mode(verbose: bool = False):
    """交互式问答模式

    Args:
        verbose: 是否显示详细的中间过程
    """
    console.print(Panel.fit(
        "[bold cyan]SQLAgent - 智能问数系统[/bold cyan]\n"
        "基于LangGraph的Text-to-SQL系统\n"
        f"详细模式: {'开启' if verbose else '关闭'}\n"
        "输入 'exit' 或 'quit' 退出",
        border_style="cyan"
    ))

    session_id = str(uuid.uuid4())

    while True:
        try:
            user_input = console.input("\n[bold green]您的问题:[/bold green] ")

            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("[yellow]再见！[/yellow]")
                break

            if not user_input.strip():
                continue

            console.print("\n[dim]正在处理您的查询...[/dim]\n")

            result = run_query(user_input, session_id, verbose=verbose)
            # 显示闲聊回复
            if result.get("chat_mode") == "common":
                console.print(Panel(
                    result["llm_messages"][-1].content,
                    title="[bold yellow]模型回复[/bold yellow]",
                    border_style="yellow"
                ))

            # 显示生成的SQL
            if result.get("generated_sql"):
                console.print(Panel(
                    result["generated_sql"],
                    title="[bold blue]生成的SQL[/bold blue]",
                    border_style="blue"
                ))

            # 显示查询结果
            if result.get("query_results"):
                results = result["query_results"]
                console.print(f"\n[dim]查询返回 {len(results)} 条记录[/dim]")

            # 显示最终答案
            if result.get("final_answer"):
                console.print(Panel(
                    Markdown(result["final_answer"]),
                    title="[bold green]回答[/bold green]",
                    border_style="green"
                ))

            # 显示错误信息
            if result.get("error_message"):
                console.print(Panel(
                    result["error_message"],
                    title="[bold red]错误[/bold red]",
                    border_style="red"
                ))

        except KeyboardInterrupt:
            console.print("\n[yellow]再见！[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {str(e)}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="SQLAgent - 智能问数系统")
    parser.add_argument("--init-db", action="store_true", help="初始化演示数据库")
    parser.add_argument("--query", type=str, help="直接执行查询")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细的中间过程（意图识别、Schema链接、验证、重试等）")
    parser.add_argument("--show-intent", action="store_true", help="显示意图识别结果")
    parser.add_argument("--show-schema", action="store_true", help="显示Schema链接过程")
    parser.add_argument("--show-agentic", action="store_true", help="显示AgenticRAG的检索过程")
    parser.add_argument("--show-validation", action="store_true", help="显示SQL验证结果")
    parser.add_argument("--show-retry", action="store_true", help="显示错误重试过程")
    parser.add_argument("--show-execution", action="store_true", help="显示SQL执行详情")

    args = parser.parse_args()

    # 设置详细输出配置
    if args.verbose:
        VERBOSE_CONFIG["show_intent"] = True
        VERBOSE_CONFIG["show_schema_linking"] = True
        VERBOSE_CONFIG["show_agentic_process"] = True
        VERBOSE_CONFIG["show_validation"] = True
        VERBOSE_CONFIG["show_retry"] = True
        VERBOSE_CONFIG["show_execution_details"] = True
    else:
        if args.show_intent:
            VERBOSE_CONFIG["show_intent"] = True
        if args.show_schema:
            VERBOSE_CONFIG["show_schema_linking"] = True
        if args.show_agentic:
            VERBOSE_CONFIG["show_agentic_process"] = True
        if args.show_validation:
            VERBOSE_CONFIG["show_validation"] = True
        if args.show_retry:
            VERBOSE_CONFIG["show_retry"] = True
        if args.show_execution:
            VERBOSE_CONFIG["show_execution_details"] = True

    # 将配置传递给nodes模块
    set_verbose_config(VERBOSE_CONFIG)

    if args.init_db:
        console.print("[cyan]正在初始化演示数据库...[/cyan]")
        initialize_demo_db()
        console.print("[green]数据库初始化完成！[/green]")
        return

    if args.query:
        result = run_query(args.query, verbose=args.verbose)
        console.print(Panel(
            result.get("final_answer", "无结果"),
            title="[bold green]回答[/bold green]",
            border_style="green"
        ))
        if result.get("generated_sql"):
            console.print(f"\n[dim]SQL: {result['generated_sql']}[/dim]")
        return

    # 默认进入交互式模式
    interactive_mode(verbose=args.verbose)


if __name__ == "__main__":
    main()
