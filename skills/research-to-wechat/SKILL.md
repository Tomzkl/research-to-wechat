---
name: research-to-wechat
description: Use when the user wants to turn an earnings report, annual/quarterly report (财报、年报、季报) or research report (研报) into a publish-ready WeChat Official Account article (公众号文章), or when financial figures from such a report need to be extracted and checked for consistency (交叉验证) before being quoted in an article.
---

# 财报/研报 → 公众号文章 (research-to-wechat)

## Overview

把一份财报或研报,变成一篇经过数据核对、可直接群发的公众号文章。核心原则:**能用脚本确定的(抽取、核对、排版)交给脚本;需要理解和写作的,交给你(Claude)来完成。**

## When to Use

- 用户给了一份财报/研报 PDF 或文本,要写成公众号文章。
- 用户说"把这份年报整理成文章""写一篇 XX 公司的财报解读""核对一下这些财务数字对不对"。
- 需要从报告中抽取关键财务指标并交叉验证,再成文发布。

**不用它:** 用户只是问一个财务概念,或要写非公众号的通用分析(直接答,不必走流水线)。

## Pipeline(五步,严格按顺序)

每一步的产出格式见 `references/output_spec.md`。**任何一步发现关键数据缺失或冲突,先停下向用户确认,不要硬往下走。**

1. **抽取** — 跑 `python scripts/extract_pdf.py <报告路径>`,得到结构化 JSON(元信息 + 关键指标 + 原文预览)。
   - 脚本只是"预抽取 + 给你开头",**权威阅读者是你**:以报告原文为准,修正脚本漏抽/误抽的数字。注意「归母净利润」与「净利润」是不同口径,别混。
2. **核对** — 把抽取结果整理成 figures JSON(格式见 `references/output_spec.md`),跑 `python scripts/validate_figures.py <figures.json>`,得到核对报告。
   - 核对规则见 `references/validation_rules.md`。有 FAIL 项必须向用户报告并确认如何处理,**不得悄悄改数字**。
3. **成文** — 按 `templates/article_structure.md` 的骨架、`references/style_guide.md` 的风格写正文。
   - 所有引用的数字都必须来自第 1、2 步核对过的结果;报告未披露就写「未披露」,**禁止编造或"合理估计"**。
4. **排版** — 把正文写成 Markdown,跑 `python scripts/render_wechat.py <article.md>`,得到公众号可粘贴的 HTML。
   - 图片用占位符(公众号需手动上传图片),脚本会自动标注。
5. **交付** — 给出:① 核对报告摘要;② 公众号 HTML 文件路径;③ 一份"待人工确认"清单(哪些数字存疑、哪些图要补)。

## Quick Reference

| 命令 | 作用 |
|------|------|
| `python scripts/extract_pdf.py <报告>` | PDF/文本 → 结构化 JSON |
| `python scripts/validate_figures.py <figures.json>` | 财务数字交叉核对 |
| `python scripts/render_wechat.py <article.md>` | Markdown → 公众号 HTML |

## Common Mistakes

- **直接信脚本抽的数字,不核对原文** —— 脚本会漏抽/误抽(尤其表格与扫描件),必须回原文确认。
- **跳过核对直接成文** —— 财务数字错了,文章就是事故。
- **编造或缺省数据** —— 报告里没有的指标,写「未披露」,不要补。
- **图片用外链** —— 公众号不认外链图片,必须用占位符 + 手动上传。
- **单位混用** —— 万元 vs 亿元、归母 vs 扣非,成文前统一口径。
