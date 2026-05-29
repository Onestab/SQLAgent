"""
SQLAgent主程序
基于LangGraph的智能问数系统
"""
import uuid
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from agent.graph import build_graph
from agent.state import AgentState
from database.connection import initialize_demo_db
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph


console = Console()

NODE_LABELS = {
    "intent_recognition": "意图识别",
    "agentic_schema_linking": "Schema 检索",
    "sql_generation": "SQL 生成",
    "sql_validation": "SQL 验证",
    "sql_execution": "SQL 执行",
    "result_interpretation": "结果解释",
    "error_handler": "错误处理",
}

LLM_STAGE_LABELS = {
    "intent_recognition": "思考中",
    "sql_generation": "生成 SQL",
    "result_interpretation": "组织回答",
}

THINKING_STAGE_LABELS = {
    "intent_recognition": "思考",
    "sql_generation": "推理",
    "result_interpretation": "构思回答",
}

ANSWER_STAGE_LABELS = {
    "intent_recognition": "结论",
    "sql_generation": "SQL",
    "result_interpretation": "回答",
}


class CliStreamRenderer:
    """渲染LangGraph流事件。"""

    def __init__(self, console: Console):
        self.console = console
        self._active_llm_stage: tuple[str, str] | None = None
        self._active_agent_source: str | None = None
        self._node_status: dict[str, str] = {}

    def render(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        data = event.get("data", {})
        if event_type == "tasks":
            self._render_task_event(data)
            return
        if event_type == "custom":
            self._render_custom_event(data)
            return

    def _render_task_event(self, data: dict[str, Any]) -> None:
        node_name = data.get("name", "unknown")
        label = NODE_LABELS.get(node_name, node_name)
        if "input" in data:
            self._flush_llm_stream()
            self._flush_agent_stream()
            self._node_status[node_name] = "running"
            self.console.print(f"[bold cyan]●[/bold cyan] {label}")
            return

        self._flush_llm_stream()
        self._flush_agent_stream()
        error = data.get("error")
        if error:
            self._node_status[node_name] = "error"
            self.console.print(f"[bold red]×[/bold red] {label}: {error}")
        else:
            self._node_status[node_name] = "done"
            self.console.print(f"[green]✓[/green] {label}")

    def _render_custom_event(self, data: dict[str, Any]) -> None:
        event_name = data.get("event")
        if event_name == "llm_stage":
            self._handle_llm_stage(data)
        elif event_name == "llm_reasoning_chunk":
            self._handle_llm_chunk(data, kind="reasoning")
        elif event_name == "llm_answer_chunk":
            self._handle_llm_chunk(data, kind="answer")
        elif event_name == "decision":
            route = data.get("route")
            text = "普通对话" if route == "common_chat" else "进入 SQL 路径"
            self.console.print(f"[dim]→ {text}[/dim]")
        elif event_name == "agent_task_start":
            task = data.get("task")
            if task == "agent":
                self.console.print("[dim]  Agent 正在规划下一步[/dim]")
            elif task == "tools":
                self.console.print("[dim]  Agent 正在调用工具[/dim]")
        elif event_name == "tool_result":
            tool = data.get("tool", "tool")
            output = (data.get("output") or "").strip()
            summary = output if output else "工具已返回结果"
            self.console.print(f"[yellow]  ↳ {tool}[/yellow] {summary}")
        elif event_name == "schema_linking_result":
            tables = ", ".join(data.get("tables", []))
            self.console.print(f"[dim]  相关表: {tables}[/dim]")
        elif event_name == "schema_linking_fallback":
            method = data.get("method")
            self.console.print(f"[dim]  回退检索: {method}[/dim]")
        elif event_name == "retry":
            retry_count = data.get("retry_count", 0)
            error = data.get("error", "")
            self.console.print(f"[yellow]  重试 {retry_count + 1}: {error}[/yellow]")
        elif event_name == "sql_generated":
            self._flush_llm_stream()
            sql = data.get("sql", "")
            if sql:
                self.console.print(Panel(sql, title="[bold blue]生成的SQL[/bold blue]", border_style="blue"))
        elif event_name == "sql_validation_start":
            self.console.print("[dim]  正在校验 SQL[/dim]")
        elif event_name == "sql_validation_end":
            status = data.get("status")
            if status == "valid":
                stmt_type = data.get("statement_type", "")
                suffix = f" ({stmt_type})" if stmt_type else ""
                self.console.print(f"[green]  SQL 校验通过{suffix}[/green]")
            else:
                self.console.print(f"[red]  SQL 校验失败[/red] {data.get('error', '')}")
        elif event_name == "sql_execution_start":
            self.console.print("[dim]  正在执行 SQL[/dim]")
        elif event_name == "sql_execution_end":
            if data.get("error"):
                self.console.print(f"[red]  执行失败[/red] {data['error']}")
            else:
                self.console.print(f"[green]  执行完成，返回 {data.get('row_count', 0)} 条记录[/green]")
        elif event_name == "agent_message_chunk":
            self._handle_agent_chunk(data)

    def _handle_llm_stage(self, data: dict[str, Any]) -> None:
        stage = data.get("stage")
        status = data.get("status")
        if status == "start":
            self._flush_llm_stream()
        elif status == "end":
            self._flush_llm_stream()
            self._active_llm_stage = None

    def _handle_llm_chunk(self, data: dict[str, Any], *, kind: str) -> None:
        text = data.get("text", "")
        stage = data.get("stage")
        if not text or not stage:
            return
        active_key = (stage, kind)
        if self._active_llm_stage != active_key:
            self._flush_llm_stream()
            self._active_llm_stage = active_key
            if kind == "reasoning":
                label = THINKING_STAGE_LABELS.get(stage, "思考")
                style = "magenta"
            else:
                label = ANSWER_STAGE_LABELS.get(stage, LLM_STAGE_LABELS.get(stage, "输出"))
                style = "bright_cyan"
            self.console.print(f"[{style}]  {label}:[/{style}] ", end="")
        self.console.print(text, end="", soft_wrap=True)

    def _handle_agent_chunk(self, data: dict[str, Any]) -> None:
        source = data.get("source") or "agent"
        text = data.get("text", "")
        if not text:
            return
        if self._active_agent_source != source:
            self._flush_agent_stream()
            self._active_agent_source = source
            label = "Agent" if source == "agent" else f"Tool<{source}>"
            self.console.print(f"[yellow]  {label}:[/yellow] ", end="")
        self.console.print(text, end="", soft_wrap=True)

    def _flush_llm_stream(self) -> None:
        if self._active_llm_stage is not None:
            self.console.print()
            self._active_llm_stage = None

    def _flush_agent_stream(self) -> None:
        if self._active_agent_source is not None:
            self.console.print()
            self._active_agent_source = None

    def finalize(self) -> None:
        self._flush_llm_stream()
        self._flush_agent_stream()


def build_initial_state(user_input: str, session_id: str) -> AgentState:
    return dict(
        user_query=user_input,
        session_id=session_id,
        intent="",
        relevant_tables=[],
        schema_context="",
        generated_sql="",
        sql_validation_result="",
        retry_count=0,
        query_results=[],
        execution_error=None,
        final_answer="",
        error_message=None,
        chat_mode="",
        llm_messages=[],
    )


def run_query(
    user_query: str,
    session_id: str | None = None,
    compiled_graph: CompiledStateGraph | None = None,
    initial_state: AgentState | None = None,
    checkpoint_config: dict[str, Any] | None = None,
    stream: bool = True,
) -> dict[str, Any]:
    """运行单个查询。"""
    if session_id is None:
        session_id = str(uuid.uuid4())
    if compiled_graph is None:
        raise ValueError("compiled_graph is required")
    if initial_state is None:
        initial_state = build_initial_state(user_query, session_id)
    if checkpoint_config is None:
        checkpoint_config = {"configurable": {"thread_id": session_id}}

    if not stream:
        return compiled_graph.invoke(input=initial_state, config=checkpoint_config)

    renderer = CliStreamRenderer(console)
    final_state: dict[str, Any] | None = None
    try:
        for event in compiled_graph.stream(
            input=initial_state,
            config=checkpoint_config,
            stream_mode=["values", "tasks", "custom"],
            version="v2",
        ):
            renderer.render(event)
            if event.get("type") == "values":
                final_state = event.get("data")
    finally:
        renderer.finalize()
    return final_state or {}


def process_single_query(
    user_input: str | None = None,
    session_id: str | None = None,
    compiled_graph: CompiledStateGraph | None = None,
    initial_state: AgentState | None = None,
    checkpoint_config: dict[str, Any] | None = None,
    stream: bool = True,
) -> None:
    console.print("\n[dim]正在处理您的查询...[/dim]\n")

    result = run_query(
        user_input,
        session_id,
        compiled_graph,
        initial_state,
        checkpoint_config,
        stream=stream,
    )

    if not stream and result.get("chat_mode") == "common" and result.get("llm_messages"):
        last_message = result["llm_messages"][-1]
        content = getattr(last_message, "content", "")
        if content:
            console.print(Panel(content, title="[bold yellow]模型回复[/bold yellow]", border_style="yellow"))

    if result.get("query_results"):
        results = result["query_results"]
        console.print(f"\n[dim]查询返回 {len(results)} 条记录[/dim]")

    if not stream and result.get("final_answer"):
        console.print(Panel(Markdown(result["final_answer"]), title="[bold green]回答[/bold green]", border_style="green"))

    if result.get("error_message"):
        console.print(Panel(result["error_message"], title="[bold red]错误[/bold red]", border_style="red"))


def interactive_mode(stream: bool = True) -> None:
    """交互式问答模式"""
    console.print(Panel.fit(
        "[bold cyan]SQLAgent - 智能问数系统[/bold cyan]\n"
        "基于LangGraph的Text-to-SQL系统\n"
        f"{'支持' if stream else '关闭'}流式显示思考、工具调用与节点流程\n"
        "输入 'exit' 或 'quit' 退出",
        border_style="cyan"
    ))

    session_id = str(uuid.uuid4())
    ckpt_config = {"configurable": {"thread_id": session_id}}
    checkpointer = MemorySaver()
    compiled_graph = build_graph(checkpointer)

    while True:
        try:
            user_input = console.input("\n[bold green]您的问题:[/bold green] ")

            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]再见！[/yellow]")
                break

            if not user_input.strip():
                continue

            initial_state = build_initial_state(user_input, session_id)
            process_single_query(
                user_input,
                session_id=session_id,
                compiled_graph=compiled_graph,
                initial_state=initial_state,
                checkpoint_config=ckpt_config,
                stream=stream,
            )

        except KeyboardInterrupt:
            console.print("\n[yellow]再见！[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {str(e)}")


def main() -> None:
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="SQLAgent - 智能问数系统")
    parser.add_argument("--init-db", action="store_true", help="初始化演示数据库")
    parser.add_argument("--query", type=str, help="直接执行查询")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出")

    args = parser.parse_args()
    stream = not args.no_stream

    if args.init_db:
        console.print("[cyan]正在初始化演示数据库...[/cyan]")
        initialize_demo_db()
        console.print("[green]数据库初始化完成！[/green]")
        return

    if args.query:
        checkpointer = MemorySaver()
        compiled_graph = build_graph(checkpointer)
        session_id = str(uuid.uuid4())
        ckpt_config = {"configurable": {"thread_id": session_id}}
        initial_state = build_initial_state(args.query, session_id)
        process_single_query(
            user_input=args.query,
            session_id=session_id,
            compiled_graph=compiled_graph,
            initial_state=initial_state,
            checkpoint_config=ckpt_config,
            stream=stream,
        )
        return

    interactive_mode(stream=stream)


if __name__ == "__main__":
    main()
