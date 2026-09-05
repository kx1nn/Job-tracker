#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""job-tracker CLI：用 AI 把岗位 JD 提取为结构化数据并写入看板。

零第三方依赖，仅使用 Python 标准库，支持任意 OpenAI 兼容接口
（OpenAI / DeepSeek / 豆包 / 通义 等，通过 base_url 切换）。

用法：
  python cli.py init                            # 初始化数据文件（不存在时自动创建）
  python cli.py add "<JD 文本>"                  # AI 提取并新增一个岗位
  python cli.py add --file jd.txt               # 从文件读取 JD 文本
  python cli.py add --json '{"co":"字节跳动",...}'  # 跳过 AI，直接按 JSON 写入
  python cli.py add "<JD>" --st wait            # 指定初始状态（默认 todo）
  python cli.py add "<JD>" --force              # 同公司同岗位已存在时覆盖更新
  python cli.py list                            # 列出当前看板里的岗位

环境变量（AI 提取时必填）：
  OPENAI_API_KEY     API 密钥
  OPENAI_BASE_URL    接口地址，默认 https://api.openai.com/v1
                     DeepSeek:  https://api.deepseek.com/v1
                     豆包:       https://ark.cn-beijing.volces.com/api/v3
  OPENAI_MODEL       模型名，默认 gpt-4o-mini（DeepSeek 可设 deepseek-chat）

数据写入逻辑：
  1. 读取 岗位数据库/看板数据.json（不存在则创建空模板）
  2. AI 提取字段（co/role/wish/date/m/ml/duty/req/info/notes）
  3. 规范化：补齐 id（cli-{co+role 的 8 位 hash}）、状态枚举校验、数组字段清洗
  4. 幂等：同 id 岗位已存在时提示并跳过；--force 则覆盖更新
  5. 追加「最近动态」日志（unshift，最多保留 30 条）
  6. 原子写回（先写临时文件再替换，避免写一半损坏数据）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
DATA_DIR = BASE_DIR / "岗位数据库"
DATA_FILE = DATA_DIR / "看板数据.json"

DEFAULT_DATA: dict[str, Any] = {
    "updatedAt": "",
    "profile": None,
    "jobs": [],
    "log": [],
    "links": [],
}

ST_OPTIONS = ["todo", "wait", "assessdone", "interview", "offer", "reject", "canceled"]
ML_OPTIONS = ["high", "medium", "low"]

EXTRACT_PROMPT = """你是岗位信息提取器。请把用户提供的岗位 JD 整理为严格的 JSON 对象，只输出 JSON，不要任何解释或 Markdown 代码块。

必须输出的字段（没有信息的字段给空值或省略）：
{
  "co": "公司名（中文全称或常用简称）",
  "role": "岗位名（如 项目管理工程师）",
  "wish": "志愿（如 第一志愿；没有则省略）",
  "date": "投递日期（YYYY-MM-DD，JD 未提供则省略）",
  "m": "匹配度分值 0-100 的整数（你根据 JD 与通用校招画像估算）",
  "ml": "优先级，只允许 high/medium/low 之一",
  "department": "部门或业务线",
  "location": "工作地点",
  "education": "学历要求",
  "experience": "经验要求",
  "duty": ["职责1", "职责2", "..."],
  "req": ["要求1", "要求2", "..."],
  "notes": "其他补充说明（JD 亮点等，没有则省略）"
}

规则：
1. 严格基于原文提取，禁止编造 JD 中没有的信息；
2. duty 与 req 保留原文要点，每条一句话；
3. 公司名缺失时用“未知公司”占位，岗位名缺失时用“未知岗位”占位；
4. 只输出一个 JSON 对象。"""


# ---------- 基础工具 ----------

def now_stamp() -> str:
    d = datetime.now()
    return d.strftime("%Y-%m-%d %H:%M")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_data() -> dict[str, Any]:
    if DATA_FILE.exists():
        with DATA_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    data = json.loads(json.dumps(DEFAULT_DATA, ensure_ascii=False))
    save_data(data)
    return data


def save_data(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, DATA_FILE)


