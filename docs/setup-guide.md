# AWS Bedrock to OpenAI API Proxy - 完整搭建指南

## 背景

作为 AWS IAM 用户，拥有 Bedrock API Key（`ABSK...` 格式），希望通过 OpenAI API 兼容接口使用 Bedrock 上的 Claude 模型，以便在各类 AI 工具（Cursor、Continue、ChatBox、OpenAI SDK 等）中使用。

AWS Bedrock 虽然提供了 OpenAI 兼容端点（`bedrock-runtime.{region}.amazonaws.com/compatible-apis/v1`），但该端点使用 SigV4 签名认证，无法直接用 Bearer Token。因此需要本地代理做协议转换。

## 架构

```
Cursor / OpenAI SDK
        |
        | OpenAI API 格式 (HTTPS)
        v
ngrok (公网 URL)           ← Cursor 需要公网地址
        |
        v
Flask 本地代理 (localhost:PORT)
        |
        | Bedrock Converse API (boto3 + Bearer Token)
        v
AWS Bedrock Runtime
        |
        v
Claude 模型
```

## 前置条件

- Python 3.10+
- AWS Bedrock API Key（`ABSK...` 格式的 Bearer Token）
- 已开通 Bedrock 上的 Claude 模型访问权限
- [ngrok](https://ngrok.com/)（用于在 Cursor 中使用，本地 curl 测试不需要）

## 搭建步骤

### 1. 安装依赖

```bash
cd aws_bedrock_to_oai_proxy
pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：
```
flask>=3.0
boto3>=1.35
python-dotenv>=1.0
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
BEDROCK_API_KEY=ABSK...你的完整API Key
BEDROCK_REGION=us-east-1
PROXY_PORT=8000
DEFAULT_MODEL=global.anthropic.claude-opus-4-6-v1
LOG_LEVEL=INFO
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BEDROCK_API_KEY` | Bedrock API Key（必填） | 无 |
| `BEDROCK_REGION` | AWS 区域 | `us-east-1` |
| `PROXY_PORT` | 代理监听端口 | `8000` |
| `DEFAULT_MODEL` | 未指定模型时的默认模型 | `global.anthropic.claude-opus-4-6-v1` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

> **注意**：macOS 上 5000 端口被 AirPlay Receiver 占用，建议使用 8000 或其他端口。

### 3. 启动代理

```bash
python app.py
```

看到以下输出表示启动成功：
```
 * Serving Flask app 'app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8000
```

### 4. 验证代理

**健康检查：**
```bash
curl http://localhost:8000/health
```

**查看可用模型：**
```bash
curl http://localhost:8000/v1/models
```

**非流式请求测试：**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus","messages":[{"role":"user","content":"hello"}]}'
```

**流式请求测试：**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus","messages":[{"role":"user","content":"hello"}],"stream":true}'
```

### 5. 在本地工具中使用

任何支持 OpenAI API 的工具都可以直接连接代理：

- **Base URL**: `http://localhost:8000/v1`
- **API Key**: 任意非空字符串（如 `sk-placeholder`，代理不校验此值）
- **Model**: 使用模型别名（见下表）

适用于 OpenAI Python/JS SDK、curl、ChatBox 等本地工具。

### 6. 通过 ngrok 暴露给远程工具

部分工具（如 Cursor、Continue）从云端发起请求，无法直接访问 localhost。需要用 ngrok 将代理暴露到公网：

```bash
ngrok http 8000  # 端口号与 PROXY_PORT 一致
```

ngrok 启动后会显示公网 URL，例如：
```
Forwarding  https://xxxx-xx-xx-xx-xx.ngrok-free.app -> http://localhost:8000
```

然后在工具中配置：

- **Base URL**: `https://xxxx-xx-xx-xx-xx.ngrok-free.app/v1`
- **API Key**: 任意非空字符串
- **Model**: 使用模型别名（见下表）

> **注意**：免费版 ngrok 每次重启会分配新的 URL，需要同步更新工具配置。付费版可以绑定固定域名。

## 可用模型别名

| 别名 | Bedrock 模型 ID |
|------|-----------------|
| `claude-sonnet` | `global.anthropic.claude-sonnet-4-6-v1` |
| `claude-sonnet-4` | `global.anthropic.claude-sonnet-4-6-v1` |
| `claude-haiku` | `global.anthropic.claude-haiku-4-5-v1` |
| `claude-opus` | `global.anthropic.claude-opus-4-6-v1` |
| `claude-opus-4` | `global.anthropic.claude-opus-4-6-v1` |
| `claude-3-5-sonnet` | `global.anthropic.claude-3-5-sonnet-20241022-v1:0` |
| `claude-3-5-haiku` | `global.anthropic.claude-3-5-haiku-20241022-v1:0` |

也可以直接使用完整的 Bedrock 模型 ID（包含 `anthropic.claude` 的字符串会自动透传）。

## 项目文件说明

```
aws_bedrock_to_oai_proxy/
├── app.py              # Flask 入口，路由: /v1/chat/completions, /v1/models, /health
├── config.py           # 从 .env / 环境变量加载配置
├── models.py           # 模型别名映射 + /v1/models 端点数据
├── converter.py        # OpenAI <-> Bedrock Converse 请求/响应格式转换
├── bedrock_client.py   # boto3 客户端，通过 AWS_BEARER_TOKEN_BEDROCK 认证
├── streaming.py        # Bedrock EventStream -> OpenAI SSE 流式转换
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
└── docs/               # 文档
```

## 核心实现要点

### 认证方式

代理通过设置 `AWS_BEARER_TOKEN_BEDROCK` 环境变量，让 boto3 使用 Bearer Token 认证调用 Bedrock Runtime API。无需配置 AWS Access Key / Secret Key。

### 请求转换（OpenAI -> Bedrock Converse）

- `messages` 中的 `system` 角色消息提取到 Bedrock 的顶层 `system` 字段
- `content: "string"` 转换为 `content: [{"text": "string"}]`
- 参数映射：`max_tokens` -> `maxTokens`, `temperature`, `top_p` -> `topP`, `stop` -> `stopSequences`
- Bedrock 不支持的参数（`n`, `presence_penalty` 等）静默忽略

### 流式响应转换（Bedrock EventStream -> OpenAI SSE）

Bedrock 的 `converse_stream` 返回二进制 EventStream，通过 boto3 解析后转换为 OpenAI 的 SSE 格式：

| Bedrock 事件 | OpenAI SSE |
|--------------|------------|
| `messageStart` | `delta: {"role": "assistant"}` |
| `contentBlockDelta` | `delta: {"content": "text"}` |
| `messageStop` | `finish_reason: "stop"` |
| 流结束 | `data: [DONE]` |

## 故障排查

| 问题 | 解决方法 |
|------|----------|
| `Address already in use` (端口被占) | 修改 `.env` 中的 `PROXY_PORT`，macOS 上避免使用 5000 |
| `BEDROCK_API_KEY is required` | 检查 `.env` 文件是否存在且 `BEDROCK_API_KEY` 已填写 |
| Bedrock 返回 403 | 确认 API Key 有效，且有对应模型的访问权限 |
| Bedrock 返回 404 | 检查模型 ID 是否正确，确认区域支持该模型 |
| 流式响应卡住 | 确认使用了 `python app.py` 启动（带 `threaded=True`） |
