"""
SQLAgent主程序
基于LangGraph的智能问数系统
"""
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from agent.graph import compiled_graph
from agent.state import AgentState
from database.connection import initialize_demo_db
from config import config

console = Console()


def run_query(user_query: str, session_id: str = None) -> dict:
    """运行单个查询"""
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

    # 执行图
    result = compiled_graph.invoke(initial_state)
    return result


def interactive_mode():
    """交互式问答模式"""
    console.print(Panel.fit(
        "[bold cyan]SQLAgent - 智能问数系统[/bold cyan]\n"
        "基于LangGraph的Text-to-SQL系统\n"
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

            result = run_query(user_input, session_id)
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

    args = parser.parse_args()

    if args.init_db:
        console.print("[cyan]正在初始化演示数据库...[/cyan]")
        initialize_demo_db()
        console.print("[green]数据库初始化完成！[/green]")
        return

    if args.query:
        result = run_query(args.query)
        console.print(Panel(
            result.get("final_answer", "无结果"),
            title="[bold green]回答[/bold green]",
            border_style="green"
        ))
        if result.get("generated_sql"):
            console.print(f"\n[dim]SQL: {result['generated_sql']}[/dim]")
        return

    # 默认进入交互式模式
    interactive_mode()


if __name__ == "__main__":
    main()
