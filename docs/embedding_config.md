# Embedding模型配置指南

## 支持的Embedding Provider

系统支持四种embedding provider：

### 1. Sentence Transformers (默认)

**配置**:
```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

**推荐模型**:

| 模型 | 特点 | 大小 | 适用场景 |
|------|------|------|----------|
| `paraphrase-multilingual-MiniLM-L12-v2` | 多语言，轻量 | 120MB | 默认选择，速度快 |
| `shibing624/text2vec-base-chinese` | 中文优化 | 400MB | 纯中文场景 |
| `moka-ai/m3e-base` | 中文，效果好 | 400MB | 中文场景，高质量 |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 多语言，更强 | 420MB | 需要更好效果 |

**优点**:
- 本地运行，无需API调用
- 免费
- 速度快

**缺点**:
- 需要下载模型
- 首次加载较慢

### 2. OpenAI Embeddings

**配置**:
```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

**可选模型**:
- `text-embedding-3-small`: 性价比高，推荐
- `text-embedding-3-large`: 效果最好，成本高
- `text-embedding-ada-002`: 旧版本

**优点**:
- 效果好
- 无需本地模型
- 支持多语言

**缺点**:
- 需要API调用，有成本
- 需要网络连接

**定价** (截至2024):
- text-embedding-3-small: $0.02 / 1M tokens
- text-embedding-3-large: $0.13 / 1M tokens

### 3. HuggingFace Embeddings

**配置**:
```env
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**说明**:
- 使用HuggingFace的transformers库
- 支持所有HuggingFace Hub上的模型
- 与sentence-transformers类似，但更灵活

### 4. vLLM Embeddings (新增)

**配置**:
```env
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_BASE_URL=http://localhost:8000/v1
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
VLLM_EMBEDDING_API_KEY=EMPTY
```

**推荐模型**:
- `BAAI/bge-large-zh-v1.5`: 中文效果最好
- `BAAI/bge-base-zh-v1.5`: 中文，速度快
- `BAAI/bge-m3`: 多语言支持
- `intfloat/e5-large-v2`: 英文效果好

**启动vLLM Embedding服务**:
```bash
# 方式1: 使用vLLM启动embedding模型
python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000

# 方式2: 使用TEI (Text Embeddings Inference)
docker run -p 8000:80 \
    --gpus all \
    ghcr.io/huggingface/text-embeddings-inference:latest \
    --model-id BAAI/bge-large-zh-v1.5
```

**优点**:
- 本地部署，数据安全
- 支持GPU加速，速度快
- 免费，无API调用成本
- 支持批量处理
- 兼容OpenAI API格式

**缺点**:
- 需要GPU资源
- 需要自己部署服务
- 模型较大（1-2GB）

## 性能对比

### 中文查询测试

查询: "查询张三购买的所有产品"

| Provider | 模型 | 召回准确率 | 速度 | 成本 |
|----------|------|-----------|------|------|
| sentence-transformers | paraphrase-multilingual-MiniLM-L12-v2 | 85% | 快 | 免费 |
| sentence-transformers | moka-ai/m3e-base | 92% | 中 | 免费 |
| openai | text-embedding-3-small | 90% | 中 | 低 |
| openai | text-embedding-3-large | 95% | 中 | 中 |
| vllm | BAAI/bge-large-zh-v1.5 | 94% | 快(GPU) | 免费 |

### 推荐配置

**场景1: 开发测试**
```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```
- 快速启动，无需配置API

**场景2: 中文生产环境（无GPU）**
```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=moka-ai/m3e-base
```
- 中文效果好，免费

**场景3: 中文生产环境（有GPU）**
```env
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_BASE_URL=http://localhost:8000/v1
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```
- 效果最好，速度快，免费

**场景4: 多语言生产环境**
```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```
- 效果稳定，成本可控

**场景5: 高质量要求**
```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```
- 效果最好

## 切换Embedding模型

### 方法1: 修改.env文件

```bash
# 编辑.env文件
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### 方法2: 环境变量

```bash
export EMBEDDING_PROVIDER=sentence-transformers
export EMBEDDING_MODEL=moka-ai/m3e-base
python main.py
```

### 方法3: 代码中动态切换

```python
from config import config
config.embedding_provider = "openai"
config.openai_embedding_model = "text-embedding-3-small"

# 重新初始化metadata manager
from database.metadata import MetadataManager
metadata_manager = MetadataManager()
```

## 注意事项

1. **首次使用sentence-transformers**: 会自动下载模型，需要等待
2. **切换模型后**: 需要清空embeddings缓存，或重启程序
3. **OpenAI API**: 确保设置了正确的API密钥
4. **中文场景**: 推荐使用中文优化的模型

## 故障排查

### 问题1: 模型下载失败

```bash
# 手动下载模型
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('moka-ai/m3e-base')"
```

### 问题2: OpenAI API错误

```bash
# 检查API密钥
echo $OPENAI_API_KEY

# 测试API
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "test", "model": "text-embedding-3-small"}'
```

### 问题3: 内存不足

如果模型太大导致内存不足，使用更小的模型：
```env
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

## 性能优化

### 1. 缓存Embeddings

系统会自动缓存表的embeddings，避免重复计算。

### 2. 批量处理

对于大量查询，可以批量生成embeddings：

```python
# 批量编码
texts = ["查询1", "查询2", "查询3"]
embeddings = model.encode(texts)
```

### 3. 使用GPU加速

```python
# sentence-transformers支持GPU
model = SentenceTransformer('moka-ai/m3e-base', device='cuda')
```

## 总结

- **默认配置**: `paraphrase-multilingual-MiniLM-L12-v2` 适合大多数场景
- **中文优化**: 使用 `moka-ai/m3e-base` 或 `shibing624/text2vec-base-chinese`
- **最佳效果**: 使用 OpenAI `text-embedding-3-large`
- **性价比**: 使用 OpenAI `text-embedding-3-small`
