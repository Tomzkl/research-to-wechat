#!/usr/bin/env python3
"""validate_figures.py — 财务数字交叉核对

输入 figures JSON:
  {
    "figures": [
      {"metric": "营业收入", "value": 123.4, "unit": "亿元", "period": "2025Q3"},
      {"metric": "营业收入", "value": 100.0, "unit": "亿元", "period": "2024Q3", "growth": 23.4}
    ]
  }

输出核对报告:
  {"summary": {"total": N, "fail": N, "warn": N}, "checks": [{"level": "PASS|WARN|FAIL", "metric": "...", "message": "..."}]}
"""
import json
import sys
import argparse
import pathlib

# Windows 下 print 中文默认走 GBK 会乱码;强制 stdout/stderr 用 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

UNIT_TO_SCALE = {
    "元": 1.0, "千元": 1e3, "万元": 1e4, "百万元": 1e6, "亿元": 1e8,
    "亿": 1e8, "万": 1e4, "%": None, "％": None,
}
RATE_METRICS = ("毛利率", "净利率", "净资产收益率", "ROE", "资产负债率")


def norm_value(value, unit):
    """把带单位的值归一到「元」,便于跨单位比较;比率类原样返回。"""
    if unit in (None, "", "%", "％"):
        return value
    scale = UNIT_TO_SCALE.get(unit)
    return None if scale is None else value * scale


# ---------- 一致性核对 ----------

def check_duplicates(figures):
    """同名同期指标出现多个且数值不一致 → FAIL(冲突)。"""
    seen, out = {}, []
    for f in figures:
        key = (f.get("metric"), f.get("period"))
        val = f.get("value")
        if key in seen and seen[key].get("value") != val:
            out.append({
                "level": "FAIL", "metric": f.get("metric"),
                "message": f"{key[0]} ({key[1]}) 出现冲突值: {seen[key].get('value')} vs {val}",
            })
        elif key not in seen:
            seen[key] = f
    return out


def check_growth(figures):
    """有本期+上期时重算同比,与报告给的 growth 对比。"""
    by_metric = {}
    for f in figures:
        by_metric.setdefault(f.get("metric"), []).append(f)
    out = []
    for metric, items in by_metric.items():
        periods = sorted({i.get("period") for i in items if i.get("period")})
        if len(periods) < 2:
            continue
        cur = next((i for i in items if i.get("period") == periods[-1]), None)
        prev = next((i for i in items if i.get("period") == periods[-2]), None)
        if not (cur and prev and prev.get("value")):
            continue
        calc = (cur["value"] - prev["value"]) / prev["value"] * 100
        stated = next((i.get("growth") for i in items if i.get("growth") is not None), None)
        if stated is not None:
            diff = abs(calc - stated)
            out.append({
                "level": "PASS" if diff < 0.5 else "WARN", "metric": metric,
                "message": f"{metric}: 计算同比 {calc:.2f}% vs 报告声称 {stated}%",
            })
    return out


def check_ranges(figures):
    """比率类指标 sanity 检查(应在 [0,100]% 内)。"""
    out = []
    for f in figures:
        if f.get("metric") in RATE_METRICS and f.get("unit") in ("%", "％"):
            v = f.get("value")
            if v is None:
                continue
            if not (0 <= v <= 100):
                out.append({
                    "level": "WARN", "metric": f.get("metric"),
                    "message": f"{f.get('metric')} = {v}% 超出合理范围 [0,100]",
                })
    return out


def check_balance(figures):
    """资产 ≈ 负债 + 权益(三者都在时,偏差 >1% 标 FAIL)。"""
    vals = {}
    for f in figures:
        m = f.get("metric")
        if m in ("总资产", "资产总计", "总负债", "负债合计", "所有者权益", "股东权益") and m not in vals:
            vals[m] = (norm_value(f.get("value"), f.get("unit")), f.get("value"), f.get("unit"))
    assets = vals.get("总资产") or vals.get("资产总计")
    liab = vals.get("总负债") or vals.get("负债合计")
    equity = vals.get("所有者权益") or vals.get("股东权益")
    if not (assets and liab and equity):
        return []
    a, l, e = assets[0], liab[0], equity[0]
    if a is None or l is None or e is None or not a:
        return []
    diff = abs(a - (l + e)) / a
    return [{
        "level": "PASS" if diff < 0.01 else "FAIL", "metric": "资产负债表",
        "message": f"资产({assets[1]}{assets[2]}) vs 负债({liab[1]}{liab[2]})+权益({equity[1]}{equity[2]}): 偏差 {diff * 100:.2f}%",
    }]


