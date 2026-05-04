"""
测试脚本
验证SQLAgent的各项功能
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from main import run_query
from database.connection import initialize_demo_db, list_tables_sync
from database.metadata import metadata_manager
from rich.console import Console

console = Console()


def test_database():
    """测试数据库连接"""
    console.print("\n[bold cyan]测试1: 数据库连接[/bold cyan]")
    try:
        tables = list_tables_sync()
        console.print(f"[green]✓[/green] 找到 {len(tables)} 个表: {', '.join(tables)}")
        return True
    except Exception as e:
        console.print(f"[red]✗[/red] 数据库连接失败: {e}")
        return False


def test_metadata():
    """测试元数据系统"""
    console.print("\n[bold cyan]测试2: 元数据系统[/bold cyan]")
    try:
        # 测试表描述
        desc = metadata_manager.get_table_description("products")
        console.print(f"[green]✓[/green] products表描述: {desc[:50]}...")

        # 测试向量检索
        relevant = metadata_manager.search_relevant_tables("查询所有订单", top_k=2)
        console.print(f"[green]✓[/green] 相关表检索: {relevant}")
        return True
    except Exception as e:
        console.print(f"[red]✗[/red] 元数据系统失败: {e}")
        return False


def test_queries():
    """测试查询功能"""
    console.print("\n[bold cyan]测试3: 查询功能[/bold cyan]")

    test_cases = [
        "查询所有产品",
        "有多少个客户？",
        "张三买了什么？",
        "电子产品有哪些？",
        "订单总金额是多少？"
    ]

    passed = 0
    for i, query in enumerate(test_cases, 1):
        console.print(f"\n[yellow]测试用例 {i}:[/yellow] {query}")
        try:
            result = run_query(query)
            if result.get("final_answer") and not result.get("error_message"):
                console.print(f"[green]✓[/green] SQL: {result.get('generated_sql', 'N/A')[:80]}...")
                console.print(f"[green]✓[/green] 答案: {result.get('final_answer', 'N/A')[:100]}...")
                passed += 1
            else:
                console.print(f"[red]✗[/red] 查询失败: {result.get('error_message', 'Unknown error')}")
        except Exception as e:
            console.print(f"[red]✗[/red] 异常: {e}")

    console.print(f"\n[bold]通过: {passed}/{len(test_cases)}[/bold]")
    return passed == len(test_cases)


def main():
    """运行所有测试"""
    console.print("[bold magenta]SQLAgent 功能测试[/bold magenta]")

    # 初始化数据库
    console.print("\n[cyan]初始化测试数据库...[/cyan]")
    try:
        initialize_demo_db()
        console.print("[green]✓[/green] 数据库初始化成功")
    except Exception as e:
        console.print(f"[red]✗[/red] 数据库初始化失败: {e}")
        return

    # 运行测试
    results = []
    results.append(test_database())
    results.append(test_metadata())
    results.append(test_queries())

    # 总结
    console.print("\n" + "="*50)
    passed = sum(results)
    total = len(results)
    if passed == total:
        console.print(f"[bold green]所有测试通过! ({passed}/{total})[/bold green]")
    else:
        console.print(f"[bold yellow]部分测试失败: {passed}/{total}[/bold yellow]")


if __name__ == "__main__":
    main()
