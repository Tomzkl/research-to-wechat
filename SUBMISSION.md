# 发布与推广清单

> 仓库本身已经是可安装的 marketplace:任何人执行 `/plugin marketplace add Tomzkl/research-to-wechat` 即可安装。下面是为了扩大分发、拿到更多曝光。

## 1. 提交到 Claude Code 官方插件目录

目标仓库 `anthropics/claude-plugins-official`,提一个 PR,在其 marketplace 的 `plugins` 列表追加一条:

```json
{
  "name": "research-to-wechat",
  "description": "把财报/研报变成核对过数据、可直接群发的公众号文章 — turn earnings/research reports into data-verified WeChat articles",
  "author": { "name": "Tomzkl" },
  "category": "productivity",
  "source": {
    "source": "github",
    "repo": "Tomzkl/research-to-wechat"
  },
  "homepage": "https://github.com/Tomzkl/research-to-wechat"
}
```

PR 标题建议:`Add research-to-wechat plugin`

PR 描述:

```
## What

A Claude Code skill that turns an earnings report / research report into a
data-verified, publish-ready WeChat Official Account article — a five-stage
pipeline (extract → cross-validate → draft → format → deliver).

## Why it's useful

- Extracts the three financial statements from real PDFs via pdfplumber table
  parsing (unit-aware), not just regex text scanning.
- Cross-validates figures before writing: conflicts, growth recompute, ratio
  sanity, balance-sheet balance, 口径 (scope) confusion, unit mixing,
  cash-flow/profit divergence, multi-period trends.
- Zero-dependency for text/JSON input; optional pdfplumber for PDF.

## Checklist

- [ ] MIT licensed
- [ ] plugin.json + marketplace.json present
- [ ] demo GIF + 4 example reports + golden article included
```

## 2. awesome 列表

搜索并 PR 到 `awesome-claude-code`、`awesome-claude` 等仓库的 "Skills / Plugins" 分类,附一句话简介和本仓库链接。

## 3. 社区渠道(中文优先)

- V2EX(分享创造) / 即刻 / 小红书 / 微信公众号 / 知乎。
- 标题建议聚焦"痛点":《把财报写成公众号文章,这条流水线帮我省了 2 小时》。
- 配一张真实跑通的 before/after 截图(真实财报 PDF → 结构化数据 → 成品文章)。

### 发帖文案(可直接复制)

> **标题:把财报写成公众号文章,这条流水线帮我省了 2 小时**
>
> 做了一个 Claude Code 的 skill:把财报 PDF 变成核对过数据、可直接群发的公众号文章。流程:抽取 → 交叉核对 → 成文 → 排版。
>
> - 抽取:pdfplumber 读三张报表 + pypdfium2 修中文乱码,自动识别合并/母公司口径、单位(元/万元)
> - 核对:8 类检查(冲突、同比重算、口径混淆、单位混用、现金流背离…)
> - 成文:Claude 按财务洞察模板写(毛利率→定价权、现金流/净利润→质量)
> - 排版:内联样式 HTML,直接粘公众号
>
> 真实案例(贵州茅台 2023 年报 143 页):自动抽出营业总收入 1505.6 亿、归母净利 747.34 亿、总资产 2727 亿,全部正确。也测了宁德时代(制造,万元单位/空首列/标题跨页),广谱验证挖出并修掉 3 个格式坑。
>
> GitHub: https://github.com/Tomzkl/research-to-wechat
> MIT,零依赖,`/plugin marketplace add Tomzkl/research-to-wechat` 即装。求 star,求真实财报来测。🙏

## 4. 让"成品"说话

README 顶部的 GIF 是合成演示。更强的证明是一段**真实录屏**(真实 A 股财报 PDF 跑完整流程),或一张"输入财报 → 输出文章"的对比图。录屏可用 Windows 自带 `Win+Alt+R`(Xbox Game Bar)或 OBS。
