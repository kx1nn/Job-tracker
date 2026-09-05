# 🎯 JobTracker · 求职投递看板

一个**本地运行、开箱即用**的校招/求职投递管理看板。纯本地部署，数据只存在你自己电脑上，无需注册、无云端依赖。

## ✨ 特性

- 📋 **投递总览**：公司分组视图、状态筛选、关键词搜索、按投递日期排序
- ⚡ **快捷操作**：点击行查看详情与 JD、行内改状态、一键推进流程（待测评 → 测评完成 → 面试中 → Offer）、标记拒信
- 🕐 **最近动态**：所有新增/改状态/推进自动写入动态时间线
- 📥 **一键导出 CSV**：Excel 直接打开不乱码（UTF-8 BOM）
- 🤖 **AI 自动录入**：CLI 把任意岗位 JD 交给 AI 提取为结构化数据，直接写入看板
- 🧭 **官网入口**：常用校招官网链接汇总
- 👤 **首次引导**：第一次打开先创建个人资料，随后的界面标题、批次均为个人化展示

## 📁 目录结构

```
job-tracker/
├── start.bat            # 👈 用户唯一需要双击的文件（Windows 一键启动）
├── README.md
├── LICENSE
├── app/                 # 应用源码（用户无需关注）
│   ├── kanban.html      # 看板界面（单文件，无前端依赖）
│   ├── server.py        # 本地服务（端口 8877，Python 标准库）
│   └── cli.py           # 命令行工具：AI 提取 JD → 写入看板
└── 岗位数据库/           # 运行时自动创建，存放你的数据（已被 .gitignore 排除）
    └── 看板数据.json
```

## 🚀 快速开始

### 方式一：Windows 双击启动

双击 `start.bat`，浏览器自动打开 `http://127.0.0.1:8877/`。

### 方式二：命令行启动（Windows / macOS / Linux）

需要 Python 3.8+（无需安装任何第三方库）：

```bash
cd job-tracker
python app/server.py      # Windows
python3 app/server.py     # macOS / Linux
```

然后浏览器访问 <http://127.0.0.1:8877/>。

### 首次使用

首次打开会看到「创建个人资料」引导页（姓名、专业、届别、求职方向、批次）。填写后进入看板；之后可随时点右上角「✏️ 编辑资料」修改。

### 🖱 就这么简单

- **启动**：双击 `start.bat` → 浏览器自动打开看板，**命令行窗口自动关闭**
- **后台运行**：关掉窗口、关闭浏览器标签都不影响，随时重新打开 <http://127.0.0.1:8877/> 即可
- **关机后**：电脑重启后，再双击一次 `start.bat` 即可
- **数据安全**：数据实时保存在本地 `岗位数据库/看板数据.json`，关闭/重启不丢失

> macOS / Linux：`python3 app/server.py` 启动，`Ctrl+C` 停止。

## 🤖 CLI：用 AI 一键录入岗位

CLI 读取任意 JD 文本，调用你配置的 **OpenAI 兼容接口**（OpenAI / DeepSeek / 豆包 / 通义等）提取结构化字段，写入看板数据。

### 1. 配置环境变量（仅 AI 录入需要）

| 变量 | 说明 | 示例 |
|---|---|---|
| `OPENAI_API_KEY` | API 密钥（必填） | `sk-xxxx` |
| `OPENAI_BASE_URL` | 接口地址（可选） | 默认 `https://api.openai.com/v1`；DeepSeek 用 `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | 模型名（可选） | 默认 `gpt-4o-mini`；DeepSeek 用 `deepseek-chat` |

**各服务商配置对照表**（都兼容，任选一家即可）：

| 服务商 | `OPENAI_BASE_URL` | `OPENAI_MODEL` | 特点 |
|---|---|---|---|
| **DeepSeek**（推荐） | `https://api.deepseek.com/v1` | `deepseek-chat` | 便宜、国内支付 |
| 豆包（火山方舟） | `https://ark.cn-beijing.volces.com/api/v3` | 推理接入点 ID（形如 `ep-xxx`） | 字节自家、有免费额度 |
| 通义千问（阿里云百炼） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 有免费额度 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | 需海外支付方式 |

PowerShell 示例（DeepSeek）：

```powershell
$env:OPENAI_API_KEY = "sk-xxxx"
$env:OPENAI_BASE_URL = "https://api.deepseek.com/v1"
$env:OPENAI_MODEL = "deepseek-chat"
```

### 2. 录入岗位

```bash
# 直接把 JD 文本作为参数
python app/cli.py add "联想 2027届项目管理岗，部门：IDG/Global Supply Chain，地点：北京、深圳……"

# 从文件读取 JD（推荐：JD 较长时）
python app/cli.py add --file jd.txt

# 指定初始状态（默认 todo=待投递）
python app/cli.py add --file jd.txt --st wait

# 同公司同岗位已存在时，强制覆盖更新
python app/cli.py add --file jd.txt --force
```

### 3. 其他命令

```bash
python app/cli.py init      # 初始化数据文件
python app/cli.py list      # 列出当前看板中的岗位
python app/cli.py --help    # 完整帮助
```

> 💡 **不想用 AI？** 可以用 `--json` 直接写入结构化数据（跳过 AI 调用）：
> ```bash
> python app/cli.py add --json '{"co":"字节跳动","role":"产品经理","wish":"第一志愿","duty":["负责..."]}'
> ```

### 🎓 手把手：第一次用 AI 录入岗位（以 DeepSeek 为例）

