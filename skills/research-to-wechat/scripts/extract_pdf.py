#!/usr/bin/env python3
"""extract_pdf.py — 财报/研报 → 结构化 JSON(预抽取 + 关键指标扫描)

用法:
    python extract_pdf.py <报告.pdf|.txt|.md|.json> [--out out.json] [--max-chars 8000]

PDF 文本抽取依赖(可选,按顺序尝试): pdfplumber > pypdf。未安装时:
  - .txt / .md 直接读取(无需依赖)
  - .pdf 会给出安装提示: pip install pdfplumber   (表格友好,推荐)

输出 JSON 结构:
  {
    "source": "...",
    "meta": {"title": "..."},
    "figures": [{"metric": "营业收入", "value": 123.4, "unit": "亿元", "period": "2025Q3", "context": "原文片段"}],
    "raw_text_preview": "...",   # 前 N 字符,供回原文核对
    "warnings": [...]
  }

注意: 本脚本是"预抽取脚手架",不是权威结果。最终以报告原文为准。
"""
import json
import re
import sys
import argparse
import pathlib

# Windows 下 print 中文默认走 GBK 会乱码;强制 stdout/stderr 用 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 关键指标(扫描时按长度降序,避免「净利润」误匹配「归母净利润」的子串)
METRICS = [
    "营业总收入", "营业收入", "归属于母公司股东的净利润", "归母净利润",
    "扣除非经常性损益的净利润", "扣非净利润", "净利润", "毛利率", "净利率",
    "净资产收益率", "ROE", "每股收益", "经营活动产生的现金流量净额",
    "货币资金", "资产负债率", "总资产", "资产总计", "总负债", "负债合计",
    "所有者权益", "股东权益",
]
SORTED_METRICS = sorted(METRICS, key=len, reverse=True)

UNIT_RE = r"(亿元|万元|千元|百万元|元|亿|万|%|％)"
NUM_RE = r"([-+]?\d[\d,\.]*)"


def extract_text(path: str) -> str:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".pdf":
        return _pdf_to_text(p)
    if p.suffix.lower() in (".txt", ".md", ".text", ".markdown"):
        return p.read_text(encoding="utf-8", errors="replace")
    raise SystemExit(f"不支持的文件类型: {p.suffix} (支持 .pdf/.txt/.md)")


def _pdf_to_text(p: pathlib.Path) -> str:
    for lib in ("pdfplumber", "pypdf"):
        try:
            if lib == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(p) as pdf:
                    return "\n".join((page.extract_text() or "") for page in pdf.pages)
            else:
                from pypdf import PdfReader
                return "\n".join((page.extract_text() or "") for page in PdfReader(str(p)).pages)
        except ImportError:
            continue
    raise SystemExit(
        "抽取 PDF 需要安装 pdfplumber 或 pypdf:\n"
        "    pip install pdfplumber   # 表格友好,推荐\n"
        "    pip install pypdf        # 轻量备选\n"
    )


def scan_figures(text: str) -> list:
    figures = []
    consumed = []  # 已占用的字符区间,避免「净利润」重复匹配「归母净利润」
    for metric in SORTED_METRICS:
        pat = re.compile(re.escape(metric) + r"\s*[:：]?\s*" + NUM_RE + r"\s*" + UNIT_RE)
        for m in pat.finditer(text):
            span = (m.start(), m.end())
            if any(not (span[1] <= s or e <= span[0]) for s, e in consumed):
                continue
            consumed.append(span)
            ctx = text[max(0, m.start() - 20):m.end() + 20].replace("\n", " ")
            figures.append({
                "metric": metric,
                "value": float(m.group(1).replace(",", "")),
                "unit": m.group(2),
                "context": ctx,
            })
    return figures


def scan_meta(text: str) -> dict:
    title = ""
    for line in text.splitlines()[:40]:
        line = line.strip()
        if line and len(line) < 80 and not line.startswith(("#", "//", "证券代码", "证券简称")):
            title = line
            break
    return {"title": title}


def main():
    ap = argparse.ArgumentParser(description="财报/研报 → 结构化 JSON(预抽取)")
    ap.add_argument("input", help="报告文件(.pdf/.txt/.md/.json)")
    ap.add_argument("--out", help="输出 JSON 路径(默认 stdout)")
    ap.add_argument("--max-chars", type=int, default=8000, help="原文预览长度")
    args = ap.parse_args()

    src = args.input
    if src.lower().endswith(".json"):
        data = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    else:
        text = extract_text(src)
        data = {
            "source": src,
            "meta": scan_meta(text),
            "figures": scan_figures(text),
            "raw_text_preview": text[:args.max_chars],
            "warnings": ["仅预抽取,以原文为准;PDF 表格/扫描件可能漏抽,请人工复核关键数字。"],
        }

    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out} (figures: {len(data.get('figures', []))} 条)")
    else:
        print(out)


if __name__ == "__main__":
    main()
