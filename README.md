# AI 自动化课程视频生成系统

这是一个使用 Python 实现的课程内容自动生产工具。输入一篇中文课程文稿，系统会自动完成课程结构拆解、口播稿润色、语音合成、课件渲染、字幕切分、视频合成，并输出：

- 带配音、逐句字幕和要点高亮的 `MP4` 课程视频
- 可继续编辑、带演讲者备注的 `PPTX` 课件
- 每个处理阶段的结构化 `JSON`、音频和图片中间产物

项目同时提供命令行入口和 FastAPI Web 界面，支持多套视觉主题、MiniMax 音色选择，以及 LLM/TTS 失败时的自动降级。

---

## 1. 系统能力

输入：

- 一篇 UTF-8 编码的 `.txt` 课程文稿
- 或通过 Web 页面直接粘贴课程文稿

处理：

1. 使用 OpenAI 兼容接口把文稿拆成课程、页面、要点和讲解片段。
2. 将书面讲解稿改写成更自然的中文口播稿。
3. 导出可编辑 PowerPoint，并把每页口播稿写入演讲者备注。
4. 为每个讲解片段生成独立音频。
5. 使用 Pillow 渲染课件页面、当前要点高亮和逐句字幕。
6. 使用 MoviePy 将静态画面和对应音频切片顺序拼接为视频。

输出：

```text
runs/<run_id>/
├── 01_structure.json
├── 02_scripts.json
├── 03_with_audio.json
├── 04_with_frames.json
├── course.pptx
├── output.mp4
├── audio/
│   ├── seg_000.mp3
│   └── ...
└── slides/
    ├── slide_00_base.png
    ├── slide_00_seg_00_cap_00.png
    └── ...
```

---

## 2. 技术栈与框架

| 层次 | 技术 | 用途 |
|---|---|---|
| 语言 | Python 3.13 | 主程序与全部处理流程 |
| Web 框架 | FastAPI | 上传文稿、创建任务、查询进度、下载结果 |
| Web 服务器 | Uvicorn | 运行 FastAPI 应用 |
| LLM SDK | OpenAI Python SDK | 调用 OpenAI 兼容 Chat Completions 接口 |
| TTS | MiniMax Speech API | 正式中文语音合成 |
| TTS 降级 | edge-tts | 无 MiniMax 或调用失败时的免费语音 |
| 离线降级 | Python `wave` | 生成静音占位音频，保证流程可跑通 |
| 图片渲染 | Pillow | 课件背景、文字、高亮框和字幕渲染 |
| PPT 导出 | python-pptx | 生成可编辑的 `.pptx` 课件 |
| 视频合成 | MoviePy | 图片、音频切片和最终视频拼接 |
| FFmpeg | imageio-ffmpeg | 为 MoviePy 提供内置 FFmpeg |
| 配置 | python-dotenv | 从 `.env` 加载本地配置 |
| 文件上传 | python-multipart | 解析 FastAPI 表单和上传文件 |

系统不依赖 ImageMagick。字幕和高亮均由 Pillow 直接绘制。

---

## 3. 总体架构

```text
                         ┌─────────────────┐
                         │ CLI: main.py    │
                         └────────┬────────┘
                                  │
输入文稿 ─────────────────────────┼───────┐
                                  │       │
                         ┌────────▼───────▼─┐
                         │ Web: app.py      │
                         │ FastAPI + Thread │
                         └────────┬─────────┘
                                  │ pipeline.run()
                         ┌────────▼─────────┐
                         │ src/pipeline.py  │
                         │ 端到端流程编排    │
                         └────────┬─────────┘
                                  │
        ┌─────────────┬───────────┼───────────┬──────────────┐
        │             │           │           │              │
 ┌──────▼─────┐ ┌─────▼─────┐ ┌──▼────────┐ ┌▼───────────┐ ┌▼─────────┐
 │ src/llm.py │ │ pptx_export│ │ src/tts.py│ │src/slides.py│ │src/video │
 │ 结构与口播  │ │ 可编辑 PPT │ │ 语音合成  │ │图片与字幕渲染│ │视频合成  │
 └──────┬─────┘ └─────┬─────┘ └──┬────────┘ └┬───────────┘ └┬─────────┘
        │             │           │           │              │
        └─────────────┴───────────┴─────┬─────┴──────────────┘
                                        │
                              ┌─────────▼─────────┐
                              │ src/models.py     │
                              │ Course 数据模型    │
                              └───────────────────┘
```

