#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local kanban server.

Serves the dashboard UI and persists records to ./岗位数据库/看板数据.json.
If the JSON file does not exist yet, it seeds it from the embedded DATA block
inside 看板.html or kanban.html.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# 兼容 pythonw.exe（无控制台窗口）运行：stdout/stderr 为 None 时写入系统空设备
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

HOST = "127.0.0.1"
PORT = 8877

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
DATA_DIR = BASE_DIR / "岗位数据库"
DATA_FILE = DATA_DIR / "看板数据.json"
UI_FILE = APP_DIR / "kanban.html"
LEGACY_UI_FILE = APP_DIR / "看板.html"
DEFAULT_DATA = {"updatedAt": "", "profile": None, "jobs": [], "log": [], "links": []}

DATA_LOCK = threading.Lock()
BASELINE_DATA: dict[str, Any] | None = None


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_job(job: Any) -> dict[str, Any]:
    if not isinstance(job, dict):
        job = {}
    info = job.get("info") if isinstance(job.get("info"), dict) else {}
    duty = job.get("duty") if isinstance(job.get("duty"), list) else []
    req = job.get("req") if isinstance(job.get("req"), list) else []
    sg = job.get("sg") if isinstance(job.get("sg"), list) else []

    normalized_sg = []
    for item in sg:
        if isinstance(item, dict):
            stage = _str(item.get("s")).strip()
            date = _str(item.get("d"), "-").strip() or "-"
            if stage:
                normalized_sg.append({"s": stage, "d": date})

    return {
        "id": _str(job.get("id") or f"job-{os.urandom(4).hex()}"),
        "co": _str(job.get("co")).strip(),
        "role": _str(job.get("role")).strip(),
        "wish": _str(job.get("wish"), "-").strip() or "-",
        "date": _str(job.get("date")).strip(),
        "st": _str(job.get("st"), "todo").strip() or "todo",
        "m": int(job.get("m") or 0),
        "ml": _str(job.get("ml"), "low").strip() or "low",
        "info": {str(k): _str(v) for k, v in info.items()},
        "duty": [_str(item).strip() for item in duty if _str(item).strip()],
        "req": [_str(item).strip() for item in req if _str(item).strip()],
        "sg": normalized_sg,
        "res": _str(job.get("res")).strip(),
        "research": _str(job.get("research")).strip(),
        "prep": _str(job.get("prep")).strip(),
        "notes": _str(job.get("notes"), "【待填写】"),
    }


def _normalize_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else []
    log = data.get("log") if isinstance(data.get("log"), list) else []
    links = data.get("links") if isinstance(data.get("links"), list) else []
    profile = data.get("profile")
    if not isinstance(profile, dict) or not str(profile.get("name") or "").strip():
        profile = None
    else:
        profile = {str(k): _str(v) for k, v in profile.items()}
    return {
        "updatedAt": str(data.get("updatedAt") or ""),
        "profile": profile,
        "jobs": [_normalize_job(job) for job in jobs if isinstance(job, dict)],
        "log": [item for item in log if isinstance(item, dict)],
        "links": [item for item in links if isinstance(item, dict)],
    }


def _reset_preserving_custom_jobs(current: dict[str, Any]) -> dict[str, Any]:
    baseline = _normalize_data(BASELINE_DATA or DEFAULT_DATA)
    current_jobs = _normalize_data(current).get("jobs", [])
    baseline_ids = {str(job.get("id")) for job in baseline.get("jobs", [])}
    custom_jobs = [job for job in current_jobs if str(job.get("id")) not in baseline_ids]
    return {
        "updatedAt": baseline.get("updatedAt", ""),
        "profile": current.get("profile") or baseline.get("profile"),
        "jobs": baseline.get("jobs", []) + custom_jobs,
        "log": baseline.get("log", []),
        "links": baseline.get("links", []),
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return _normalize_data(json.load(handle))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(_normalize_data(data), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp_path, path)


def _extract_seed_data(text: str) -> dict[str, Any] | None:
    match = re.search(r"DATA\s*=\s*(\{.*?\});\s*bootstrapData", text, re.S)
    if not match:
        return None
    return _normalize_data(json.loads(match.group(1)))


def _load_seed_data() -> dict[str, Any]:
    # 开源版：无内置种子数据，首次使用从空模板开始，由前端引导创建个人资料
    return _normalize_data(DEFAULT_DATA)


def ensure_data_file() -> dict[str, Any]:
    global BASELINE_DATA
    with DATA_LOCK:
        if DATA_FILE.exists():
            data = _read_json(DATA_FILE)
        else:
            data = _load_seed_data()
            _write_json(DATA_FILE, data)
        if BASELINE_DATA is None:
            BASELINE_DATA = json.loads(json.dumps(data, ensure_ascii=False))
        return data


def read_data() -> dict[str, Any]:
    with DATA_LOCK:
        if DATA_FILE.exists():
            return _read_json(DATA_FILE)
        return ensure_data_file()


def write_data(data: Any) -> dict[str, Any]:
    normalized = _normalize_data(data)
    with DATA_LOCK:
        _write_json(DATA_FILE, normalized)
        return normalized


def reset_data() -> dict[str, Any]:
    global BASELINE_DATA
    with DATA_LOCK:
        current = _read_json(DATA_FILE) if DATA_FILE.exists() else _load_seed_data()
        baseline = BASELINE_DATA or _load_seed_data()
        BASELINE_DATA = json.loads(json.dumps(baseline, ensure_ascii=False))
        reset_payload = _reset_preserving_custom_jobs(current)
        _write_json(DATA_FILE, reset_payload)
        return reset_payload


class KanbanHandler(SimpleHTTPRequestHandler):
    server_version = "KanbanServer/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str = "text/html; charset=utf-8") -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"ok": True})
            return
        if path == "/api/data":
            self._send_json(read_data())
            return
        if path in {"/", "/kanban.html", "/看板.html"}:
            self._send_file(UI_FILE)
            return
        super().do_GET()

    def do_PUT(self) -> None:
        self._handle_write()

    def do_PATCH(self) -> None:
        self._handle_write()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/reset":
            self._send_json(reset_data())
            return
        self._handle_write()

    def _handle_write(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/data":
            self.send_error(HTTPStatus.NOT_FOUND, "API not found")
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            payload = raw_body.decode("utf-16")
        try:
            data = json.loads(payload or "{}")
            saved = write_data(data)
            self._send_json(saved)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)


def main() -> None:
    ensure_data_file()
    try:
        server = ThreadingHTTPServer((HOST, PORT), KanbanHandler)
    except OSError as exc:
        message = f"[错误] 看板服务启动失败：{exc}\n端口 {PORT} 可能已被占用，请先关闭已运行的看板后再试。"
        print(message)
        try:
            with (BASE_DIR / "服务错误.log").open("w", encoding="utf-8") as log_handle:
                log_handle.write(message + "\n")
        except Exception:
            pass
        return
    url = f"http://{HOST}:{PORT}/"
    print(f"Kanban server running at {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
