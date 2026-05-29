# SQLAgent MCP Protocol

本文件定义 SQLAgent 未来接入外部 MCP 工具时的协议约定，覆盖两类能力：

- 元数据查询：`metadata.*`
- 数据库查询：`database.*`

目标：

1. Agent 只依赖稳定工具协议，不依赖本地实现细节。
2. 现有本地工具与未来 MCP 工具保持一致的输入输出语义。
3. 所有接口均为只读、结构化、可审计、可扩展。

## 1. 设计原则

1. 工具返回结构化数据，不把大段拼接文本作为唯一输出。
2. 元数据查询和数据库查询严格分层。
3. SQL 方言适配、校验、权限控制优先放在工具服务端。
4. Agent 节点只消费工具语义，不处理底层连接与路由。
5. 所有工具统一返回 `ok/data/error/meta` 四段结构。

## 2. 通用响应格式

成功：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "uuid",
    "server_time": "2026-05-29T12:00:00Z",
    "latency_ms": 42,
    "truncated": false,
    "source": "local|mcp"
  }
}
```

失败：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "SQL_VALIDATION_ERROR",
    "message": "column not found",
    "retryable": false
  },
  "meta": {
    "request_id": "uuid",
    "source": "local|mcp"
  }
}
```

## 3. 通用请求控制字段

所有查询类接口建议支持以下字段：

```json
{
  "datasource_id": "prod_ecommerce",
  "tenant_id": "optional",
  "trace_id": "agent-run-id",
  "timeout_ms": 10000,
  "max_rows": 100,
  "read_only": true
}
```

说明：

- `datasource_id`：数据源标识
- `tenant_id`：多租户场景可选
- `trace_id`：链路追踪
- `timeout_ms`：调用超时
- `max_rows`：结果行数上限
- `read_only`：必须为只读

## 4. 元数据工具协议

### 4.1 `metadata.describe_database`

请求：

```json
{
  "include_table_count": true
}
```

响应 `data`：

```json
{
  "database_name": "ecommerce",
  "table_count": 12,
  "tables": ["orders", "customers", "products"]
}
```

### 4.2 `metadata.search_tables`

请求：

```json
{
  "query": "近30天订单金额最高的客户",
  "top_k": 5,
  "include_scores": true
}
```

响应 `data`：

```json
{
  "tables": [
    {
      "table_name": "orders",
      "score": 0.92,
      "reason": "包含订单金额、创建时间"
    }
  ]
}
```

### 4.3 `metadata.get_table`

请求：

```json
{
  "table_name": "orders"
}
```

响应 `data`：

```json
{
  "table_name": "orders",
  "description": "订单主表",
  "business_context": "记录订单事实信息",
  "columns": [
    {
      "name": "order_id",
      "type": "integer",
      "description": "订单ID"
    }
  ],
  "relations": [
    {
      "target_table": "customers",
      "source_column": "customer_id",
      "target_column": "customer_id",
      "relation_type": "many_to_one"
    }
  ],
  "examples": [
    {
      "question": "金额最高的订单",
      "sql": "SELECT ..."
    }
  ]
}
```

### 4.4 `metadata.get_related_tables`

请求：

```json
{
  "table_name": "orders",
  "max_depth": 1
}
```

响应 `data`：

```json
{
  "table_name": "orders",
  "related_tables": [
    {
      "table_name": "customers",
      "relation_type": "many_to_one"
    }
  ]
}
```

### 4.5 `metadata.get_schema_context`

请求：

```json
{
  "table_names": ["orders", "customers"],
  "include_examples": true,
  "include_relations": true
}
```

响应 `data`：

```json
{
  "schema_context": "供LLM使用的文本化Schema上下文",
  "tables": [
    {
      "table_name": "orders",
      "columns": [
        {
          "name": "order_id",
          "type": "integer",
          "description": "订单ID"
        }
      ]
    }
  ]
}
```

说明：

- `schema_context` 用于喂给 LLM
- `tables` 用于未来严格结构化推理

### 4.6 `metadata.get_examples`

请求：

```json
{
  "table_name": "orders",
  "limit": 5
}
```

响应 `data`：

```json
{
  "examples": [
    {
      "question": "金额最高的订单",
      "sql": "SELECT ..."
    }
  ]
}
```

## 5. 数据库工具协议

### 5.1 `database.list_tables`

请求：

```json
{}
```

响应 `data`：

```json
{
  "tables": ["orders", "customers", "products"]
}
```

### 5.2 `database.get_table_schema`

请求：

```json
{
  "table_name": "orders"
}
```

响应 `data`：

```json
{
  "table_name": "orders",
  "columns": [
    {
      "name": "order_id",
      "type": "INTEGER",
      "nullable": false,
      "primary_key": true
    }
  ]
}
```

### 5.3 `database.validate_sql`

请求：

```json
{
  "sql": "SELECT * FROM orders LIMIT 10",
  "dialect": "sqlite"
}
```

响应 `data`：

```json
{
  "valid": true,
  "normalized_sql": "SELECT * FROM orders LIMIT 10",
  "statement_type": "SELECT",
  "warnings": []
}
```

### 5.4 `database.transpile_sql`

请求：

```json
{
  "sql": "SELECT 'a' || 'b'",
  "source_dialect": "ansi",
  "target_dialect": "mysql"
}
```

响应 `data`：

```json
{
  "sql": "SELECT CONCAT('a', 'b')",
  "source_dialect": "ansi",
  "target_dialect": "mysql"
}
```

### 5.5 `database.execute_sql`

请求：

```json
{
  "sql": "SELECT order_id, total_amount FROM orders LIMIT 20",
  "dialect": "sqlite",
  "max_rows": 100,
  "timeout_ms": 10000
}
```

响应 `data`：

```json
{
  "columns": [
    {"name": "order_id", "type": "INTEGER"},
    {"name": "total_amount", "type": "REAL"}
  ],
  "rows": [
    [1, 199.0],
    [2, 299.0]
  ],
  "row_count": 2
}
```

## 6. 错误码约定

建议统一使用：

- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `TIMEOUT`
- `RATE_LIMITED`
- `SQL_VALIDATION_ERROR`
- `SQL_EXECUTION_ERROR`
- `UPSTREAM_UNAVAILABLE`
- `INTERNAL_ERROR`

## 7. 与当前本地工具映射

- `search_relevant_tables` -> `metadata.search_tables`
- `get_table_metadata` -> `metadata.get_table`
- `get_table_description` -> `metadata.get_table`
- `get_related_tables` -> `metadata.get_related_tables`
- `get_schema_context` -> `metadata.get_schema_context`
- `get_example_queries` -> `metadata.get_examples`
- `list_tables` -> `database.list_tables`
- `get_table_schema` -> `database.get_table_schema`
- `validate_sql` -> `database.validate_sql`
- `execute_query` -> `database.execute_sql`

## 8. 迁移建议

1. 先冻结本协议，不改 Agent 节点语义。
2. 在 `tools/` 层保留兼容适配器。
3. 适配器先调用本地实现，返回协议兼容格式。
4. 后续将适配器替换为 MCP 客户端调用。
5. 节点与图逻辑不感知本地/远端切换。

## 9. 当前代码约束

当前项目仍有历史工具返回简化格式，例如：

- `List[str]`
- `Dict[str, Any]`
- `list[dict]`

这是为了兼容现有 Agent 节点。

建议后续分两步演进：

1. 工具层同时暴露：
   - 面向当前节点的兼容接口
   - 面向未来 MCP 的协议接口
2. 节点逐步改为直接消费协议接口
