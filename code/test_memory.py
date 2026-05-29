from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, Optional, Any
from config import get_llm
import operator
from langchain_core.messages import HumanMessage, AIMessage
from rich.console import Console
from rich.panel import Panel
console = Console()

class AgentState(TypedDict):
    user_query: str
    session_id: str
    messages: Annotated[list[Any], operator.add]

def ask_user_node(state: AgentState) -> dict[str, Any]:

    llm = get_llm()
    user_query = state["user_query"]
    history = state.get("messages", [])
    messages = history + [HumanMessage(content=user_query)]
    print("####################")
    print(messages)
    print("####################")
    response = llm.invoke(messages)
    return {
        "messages": [HumanMessage(content=user_query), AIMessage(content=response.content)]
    }

# 1. 创建内存保存器
memory_saver = MemorySaver()

# 2. 构建图时传入 checkpointer
builder = StateGraph(AgentState)
builder.add_node("ask_user", ask_user_node)
builder.add_edge(START, "ask_user")
builder.add_edge("ask_user", END)

graph = builder.compile(checkpointer=memory_saver)

# 3. 配置 thread_id（Checkpoint 的命名空间，必须唯一）
config = {"configurable": {"thread_id": "session_abc123"}}

# 4. 执行（支持中断）
result = graph.invoke({"user_query": "你是一个复读机，从下一轮开始，我说什么你就得重复什么"}, config)
console.print(Panel(
    result["messages"][-1].content,
    title="[bold yellow]模型回复[/bold yellow]",
    border_style="yellow"
))

result = graph.invoke({"user_query": "啊吧啊吧"}, config)
console.print(Panel(
    result["messages"][-1].content,
    title="[bold yellow]模型回复[/bold yellow]",
    border_style="yellow"
))
