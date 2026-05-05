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

# 只处理 174 到 220 页
python extract_questions.py --dir ./pdf_images --start-from 174 --end-at 220 --step 5 --context 1 -o questions.json --log extract.log

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

# 只处理指定区间
python extract_questions.py --dir ./pdf_images --start-from 35 --end-at 60 --step 5 --context 1 -o questions.json --log extract.log
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
| `--end-at N` | 处理到文件名中的数字序号小于等于该值的图片结束。 | `--end-at 220` |
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

如果额外指定 `--end-at 188`，则主批次只会处理到 `188` 为止，但最后一批仍可能附带 `189` 作为上下文页发送给模型。

去重规则使用 `(chapter, number)`，因此即使上下文页重复发送，也不会重复写入题目。

#### 特性

- 调用 OpenAI 标准 API（兼容 GPT、Gemini、GLM 等模型）
- 支持“主批次 + 前后邻页上下文”模式，兼容题干、答案、解析前后跨页
- 测试模式默认自动附带前一页和后一页，便于排查跨页题目提取
- 多章节自动识别，每道题独立标注所属章节
- 断点续跑：重复运行只追加新题，不覆盖已有结果
- 支持从指定图片序号继续处理，适合中途失败后从某页恢复
- 支持限制处理结束图片序号，适合按区间抽取
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
| `TEMPERATURE` | 模型温度 | `0.0` |
| `RESPONSE_FORMAT` | 响应格式：text/none、json_object、json_schema、auto | `auto` |
| `REQUEST_TIMEOUT` | 单次请求超时秒数 | `180` |
| `API_CALL_INTERVAL` | API调用间隔时间（秒） | `3.0` |
| `CONTEXT_PAGES_BEFORE` | 前面附带的上下文页数 | `1` |
| `CONTEXT_PAGES_AFTER` | 后面附带的上下文页数 | `0` |
| `CONSENSUS` | 是否启用共识机制（2次提取+AI裁决） | `true` |

#### 产物目录结构

使用 `ARTIFACT_DIR` + `ARTIFACT_NAME` 会自动创建完整的产物目录结构：

```
{ARTIFACT_DIR}/{ARTIFACT_NAME}/
  ├── batch{N}_{首图}-{末图}/    # 每个批次的文件夹
  │   ├── 1.json                  # 第1次提取响应
  │   ├── 2.json                  # 第2次提取响应（共识模式）
  │   ├── 1-2-diff.txt            # 批次内共识差异对比
  │   ├── 1-2-llm.json            # 批次内AI判断结果
  │   ├── overlapping_diff.txt    # 批次间重复页面差异
  │   └── overlapping_llm.json    # 批次间AI判断结果
  ├── run.log                     # 简要运行日志
  └── {ARTIFACT_NAME}.json        # 最终题库文件
```

## 完整流程

```bash
# 1. PDF 拆成图片
python split_pdf.py 试卷.pdf

# 2. 提取题目
python extract_questions.py --dir 试卷_images -o questions.json --log extract.log
```
