# SQLAgent SEE Frontend Streaming API

本文档定义 SQLAgent 当前 SEE 事件流对前端的推荐接入方式，用于实现类似市面上常见大模型产品的聊天界面。

结论先说：

1. 当前后端**具备支持前端流式界面的基础能力**。
2. 前端**不要消费 CLI 文本输出**。
3. 前端应消费**结构化事件流**，推荐通过 **SSE** 或 **chunked JSON stream** 暴露。
4. 当前事件语义已经足够支撑：
   - 思考区
   - 工具调用区
   - SQL 区
   - 最终回答区
   - 节点状态时间线

## 1. 推荐总体方案

前端与后端交互建议分两层：

1. 请求层
   - 前端发起一次对话请求
   - 后端启动一次 graph run
2. 事件层
   - 后端将 LangGraph 的结构化事件转为前端可消费的 SEE 事件
   - 前端按事件逐步更新消息 UI

推荐传输协议：

- 首选：`text/event-stream`（SSE）
- 备选：`application/x-ndjson`

不推荐：

- 直接把 CLI 渲染后的文本推给前端
- 让前端解析终端格式，比如 `┌─ THINK`

## 2. 当前后端真实可用的事件来源

当前代码中，事件来自两部分：

1. LangGraph `tasks` 事件
   - 节点开始
   - 节点结束

2. 自定义 `custom` 事件
   - `llm_stage`
   - `llm_reasoning_chunk`
   - `llm_answer_chunk`
   - `decision`
   - `agent_task_start`
   - `agent_task_end`
   - `agent_message_chunk`
   - `tool_result`
   - `schema_linking_context`
   - `schema_linking_result`
   - `schema_linking_fallback`
   - `retry`
   - `sql_dialect_adapted`
   - `sql_dialect_adaptation_failed`
   - `sql_generated`
   - `sql_validation_start`
   - `sql_validation_end`
   - `sql_execution_start`
   - `sql_execution_end`

说明：

- 当前这些事件已经足够支持前端 UI。
- 前端不需要直接理解 LangGraph，只需要消费统一包装后的 SEE 事件。

## 3. 推荐前端接口

## 3.1 发起一次对话

`POST /api/chat/stream`

请求体：

```json
{
  "session_id": "optional-session-id",
  "message": "历史消费金额最大的订单是谁",
  "stream": true
}
```

响应头：

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

## 3.2 SSE 事件格式

推荐每条 SSE event 使用：

```text
event: see
data: {"seq":1,"type":"run.started","run_id":"...","session_id":"...","payload":{...}}
```

结束时：

```text
event: done
data: {"seq":999,"type":"run.completed","run_id":"...","payload":{}}
```

失败时：

```text
event: error
data: {"seq":999,"type":"run.failed","run_id":"...","payload":{"message":"..."}}
```

## 4. 推荐 SEE 统一事件封装

虽然当前后端内部是 `tasks/custom/values`，但对前端建议统一包装成下面的格式：

```json
{
  "seq": 12,
  "type": "llm.reasoning.delta",
  "run_id": "run-uuid",
  "session_id": "session-uuid",
  "node": "intent_recognition",
  "stage": "intent_recognition",
  "ts": "2026-05-30T10:00:00Z",
  "payload": {
    "text": "用户输入是问候语，不需要查库。"
  }
}
```

字段说明：

- `seq`: 单次 run 内严格递增序号
- `type`: 事件类型
- `run_id`: 本次问答运行 ID
- `session_id`: 会话 ID
- `node`: 当前节点名，可为空
- `stage`: 当前逻辑阶段名，可为空
- `ts`: 时间戳
- `payload`: 事件实际内容

## 5. 事件类型定义

以下是推荐前端直接消费的标准事件类型，以及它们与当前后端事件的映射关系。

## 5.1 生命周期事件

### `run.started`

表示一次问答开始。

```json
{
  "type": "run.started",
  "payload": {
    "user_message": "你好"
  }
}
```

### `run.completed`

表示一次问答正常结束。

```json
{
  "type": "run.completed",
  "payload": {}
}
```

### `run.failed`

表示一次问答失败。

```json
{
  "type": "run.failed",
  "payload": {
    "message": "Connection error"
  }
}
```

## 5.2 节点状态事件

### `node.started`

来源：LangGraph `tasks` 开始事件

```json
{
  "type": "node.started",
  "node": "intent_recognition",
  "payload": {
    "label": "意图识别"
  }
}
```

### `node.completed`

来源：LangGraph `tasks` 结束事件

