#!/usr/bin/env python3
"""刷新并整理小红书小工具容器能力指南。"""

from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_URL = "https://fe-video-qc.xhscdn.com/fe-platform-file/104101b8323q4m0uaga06277180ac7t8006ptl0e12ek1g"
SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES_DIR = SKILL_DIR / "references"
HTML_PATH = REFERENCES_DIR / "guide.html"
MARKDOWN_PATH = REFERENCES_DIR / "guide.md"
STATE_PATH = REFERENCES_DIR / ".update-state.json"
REQUIRED_MARKDOWN_MARKERS = (
    "# 小工具容器 · 能力清单",
    "## 01 运行环境",
    "## 02 可用能力",
    "### 2.5 资源加载规则",
    "## 03 端能力 JS API",
    "### 3.1 调用约定",
    "### 3.2 API 一览",
    "### 3.3 postNote — 发布笔记",
    "### 3.4 saveImageToPhotosAlbum — 保存图片到相册",
    "### 3.5 writeTempFile — base64 转临时文件",
    "## 04 不可用能力",
    "### 4.1 已禁用的 Web API",
    "### 4.2 已禁用的行为",
    "### 4.3 移动端不支持",
    "## 05 WebGL / 图形计算边界",
    "## 06 常见问题 FAQ",
)
MIN_TABLE_COUNT = 10
MIN_CODE_BLOCK_COUNT = 4


class GuideValidationError(ValueError):
    """表示下载内容不是可用的小工具能力指南。"""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


