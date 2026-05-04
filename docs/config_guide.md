# 配置指南

## 支持的LLM Provider

系统支持三种LLM提供商：

### 1. Ollama (推荐，本地部署)

**配置**:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

**推荐模型**:
- `qwen2.5:7b` - 通义千问2.5，中文效果好
- `qwen2.5:14b` - 更强大的版本
- `llama3.1:8b` - Meta的开源模型
- `deepseek-coder:6.7b` - 代码能力强

**启动Ollama**:
```bash
# 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull qwen2.5:7b

# 启动服务（自动后台运行）
ollama serve
```

**注意**:
- Ollama的base_url配置为`http://localhost:11434`
- ChatOllama会自动处理API路径（如`/api/chat`）

**优点**:
- 完全本地部署，数据安全
- 免费使用
- 安装简单
- 支持多种开源模型

### 2. vLLM (本地GPU加速)

**配置**:
```env
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_API_KEY=EMPTY
```

**推荐模型**:
- `Qwen/Qwen2.5-7B-Instruct` - 通义千问2.5
- `Qwen/Qwen2.5-14B-Instruct` - 更强版本
- `deepseek-ai/DeepSeek-Coder-V2-Instruct` - 代码专用
- `meta-llama/Llama-3.1-8B-Instruct` - Llama 3.1

**启动vLLM**:
```bash
# 安装vLLM
pip install vllm

# 启动服务
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --port 8000 \
    --trust-remote-code
```

**注意**: 
- vLLM的base_url配置为`http://localhost:8000/v1`
- LangChain会自动添加`/chat/completions`和`/embeddings`路径
- 最终请求地址为`http://localhost:8000/v1/chat/completions`

**优点**:
- GPU加速，推理速度快
- 支持批处理
- OpenAI兼容API
- 本地部署，数据安全

### 3. 阿里百炼 (DashScope)

**配置**:
```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_MODEL=qwen-plus
```

**可选模型**:
- `qwen-plus` - 通义千问Plus，性价比高
- `qwen-max` - 通义千问Max，效果最好
- `qwen-turbo` - 速度快，成本低
- `qwen-long` - 长文本支持

**获取API Key**:
1. 访问 https://dashscope.aliyun.com/
2. 注册/登录阿里云账号
3. 开通百炼服务
4. 创建API Key

**优点**:
- 无需本地部署
- 中文效果好
- 稳定可靠
- 按量付费

**定价** (参考):
- qwen-turbo: ¥0.002/1K tokens
- qwen-plus: ¥0.004/1K tokens
- qwen-max: ¥0.04/1K tokens

## 支持的Embedding Provider

### 1. Sentence Transformers (默认)

**配置**:
```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

**推荐模型**:
- `paraphrase-multilingual-MiniLM-L12-v2` - 多语言，轻量
- `BAAI/bge-base-zh-v1.5` - 中文优化，推荐
- `moka-ai/m3e-base` - 中文效果好
- `shibing624/text2vec-base-chinese` - 中文专用

### 2. vLLM Embedding (GPU加速)

**配置**:
```env
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_BASE_URL=http://localhost:8000/v1
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

**推荐模型**:
- `BAAI/bge-large-zh-v1.5` - 中文最佳
- `BAAI/bge-base-zh-v1.5` - 速度快
- `BAAI/bge-m3` - 多语言

### 3. 阿里百炼 Embedding

**配置**:
```env
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v2
```

**可选模型**:
- `text-embedding-v2` - 通用embedding
- `text-embedding-v3` - 新版本，效果更好

## 推荐配置方案

### 方案1: 纯本地部署（推荐）

```env
# LLM使用Ollama
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b

# Embedding使用本地模型
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
```

**优点**: 完全免费，数据安全，无需网络

### 方案2: 本地GPU加速

```env
# LLM使用vLLM
LLM_PROVIDER=vllm
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct

# Embedding使用vLLM
EMBEDDING_PROVIDER=vllm
VLLM_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

**优点**: 速度快，效果好，免费

### 方案3: 云端API

```env
# LLM使用阿里百炼
LLM_PROVIDER=dashscope
DASHSCOPE_MODEL=qwen-plus

# Embedding使用阿里百炼
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v2
```

**优点**: 无需部署，稳定可靠

### 方案4: 混合部署

```env
# LLM使用阿里百炼（效果好）
LLM_PROVIDER=dashscope
DASHSCOPE_MODEL=qwen-plus

# Embedding使用本地（节省成本）
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
```

**优点**: 平衡效果和成本

## 快速开始

### 使用Ollama（最简单）

```bash
# 1. 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. 拉取模型
ollama pull qwen2.5:7b

# 3. 配置.env
cat > .env << EOF
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
EOF

# 4. 运行
python main.py --init-db
python main.py --interactive
```

### 使用阿里百炼

```bash
# 1. 获取API Key（访问 https://dashscope.aliyun.com/）

# 2. 配置.env
cat > .env << EOF
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-your-api-key
DASHSCOPE_MODEL=qwen-plus
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v2
EOF

# 3. 运行
python main.py --init-db
python main.py --interactive
```

## 性能对比

| 方案 | LLM速度 | Embedding速度 | 成本 | 部署难度 |
|------|---------|---------------|------|----------|
| Ollama + 本地Embedding | 中 | 快 | 免费 | 简单 |
| vLLM + vLLM Embedding | 快 | 快 | 免费 | 中等 |
| 阿里百炼 | 快 | 快 | 低 | 简单 |
| 混合部署 | 快 | 快 | 低 | 简单 |

## 故障排查

### Ollama连接失败

```bash
# 检查服务状态
ollama list

# 重启服务
ollama serve
```

### vLLM启动失败

```bash
# 检查GPU
nvidia-smi

# 检查CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

### 阿里百炼API错误

```bash
# 测试API Key
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-turbo","input":{"messages":[{"role":"user","content":"你好"}]}}'
```