def push_log(data: dict[str, Any], text: str) -> None:
    log = data.get("log") if isinstance(data.get("log"), list) else []
    log.insert(0, {"date": now_stamp(), "text": str(text)})
    data["log"] = log[:30]


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    co = str(raw.get("co") or "").strip()
    role = str(raw.get("role") or "").strip()
    st = str(raw.get("st") or "todo").strip()
    if st not in ST_OPTIONS:
        st = "todo"
    ml = str(raw.get("ml") or "").strip()
    if ml not in ML_OPTIONS:
        m = int(raw.get("m") or 0)
        ml = "high" if m >= 85 else "medium" if m >= 65 else "low"
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    duty = [str(v).strip() for v in (raw.get("duty") or []) if str(v).strip()]
    req = [str(v).strip() for v in (raw.get("req") or []) if str(v).strip()]
    sg = []
    for item in raw.get("sg") or []:
        if isinstance(item, dict) and str(item.get("s") or "").strip():
            sg.append({"s": str(item["s"]).strip(), "d": str(item.get("d") or "-").strip() or "-"})
    return {
        "id": str(raw.get("id") or new_job_id(co, role)),
        "co": co,
        "role": role,
        "wish": str(raw.get("wish") or "-").strip() or "-",
        "date": str(raw.get("date") or "").strip(),
        "st": st,
        "m": int(raw.get("m") or 0),
        "ml": ml,
        "info": {str(k): str(v) for k, v in info.items()},
        "duty": duty,
        "req": req,
        "sg": sg,
        "res": str(raw.get("res") or "").strip(),
        "research": str(raw.get("research") or "").strip(),
        "prep": str(raw.get("prep") or "").strip(),
        "notes": str(raw.get("notes") or "【CLI+AI 录入】").strip(),
    }


def new_job_id(co: str, role: str) -> str:
    """确定性 id：同公司同岗位重跑得到相同 id，便于 --force 覆盖。"""
    digest = hashlib.sha1(f"{co}|{role}".encode("utf-8")).hexdigest()[:8]
    return f"cli-{digest}"


def map_extracted(raw: dict[str, Any]) -> dict[str, Any]:
    """把 AI 返回的字段映射为 job 结构。"""
    co = str(raw.get("co") or raw.get("company") or "未知公司").strip()
    role = str(raw.get("role") or raw.get("岗位") or "未知岗位").strip()
    info: dict[str, str] = {}
    for key, label in (("department", "部门"), ("location", "地点"),
                       ("education", "学历"), ("experience", "经验")):
        value = str(raw.get(key) or "").strip()
        if value:
            info[label] = value
    m = raw.get("m")
    try:
        m = int(m) if m is not None else 0
    except (TypeError, ValueError):
        m = 0
    m = max(0, min(100, m))
    ml = str(raw.get("ml") or "").strip()
    if ml not in ML_OPTIONS:
        ml = "high" if m >= 85 else "medium" if m >= 65 else "low"
    duty = raw.get("duty") or raw.get("responsibilities") or []
    req = raw.get("req") or raw.get("requirements") or []
    notes = str(raw.get("notes") or "【CLI+AI 录入】").strip()
    return {
        "co": co, "role": role,
        "wish": str(raw.get("wish") or "-").strip() or "-",
        "date": str(raw.get("date") or today()).strip(),
        "m": m, "ml": ml,
        "info": info,
        "duty": [str(v).strip() for v in duty if str(v).strip()],
        "req": [str(v).strip() for v in req if str(v).strip()],
        "notes": notes,
    }


# ---------- AI 提取 ----------

def ai_extract(jd_text: str, api_key: str, base_url: str, model: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": jd_text},
        ],
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    # 部分兼容接口支持 JSON 输出模式；不支持时由 prompt 兜底
    payload["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"[错误] AI 接口返回 {exc.code}：{detail}\n"
            f"请检查 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 配置是否正确。"
        )
    except urllib.error.URLError as exc:
        raise SystemExit(f"[错误] 无法连接 AI 接口：{exc.reason}\n请检查网络与 OPENAI_BASE_URL。")
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise SystemExit(f"[错误] AI 接口返回格式异常：{json.dumps(body, ensure_ascii=False)[:300]}")
    text = str(content).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] AI 返回的不是有效 JSON：{exc}\n返回内容：{text[:300]}")


