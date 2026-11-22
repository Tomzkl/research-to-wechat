#!/usr/bin/env python3
"""render_wechat.py — Markdown → 公众号可粘贴 HTML(内联样式,零依赖)

公众号约束: 只认内联样式,不认外链资源;图片需手动上传。
用法:
    python render_wechat.py <article.md> [--out article.html]

支持: h1-h3 / 段落 / 加粗 / 斜体 / 行内代码 / 引用 / 有序无序列表 /
      表格 / 代码块 / 分隔线 / 图片占位符。
"""
import re
import html
import sys
import argparse
import pathlib

# Windows 下 print 中文默认走 GBK 会乱码;强制 stdout/stderr 用 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 公众号风格基础样式(内联,因为公众号编辑器不认 <style>)
STYLE = {
    "body": "margin:0;padding:16px;color:#3f3f3f;font-size:16px;line-height:1.8;"
            "font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;word-break:break-word;",
    "h1": "font-size:22px;font-weight:700;color:#1a1a1a;margin:24px 0 12px;",
    "h2": "font-size:19px;font-weight:700;color:#1a1a1a;margin:20px 0 10px;",
    "h3": "font-size:17px;font-weight:700;color:#1a1a1a;margin:16px 0 8px;",
    "p": "margin:0 0 14px;",
    "blockquote": "margin:0 0 14px;padding:10px 14px;background:#f7f7f7;"
                  "border-left:3px solid #c0c0c0;color:#666;font-size:15px;",
    "ul": "margin:0 0 14px;padding-left:22px;",
    "ol": "margin:0 0 14px;padding-left:22px;",
    "li": "margin:4px 0;",
    "code": "background:#f2f2f2;padding:2px 5px;border-radius:3px;font-size:14px;"
            "font-family:Consolas,Menlo,monospace;",
    "pre": "background:#f2f2f2;padding:12px;border-radius:4px;overflow-x:auto;font-size:14px;",
    "table": "border-collapse:collapse;margin:0 0 14px;width:100%;font-size:14px;",
    "th": "border:1px solid #ddd;padding:8px;background:#fafafa;font-weight:700;text-align:left;",
    "td": "border:1px solid #ddd;padding:8px;",
    "hr": "border:none;border-top:1px solid #e5e5e5;margin:20px 0;",
    "a": "color:#576b95;text-decoration:none;",
}


def inline(text: str) -> str:
    """行内元素: 转义 → 加粗/行内代码/斜体/链接。"""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", lambda m: f'<code style="{STYLE["code"]}">{m.group(1)}</code>', text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{m.group(2)}" style="{STYLE["a"]}">{m.group(1)}</a>', text)
    return text


def render_table(lines):
    rows = [ln for ln in lines if re.match(r"^\s*\|", ln)]
    if not rows:
        return None
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    # 去掉分隔行(|---|)
    cells = [r for r in cells if r and not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    if not cells:
        return None
    out = [f'<table style="{STYLE["table"]}">']
    for i, row in enumerate(cells):
        tag, sty = ("th", STYLE["th"]) if i == 0 else ("td", STYLE["td"])
        out.append("<tr>" + "".join(f'<{tag} style="{sty}">{inline(c)}</{tag}>' for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def render(md: str) -> str:
    lines = md.splitlines()
    out = []
    i = 0
    in_list = None
    in_pre = False
    pre_buf = []

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            if not in_pre:
                in_pre, pre_buf = True, []
            else:
                in_pre = False
                out.append(f'<pre style="{STYLE["pre"]}">{html.escape(chr(10).join(pre_buf))}</pre>')
            i += 1
            continue
        if in_pre:
            pre_buf.append(line)
            i += 1
            continue

        # 表格: 当前行以 | 开头,下一行是分隔行
        if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"[\s|:\-]+", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            close_list()
            tbl = render_table(lines[i:j])
            if tbl:
                out.append(tbl)
            i = j
            continue

        if s == "":
            close_list()
            i += 1
            continue
        if re.fullmatch(r"-{3,}", s):
            close_list()
            out.append(f'<hr style="{STYLE["hr"]}">')
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            close_list()
            lvl = len(m.group(1))
            out.append(f'<h{lvl} style="{STYLE["h" + str(lvl)]}">{inline(m.group(2))}</h{lvl}>')
            i += 1
            continue

        if s.startswith(">"):
            close_list()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f'<blockquote style="{STYLE["blockquote"]}">'
                       f'{"<br>".join(inline(b) for b in buf)}</blockquote>')
            continue

        m = re.match(r"^[-*+]\s+(.*)$", s)
        if m:
            if in_list != "ul":
                close_list()
                out.append(f'<ul style="{STYLE["ul"]}">')
                in_list = "ul"
            out.append(f'<li style="{STYLE["li"]}">{inline(m.group(1))}</li>')
            i += 1
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", s)
        if m:
            if in_list != "ol":
                close_list()
                out.append(f'<ol style="{STYLE["ol"]}">')
                in_list = "ol"
            out.append(f'<li style="{STYLE["li"]}">{inline(m.group(1))}</li>')
            i += 1
            continue

        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if m:
            close_list()
            alt = html.escape(m.group(1)) or "图片"
            out.append(f'<p style="margin:0 0 14px;color:#999;font-size:13px;text-align:center;">'
                       f'【图片占位:{alt}】<br><span style="color:#999;">请手动上传图片后替换此占位</span></p>')
            i += 1
            continue

        close_list()
        out.append(f'<p style="{STYLE["p"]}">{inline(s)}</p>')
        i += 1

    close_list()
    return f'<div style="{STYLE["body"]}">\n' + "\n".join(out) + "\n</div>"


def main():
    ap = argparse.ArgumentParser(description="Markdown → 公众号 HTML(内联样式)")
    ap.add_argument("input", help="Markdown 文件")
    ap.add_argument("--out", help="输出 HTML 路径(默认 stdout)")
    args = ap.parse_args()
    result = render(pathlib.Path(args.input).read_text(encoding="utf-8"))
    if args.out:
        pathlib.Path(args.out).write_text(result, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(result)


if __name__ == "__main__":
    main()