`src/pipeline.py` 是系统中心。CLI 和 Web 层都不直接操作 LLM、TTS 或视频模块，而是统一调用 `pipeline.run()`。

---

## 4. 项目目录

```text
mianshi/
├── main.py                 # 命令行入口
├── app.py                  # FastAPI 服务与内嵌前端
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── .gitignore              # 忽略密钥、虚拟环境和生成产物
├── data/
│   └── sample_input.txt    # 示例课程文稿
├── runs/                   # 每次运行的输出目录
└── src/
    ├── __init__.py         # 包标识与版本号
    ├── config.py           # 配置、主题、音色、字体探测
    ├── models.py           # Course/Slide/Segment/Caption
    ├── llm.py              # 课程拆解、口播润色、规则兜底
    ├── tts.py              # MiniMax/Edge/Offline TTS
    ├── slides.py           # Pillow 页面、高亮和字幕渲染
    ├── pptx_export.py      # 可编辑 PPTX 导出
    ├── video.py            # MoviePy 视频合成
    └── pipeline.py         # 端到端流水线
```

---

## 5. 核心数据模型

模型定义在 `src/models.py`，层级如下：

```text
Course
└── Slide[]
    └── Segment[]
        └── Caption[]
```

### 5.1 `Course`

表示一门完整课程：

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | `str` | 课程标题 |
| `subtitle` | `str` | 课程副标题 |
| `slides` | `list[Slide]` | 页面列表 |

`Course.to_json()` 用于保存阶段快照，`Course.load_json()` 可从快照恢复数据。

### 5.2 `Slide`

表示一页课件：

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | `str` | 页面标题 |
| `bullets` | `list[str]` | 页面展示的要点 |
| `segments` | `list[Segment]` | 该页的讲解片段 |
| `index` | `int` | 页面序号 |
| `kind` | `str` | `cover`、`content` 或 `summary` |
| `base_image` | `str \| None` | 运行时生成的基础页面路径 |

### 5.3 `Segment`

Segment 是系统最关键的时间与表现单位。一页通常包含：

- 一个 `intro`：进入页面时的过渡讲解，不高亮要点
- 多个 `bullet`：每个要点对应一段讲解，并高亮对应要点

| 字段 | 类型 | 说明 |
|---|---|---|
| `kind` | `str` | `intro` 或 `bullet` |
| `script` | `str` | TTS 和字幕使用的口播稿 |
| `bullet_index` | `int` | 对应页面要点下标，intro 为 `-1` |
| `audio_path` | `str \| None` | 运行时生成的音频路径 |
| `duration` | `float` | 音频时长 |
| `frame_path` | `str \| None` | 片段首帧路径 |
| `captions` | `list[Caption]` | 片段内逐句字幕 |

### 5.4 `Caption`

一个 Segment 会继续切成多个 Caption：

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | `str` | 当前字幕文本 |
| `start` | `float` | 相对片段音频的起始秒数 |
| `duration` | `float` | 显示时长 |
| `frame_path` | `str \| None` | 对应该字幕的完整画面 |

这种设计让视频合成不需要动态绘制文字。每条 Caption 预先对应一张完整图片和一段音频切片。

---

## 6. 端到端处理流程

核心函数：

```python
pipeline.run(
    input_text,
    run_dir,
    progress_cb=None,
    subtitle=True,
    theme=None,
    voice=None,
)
```

