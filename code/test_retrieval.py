"""
测试混合检索策略
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from database.metadata import metadata_manager
from rich.console import Console
from rich.table import Table

console = Console()


def test_keyword_matching():
    """测试关键词匹配"""
    console.print("\n[bold cyan]测试1: 关键词匹配[/bold cyan]")

    test_cases = [
        ("查询所有产品", ["products"]),
        ("张三买了什么", ["customers", "orders"]),
        ("订单总金额", ["orders"]),
        ("库存不足的商品", ["products"]),
        ("电子产品有哪些", ["products", "categories"]),
    ]

    for query, expected_tables in test_cases:
        console.print(f"\n[yellow]查询:[/yellow] {query}")

        # 纯关键词匹配
        results = metadata_manager.search_relevant_tables(
            query,
            top_k=3,
            keyword_weight=1.0,
            vector_weight=0.0,
            expand_related=False
        )
        console.print(f"[green]关键词匹配结果:[/green] {results}")

        # 检查是否包含预期表
        matched = any(table in results for table in expected_tables)
        status = "✓" if matched else "✗"
        console.print(f"[{'green' if matched else 'red'}]{status}[/] 预期包含: {expected_tables}")


def test_vector_search():
    """测试向量检索"""
    console.print("\n[bold cyan]测试2: 向量检索[/bold cyan]")

    test_cases = [
        "我想知道哪些用户购买了手机",
        "最近一个月的销售情况如何",
        "哪个类别的商品最受欢迎",
    ]

    for query in test_cases:
        console.print(f"\n[yellow]查询:[/yellow] {query}")

        # 纯向量检索
        results = metadata_manager.search_relevant_tables(
            query,
            top_k=3,
            keyword_weight=0.0,
            vector_weight=1.0,
            expand_related=False
        )
        console.print(f"[green]向量检索结果:[/green] {results}")


def test_hybrid_search():
    """测试混合检索"""
    console.print("\n[bold cyan]测试3: 混合检索（关键词 + 向量）[/bold cyan]")

    test_cases = [
        "查询张三购买的所有产品",
        "库存低于50的电子产品",
        "2024年订单总额",
    ]

    for query in test_cases:
        console.print(f"\n[yellow]查询:[/yellow] {query}")

        # 混合检索
        results = metadata_manager.search_relevant_tables(
            query,
            top_k=3,
            keyword_weight=0.6,
            vector_weight=0.4,
            expand_related=False
        )
        console.print(f"[green]混合检索结果:[/green] {results}")


def test_related_expansion():
    """测试关联表扩展"""
    console.print("\n[bold cyan]测试4: 关联表扩展[/bold cyan]")

    test_cases = [
        ("查询产品信息", "products"),
        ("查询订单", "orders"),
        ("客户数据", "customers"),
    ]

    for query, main_table in test_cases:
        console.print(f"\n[yellow]查询:[/yellow] {query}")

        # 不扩展
        results_no_expand = metadata_manager.search_relevant_tables(
            query,
            top_k=2,
            expand_related=False
        )
        console.print(f"[blue]不扩展:[/blue] {results_no_expand}")

        # 扩展关联表
        results_expand = metadata_manager.search_relevant_tables(
            query,
            top_k=2,
            expand_related=True
        )
        console.print(f"[green]扩展后:[/green] {results_expand}")

        # 显示关联关系
        if main_table in results_no_expand:
            related = metadata_manager.get_related_tables(main_table)
            console.print(f"[dim]{main_table}的关联表: {related}[/dim]")


def test_schema_context():
    """测试schema上下文生成"""
    console.print("\n[bold cyan]测试5: Schema上下文生成[/bold cyan]")

    tables = ["products", "categories"]
    context = metadata_manager.get_schema_context(
        tables,
        include_examples=True,
        include_relationships=True
    )

    console.print("\n[yellow]生成的Schema上下文:[/yellow]")
    console.print(context[:1000] + "..." if len(context) > 1000 else context)


def compare_strategies():
    """对比不同策略的效果"""
    console.print("\n[bold cyan]测试6: 策略对比[/bold cyan]")

    query = "查询张三买了哪些电子产品"
    console.print(f"\n[yellow]查询:[/yellow] {query}\n")

    table = Table(title="不同策略的检索结果")
    table.add_column("策略", style="cyan")
    table.add_column("结果", style="green")

    # 纯关键词
    kw_results = metadata_manager.search_relevant_tables(
        query, top_k=3, keyword_weight=1.0, vector_weight=0.0, expand_related=False
    )
    table.add_row("纯关键词", str(kw_results))

    # 纯向量
    vec_results = metadata_manager.search_relevant_tables(
        query, top_k=3, keyword_weight=0.0, vector_weight=1.0, expand_related=False
    )
    table.add_row("纯向量", str(vec_results))

    # 混合(6:4)
    hybrid_results = metadata_manager.search_relevant_tables(
        query, top_k=3, keyword_weight=0.6, vector_weight=0.4, expand_related=False
    )
    table.add_row("混合(6:4)", str(hybrid_results))

    # 混合+扩展
    expand_results = metadata_manager.search_relevant_tables(
        query, top_k=3, keyword_weight=0.6, vector_weight=0.4, expand_related=True
    )
    table.add_row("混合+扩展", str(expand_results))

    console.print(table)


def main():
    console.print("[bold magenta]混合检索策略测试[/bold magenta]")

    test_keyword_matching()
    test_vector_search()
    test_hybrid_search()
    test_related_expansion()
    test_schema_context()
    compare_strategies()

    console.print("\n[bold green]测试完成！[/bold green]")


if __name__ == "__main__":
    main()
