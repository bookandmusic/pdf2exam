# PDF 试卷处理工具

## 脚本说明

### 1. `split_pdf.py` — PDF 拆图

将 PDF 试卷按页拆分为 PNG 图片。

```bash
python split_pdf.py <PDF文件> [输出目录]
python split_pdf.py 试卷.pdf
python split_pdf.py 试卷.pdf ./pdf_images --dpi 300
```

- 输出目录默认为 `{PDF文件名}_images/`
- 图片命名格式：`page_0001.png`、`page_0002.png` ……
- 支持 `--dpi` 调整图片清晰度，默认 `200`
- 依赖：`PyMuPDF`

### 2. `extract_questions.py` — 题目提取

从试卷图片中自动识别并提取选择题，输出结构化 JSON。

#### 最简执行命令

```bash
# 处理整个图片目录，输出到 questions.json
python extract_questions.py --dir ./pdf_images -o questions.json

# 从第 174 页开始，每批主处理 5 页，前后各带 1 页上下文
python extract_questions.py --dir ./pdf_images --start-from 174 --step 5 --context 1 -o questions.json --log extract.log

# 测试单张图片，默认自动带前后邻页；不带 -o 时输出到 stdout
python extract_questions.py --test ./pdf_images/page_0174.png
```

#### 常用命令

```bash
# 测试模式（指定单张图片，默认带前后邻页；解析后输出 JSON，配合 -o 可保存文件）
python extract_questions.py --test page_0001.png

# 生产模式（整个目录，主批次 + 前后邻页）
python extract_questions.py --dir ./pdf_images -o questions.json --log extract.log

# 指定章节
python extract_questions.py --dir ./pdf_images --chapter "第一章" -o questions.json

# 从指定图片序号继续处理（仍会自动带上一页/下一页作为上下文）
python extract_questions.py --dir ./pdf_images --start-from 30 -o questions.json --log extract.log

# 每批主处理 5 页，并额外带前后各 1 页上下文
python extract_questions.py --dir ./pdf_images --start-from 35 --step 5 --context 1 -o questions.json --log extract.log
```

#### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--test IMAGE` | 测试模式。指定一张图片，脚本会自动带同目录中的前一页和后一页一起请求。 | `--test ./pdf_images/page_0174.png` |
| `--dir DIR` | 生产模式。处理整个图片目录。 | `--dir ./pdf_images` |
| `images...` | 默认模式。手动指定一张或多张图片。 | `page_0001.png page_0002.png` |
| `--chapter TEXT` | 指定默认章节名；当图片里没有明确章节时作为回退值。 | `--chapter "第一章"` |
| `--window N` | 兼容旧模式。未指定 `--step` 时使用的总窗口大小，建议奇数。 | `--window 3` |
| `--step N` | 生产模式下每批主处理页数。 | `--step 5` |
| `--context N` | 生产模式下主批次前后各带几页上下文。 | `--context 1` |
| `--start-from N` | 从文件名中的数字序号大于等于该值的图片开始处理。 | `--start-from 174` |
| `-o, --output FILE` | 输出 JSON 文件；不传时输出到 stdout。目录模式下支持续跑追加。 | `-o questions.json` |
| `--log FILE` | 将运行日志写入文件。 | `--log extract.log` |

#### 批次行为示例

命令：

```bash
python extract_questions.py --dir ./pdf_images --start-from 174 --step 5 --context 1 -o questions.json --log extract.log
```

如果图片编号连续，批次大致如下：

- 第 1 批主处理 `174-178`，实际发送 `173 + 174-178 + 179`
- 第 2 批主处理 `179-183`，实际发送 `178 + 179-183 + 184`
- 第 3 批主处理 `184-188`，实际发送 `183 + 184-188 + 189`

去重规则使用 `(chapter, number)`，因此即使上下文页重复发送，也不会重复写入题目。

#### 特性

- 调用 OpenAI 标准 API（兼容 GPT、Gemini、GLM 等模型）
- 支持“主批次 + 前后邻页上下文”模式，兼容题干、答案、解析前后跨页
- 测试模式默认自动附带前一页和后一页，便于排查跨页题目提取
- 多章节自动识别，每道题独立标注所属章节
- 断点续跑：重复运行只追加新题，不覆盖已有结果
- 支持从指定图片序号继续处理，适合中途失败后从某页恢复
- 日志记录：`--log` 参数输出到文件
- 环境变量配置：API 密钥、地址、模型等通过 `.env` 文件设置

#### 输出格式

```json
{
  "chapters": ["第一章 民法总则"],
  "questions": [
    {
      "number": "1",
      "chapter": "第一章 民法总则",
      "title": "题目内容",
      "options": [
        {"label": "A", "text": "选项A"},
        {"label": "B", "text": "选项B"}
      ],
      "correct_answer": "A",
      "analysis": "解析文本"
    }
  ]
}
```

#### 配置

创建 `.env` 文件（参考 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_KEY` | API 密钥 | — |
| `API_URL` | API 地址 | `https://api.openai.com/v1` |
| `MODEL_NAME` | 模型名称 | `gpt-4o` |
| `IMAGES_PER_REQUEST` | 兼容旧模式：未指定 `--step` 时的总窗口页数 | `3` |
| `CONTEXT_PAGES` | 指定 `--step` 时，前后附带的上下文页数 | `1` |
| `RESPONSE_FORMAT` | `auto`、`json_object`、`text`；默认自动兼容后端 | `auto` |
| `REQUEST_TIMEOUT` | 单次模型请求超时秒数 | `180` |
| `REQUEST_RETRY_LIMIT` | 请求失败后的最大重试次数 | `6` |
| `REQUEST_RETRY_BASE_DELAY` | 重试基础等待秒数，按次数递增 | `10` |
| `BATCH_DELAY_SECONDS` | 批次之间固定等待秒数 | `5` |
| `DEBUG_LOG_RAW_RESPONSE` | 是否在日志中打印原始响应预览 | `false` |
| `RAW_RESPONSE_DIR` | 保存模型原始响应的目录 | 空 |
| `TEMPERATURE` | 模型温度 | `0.1` |
| `MAX_OUTPUT_TOKENS` | 最大输出 token | `8192` |
| `ENABLE_JSON_MODE` | JSON 模式开关 | `true` |

## 完整流程

```bash
# 1. PDF 拆成图片
python split_pdf.py 试卷.pdf

# 2. 提取题目
python extract_questions.py --dir 试卷_images -o questions.json --log extract.log
```