**第 1 步 · 拿到密钥（约 2 分钟）**

1. 打开 DeepSeek 开放平台 <https://platform.deepseek.com>，注册并登录
2. 左侧「API Keys」→「创建 API Key」→ 复制生成的 `sk-...` 字符串（只显示一次，注意保存）

**第 2 步 · 配置（在命令行窗口执行）**

```powershell
$env:OPENAI_API_KEY = "sk-你复制的密钥"
$env:OPENAI_BASE_URL = "https://api.deepseek.com/v1"
$env:OPENAI_MODEL = "deepseek-chat"
```

**第 3 步 · 准备 JD 文本**

把岗位 JD 复制到一个文本文件，保存为 `jd.txt`（放在 job-tracker 目录里）。

**第 4 步 · 录入**

```powershell
# 进入你存放 job-tracker 的文件夹（把 jd.txt 也放这里）
cd C:\Users\你的用户名\Downloads\job-tracker
python app/cli.py add --file jd.txt
```

看到 `[OK] 新增成功：xxx公司 · xxx岗位` 就完成了。刷新看板页面，岗位已在列表里。

**想换其他家？** 见上方配置对照表，只改 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 即可。

### AI 提取规则

CLI 内置提取提示词，要求 AI 严格基于 JD 原文输出以下字段，**禁止编造**：

| 字段 | 说明 |
|---|---|
| `co` | 公司名 |
| `role` | 岗位名 |
| `wish` | 志愿（如"第一志愿"） |
| `date` | 投递日期 `YYYY-MM-DD`（缺省取当天） |
| `m` / `ml` | 匹配度 0-100 / 优先级 high·medium·low |
| `department` / `location` | 部门 / 地点 |
| `duty` / `req` | 岗位职责 / 任职要求（数组，每条一句话） |
| `notes` | 其他补充 |

## 📐 数据写入逻辑

看板的全部数据保存在 `岗位数据库/看板数据.json`（UTF-8）。数据结构如下：

```jsonc
{
  "updatedAt": "2026-09-05 20:43",   // 最后更新时间
  "profile": {                        // 个人资料（首次引导创建）
    "name": "张三", "major": "软件工程",
    "gradYear": "2027届", "direction": "后端开发", "batch": "2027届秋招"
  },
  "jobs": [ /* 岗位数组，见下 */ ],
  "log": [  // 最近动态，最多保留 30 条，新的在前
    { "date": "2026-09-05 20:43", "text": "新增岗位：联想 · 项目管理" }
  ],
  "links": [ // 官网入口
    { "name": "联想校招", "url": "https://..." }
  ]
}
```

### 岗位（job）字段

| 字段 | 类型 | 说明 | 枚举 / 示例 |
|---|---|---|---|
| `id` | string | 唯一标识 | 界面新增为 `job-{时间戳}`；CLI 为 `cli-{co+role 的 8 位 hash}` |
| `co` | string | 公司名 | `联想` |
| `role` | string | 岗位名 | `项目管理（非技术方向）` |
| `wish` | string | 志愿 | `第1志愿` / `-` |
| `date` | string | 投递日期 | `2026-08-08` |
| `st` | string | 状态 | `todo`(待投递) / `wait`(待笔试测评) / `assessdone`(测评完成) / `interview`(面试中) / `offer` / `reject`(拒信) / `canceled`(取消) |
| `m` | number | 匹配度 0-100 | `85` |
| `ml` | string | 优先级 | `high` / `medium` / `low` |
| `info` | object | 补充信息（键值） | `{"部门":"IDG","地点":"北京"}` |
| `duty` | string[] | 岗位职责 | `["全面统筹项目进程"]` |
| `req` | string[] | 任职要求 | `["2027届应届生"]` |
| `sg` | object[] | 流程时间线 | `[{"s":"✅ 已投递","d":"08.08"}]` |
| `res` / `research` / `prep` | string | 简历 / 调研官网 / 面试准备链接 | `https://...` |
| `notes` | string | 备注 / 面试复盘 | |

### 写入路径（三处都会写同一个 JSON）

1. **界面操作**（浏览器里点新增/编辑/改状态/推进/标记拒信）
   - 浏览器 `PUT /api/data` 把整份 DATA 写回服务端，服务端原子写盘（先写临时文件再替换，防写坏）
   - 每次写入同步更新 `updatedAt`，并追加一条 `log`
2. **CLI 录入**（`python app/cli.py add`）
   - 读取 JSON → AI 提取字段 → 规范化（补齐 `id`、校验 `st`/`ml` 枚举、清洗 `duty`/`req`/`sg` 数组）→ 追加 job → 写回
   - **幂等规则**：`id` 由 `co|role` 哈希生成，同一公司同一岗位再次 `add` 会提示"已存在"并跳过；加 `--force` 则覆盖该岗位（不产生重复记录）
3. **CLI 初始化**（`python app/cli.py init`）：数据文件不存在时创建空模板 `{profile:null, jobs:[], log:[], links:[]}`

> ⚠️ 两个进程同时写入可能互相覆盖，请勿同时运行 CLI 录入和浏览器编辑。

## 🔒 隐私说明

- 所有数据保存在本机 `岗位数据库/看板数据.json`，**不联网、不上传**
- AI 录入时，JD 文本会发送到你配置的 AI 接口（OpenAI / DeepSeek 等），请勿粘贴敏感信息
- 仓库 `.gitignore` 已排除 `岗位数据库/`，提交代码不会带上个人数据

## 📄 License

[MIT](./LICENSE)
