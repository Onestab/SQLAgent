# SQLAgent 使用说明

## 命令行参数

### 基本用法

```bash
# 初始化数据库
python main.py --init-db

# 交互式模式（默认）
python main.py

# 直接查询
python main.py --query "查询所有产品"
```

### 详细输出控制

SQLAgent支持多种详细输出选项，帮助你了解系统的内部工作流程。

#### 1. 全局详细模式

显示所有中间过程：

```bash
python main.py -v
# 或
python main.py --verbose
```

这将显示：
- 意图识别结果
- Schema链接过程
- AgenticRAG检索详情
- SQL验证结果
- 错误重试过程
- SQL执行详情

#### 2. 选择性显示

你可以只显示特定的中间过程：

**显示意图识别：**
```bash
python main.py --show-intent
```

**显示Schema链接过程：**
```bash
python main.py --show-schema
```

**显示AgenticRAG检索过程：**
```bash
python main.py --show-agentic
```
这将显示：
- Agent的每一步推理过程
- 调用的工具和参数
- 找到的相关表

**显示SQL验证结果：**
```bash
python main.py --show-validation
```

**显示错误重试过程：**
```bash
python main.py --show-retry
```
当SQL执行失败时，显示重试次数和错误信息

**显示SQL执行详情：**
```bash
python main.py --show-execution
```

#### 3. 组合使用

可以组合多个参数：

```bash
# 只显示AgenticRAG和重试过程
python main.py --show-agentic --show-retry

# 在直接查询模式下使用详细输出
python main.py --query "查询iPhone的价格" --verbose

# 交互式模式 + 显示Schema和验证
python main.py --show-schema --show-validation
```

## 使用示例

### 示例1：调试AgenticRAG检索

```bash
python main.py --show-agentic
```

然后输入查询：
```
您的问题: 查询购买iPhone的客户及其收货地址
```

输出将显示：
```
============================================================
AgenticRAG Schema检索过程
============================================================
用户问题: 查询购买iPhone的客户及其收货地址
用户意图: 查询购买特定产品的客户信息和收货地址
------------------------------------------------------------

Agent检索过程:

[步骤 1] SystemMessage:
你是一个数据库Schema检索专家...

[步骤 2] AIMessage:
我需要找到产品、订单、客户和地址相关的表...
  → 调用工具: search_relevant_tables
    参数: {'query': '产品 订单 客户', 'top_k': 5}

[步骤 3] ToolMessage:
['products', 'orders', 'customers', 'order_items']

[步骤 4] AIMessage:
还需要查找地址表...
  → 调用工具: get_related_tables
    参数: {'table_name': 'orders'}

[步骤 5] ToolMessage:
['addresses', 'customers', 'payments']

------------------------------------------------------------
✓ 最终找到的相关表: ['products', 'orders', 'customers', 'order_items', 'addresses']
============================================================
```

### 示例2：查看完整执行流程

```bash
python main.py --verbose --query "统计每个类别的产品数量"
```

输出：
```
开始执行查询流程...

┌─────────────────────────────────────────┐
│ 意图识别                                 │
├─────────────────────────────────────────┤
│ 用户想要统计产品按类别分组的数量         │
└─────────────────────────────────────────┘

相关表识别
┏━━━━━━━━━━━━━┓
┃ 表名        ┃
┡━━━━━━━━━━━━━┩
│ products    │
│ categories  │
└─────────────┘

SQL验证: valid

执行成功，返回 4 条记录

┌─────────────────────────────────────────┐
│ 生成的SQL                                │
├─────────────────────────────────────────┤
│ SELECT c.category_name,                 │
│        COUNT(p.product_id) as count     │
│ FROM categories c                       │
│ LEFT JOIN products p                    │
│   ON c.category_id = p.category_id      │
│ GROUP BY c.category_id, c.category_name │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 回答                                     │
├─────────────────────────────────────────┤
│ 根据查询结果，各类别的产品数量如下：     │
│ - 电子产品: 4个                          │
│ - 图书: 4个                              │
│ - 服装: 2个                              │
│ - 食品: 2个                              │
└─────────────────────────────────────────┘
```

### 示例3：调试SQL错误重试

```bash
python main.py --show-retry --show-validation
```

当SQL执行失败时，你会看到：
```
SQL验证: valid
重试次数: 1
错误信息: no such column: product.name

SQL验证: valid
重试次数: 2
错误信息: ambiguous column name: id

SQL验证: valid
执行成功，返回 10 条记录
```

## 环境变量

你也可以通过环境变量控制AgenticRAG的输出：

```bash
# Linux/Mac
export SHOW_AGENTIC_PROCESS=true
python main.py

# Windows
set SHOW_AGENTIC_PROCESS=true
python main.py
```

## 参数总览

| 参数 | 简写 | 说明 |
|------|------|------|
| `--init-db` | - | 初始化演示数据库 |
| `--query` | - | 直接执行查询 |
| `--interactive` | - | 交互式模式（默认） |
| `--verbose` | `-v` | 显示所有详细信息 |
| `--show-intent` | - | 显示意图识别 |
| `--show-schema` | - | 显示Schema链接 |
| `--show-agentic` | - | 显示AgenticRAG过程 |
| `--show-validation` | - | 显示SQL验证 |
| `--show-retry` | - | 显示错误重试 |
| `--show-execution` | - | 显示执行详情 |

## 推荐使用场景

1. **开发调试**：使用 `--verbose` 查看完整流程
2. **性能优化**：使用 `--show-agentic` 分析Schema检索效率
3. **SQL调试**：使用 `--show-validation --show-retry` 定位SQL问题
4. **演示展示**：使用 `--show-schema` 展示智能检索能力
5. **生产环境**：不使用任何详细参数，只显示最终结果