```json
{
  "type": "node.completed",
  "node": "intent_recognition",
  "payload": {
    "label": "意图识别"
  }
}
```

### `node.failed`

```json
{
  "type": "node.failed",
  "node": "sql_execution",
  "payload": {
    "label": "SQL 执行",
    "error": "column not found"
  }
}
```

## 5.3 思考流事件

### `llm.reasoning.started`

来源：`llm_stage` + `status=start`

```json
{
  "type": "llm.reasoning.started",
  "stage": "intent_recognition",
  "payload": {}
}
```

### `llm.reasoning.delta`

来源：`llm_reasoning_chunk`

```json
{
  "type": "llm.reasoning.delta",
  "stage": "intent_recognition",
  "payload": {
    "text": "判断当前用户只是问候。"
  }
}
```

### `llm.reasoning.completed`

来源：`llm_stage` + `status=end`

```json
{
  "type": "llm.reasoning.completed",
  "stage": "intent_recognition",
  "payload": {}
}
```

## 5.4 结论/回答流事件

### `llm.answer.delta`

来源：`llm_answer_chunk`

```json
{
  "type": "llm.answer.delta",
  "stage": "result_interpretation",
  "payload": {
    "text": "历史消费金额最大的订单是..."
  }
}
```

说明：

- 当 `stage = intent_recognition`，这表示“意图识别后的规范化结论”
- 当 `stage = sql_generation`，这表示模型生成 SQL 时的文本流
- 当 `stage = result_interpretation`，这表示最终用户可见答案流

## 5.5 路由决策事件

### `decision.route`

来源：`decision`

```json
{
  "type": "decision.route",
  "node": "intent_recognition",
  "payload": {
    "route": "common_chat"
  }
}
```

可能值：

- `common_chat`
- `sql`

## 5.6 工具和 Agent 事件

### `agent.task.started`

来源：`agent_task_start`

```json
{
  "type": "agent.task.started",
  "node": "agentic_schema_linking",
  "payload": {
    "task": "agent"
  }
}
```

### `agent.task.completed`

来源：`agent_task_end`

```json
{
  "type": "agent.task.completed",
  "node": "agentic_schema_linking",
  "payload": {
    "task": "tools",
    "error": null
  }
}
```

### `agent.message.delta`

来源：`agent_message_chunk`

```json
{
  "type": "agent.message.delta",
  "node": "agentic_schema_linking",
  "payload": {
    "source": "agent",
    "text": "先搜索订单表..."
  }
}
```

### `tool.result`

来源：`tool_result`

```json
{
  "type": "tool.result",
  "node": "agentic_schema_linking",
  "payload": {
    "tool": "search_relevant_tables",
    "output": "[\"orders\", \"customers\"]"
  }
}
```

## 5.7 Schema Linking 事件

### `schema.context`

来源：`schema_linking_context`

```json
{
  "type": "schema.context",
  "payload": {
    "user_query": "查询消费最高的用户",
    "intent": "查询累计消费最高的客户"
  }
}
```

### `schema.result`

来源：`schema_linking_result`

```json
{
  "type": "schema.result",
  "payload": {
    "tables": ["orders", "customers"]
  }
}
```

### `schema.fallback`

来源：`schema_linking_fallback`

```json
{
  "type": "schema.fallback",
  "payload": {
    "method": "metadata_search"
  }
}
```

## 5.8 SQL 事件

### `sql.retry`

来源：`retry`

```json
{
  "type": "sql.retry",
  "node": "sql_generation",
  "payload": {
    "retry_count": 1,
    "error": "Unknown column"
  }
}
```

### `sql.dialect_adapted`

来源：`sql_dialect_adapted`

```json
{
  "type": "sql.dialect_adapted",
  "payload": {
    "source_sql": "SELECT 'a' || 'b'",
    "adapted_sql": "SELECT CONCAT('a', 'b')",
    "target_dialect": "mysql"
  }
}
```

### `sql.dialect_adaptation_failed`

来源：`sql_dialect_adaptation_failed`

```json
{
  "type": "sql.dialect_adaptation_failed",
  "payload": {
    "source_sql": "SELECT ...",
    "target_dialect": "postgresql",
    "error": "..."
  }
}
```

### `sql.generated`

来源：`sql_generated`

```json
{
  "type": "sql.generated",
  "payload": {
    "sql": "SELECT * FROM orders LIMIT 10"
  }
}
```

### `sql.validation.started`

来源：`sql_validation_start`

```json
{
  "type": "sql.validation.started",
  "payload": {}
}
```

