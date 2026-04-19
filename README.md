# Aegis Torture

一个本地运行的、由 LLM 驱动的每日算法与工程知识自测系统。每次运行会生成一份包含算法编程题和多项选择题的试卷，批改后自动更新你的学习画像，并在下次出题时优先考察薄弱环节。

## 功能

- **2+1 算法题**：从本地题库随机抽取 2 道，LLM 额外生成 1 道带业务外壳的原创题
- **12 道 MCQ**：覆盖后端工程、分布式、LLM、强化学习等多个技术领域，每 4 题中 2 道纯理论、2 道业务场景应用
- **自适应出题**：Profiler 模块根据历史得分和遗忘曲线动态加权，优先复现薄弱知识点
- **两种作答方式**：直接编辑 Markdown 文件，或启动本地 Web 服务在浏览器中作答
- **自动批改与画像更新**：MCQ 精确判分，算法题由 LLM 按逻辑正确性 / 复杂度 / 工程质量三维评分

## 快速开始

### 1. 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器（或直接用 pip）

### 2. 安装依赖

```bash
uv sync
# 或
pip install -r requirements.txt
```

### 3. 配置

在项目根目录创建 `.env` 文件：

```env
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://api.openai.com/v1   # 兼容 OpenAI 格式的任意接口
LLM_MODEL=gpt-4o

# 可选，以下为默认值
LOCAL_BANK_PATH=./local_bank
DATA_PATH=./data
OUTPUT_PATH=./output
```

### 4. 使用

```bash
# 生成今日试卷（同时输出 Markdown 文件和题目 JSON）
python main.py run

# 在浏览器中作答（推荐）
python main.py serve
# 或指定端口
python main.py serve --port=9090

# 批改最新一份试卷并更新学习画像（CLI 作答模式）
python main.py grade

# 单独重新生成进度报告
python main.py report
```

### CLI 作答流程

1. `python main.py run` 生成 `output/Exam_YYYYMMDD_HHMMSS.md`
2. 在 Markdown 文件中填写答案：
   - MCQ：将 `**你的答案: [ ]**` 改为 `**你的答案: [A, C]**`
   - 算法题：在对应代码块中编写 Python 解法
3. `python main.py grade` 批改并更新 `data/learning_progress.md`

## 目录结构

```
.
├── main.py                  # 统一入口
├── config.py                # 配置加载
├── local_bank/              # 本地算法题库（.py 文件）
├── data/                    # 运行时数据（mcq_stats.json, problem_set_*.json）
├── output/                  # 生成的试卷（Exam_*.md）
├── profiler/                # 学习画像与出题权重模块
├── problem_synthesizer/     # 题目生成模块
├── exam_formatter/          # 试卷排版模块
├── grader/                  # 批改模块
└── server/                  # Flask Web 服务
```
