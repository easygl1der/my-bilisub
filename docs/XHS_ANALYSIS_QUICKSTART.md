# 小红书图文分析 - 快速开始

## 🚀 一键使用（推荐）

### 从 URL 直接下载并分析

```bash
python analysis/xhs_image_analysis.py --url "小红书完整链接"
```

**就这么简单！** 工具会自动：
- ✅ 下载所有图片
- ✅ 提取文案和链接信息
- ✅ 使用 AI 分析内容
- ✅ 生成包含所有链接的 Markdown 报告

---

## 📋 工作模式对比

| 模式 | 命令 | 优点 | 适用场景 |
|------|------|------|----------|
| **URL 模式** | `--url "链接"` | 一键完成，自动保存链接 | 分析新笔记 |
| **文件夹模式** | `--dir "路径"` | 分析已有内容 | 本地已有图片 |
| **批量模式** | `--user-dir "路径"` | 批量处理 | 分析用户所有笔记 |

---

## 🎯 完整示例

```bash
# 1. 从 URL 下载并分析（最简单）
python analysis/xhs_image_analysis.py --url "https://www.xiaohongshu.com/explore/xxxxx"

# 2. 只下载不分析
python analysis/xhs_image_analysis.py --url "链接" --download-only

# 3. 使用更好的 AI 模型
python analysis/xhs_image_analysis.py --url "链接" --model flash

# 4. 分析已下载的笔记
python analysis/xhs_image_analysis.py --dir "xhs_images/用户名/笔记标题"

# 5. 批量分析
python analysis/xhs_image_analysis.py --user-dir "xhs_images/用户名"
```

---

## 📂 输出文件

### 下载的内容
```
xhs_images/
└── 用户名/
    └── 笔记标题/
        ├── content.txt    # 包含标题、链接、用户主页、文案
        ├── image_01.jpg
        └── ...
```

### 分析结果
```
xhs_analysis/
└── 用户名/
    └── 笔记标题_时间戳.md
```

### Markdown 包含的信息

```markdown
## 📌 元信息

| 项目 | 内容 |
|------|------|
| **作者** | 用户名 |
| **笔记标题** | 标题 |
| **笔记链接** | [可点击链接](URL) ✨ |
| **用户主页** | [可点击链接](URL) ✨ |
| **AI 分析** | 完整的分析报告 |
```

---

## 🔗 如何获取小红书链接

1. 打开小红书 APP
2. 找到想要分析的笔记
3. 点击分享 → 复制链接
4. 粘贴到命令行

**注意：** 复制的链接必须完整（包含 xsec_token 参数）

---

## 💡 提示

- **推荐使用 URL 模式** - 最简单，自动保存所有信息
- **AI 模型选择**：
  - `flash-lite` (默认) - 快速便宜
  - `flash` - 平衡性能
  - `pro` - 最佳质量
- **批量处理** - 使用 `--user-dir` 一次性分析用户所有笔记

---

## 📖 详细文档

查看完整指南：[docs/XHS_IMAGE_ANALYSIS_LINKS_GUIDE.md](docs/XHS_IMAGE_ANALYSIS_LINKS_GUIDE.md)
