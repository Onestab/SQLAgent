# SQLAgent - 智能问数系统

基于LangGraph的Text-to-SQL智能问答系统，支持自然语言查询结构化数据库。

## 功能特性

- **自然语言理解**: 支持中文自然语言查询
- **智能模式链接**: 基于向量检索的表和列识别
- **SQL生成**: 自动生成准确的SQL查询语句
- **错误重试**: 自动检测和修复SQL错误
- **多数据库支持**: 支持SQLite、MySQL、PostgreSQL
- **多模型支持**: 支持Ollama、vLLM、阿里百炼
- **元数据管理**: 丰富的业务语义信息支持

## 系统架构

```
用户查询 → 意图识别 → 模式链接 → SQL生成 → SQL验证 → SQL执行 → 结果解释
                                      ↓ (错误)
                                    错误处理 → 重试
```

## 快速开始

### 1. 安装依赖

```bash
cd code
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 选择LLM提供商
LLM_PROVIDER=ollama  # 可选: ollama, vllm, dashscope

# Ollama配置（推荐，本地部署）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# 或使用vLLM（本地GPU加速）
# LLM_PROVIDER=vllm
# VLLM_BASE_URL=http://localhost:8000/v1
# VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct

# 或使用阿里百炼
# LLM_PROVIDER=dashscope
# DASHSCOPE_API_KEY=sk-...
# DASHSCOPE_MODEL=qwen-plus

# Embedding配置
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
```

### 3. 初始化数据库

```bash
python main.py --init-db
```

这将创建一个包含电商数据的SQLite演示数据库。

### 4. 运行测试

```bash
python test.py
```

### 5. 交互式使用

```bash
python main.py --interactive
```

或直接查询：

```bash
python main.py --query "查询所有产品"
```

## 使用示例

```python
from main import run_query

# 执行查询
result = run_query("张三买了什么？")

print(result["generated_sql"])  # 生成的SQL
print(result["final_answer"])   # 自然语言答案
print(result["query_results"])  # 原始查询结果
```

## 项目结构

```
code/
├── agent/              # LangGraph工作流
│   ├── graph.py       # 图定义
│   ├── nodes.py       # 节点实现
│   └── state.py       # 状态定义
├── database/          # 数据库管理
│   ├── connection.py  # 连接管理
│   ├── metadata.py    # 元数据管理
│   └── init_db.py     # 数据库初始化
├── metadata/          # 元数据配置
│   ├── products.yaml
│   ├── orders.yaml
│   └── ...
├── tools/             # 工具函数
│   └── sql_tools.py
├── config.py          # 配置管理
├── main.py            # 主程序
└── test.py            # 测试脚本
```

## 元数据系统

元数据文件（YAML格式）包含：

- **表描述**: 业务含义
- **列描述**: 字段说明
- **业务上下文**: 使用场景
- **示例查询**: 常见问题和SQL

示例 (`metadata/products.yaml`):

```yaml
description: "产品表，存储所有商品信息"
business_context: "记录电商平台的商品基本信息"
columns:
  - name: product_id
    type: INTEGER
    description: "产品唯一标识符"
  - name: product_name
    type: TEXT
    description: "产品名称"
example_queries:
  - question: "查询所有电子产品"
    sql: "SELECT p.* FROM products p JOIN categories c..."
```

## 本地模型配置

### 使用Ollama

1. 安装Ollama: https://ollama.ai
2. 拉取模型: `ollama pull llama3`
3. 配置 `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### 使用vLLM

1. 启动vLLM服务:
```bash
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3-8b \
    --port 8000
```

2. 配置 `.env`:
```env
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=meta-llama/Llama-3-8b
```

## 数据库配置

### SQLite (默认)

```env
DB_TYPE=sqlite
DB_PATH=./database/ecommerce.db
```

### MySQL

```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ecommerce
DB_USER=root
DB_PASSWORD=password
```

### PostgreSQL

```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce
DB_USER=postgres
DB_PASSWORD=password
```

## 高级功能

### 自定义元数据

在 `metadata/` 目录下创建新的YAML文件，系统会自动加载。

### 向量检索优化

元数据管理器使用 `sentence-transformers` 进行语义检索，自动找到最相关的表。

### 错误重试机制

系统会自动重试失败的SQL查询（最多3次），并根据错误信息调整SQL。

## 常见问题

**Q: 如何添加新表？**

A: 在数据库中创建表后，在 `metadata/` 目录添加对应的YAML文件。

**Q: 支持哪些SQL操作？**

A: 目前主要支持SELECT查询，可以扩展支持INSERT/UPDATE/DELETE。

**Q: 如何提高SQL生成准确率？**

A: 
1. 完善元数据描述
2. 添加更多示例查询
3. 使用更强大的LLM模型

## 许可证

MIT License