# ---------- 财务语义核对(新增) ----------

def check_metric_consistency(figures):
    """口径检查:净利润 vs 归母净利润、扣非 vs 归母。"""
    out = []
    periods = sorted({f.get("period") for f in figures if f.get("period")})
    for period in periods:
        def pick(metric):
            return next((f for f in figures if f.get("metric") == metric and f.get("period") == period), None)
        net, guimu, kf = pick("净利润"), pick("归母净利润"), pick("扣非净利润")
        if net and guimu and net.get("value") == guimu.get("value"):
            out.append({"level": "WARN", "metric": "净利润",
                        "message": f"净利润 == 归母净利润 ({period}),口径可能混淆(净利润应含少数股东损益)。"})
        if kf and guimu and guimu.get("value") is not None and kf.get("value") is not None and kf["value"] > guimu["value"]:
            out.append({"level": "WARN", "metric": "扣非净利润",
                        "message": f"扣非净利润({kf['value']}) > 归母净利润({guimu['value']}) ({period}),非经常性损益为负(可能有减值),需关注。"})
    return out


def check_unit_consistency(figures):
    """同一指标不同报告期单位不一致 → WARN(万元/亿元混用)。"""
    by_metric = {}
    for f in figures:
        by_metric.setdefault(f.get("metric"), []).append(f)
    out = []
    for metric, items in by_metric.items():
        units = {i.get("unit") for i in items if i.get("unit")}
        if len(units) > 1:
            out.append({"level": "WARN", "metric": metric,
                        "message": f"{metric} 出现多个单位 {sorted(units)},注意万元/亿元混用。"})
    return out


def check_cashflow_divergence(figures):
    """净利润为正但经营现金流为负 → 盈利质量存疑。"""
    out = []
    for f in figures:
        if f.get("metric") in ("归母净利润", "净利润") and (f.get("value") or 0) > 0:
            cf = next((x for x in figures if x.get("metric") == "经营活动产生的现金流量净额"
                       and x.get("period") == f.get("period")), None)
            if cf and cf.get("value") is not None and cf.get("value") < 0:
                out.append({"level": "WARN", "metric": f.get("metric"),
                            "message": f"{f.get('metric')} 为正({f.get('value')}),但经营现金流为负({cf.get('value')}) ({f.get('period')}),盈利质量存疑。"})
    return out


def check_trend(figures):
    """营业收入/归母净利润连续 ≥3 期下滑 → 提示。"""
    out = []
    for metric in ("营业收入", "归母净利润"):
        items = sorted([f for f in figures if f.get("metric") == metric and f.get("period")],
                       key=lambda f: str(f.get("period")))
        vals = [i.get("value") for i in items if i.get("value") is not None]
        if len(vals) >= 3 and all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
            out.append({"level": "WARN", "metric": metric,
                        "message": f"{metric} 连续 {len(vals)} 期下滑,趋势需关注。"})
    return out


def main():
    ap = argparse.ArgumentParser(description="财务数字交叉核对")
    ap.add_argument("input", help="figures JSON 文件")
    ap.add_argument("--out", help="输出报告 JSON 路径(默认 stdout)")
    args = ap.parse_args()

    data = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    figures = data.get("figures") if isinstance(data, dict) else data
    if not isinstance(figures, list):
        raise SystemExit("输入格式错误: 需要 {\"figures\": [...]} 或 [...]")

    checks = []
    checks += check_duplicates(figures)
    checks += check_growth(figures)
    checks += check_ranges(figures)
    checks += check_balance(figures)
    checks += check_metric_consistency(figures)
    checks += check_unit_consistency(figures)
    checks += check_cashflow_divergence(figures)
    checks += check_trend(figures)
    if not checks:
        checks.append({"level": "PASS", "metric": "-", "message": "未发现可自动核对的项目(或数据太少)。"})

    fail = sum(1 for c in checks if c["level"] == "FAIL")
    warn = sum(1 for c in checks if c["level"] == "WARN")
    report = {"summary": {"total": len(checks), "fail": fail, "warn": warn}, "checks": checks}

    out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out} (FAIL={fail}, WARN={warn})")
    else:
        print(out)


if __name__ == "__main__":
    main()
