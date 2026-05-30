"""
SQLAgent主程序
基于LangGraph的智能问数系统
"""
from contextlib import contextmanager
from pathlib import Path
import uuid
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from agent.graph import build_graph
from agent.state import AgentState
from config import config
from database.connection import initialize_demo_db
from langgraph.checkpoint.sqlite import SqliteSaver
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

class CliStreamRenderer:
    """渲染LangGraph流事件。"""

    def __init__(self, console: Console):
        self.console = console
        self._active_llm_stage: tuple[str, str] | None = None
        self._active_agent_source: str | None = None
        self._node_status: dict[str, str] = {}
        self._section_open: str | None = None
        self._llm_accumulated: dict[tuple[str, str], str] = {}

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
            self._open_section("status", "STATUS", "cyan")
            self.console.print(f"[bold cyan]●[/bold cyan] {label}")
            return

        self._flush_llm_stream()
        self._flush_agent_stream()
        self._open_section("status", "STATUS", "cyan")
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
            self._open_section("status", "STATUS", "cyan")
            self.console.print(f"[dim]→ {text}[/dim]")
        elif event_name == "agent_task_start":
            task = data.get("task")
            self._open_section("tool", "TOOL", "yellow")
            if task == "agent":
                self.console.print("[dim]  Agent 正在规划下一步[/dim]")
            elif task == "tools":
                self.console.print("[dim]  Agent 正在调用工具[/dim]")
        elif event_name == "tool_result":
            self._open_section("tool", "TOOL", "yellow")
            tool = data.get("tool", "tool")
            output = (data.get("output") or "").strip()
            summary = output if output else "工具已返回结果"
            self.console.print(f"[yellow]  ↳ {tool}[/yellow] {summary}")
        elif event_name == "schema_linking_result":
            self._open_section("tool", "TOOL", "yellow")
            tables = ", ".join(data.get("tables", []))
            self.console.print(f"[dim]  相关表: {tables}[/dim]")
        elif event_name == "schema_linking_fallback":
            self._open_section("tool", "TOOL", "yellow")
            method = data.get("method")
            self.console.print(f"[dim]  回退检索: {method}[/dim]")
        elif event_name == "retry":
            self._open_section("status", "STATUS", "cyan")
            retry_count = data.get("retry_count", 0)
            error = data.get("error", "")
            self.console.print(f"[yellow]  重试 {retry_count + 1}: {error}[/yellow]")
        elif event_name == "sql_generated":
            self._flush_llm_stream()
            sql = data.get("sql", "")
            if sql:
                self._open_section("final", "FINAL", "green")
                self.console.print(Panel(sql, title="[bold blue]生成的SQL[/bold blue]", border_style="blue"))
        elif event_name == "sql_validation_start":
            self._open_section("status", "STATUS", "cyan")
            self.console.print("[dim]  正在校验 SQL[/dim]")
        elif event_name == "sql_validation_end":
            self._open_section("status", "STATUS", "cyan")
            status = data.get("status")
            if status == "valid":
                stmt_type = data.get("statement_type", "")
                suffix = f" ({stmt_type})" if stmt_type else ""
                self.console.print(f"[green]  SQL 校验通过{suffix}[/green]")
            else:
                self.console.print(f"[red]  SQL 校验失败[/red] {data.get('error', '')}")
        elif event_name == "sql_execution_start":
            self._open_section("status", "STATUS", "cyan")
            self.console.print("[dim]  正在执行 SQL[/dim]")
        elif event_name == "sql_execution_end":
            self._open_section("status", "STATUS", "cyan")
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
            if stage:
                self._llm_accumulated.pop((stage, "reasoning"), None)
                self._llm_accumulated.pop((stage, "answer"), None)
        elif status == "end":
            self._flush_llm_stream()
            self._active_llm_stage = None

    def _handle_llm_chunk(self, data: dict[str, Any], *, kind: str) -> None:
        text = data.get("text", "")
        stage = data.get("stage")
        if not text or not stage:
            return
        active_key = (stage, kind)
        text = self._sanitize_llm_chunk(stage, kind, text)
        if not text:
            return
        if self._active_llm_stage != active_key:
            self._flush_llm_stream()
            self._active_llm_stage = active_key
            if kind == "reasoning":
                self._open_section("think", "THINK", "magenta")
            else:
                section = "answer" if stage != "result_interpretation" else "final"
                title = "ANSWER" if stage != "result_interpretation" else "FINAL"
                color = "bright_cyan" if stage != "result_interpretation" else "green"
                self._open_section(section, title, color)
        self.console.print(text, end="", soft_wrap=True)
        self._llm_accumulated[active_key] = self._llm_accumulated.get(active_key, "") + text

    def _handle_agent_chunk(self, data: dict[str, Any]) -> None:
        source = data.get("source") or "agent"
        text = data.get("text", "")
        if not text:
            return
        if self._active_agent_source != source:
            self._flush_agent_stream()
            self._active_agent_source = source
            self._open_section("tool", "TOOL", "yellow")
            label = "Agent" if source == "agent" else f"Tool<{source}>"
            self.console.print(f"[yellow]  {label}:[/yellow] ", end="")
        self.console.print(text, end="", soft_wrap=True)

    def _open_section(self, section: str, title: str, color: str) -> None:
        if self._section_open == section:
            return
        self._flush_llm_stream()
        self._flush_agent_stream()
        if self._section_open is not None:
            self.console.print()
        header = Text()
        header.append("┌─ ", style=color)
        header.append(title, style=f"bold {color}")
        self.console.print(header)
        self._section_open = section

    def _sanitize_llm_chunk(self, stage: str, kind: str, text: str) -> str:
        active_key = (stage, kind)
        existing = self._llm_accumulated.get(active_key, "")
        if existing:
            return text

        normalized = text.lstrip()
        if kind == "reasoning":
            for prefix in ("思考：", "思考:", "推理：", "推理:"):
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix):].lstrip()
                    break
            return normalized

        for prefix in ("结论：", "结论:", "回答：", "回答:", "最终回答：", "最终回答:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].lstrip()
                break
        return normalized

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
        if self._section_open is not None:
            self.console.print()
            self._section_open = None


def ensure_checkpoint_db_path() -> Path:
    """确保 checkpoint sqlite 文件所在目录存在。"""
    checkpoint_path = Path(config.checkpoint_db_path).expanduser()
    if not checkpoint_path.is_absolute():
        checkpoint_path = Path(__file__).resolve().parent / checkpoint_path
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    return checkpoint_path


@contextmanager
def graph_session() -> Any:
    """创建绑定 SQLite checkpointer 的图会话。"""
    checkpoint_path = ensure_checkpoint_db_path()
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        yield build_graph(checkpointer)


def build_initial_state(user_input: str, session_id: str) -> AgentState:
    return dict(
        user_query=user_input,
        session_id=session_id,
        intent="",
        relevant_tables=[],
        common_reply="",
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

    if not stream and result.get("chat_mode") == "common":
        content = result.get("common_reply", "")
        if content:
            console.print(Panel(content, title="[bold yellow]模型回复[/bold yellow]", border_style="yellow"))

    if result.get("query_results"):
        results = result["query_results"]
        console.print(f"\n[dim]查询返回 {len(results)} 条记录[/dim]")

    if not stream and result.get("final_answer"):
        console.print(Panel(Markdown(result["final_answer"]), title="[bold green]最终回答[/bold green]", border_style="green"))

    if result.get("error_message"):
        console.print(Panel(result["error_message"], title="[bold red]错误[/bold red]", border_style="red"))


def interactive_mode(stream: bool = True, session_id: str | None = None) -> None:
    """交互式问答模式"""
    console.print(Panel.fit(
        "[bold cyan]SQLAgent - 智能问数系统[/bold cyan]\n"
        "基于LangGraph的Text-to-SQL系统\n"
        f"{'支持' if stream else '关闭'}流式显示思考、工具调用与节点流程\n"
        "输入 'exit' 或 'quit' 退出",
        border_style="cyan"
    ))

    session_id = session_id or str(uuid.uuid4())
    ckpt_config = {"configurable": {"thread_id": session_id}}

    with graph_session() as compiled_graph:
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
    parser.add_argument("--session-id", type=str, help="指定会话ID，用于复用历史记忆")

    args = parser.parse_args()
    stream = not args.no_stream

    if args.init_db:
        console.print("[cyan]正在初始化演示数据库...[/cyan]")
        initialize_demo_db()
        console.print("[green]数据库初始化完成！[/green]")
        return

    if args.query:
        session_id = args.session_id or str(uuid.uuid4())
        ckpt_config = {"configurable": {"thread_id": session_id}}
        initial_state = build_initial_state(args.query, session_id)
        with graph_session() as compiled_graph:
            process_single_query(
                user_input=args.query,
                session_id=session_id,
                compiled_graph=compiled_graph,
                initial_state=initial_state,
                checkpoint_config=ckpt_config,
                stream=stream,
            )
        return

    interactive_mode(stream=stream, session_id=args.session_id)


if __name__ == "__main__":
    main()