### 阶段 1：课程结构化

`src/llm.py::structure_course()` 将原始文稿转换为 `Course`。

LLM 提示词要求模型输出 JSON，包括：

- 课程标题和副标题
- 6 到 10 页幻灯片
- 页面类型
- 每页标题和 2 到 4 条要点
- 页面过渡讲解
- 与每条要点一一对应的讲解稿

LLM 返回结果经 `_course_from_struct()` 转为项目内部数据模型。函数会自动补齐不足的 `bullet_scripts`，防止要点与讲解数量不一致导致越界。

如果没有配置 API Key、请求失败、JSON 无法解析或返回空页面，系统会调用 `_rule_based_structure()`：

1. 按空行切分段落。
2. 第一行作为课程标题。
3. 每个段落生成一页。
4. 段落首句生成页标题和 intro。
5. 后续句子最多取四条作为要点。
6. 最后一页标记为 `summary`。

`LAST_STATUS` 记录本次是否真正使用 LLM，供 Web 页面显示降级警告。

### 阶段 2：口播稿润色

`src/llm.py::polish_narration()` 按页面调用 LLM，要求：

- 保持原意
- 增加自然断句和停顿
- 使用适量课堂衔接词
- 不明显增加篇幅
- 保持输入输出数组长度一致

某一页润色失败时，只保留该页原稿，不中断整个任务。

### 阶段 3：导出可编辑 PPT

`src/pptx_export.py::export_pptx()` 使用 python-pptx 生成标准 16:9 文件：

- 封面：居中大标题和主题强调线
- 内容页：标题、强调线和要点列表
- 配色：跟随当前主题
- 演讲者备注：该页所有 Segment 的口播稿，以空行分隔

PPT 导出属于非关键步骤。导出异常会被记录，但视频流程仍继续执行。

### 阶段 4：逐片段语音合成

`src/tts.py::synthesize()` 为每个 Segment 生成独立音频。

当 `TTS_PROVIDER=minimax` 时，尝试顺序为：

```text
MiniMax -> Edge TTS -> Offline 静音
```

当 `TTS_PROVIDER=edge` 时：

```text
Edge TTS -> Offline 静音
```

当 `TTS_PROVIDER=offline` 时，只生成离线静音。

MiniMax 使用 `/v1/t2a_v2` 接口，输出 32 kHz、128 kbps、单声道 MP3。遇到状态码 `1002` 时采用指数退避，最长尝试六次。

Offline 模式按照“中文约每秒 4.5 字”估算时长，生成 16 kHz 单声道 WAV 静音文件。它的目的是验证完整流水线，不提供真实朗读。

### 阶段 5：页面与字幕帧渲染

`src/slides.py::render_slide_frames()` 使用 Pillow 渲染：

1. 当前主题的渐变背景
2. 页面标题和强调线
3. 要点列表
4. 当前 bullet 对应的半透明高亮框
5. 当前 Caption 对应的底部字幕

标题支持自动缩小字号。换行逻辑会把英文和数字串视为一个整体，避免英文单词从中间拆开。

`build_captions()` 先按句号、问号和感叹号切句，长句再按逗号、顿号和分号切分。字幕时间按各句字符数占比分配，最后一条字幕吸收浮点累计误差。

每个页面会生成：

- 一个不含字幕和高亮的 `base` 图片
- 每个 Segment、每条 Caption 对应的一张完整图片

### 阶段 6：视频合成

`src/video.py::compose_course()` 遍历全部 Caption：

1. 加载 Segment 的完整音频。
2. 根据 Caption 的 `start` 和 `duration` 截取音频。
3. 使用 Caption 对应图片创建等长 `ImageClip`。
4. 将图片和音频切片绑定。
5. 按课程顺序拼接全部 Clip。
6. 使用 H.264 和 AAC 写出 MP4。

编码参数：

```text
视频编码：libx264
音频编码：aac
Preset：medium
线程数：4
帧率：VIDEO_FPS
```