### `sql.validation.completed`

来源：`sql_validation_end`

```json
{
  "type": "sql.validation.completed",
  "payload": {
    "status": "valid",
    "statement_type": "SELECT"
  }
}
```

失败：

```json
{
  "type": "sql.validation.completed",
  "payload": {
    "status": "invalid",
    "error": "Unsupported statement type"
  }
}
```

### `sql.execution.started`

来源：`sql_execution_start`

```json
{
  "type": "sql.execution.started",
  "payload": {
    "sql": "SELECT ..."
  }
}
```

### `sql.execution.completed`

来源：`sql_execution_end`

```json
{
  "type": "sql.execution.completed",
  "payload": {
    "row_count": 10
  }
}
```

失败：

```json
{
  "type": "sql.execution.completed",
  "payload": {
    "error": "SQL execution error: ..."
  }
}
```

## 6. 前端推荐 UI 组织方式

前端每次 assistant 响应建议组织为 5 个区块：

1. `status_timeline`
   - 节点开始/结束
   - 路由决策
   - 校验/执行状态

2. `thinking`
   - 来自 `llm.reasoning.*`
   - 默认可折叠

3. `tool_calls`
   - Agent 规划
   - 工具调用
   - 工具结果
   - 相关表识别

4. `sql`
   - `sql.generated`
   - `sql.dialect_adapted`
   - `sql.validation.completed`

5. `final_answer`
   - `stage = result_interpretation` 的 `llm.answer.delta`

## 7. 前端状态机建议

每一轮 assistant 消息建议维护如下状态：

```ts
type AssistantTurn = {
  runId: string
  sessionId: string
  status: "streaming" | "completed" | "failed"
  nodes: Array<{
    name: string
    status: "running" | "completed" | "failed"
    error?: string
  }>
  thinkingText: string
  toolLogs: Array<{
    type: string
    text?: string
    tool?: string
    output?: string
  }>
  sql?: string
  sqlValidation?: {
    status: "valid" | "invalid"
    error?: string
    statementType?: string
  }
  execution?: {
    rowCount?: number
    error?: string
  }
  finalAnswer: string
}
```

## 8. 前端事件处理建议

### 8.1 对 `llm.reasoning.delta`

- 追加到 `thinkingText`
- 默认折叠显示

### 8.2 对 `agent.message.delta`

- 追加到工具日志
- 按 `source=agent / tool` 分组

### 8.3 对 `tool.result`

- 作为离散日志项追加
- 可只显示摘要

### 8.4 对 `sql.generated`

- 覆盖当前 SQL 面板内容

### 8.5 对 `llm.answer.delta`

- 如果 `stage = result_interpretation`
  - 追加到 `finalAnswer`
- 如果 `stage = intent_recognition`
  - 可放在隐藏诊断区，也可不展示

## 9. 当前格式能否直接支持前端

答案：

- **能支持**
- 但**不能直接把当前 CLI 格式给前端**

原因：

1. 当前 CLI 输出已经是渲染后的终端视图，不适合前端复用
2. 前端真正需要的是结构化语义事件，而不是 `┌─ THINK` 这种字符串
3. 当前底层事件语义已经够了，只差一层“API 输出规范化”

所以，当前最合理的后端改造方向不是重写节点，而是增加一个“前端流事件适配层”：

```text
LangGraph tasks/custom
  -> SEE event mapper
    -> SSE output
      -> Frontend UI
```

## 10. 后端建议补充但非必须

当前事件已经够用，但为了让前端开发更舒服，建议后端再补下面几个字段：

1. `run_id`
2. `seq`
3. `ts`
4. 标准化 `type`
5. 标准化 `payload`

这层可以在 HTTP handler 里做，不一定要改节点内部事件定义。

## 11. 前端开发建议

建议前端优先实现：

1. 普通聊天消息流
2. 可折叠思考区
3. 工具调用时间线
4. SQL 展示卡片
5. 错误态和重试态

建议先不要实现：

1. 对所有内部节点做复杂可视化 DAG
2. 对工具结果做深层结构化渲染
3. 对历史事件做复杂回放

因为当前事件流最成熟的部分是“聊天消息 + 思考 + 工具日志 + SQL + 最终回答”。

## 12. 推荐前端落地顺序

1. 先按本文档接一个基础 SSE 客户端
2. 完成 `thinking / tool / final` 三个区块
3. 再补节点时间线与 SQL 卡片
4. 最后再要求后端做更严格的 `type/seq/run_id` 统一封装