class GuideMarkdownParser(HTMLParser):
    """不依赖第三方包，将指南提取为便于阅读的 Markdown。"""

    BLOCK_TAGS = {"p", "li", "summary"}
    SKIP_TAGS = {"style", "script", "noscript", "aside", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.skip_depth = 0
        self.block_tag: str | None = None
        self.block_parts: list[str] = []
        self.blocks: list[str] = []
        self.heading_level: int | None = None
        self.in_pre = False
        self.pre_parts: list[str] = []
        self.in_table = False
        self.table_rows: list[list[str]] = []
        self.table_row: list[str] | None = None
        self.table_cell: list[str] | None = None
        self.inline_code = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "body":
            self.in_body = True
            return
        if not self.in_body:
            return
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in self.SKIP_TAGS:
            self.skip_depth = 1
            return
        if tag == "pre":
            self.in_pre = True
            self.pre_parts = []
            return
        if tag == "table":
            self.in_table = True
            self.table_rows = []
            return
        if self.in_table:
            if tag == "tr":
                self.table_row = []
            elif tag in {"th", "td"}:
                self.table_cell = []
            elif tag == "br" and self.table_cell is not None:
                self.table_cell.append("<br>")
            elif tag == "code" and self.table_cell is not None:
                self.table_cell.append("`")
            return
        if self.in_pre:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._flush_block()
            self.heading_level = int(tag[1])
            self.block_tag = tag
            self.block_parts = []
            return
        classes = set((attrs_dict.get("class") or "").split())
        if tag in self.BLOCK_TAGS or (tag == "div" and classes.intersection({"answer", "txt", "meta"})):
            self._flush_block()
            self.block_tag = tag
            self.block_parts = []
            return
        if tag == "br" and self.block_tag:
            self.block_parts.append("\n")
        elif tag == "code" and self.block_tag:
            self.block_parts.append("`")
            self.inline_code = True
        elif tag in {"b", "strong"} and self.block_tag:
            self.block_parts.append("**")

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            self._flush_block()
            self.in_body = False
            return
        if not self.in_body:
            return
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "pre" and self.in_pre:
            code = "".join(self.pre_parts).strip("\n")
            self.blocks.append(f"```javascript\n{code}\n```")
            self.in_pre = False
            self.pre_parts = []
            return
        if self.in_table:
            if tag == "code" and self.table_cell is not None:
                self.table_cell.append("`")
            elif tag in {"th", "td"} and self.table_cell is not None:
                cell = clean_text("".join(self.table_cell)).replace("|", "\\|")
                if self.table_row is not None:
                    self.table_row.append(cell)
                self.table_cell = None
            elif tag == "tr" and self.table_row is not None:
                if any(self.table_row):
                    self.table_rows.append(self.table_row)
                self.table_row = None
            elif tag == "table":
                self._emit_table()
                self.in_table = False
            return
        if tag == "code" and self.block_tag and self.inline_code:
            self.block_parts.append("`")
            self.inline_code = False
        elif tag in {"b", "strong"} and self.block_tag:
            self.block_parts.append("**")
        if self.block_tag == tag:
            self._flush_block()

    def handle_data(self, data: str) -> None:
        if not self.in_body or self.skip_depth:
            return
        if self.in_pre:
            self.pre_parts.append(data)
        elif self.in_table and self.table_cell is not None:
            self.table_cell.append(data)
        elif self.block_tag and data.strip():
            self.block_parts.append(data)

    def _flush_block(self) -> None:
        if not self.block_tag:
            return
        value = clean_text("".join(self.block_parts))
        if value:
            if self.heading_level:
                value = re.sub(r"^(0[1-9])(?=\D)", r"\1 ", value)
                value = f"{'#' * self.heading_level} {value}"
            elif self.block_tag == "li":
                value = f"- {value}"
            elif self.block_tag == "summary":
                value = f"**问：{value}**"
            self.blocks.append(value)
        self.block_tag = None
        self.block_parts = []
        self.heading_level = None
        self.inline_code = False

    def _emit_table(self) -> None:
        if not self.table_rows:
            return
        width = max(len(row) for row in self.table_rows)
        rows = [row + [""] * (width - len(row)) for row in self.table_rows]
        lines = ["| " + " | ".join(rows[0]) + " |"]
        lines.append("| " + " | ".join(["---"] * width) + " |")
        lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
        self.blocks.append("\n".join(lines))
        self.table_rows = []

    def markdown(self) -> str:
        self._flush_block()
        return "\n\n".join(self.blocks).strip() + "\n"


def to_markdown(source: str, fetched_at: str) -> str:
    parser = GuideMarkdownParser()
    parser.feed(source)
    body = parser.markdown()
    prefix = (
        "# 小红书小工具容器能力指南\n\n"
        f"- 官方来源：{SOURCE_URL}\n"
        f"- 本地同步时间：{fetched_at}\n"
        "- 说明：本文件由更新脚本从官方 HTML 自动生成；如格式有歧义，请查阅 `guide.html`。\n\n"
    )
    return prefix + body


def build_validated_markdown(source: str, fetched_at: str) -> str:
    markdown = to_markdown(source, fetched_at)
    missing = [marker for marker in REQUIRED_MARKDOWN_MARKERS if marker not in markdown]
    if missing:
        raise GuideValidationError(f"缺少核心内容：{'、'.join(missing)}")
    table_count = len(re.findall(r"(?m)^\| ---", markdown))
    if table_count < MIN_TABLE_COUNT:
        raise GuideValidationError(f"表格数量异常：期望至少 {MIN_TABLE_COUNT} 个，实际 {table_count} 个")
    code_block_count = markdown.count("```javascript\n")
    if code_block_count < MIN_CODE_BLOCK_COUNT:
        raise GuideValidationError(
            f"代码示例数量异常：期望至少 {MIN_CODE_BLOCK_COUNT} 个，实际 {code_block_count} 个"
        )
    return markdown


def read_state() -> dict[str, object]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def write_state(state: dict[str, object]) -> None:
    atomic_write(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def parse_force() -> bool:
    args = sys.argv[1:]
    if not args:
        return False
    if args == ["--force"]:
        return True
    if args in (["-h"], ["--help"]):
        print(
            "用法：update_guide.py [--force]\n\n"
            "刷新并整理小红书小工具容器能力指南。\n\n"
            "选项：\n"
            "  -h, --help  显示此帮助信息并退出\n"
            "  --force     即使今日已经检查过，仍然再次检查"
        )
        raise SystemExit(0)
    print(f"参数错误：不支持的参数：{' '.join(args)}", file=sys.stderr)
    print("请运行 update_guide.py --help 查看用法。", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    force = parse_force()

    now = datetime.now().astimezone()
    today = now.date().isoformat()
    checked_at = now.isoformat(timespec="seconds")
    state = read_state()
    cache_exists = HTML_PATH.exists() and MARKDOWN_PATH.exists()

    if not force and state.get("checked_on") == today and cache_exists:
        print(f"指南：使用缓存；{today} 已检查；来源={SOURCE_URL}")
        return 0

    headers = {"User-Agent": "Codex-XHS-Mini-Tool-Guide/1.0"}
    if state.get("etag"):
        headers["If-None-Match"] = str(state["etag"])
    if state.get("last_modified"):
        headers["If-Modified-Since"] = str(state["last_modified"])

    request = Request(SOURCE_URL, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            source = raw.decode(charset, errors="replace")
            fetched_at = checked_at
            digest = hashlib.sha256(raw).hexdigest()
            try:
                markdown = build_validated_markdown(source, fetched_at)
            except GuideValidationError as exc:
                error = f"内容校验失败：{exc}"
            else:
                atomic_write(HTML_PATH, source)
                atomic_write(MARKDOWN_PATH, markdown)
                state.update(
                    {
                        "source_url": SOURCE_URL,
                        "checked_on": today,
                        "checked_at": checked_at,
                        "fetched_at": fetched_at,
                        "status": "已更新",
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "sha256": digest,
                        "error": None,
                    }
                )
                write_state(state)
                print(f"指南：已更新；sha256={digest[:12]}；来源={SOURCE_URL}")
                return 0
    except HTTPError as exc:
        if exc.code == 304 and cache_exists:
            try:
                cached_source = HTML_PATH.read_text(encoding="utf-8")
                fetched_at = str(state.get("fetched_at") or checked_at)
                markdown = build_validated_markdown(cached_source, fetched_at)
            except (GuideValidationError, OSError) as cache_exc:
                error = f"缓存校验失败：{cache_exc}"
            else:
                atomic_write(MARKDOWN_PATH, markdown)
                state.update(
                    {
                        "source_url": SOURCE_URL,
                        "checked_on": today,
                        "checked_at": checked_at,
                        "status": "未变更",
                        "error": None,
                    }
                )
                write_state(state)
                print(f"指南：内容未变更；来源={SOURCE_URL}")
                return 0
        else:
            error = f"HTTP {exc.code}：{exc.reason}"
    except (URLError, TimeoutError, OSError, UnicodeError) as exc:
        error = str(exc)

    state.update(
        {
            "source_url": SOURCE_URL,
            "checked_on": today,
            "checked_at": checked_at,
            "status": "错误",
            "error": error,
        }
    )
    write_state(state)
    if cache_exists:
        print(f"指南：刷新失败，继续使用缓存；错误={error}", file=sys.stderr)
        return 0
    print(f"指南：刷新失败且没有可用缓存；错误={error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