---

## 7. 核心脚本说明

### `main.py`：CLI 入口

负责：

- 解析输入文件、输出目录、主题、音色和字幕参数
- 读取 UTF-8 文稿
- 创建默认时间戳输出目录
- 打印 LLM/TTS 配置
- 将进度回调转换为控制台进度条
- 调用 `pipeline.run()`

参数：

```text
--input, -i       输入文稿，默认 data/sample_input.txt
--out, -o         输出目录，默认 runs/<时间戳>
--no-subtitle     不渲染字幕
--theme           视觉主题
--voice           MiniMax voice_id
```

### `app.py`：Web 应用

FastAPI 后端和单页前端都在此文件中。

后端使用守护线程执行耗时任务，避免生成过程阻塞 HTTP 请求。任务状态存放在进程内的 `JOBS` 字典：

```python
{
    "progress": 0.0,
    "message": "排队中…",
    "status": "queued | running | done | error",
    "result": {...},
    "error": "...",
}
```

前端使用原生 HTML/CSS/JavaScript：

- 文本输入或 `.txt` 文件上传
- 主题色卡选择
- MiniMax 音色下拉框
- 字幕开关
- 每 1.2 秒轮询任务状态
- 在线预览 MP4
- 下载 MP4 和 PPTX

### `src/config.py`：配置中心

负责：

- 加载 `.env`
- 探测 Windows、Linux 和 macOS 中文字体
- 定义 MiniMax 音色列表
- 定义六套视觉主题
- 把环境变量转换为 `Settings`

主题：

| ID | 名称 | 风格 |
|---|---|---|
| `apple` | 简约亮色 | 浅灰背景、橙色强调 |
| `ink` | 宣纸学术 | 暖米白背景、朱红强调 |
| `mint` | 薄荷清新 | 浅绿背景、翡翠强调 |
| `dark` | 深色专业 | 藏蓝背景、橙色强调 |
| `ocean` | 深海蓝 | 深蓝背景、青色强调 |
| `violet` | 霓夜紫 | 深紫背景、亮紫强调 |

### `src/models.py`：共享数据协议

所有处理模块都通过 `Course` 数据结构交换信息，避免模块间依赖临时字典。每完成一个阶段，模型都会序列化为 JSON，便于定位具体阶段的问题。

### `src/llm.py`：课程理解与文案处理

主要公开函数：

- `structure_course(text)`：文稿转课程结构
- `polish_narration(course)`：逐页润色口播稿

主要内部函数：

- `_chat_json()`：统一的 OpenAI 兼容 JSON 请求
- `_course_from_struct()`：LLM JSON 转内部模型
- `_rule_based_structure()`：无 LLM 时的本地规则拆解

### `src/tts.py`：语音合成

主要公开函数：

- `synthesize(text, out_path)`：自动选择 TTS 并返回实际路径和时长

内部实现：

- `_minimax()`：MiniMax HTTP API
- `_edge()`：edge-tts 异步合成
- `_offline()`：本地静音 WAV
- `_probe_duration()`：使用 MoviePy 或 WAV 元数据获取时长

### `src/slides.py`：图片渲染

主要能力：

- 字体缓存
- 中英文混排换行
- 标题自动缩放
- 主题渐变背景
- 封面和内容页布局
- 要点区域位置记录
- 当前要点高亮
- 最多两行字幕
- Caption 切分和时间分配
- 逐字幕帧导出

### `src/pptx_export.py`：PPTX 导出

使用当前主题生成可编辑形状和文本，而不是把页面导出为整张图片。老师可以在 PowerPoint 中继续修改标题和要点，口播稿保存在演讲者备注中。

### `src/video.py`：视频编码

负责将所有 Caption 的静态图片和对应音频切片组成 MoviePy Clip，并按课程顺序拼接。`_subclip()` 同时兼容 MoviePy 1.x 和 2.x 的音频截取方法。

### `src/pipeline.py`：总调度器

