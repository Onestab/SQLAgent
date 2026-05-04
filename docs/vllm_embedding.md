# vLLM Embedding部署指南

## 什么是vLLM Embedding

vLLM不仅支持LLM推理，也支持Embedding模型的部署，提供OpenAI兼容的API接口。

## 部署方式

### 方式1: 使用vLLM直接部署

```bash
# 安装vLLM
pip install vllm

# 启动embedding服务
python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000 \
    --trust-remote-code
```

### 方式2: 使用Text Embeddings Inference (TEI)

TEI是HuggingFace推出的专门用于embedding的推理服务，性能更优。

```bash
# 使用Docker部署
docker run -p 8000:80 \
    --gpus all \
    -v $PWD/data:/data \
    ghcr.io/huggingface/text-embeddings-inference:latest \
    --model-id BAAI/bge-large-zh-v1.5 \
    --max-batch-tokens 16384
```

### 方式3: 使用Xinference

Xinference是一个统一的模型推理框架，支持LLM和Embedding。

```bash
# 安装
pip install xinference

# 启动服务
xinference-local --host 0.0.0.0 --port 9997

# 通过Web UI或API部署embedding模型
```

## 推荐的Embedding模型

### 中文场景

| 模型 | 维度 | 大小 | 特点 |
|------|------|------|------|
| `BAAI/bge-large-zh-v1.5` | 1024 | 1.3GB | 中文最佳 |
| `BAAI/bge-base-zh-v1.5` | 768 | 400MB | 速度快 |
| `BAAI/bge-small-zh-v1.5` | 512 | 100MB | 轻量级 |
| `moka-ai/m3e-large` | 1024 | 1.2GB | 中文效果好 |

### 多语言场景

| 模型 | 维度 | 大小 | 特点 |
|------|------|------|------|
| `BAAI/bge-m3` | 1024 | 2.2GB | 多语言支持 |
| `intfloat/multilingual-e5-large` | 1024 | 2.2GB | 多语言 |

### 英文场景

| 模型 | 维度 | 大小 | 特点 |
|------|------|------|------|
| `intfloat/e5-large-v2` | 1024 | 1.3GB | 英文最佳 |
| `BAAI/bge-large-en-v1.5` | 1024 | 1.3GB | 英文优化 |

## 配置SQLAgent使用vLLM Embedding

### 1. 启动vLLM服务

```bash
python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000 \
    --trust-remote-code
```

### 2. 配置.env文件

```env
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_BASE_URL=http://localhost:8000/v1
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
VLLM_EMBEDDING_API_KEY=EMPTY
```

### 3. 测试连接

```python
from config import get_embedding_model

model = get_embedding_model()
embedding = model.embed_query("测试文本")
print(f"Embedding维度: {len(embedding)}")
```

## 性能优化

### 1. 批量处理

vLLM支持批量embedding，提高吞吐量：

```python
texts = ["文本1", "文本2", "文本3"]
embeddings = model.embed_documents(texts)
```

### 2. GPU配置

```bash
# 指定GPU
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000

# 多GPU
CUDA_VISIBLE_DEVICES=0,1 python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000 \
    --tensor-parallel-size 2
```

### 3. 量化加速

使用INT8量化减少显存占用：

```bash
python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000 \
    --quantization int8
```

## 与其他方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| vLLM | 高性能，OpenAI兼容 | 需要GPU | 生产环境 |
| TEI | 专为embedding优化 | 功能单一 | 大规模embedding |
| sentence-transformers | 简单易用 | 性能一般 | 开发测试 |
| OpenAI API | 无需部署 | 有成本 | 快速上线 |

## 故障排查

### 问题1: 模型下载失败

```bash
# 设置HuggingFace镜像
export HF_ENDPOINT=https://hf-mirror.com

# 手动下载模型
huggingface-cli download BAAI/bge-large-zh-v1.5
```

### 问题2: GPU内存不足

```bash
# 使用更小的模型
--model BAAI/bge-base-zh-v1.5

# 或使用量化
--quantization int8
```

### 问题3: 连接超时

```bash
# 检查服务是否启动
curl http://localhost:8000/v1/models

# 测试embedding
curl http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "测试文本",
    "model": "BAAI/bge-large-zh-v1.5"
  }'
```

## 生产环境建议

1. **使用TEI**: 专为embedding优化，性能最好
2. **启用批处理**: 提高吞吐量
3. **监控GPU使用**: 避免OOM
4. **设置超时**: 防止请求堆积
5. **负载均衡**: 多实例部署

## 示例：完整部署流程

```bash
# 1. 安装依赖
pip install vllm

# 2. 下载模型（可选，首次运行会自动下载）
huggingface-cli download BAAI/bge-large-zh-v1.5

# 3. 启动服务
python -m vllm.entrypoints.openai.api_server \
    --model BAAI/bge-large-zh-v1.5 \
    --port 8000 \
    --trust-remote-code \
    --max-model-len 512

# 4. 配置SQLAgent
cat > .env << EOF
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_BASE_URL=http://localhost:8000/v1
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
VLLM_EMBEDDING_API_KEY=EMPTY
EOF

# 5. 测试
python test_retrieval.py
```

## 总结

vLLM Embedding提供了：
- ✅ 高性能GPU加速
- ✅ OpenAI兼容API
- ✅ 本地部署，数据安全
- ✅ 免费使用
- ✅ 支持批量处理

推荐在有GPU资源的生产环境中使用。
