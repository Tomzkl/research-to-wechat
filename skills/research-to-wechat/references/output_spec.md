# 各环节交接格式

## 1. 抽取 → 输出(extract_pdf.py)

```json
{
  "source": "报告路径",
  "meta": {"title": "..."},
  "figures": [
    {"metric": "营业收入", "value": 123.4, "unit": "亿元", "period": "2025Q3", "context": "原文片段"}
  ],
  "raw_text_preview": "……"
}
```

## 2. 核对 → 输入 / 输出

- 输入:将抽取结果整理为 figures JSON(可加 `growth` 字段供同比校验):

```json
{
  "figures": [
    {"metric": "营业收入", "value": 123.4, "unit": "亿元", "period": "2025Q3"},
    {"metric": "营业收入", "value": 100.0, "unit": "亿元", "period": "2024Q3", "growth": 23.4}
  ]
}
```

- 输出:

```json
{
  "summary": {"total": 5, "fail": 1, "warn": 1},
  "checks": [{"level": "FAIL", "metric": "营业收入", "message": "..."}]
}
```

## 3. 成文 → 输出

- Markdown,遵循 `templates/article_structure.md` 骨架与 `references/style_guide.md` 风格。

## 4. 排版 → 输出

- `render_wechat.py` 输出内联样式 HTML,可直接粘贴公众号编辑器。