负责：

- 接收一次任务的主题和音色
- 创建输出目录
- 串联全部阶段
- 保存四份 JSON 快照
- 上报进度
- 汇总最终结果

返回示例：

```json
{
  "video": "runs/demo/output.mp4",
  "pptx": "runs/demo/course.pptx",
  "llm_used": true,
  "warning": "",
  "course_title": "大模型应用开发入门",
  "slides": 7,
  "segments": 25,
  "video_seconds": 318.4,
  "elapsed_seconds": 142.7,
  "run_dir": "runs/demo"
}
```

---

## 8. 安装与启动

### 8.1 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 8.2 创建本地配置

Windows：

```powershell
Copy-Item .env.example .env
```

macOS/Linux：

```bash
cp .env.example .env
```

真实密钥只写入 `.env`。`.env` 已在 `.gitignore` 中，不要把密钥写入源码、README 或 `.env.example`。

### 8.3 CLI 运行

使用示例文稿：

```powershell
python main.py --input data/sample_input.txt --out runs/demo
```

选择主题和音色：

```powershell
python main.py `
  --input data/sample_input.txt `
  --theme ocean `
  --voice "Chinese (Mandarin)_Radio_Host"
```

关闭字幕：

```powershell
python main.py --input data/sample_input.txt --no-subtitle
```

### 8.4 Web 运行

```powershell
uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

开发时可开启自动重载：

```powershell
uvicorn app:app --reload --port 8000
```

---

## 9. Web API

### `GET /`

返回内嵌 Web 页面。

### `POST /api/generate`

创建生成任务，使用 `multipart/form-data`。

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `file` | 文件 | 空 | UTF-8 `.txt` 文稿 |
| `text` | 字符串 | 空 | 直接粘贴的文稿 |
| `subtitle` | 布尔 | `true` | 是否叠加字幕 |
| `theme` | 字符串 | `apple` | 视觉主题 |
| `voice` | 字符串 | 空 | MiniMax voice_id |

如果同时提交文件和文本，文件内容优先。

响应：

```json
{"job_id": "20260614_123456_a1b2c3"}
```

### `GET /api/status/{job_id}`

返回任务状态、进度、提示、结果或错误。

### `GET /api/video/{job_id}`

任务完成后下载或预览 MP4。

### `GET /api/pptx/{job_id}`

任务完成后下载 PPTX。

---

## 10. 环境变量

### LLM

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | OpenAI 兼容 API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 地址 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名 |

