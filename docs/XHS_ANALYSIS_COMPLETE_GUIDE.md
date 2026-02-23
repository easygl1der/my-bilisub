# 小红书图文分析工具 - 完整更新说明

## 🎉 新功能总结

### 1. ✅ 从 URL 直接下载并分析
只需一个小红书链接，自动完成所有操作！

### 2. ✅ 自动保存链接信息
生成的 Markdown 包含笔记链接和用户主页

### 3. ✅ 图片上传到 GitHub
使用 jsDelivr CDN 加速，永久存储

### 4. ✅ 图片展示在 Markdown 中
每张图片都会显示在分析结果中

---

## 🚀 快速开始

### 基本用法（最简单）

```bash
python analysis/xhs_image_analysis.py --url "小红书完整链接"
```

### 上传图片到 GitHub

```bash
# 1. 先配置 GitHub（见下方）
# 2. 运行时添加 --upload-github 参数
python analysis/xhs_image_analysis.py --url "小红书链接" --upload-github
```

---

## 📋 完整命令列表

```bash
# 从 URL 下载并分析（推荐）
python analysis/xhs_image_analysis.py --url "链接"

# 上传图片到 GitHub
python analysis/xhs_image_analysis.py --url "链接" --upload-github

# 只下载不分析
python analysis/xhs_image_analysis.py --url "链接" --download-only

# 使用更好的 AI 模型
python analysis/xhs_image_analysis.py --url "链接" --model flash

# 分析本地文件夹
python analysis/xhs_image_analysis.py --dir "xhs_images/用户名/笔记标题"

# 批量分析
python analysis/xhs_image_analysis.py --user-dir "xhs_images/用户名"
```

---

## 🔧 GitHub 配置（可选）

### 为什么需要？

- ✅ 图片永久存储在云端
- ✅ CDN 加速，全球访问快
- ✅ Markdown 可在任何地方查看
- ✅ 不占用本地空间

### 快速配置

#### 方法 1：环境变量（推荐）

```bash
# Windows PowerShell
$env:GITHUB_TOKEN="你的Token"
$env:GITHUB_REPO="用户名/仓库名"

# Linux/Mac
export GITHUB_TOKEN="你的Token"
export GITHUB_REPO="用户名/仓库名"
```

#### 方法 2：配置文件

在用户主目录创建 `.github_upload_config`：

```json
{
  "token": "你的 GitHub Token",
  "repo": "用户名/仓库名"
}
```

### 如何获取 GitHub Token？

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 Token

**详细配置指南**: [docs/GITHUB_IMAGE_UPLOAD_GUIDE.md](docs/GITHUB_IMAGE_UPLOAD_GUIDE.md)

---

## 📂 生成的文件结构

### 下载的内容
```
xhs_images/
└── 用户名/
    └── 笔记标题/
        ├── content.txt      # 包含标题、链接、用户主页、文案
        ├── image_01.jpg
        ├── image_02.jpg
        └── ...
```

### 分析结果
```
xhs_analysis/
└── 用户名/
    └── 笔记标题_时间戳.md
```

---

## 📄 Markdown 输出示例

```markdown
# 笔记标题

## 📌 元信息

| 项目 | 内容 |
|------|------|
| **作者** | 用户名 |
| **笔记标题** | 笔记标题 |
| **笔记链接** | [链接](URL) ✨ |
| **用户主页** | [链接](URL) ✨ |
| **图片数量** | 14 |

---

## 🖼️ 笔记图片

### 图片 1

![笔记标题 - 图片1](https://cdn.jsdelivr.net/gh/.../image_001.jpg) ✨

### 图片 2

![笔记标题 - 图片2](https://cdn.jsdelivr.net/gh/.../image_002.jpg) ✨

---

## 📄 原始文字内容

原始文案...

---

## 🤖 AI 分析结果

完整的 AI 分析...
```

---

## 🎯 功能对比

| 功能 | 不使用 GitHub | 使用 GitHub |
|------|--------------|-------------|
| 图片链接 | 本地路径 | CDN 链接 ✨ |
| 访问速度 | 仅本地 | 全球加速 ✨ |
| 分享便利性 | 需要本地文件 | 任意地方可看 ✨ |
| 存储空间 | 占用本地 | 云端存储 ✨ |
| 配置复杂度 | 无需配置 | 需要配置 |

---

## 📚 完整文档

- **快速开始**: [docs/XHS_ANALYSIS_QUICKSTART.md](docs/XHS_ANALYSIS_QUICKSTART.md)
- **链接功能**: [docs/XHS_IMAGE_ANALYSIS_LINKS_GUIDE.md](docs/XHS_IMAGE_ANALYSIS_LINKS_GUIDE.md)
- **GitHub 上传**: [docs/GITHUB_IMAGE_UPLOAD_GUIDE.md](docs/GITHUB_IMAGE_UPLOAD_GUIDE.md)

---

## ⚙️ 配置文件位置

### GitHub 配置
- **Windows**: `C:\Users\你的用户名\.github_upload_config`
- **Linux/Mac**: `~/.github_upload_config`

### Gemini API Key
- **Windows**: `C:\Users\你的用户名\.gemini_api_key`
- **Linux/Mac**: `~/.gemini_api_key`

---

## 🔍 常见问题

### Q: 必须配置 GitHub 吗？

A: 不是！GitHub 上传是**可选功能**。不配置也能正常使用，只是图片会使用本地路径。

### Q: 如何获取小红书链接？

A:
1. 打开小红书 APP
2. 找到笔记 → 分享 → 复制链接
3. 粘贴到命令行

### Q: AI 分析失败怎么办？

A: 检查 Gemini API Key 是否正确配置。

### Q: 图片上传失败怎么办？

A:
1. 检查 GitHub Token 是否正确
2. 确认仓库名格式：`用户名/仓库名`
3. 查看详细错误信息

---

## 🆕 更新日志

### v2.1 (2026-02-23)

- ✨ 新增 GitHub 图片上传功能
- ✨ 支持 jsDelivr CDN 加速
- ✨ Markdown 中添加图片展示区域
- ✨ 自动替换本地图片为 CDN 链接
- 📝 完善文档

### v2.0 (2026-02-23)

- ✨ 新增 URL 模式：一键下载并分析
- ✨ 自动提取并保存笔记链接和用户主页
- 🐛 修复语法错误

---

## 🎓 使用建议

1. **推荐工作流**：
   ```bash
   # 1. 配置 GitHub（一次性）
   # 2. 使用 URL 模式（最简单）
   python analysis/xhs_image_analysis.py --url "链接" --upload-github
   ```

2. **批量处理**：
   ```bash
   # 先批量下载，再批量分析
   python analysis/xhs_image_analysis.py --user-dir "xhs_images/用户名" --upload-github
   ```

3. **模型选择**：
   - `flash-lite`（默认）- 快速便宜，适合日常使用
   - `flash` - 平衡性能
   - `pro` - 最佳质量，重要笔记使用

---

现在你可以轻松地：
- 📥 一键下载小红书笔记
- 🤖 AI 智能分析内容
- 📤 上传图片到 GitHub
- 📝 生成精美的 Markdown 笔记

所有功能都已经整合到一个工具中！🎉
