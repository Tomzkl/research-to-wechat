#!/usr/bin/env python3
"""extract_pdf.py — 财报/研报 → 结构化 JSON(表格抽取 + 关键指标扫描)

用法:
    python extract_pdf.py <报告.pdf|.txt|.md|.json> [--out out.json] [--max-chars 8000]

PDF 处理(推荐安装 pdfplumber,它自带 pypdfium2):
  - 文字提取用 pypdfium2(PDFium 引擎,中文 ToUnicode 更稳,避免「公/元/年」等字乱码)。
  - 表格抽取用 pdfplumber(识别利润表/资产负债表/现金流量表,检测列头单位)。
  - 未装: 退化为纯文本正则扫描(.txt/.md 始终走文本路径)。

输出 JSON 结构:
  {
    "source": "...",
    "meta": {"title": "..."},
    "statements": [                 # 从 PDF 表格抽取的三张报表(结构化)
      {"type": "income_statement|balance_sheet|cash_flow_statement|unknown",
       "unit": "元|万元|亿元|...", "columns": ["项目", "2025年", "2024年"],
       "rows": [{"label": "营业收入", "values": ["12340000000", "10000000000"]}]}
    ],
    "figures": [...],               # 扁平关键指标(正则预抽取,供核对步骤用)
    "raw_text_preview": "...",
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

# 三张报表的关键词(用于识别表格类型)
STATEMENT_KEYWORDS = {
    "income_statement": ["营业收入", "营业成本", "营业利润", "利润总额", "净利润", "每股收益", "毛利"],
    "balance_sheet": ["货币资金", "应收账款", "存货", "固定资产", "总资产", "总负债",
                      "所有者权益", "流动资产", "流动负债", "资产总计", "负债合计"],
    "cash_flow_statement": ["经营活动产生的现金流量", "投资活动产生的现金流量",
                            "筹资活动产生的现金流量", "现金及现金等价物"],
}


def extract_text(path: str) -> str:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".pdf":
        return _pdf_to_text(p)
    if p.suffix.lower() in (".txt", ".md", ".text", ".markdown"):
        return p.read_text(encoding="utf-8", errors="replace")
    raise SystemExit(f"不支持的文件类型: {p.suffix} (支持 .pdf/.txt/.md)")


def _pdf_to_text(p: pathlib.Path) -> str:
    # 文字提取优先 pypdfium2(PDFium 引擎,中文 ToUnicode 处理最稳),
    # 它对部分中文财报 PDF 的字体映射比 pdfminer 更可靠,能避免「公/元/年」等字乱码。
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(p))
        try:
            return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
        finally:
            pdf.close()
    except ImportError:
        pass
    except Exception:
        pass  # pypdfium2 处理异常则回退到 pdfplumber/pypdf

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
        "抽取 PDF 需要安装 pypdfium2 / pdfplumber / pypdf 之一:\n"
        "    pip install pdfplumber   # 含 pypdfium2(中文友好)+ pdfplumber(表格友好)\n"
    )


# ---------- 表格抽取(仅 PDF) ----------

def extract_pdf_tables(path: str):
    """返回 PDF 中所有表格(每个表格 = 二维列表)。pdfplumber 未装时返回 None。"""
    try:
        import pdfplumber
    except ImportError:
        return None
    tables = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables():
                tables.append(t)
    return tables


def classify_table(rows) -> str:
    """按关键词命中数,判断表格属于哪张报表。"""
    text = " ".join(" ".join(str(c or "") for c in row) for row in rows)
    scores = {k: sum(text.count(kw) for kw in kws) for k, kws in STATEMENT_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def detect_unit(text: str):
    """从表格文本里识别金额单位(列头「单位:万元」或单元格里的「万元」)。"""
    m = re.search(r"单位[:：]?\s*(元|万元|亿元|千元|百万元)", text)
    if m:
        return m.group(1)
    for u in ("亿元", "万元", "千元", "百万元", "元"):
        if u in text:
            return u
    return None


def _is_title_row(row) -> bool:
    joined = "".join(row)
    return bool(joined) and not any(ch.isdigit() for ch in joined)


def table_to_statement(table):
    """把一张二维表格转成结构化 statement;非数据表返回 None。"""
    rows = []
    for raw in table:
        cells = [("" if c is None else str(c).strip().replace("\n", " ")) for c in raw]
        if any(cells):
            rows.append(cells)
    if not rows:
        return None

    # 跳过开头无数字的标题行(如「合并利润表」「资产负债表」)
    idx = 0
    while idx < len(rows) and _is_title_row(rows[idx]):
        idx += 1
    if idx >= len(rows):
        return None
    header = rows[idx]
    data_rows = rows[idx + 1:]

    text = " ".join(" ".join(r) for r in rows)
    stype = classify_table(rows)
    unit = detect_unit(text)

    parsed = []
    for r in data_rows:
        if not r or not r[0]:
            continue
        if all(not c or set(c) <= set("-—:：") for c in r):
            continue
        parsed.append({"label": r[0], "values": [v for v in r[1:] if v]})
    if not parsed:
        return None
    return {"type": stype, "unit": unit, "columns": [c for c in header if c], "rows": parsed}


# ---------- 文本正则扫描(兼容 .txt/.md 及无表格的 PDF) ----------

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
    ap = argparse.ArgumentParser(description="财报/研报 → 结构化 JSON(表格抽取 + 指标扫描)")
    ap.add_argument("input", help="报告文件(.pdf/.txt/.md/.json)")
    ap.add_argument("--out", help="输出 JSON 路径(默认 stdout)")
    ap.add_argument("--max-chars", type=int, default=8000, help="原文预览长度")
    args = ap.parse_args()

    src = args.input
    if src.lower().endswith(".json"):
        data = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    else:
        p = pathlib.Path(src)
        text = extract_text(src)
        meta = scan_meta(text)
        meta["unit_hint"] = detect_unit(text)
        data = {
            "source": src,
            "meta": meta,
            "statements": [],
            "figures": scan_figures(text),
            "raw_text_preview": text[:args.max_chars],
            "warnings": [],
        }

        if p.suffix.lower() == ".pdf":
            tables = extract_pdf_tables(src)
            if tables:
                for t in tables:
                    stmt = table_to_statement(t)
                    if stmt:
                        data["statements"].append(stmt)
                kinds = {s["type"] for s in data["statements"]}
                data["warnings"].append(
                    f"已从 PDF 抽取 {len(data['statements'])} 张表格"
                    f"({', '.join(sorted(kinds)) or 'unknown'})。单位与金额仍需回原文复核。"
                )
            else:
                data["warnings"].append("PDF 未检测到表格,仅做文本正则扫描;建议人工核对关键数字。")

    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out} (statements: {len(data.get('statements', []))}, figures: {len(data.get('figures', []))})")
    else:
        print(out)


if __name__ == "__main__":
    main()