# ---------- 子命令 ----------

def cmd_init(_: argparse.Namespace) -> int:
    data = load_data()
    print(f"[OK] 数据文件已就绪：{DATA_FILE}")
    print(f"     现有岗位 {len(data.get('jobs') or [])} 条")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    data = load_data()
    jobs = data.get("jobs") or []
    if not jobs:
        print("（暂无岗位）")
        return 0
    print(f"共 {len(jobs)} 条岗位：")
    for idx, job in enumerate(jobs, 1):
        print(f"  {idx}. [{job.get('st','?')}] {job.get('co','?')} · {job.get('role','?')}"
              f"（{job.get('date','-')}，分 {job.get('m',0)}，{job.get('ml','?')}）")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    if args.json_text:
        try:
            extracted = json.loads(args.json_text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[错误] --json 不是有效 JSON：{exc}")
        job = map_extracted(extracted)
        source = "JSON"
    else:
        jd_text = args.jd or ""
        if args.file:
            try:
                jd_text = Path(args.file).read_text(encoding="utf-8")
            except OSError as exc:
                raise SystemExit(f"[错误] 无法读取文件 {args.file}：{exc}")
        jd_text = jd_text.strip()
        if not jd_text:
            raise SystemExit("[错误] 请提供 JD 文本（位置参数）或 --file 文件路径")
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise SystemExit(
                "[错误] 未配置 OPENAI_API_KEY。\n"
                "请先设置环境变量，例如（PowerShell）：\n"
                "  $env:OPENAI_API_KEY = \"sk-...\"\n"
                "或（CMD）：\n"
                "  set OPENAI_API_KEY=sk-..."
            )
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
        print(f"[AI] 正在用 {model} 提取岗位信息…")
        extracted = ai_extract(jd_text, api_key, base_url, model)
        job = map_extracted(extracted)
        source = "AI"

    job["id"] = new_job_id(job["co"], job["role"])
    if args.st:
        job["st"] = args.st if args.st in ST_OPTIONS else "todo"
    job = normalize_job(job)
    if not job["co"] or not job["role"]:
        raise SystemExit("[错误] 公司名与岗位名不能为空，请检查提取结果")

    data = load_data()
    jobs = data.get("jobs") or []
    existing = next((i for i, j in enumerate(jobs) if str(j.get("id")) == job["id"]), None)
    if existing is not None and not args.force:
        print(f"[跳过] 岗位已存在：{job['co']} · {job['role']}（id={job['id']}）")
        print("       如需覆盖更新，请加 --force")
        return 1
    if existing is not None:
        jobs[existing] = job
        push_log(data, f"CLI 更新岗位：{job['co']} · {job['role']}")
        action = "更新"
    else:
        jobs.append(job)
        push_log(data, f"CLI 新增岗位：{job['co']} · {job['role']}")
        action = "新增"
    data["jobs"] = jobs
    data["updatedAt"] = now_stamp()
    save_data(data)
    print(f"[OK] {action}成功：{job['co']} · {job['role']}（{job['st']}）")
    print(f"     写入：{DATA_FILE}")
    return 0


# ---------- 入口 ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="job-tracker CLI：AI 提取 JD 并写入求职投递看板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="初始化数据文件")

    p_add = sub.add_parser("add", help="新增/更新岗位（AI 提取或直接 JSON）")
    p_add.add_argument("jd", nargs="?", help="JD 文本")
    p_add.add_argument("--file", help="从文件读取 JD 文本")
    p_add.add_argument("--json", dest="json_text", help="直接传入 job JSON（跳过 AI）")
    p_add.add_argument("--st", help=f"初始状态，可选：{'/'.join(ST_OPTIONS)}（默认 todo）")
    p_add.add_argument("--force", action="store_true", help="同 id 岗位已存在时覆盖更新")

    sub.add_parser("list", help="列出当前岗位")

    args = parser.parse_args()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "add":
        return cmd_add(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