### TTS

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TTS_PROVIDER` | `minimax` | `minimax`、`edge` 或 `offline` |
| `MINIMAX_API_KEY` | 空 | MiniMax API Key |
| `MINIMAX_GROUP_ID` | 空 | MiniMax Group ID |
| `MINIMAX_API_HOST` | `https://api.minimax.io` | MiniMax 国际站或国内站 |
| `MINIMAX_MODEL` | `speech-01-turbo` | 语音模型 |
| `MINIMAX_VOICE` | `female-shaonv` | 默认 voice_id |
| `MINIMAX_SPEED` | `1.0` | 语速 |
| `EDGE_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 音色 |

### 视频与主题

| 变量 | 默认值 | 说明 |
|---|---|---|
| `THEME` | `apple` | 默认视觉主题 |
| `VIDEO_WIDTH` | `1920` | 视频宽度 |
| `VIDEO_HEIGHT` | `1080` | 视频高度 |
| `VIDEO_FPS` | `24` | 视频帧率 |
| `CJK_FONT_PATH` | 空 | 自定义中文字体路径 |

---

## 11. 中间产物与排错

### `01_structure.json`

检查：

- LLM 是否正确理解课程结构
- 页面数量和类型是否合理
- bullets 与 bullet segments 是否对应

### `02_scripts.json`

检查润色后的口播稿是否过长、偏离原意或包含不适合朗读的格式。

### `03_with_audio.json`

检查：

- 每个 Segment 是否有 `audio_path`
- `duration` 是否合理
- 是否从 MP3 降级成 WAV 静音

### `04_with_frames.json`

检查：

- 每个 Caption 的时间
- `frame_path` 是否存在
- 当前 bullet 是否被正确高亮

### `slides/`

可以直接打开 PNG，检查字体、换行、主题、高亮和字幕，无需重新编码视频。

---

## 12. 降级与容错策略

| 故障 | 系统行为 |
|---|---|
| 未配置 LLM Key | 使用本地规则拆解 |
| LLM 请求或 JSON 解析失败 | 使用本地规则拆解，并返回 warning |
| 某页口播润色失败 | 保留该页原始讲解稿 |
| PPTX 导出失败 | 记录错误，继续生成视频 |
| MiniMax 未配置或失败 | 尝试 Edge TTS |
| Edge TTS 失败或断网 | 生成离线静音 WAV |
| Caption 时间超过真实音频 | 合成时裁剪到真实音频范围 |
| 没有任何可合成片段 | 抛出“没有可合成的片段”错误 |

---

## 13. 当前限制

1. 字幕时间按字符数比例估算，不是基于语音识别的词级对齐。
2. Web 任务状态只保存在进程内存，服务重启后无法查询旧任务。
3. Web 使用本地线程执行任务，不适合直接承担大量并发生产任务。
4. `settings.theme_name` 和 `settings.minimax_voice` 是进程级可变配置；并发任务选择不同主题或音色时可能互相影响。
5. 生成过程中没有断点续跑；任务中断后需要重新执行或手工复用中间产物。
6. 页面布局主要针对每页 2 到 4 条短要点，过多或过长文本可能超出画面。
7. LLM 使用 Chat Completions 的 `response_format=json_object`，接入的兼容服务必须支持或正确忽略该参数。
8. 规则兜底依赖文稿的段落结构，输入缺少空行时，页面拆分质量会下降。

---

## 14. 扩展指南

### 添加视觉主题

在 `src/config.py` 的 `THEMES` 中新增 `Theme`。CLI 的可选参数和 Web 色卡会自动读取该字典。

### 添加 MiniMax 音色

在 `MINIMAX_VOICES` 中添加：

```python
("voice_id", "中文名称", "适用场景")
```

Web 下拉框会自动显示，合法值校验也会自动更新。

### 接入新的 TTS

1. 在 `src/tts.py` 实现新的私有函数，返回 `(audio_path, duration)`。
2. 在 `synthesize()` 中加入 provider 和回退顺序。
3. 在 `.env.example` 与本文档补充配置项。

### 提高字幕精度

可以在 TTS 后增加 Whisper 或云端语音识别对齐阶段，把 `build_captions()` 的字符比例时间替换为真实词句时间戳。

### 生产化任务系统

建议将：

- `JOBS` 替换为 Redis 或数据库
- 本地线程替换为 Celery、RQ 或独立 worker
- 进程级主题/音色改为显式参数传递
- 生成产物上传到对象存储
- 增加任务取消、重试、超时和清理策略

---

## 15. 安全与版本管理

`.gitignore` 已排除：

```text
.env
.venv/
__pycache__/
runs/
*.mp4
*.mp3
*.wav
```

安全要求：

- 不要把真实 API Key 写入 `.env.example`
- 不要在日志中打印完整 Authorization Header
- 对已经泄露或进入共享文件的 Key 立即作废并重新生成
- 对外部署 Web 服务时增加认证、上传大小限制和任务配额

---

## 16. 建议的后续工作

优先级较高的改进：

1. 增加 `pytest`，覆盖模型序列化、规则拆课、字幕切分和离线 TTS。
2. 消除全局可变主题/音色，保证并发任务隔离。
3. 增加持久化任务队列和失败重试。
4. 增加 Whisper 字幕对齐。
5. 增加页面文本溢出检测。
6. 增加中间阶段恢复和产物自动清理。

