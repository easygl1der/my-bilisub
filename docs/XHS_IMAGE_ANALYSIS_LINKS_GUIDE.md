# 小红书图文分析工具 - 完整使用指南

## 新增功能

现在工具支持两种工作模式：

### 模式 1：从 URL 直接下载并分析（推荐）✨

只需提供小红书笔记链接，工具会自动：
1. 下载笔记图片和文案
2. 提取笔记链接和用户主页
3. 使用 AI 进行内容分析
4. 生成包含所有链接信息的 Markdown 报告

### 模式 2：分析本地已有的图片文件夹

如果你已经下载了笔记内容，可以直接分析本地文件夹。

---

## 工作模式 1：从 URL 直接下载并分析

### 使用方法

```bash
# 下载并分析单个笔记
python analysis/xhs_image_analysis.py --url "小红书完整链接"

# 只下载不分析
python analysis/xhs_image_analysis.py --url "小红书完整链接" --download-only

# 指定 AI 模型
python analysis/xhs_image_analysis.py --url "小红书完整链接" --model flash
```

### 特点

✅ **一键完成** - 从下载到分析全自动
✅ **自动保存链接** - content.txt 包含完整的笔记链接和用户主页
✅ **结构化保存** - 自动创建 `xhs_images/用户名/笔记标题/` 目录
✅ **智能分析** - 自动检测内容风格并使用专业提示词

### 示例

```bash
python analysis/xhs_image_analysis.py --url "https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6?xsec_token=xxxxx"
```

输出：
```
📡 正在获取笔记信息...
✅ 成功提取笔记信息
   标题: 就这样跌跌撞撞跑向你⊂((・x・))⊃
   图片: 14 张
📥 开始下载 14 张图片...
[1/14] ✅ 245.3KB
[2/14] ✅ 198.7KB
...
🎉 下载完成!
🤖 开始分析...
✅ 分析完成!
💾 结果已保存: xhs_analysis/小红书用户/就这样跌跌撞撞跑向你⊂((・x・))⊃_20260223_153045.md
```

---

## 工作模式 2：分析本地文件夹

### 使用方法

```bash
# 分析单个笔记（自动检测风格）
python analysis/xhs_image_analysis.py --dir "xhs_images/用户名/笔记标题"

# 指定内容风格
python analysis/xhs_image_analysis.py --dir "images" --style life_vlog

# 批量分析用户的所有笔记
python analysis/xhs_image_analysis.py --user-dir "xhs_images/塑料叉FOKU"
```

---

## content.txt 文件格式

### 完整格式（推荐）

```
标题: 就这样跌跌撞撞跑向你⊂((・x・))⊃
链接: https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6
用户主页: https://www.xiaohongshu.com/user/profile/5f4e3d2c1b0a9

文案:
发个图文版～嘿嘿，让我水一期！
14张里面你最喜欢哪张！

这几天第二学期开学，论文开题，又与世隔绝了两天外拍，整个人都累升华了，每天倒头就睡～不过很充实，超绝开心！！期待新视频✌️✌️
#塑料叉[话题]# #见喜欢的人是用跑的[话题]# #日常[话题]##拍照[话题]#
```

### 字段说明

| 字段 | 是否必需 | 说明 |
|------|---------|------|
| 标题/Title | 可选 | 笔记的标题 |
| 链接/URL/Link | 可选 | 笔记的完整 URL（使用 URL 模式会自动填充） |
| 主页/Homepage/用户主页 | 可选 | 作者主页的完整 URL（使用 URL 模式会自动填充） |
| 文案/desc | 必需 | 笔记的文字内容 |

### 支持的字段名称

**笔记链接：** `链接:` / `URL:` / `Link:`
**用户主页：** `主页:` / `Homepage:` / `用户主页:`
**标题：** `标题:` / `Title:`
**文案：** `文案:` / `desc:` / `DESC:`

### 兼容性

- ✅ 完全兼容旧格式（只有文案的 content.txt）
- ✅ 字段可选，缺少的字段会自动省略
- ✅ 中英文字段名都支持

---

## 生成的 Markdown 输出

### 包含完整信息的示例

```markdown
## 📌 元信息

| 项目 | 内容 |
|------|------|
| **作者** | 塑料叉FOKU |
| **笔记标题** | 就这样跌跌撞撞跑向你⊂((・x・))⊃ |
| **分析时间** | 2026-02-23 15:30:45 |
| **使用模型** | gemini-2.5-flash |
| **内容风格** | 生活记录/日常分享 |
| **图片数量** | 14 |
| **来源目录** | `xhs_images/塑料叉FOKU/就这样跌跌撞撞跑向你⊂((・x・))⊃` |
| **笔记链接** | [https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6](https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6) |
| **用户主页** | [https://www.xiaohongshu.com/user/profile/5f4e3d2c1b0a9](https://www.xiaohongshu.com/user/profile/5f4e3d2c1b0a9) |
```

所有链接都是可点击的，方便直接跳转到原始内容！

---

## 完整命令参考

### URL 模式（推荐）

```bash
# 基本用法
python analysis/xhs_image_analysis.py --url "笔记链接"

# 只下载不分析
python analysis/xhs_image_analysis.py --url "笔记链接" --download-only

# 指定 AI 模型
python analysis/xhs_image_analysis.py --url "笔记链接" --model flash

# 指定输出目录
python analysis/xhs_image_analysis.py --url "笔记链接" -o "my_analysis"
```

### 本地文件夹模式

```bash
# 分析单个笔记
python analysis/xhs_image_analysis.py --dir "xhs_images/用户名/笔记标题"

# 指定风格
python analysis/xhs_image_analysis.py --dir "images" --style quote_wisdom

# 批量分析
python analysis/xhs_image_analysis.py --user-dir "xhs_images/用户名"

# 读取指定文案文件
python analysis/xhs_image_analysis.py --dir "images" --text-file "my_content.txt"

# 禁用自动风格检测
python analysis/xhs_image_analysis.py --dir "images" --no-auto-style
```

### 通用选项

```bash
# AI 模型选择
--model flash-lite    # 默认，快速便宜
--model flash         # 平衡性能
--model pro           # 最佳质量

# 输出目录
-o, --output DIR      # 默认: xhs_analysis

# API Key
--api-key KEY         # 覆盖配置文件

# 列出所有支持的风格
--list-styles
```

---

## 如何获取小红书笔记链接

### 方法 1：从小红书 APP（推荐）

1. 打开笔记
2. 点击右上角分享按钮
3. 选择"复制链接"
4. 粘贴到命令行

**注意：** 复制的链接必须包含 `xsec_token` 参数才能正常访问

### 方法 2：从网页版

1. 访问 https://www.xiaohongshu.com
2. 找到对应笔记
3. 复制浏览器地址栏的 URL

---

## 目录结构

### 下载后的结构

```
xhs_images/
└── 小红书用户/
    └── 就这样跌跌撞撞跑向你⊂((・x・))⊃/
        ├── content.txt          # 包含标题、链接、用户主页、文案
        ├── image_01.jpg
        ├── image_02.jpg
        └── ...
```

### 分析结果的结构

```
xhs_analysis/
└── 小红书用户/
    └── 就这样跌跌撞撞跑向你⊂((・x・))⊃_20260223_153045.md
```

---

## 常见问题

### Q: URL 模式提示"页面无法访问"怎么办？

A: 可能的原因：
1. 链接缺少 `xsec_token` 参数 - 请从小红书 APP 重新复制完整链接
2. 链接已过期 - 小红书分享链接有时效性
3. 需要登录 - 部分私密笔记需要登录才能访问

### Q: 旧格式的 content.txt 还能用吗？

A: 完全可以！工具会自动兼容，只是不会显示链接信息。建议使用 URL 模式重新下载以获得完整信息。

### Q: 如何批量分析多个笔记？

A: 有两种方法：
1. 使用 `--user-dir` 批量分析已下载的笔记
2. 编写简单的 shell 脚本循环调用 `--url` 参数

### Q: AI 分析失败怎么办？

A: 检查：
1. API Key 是否正确配置
2. 网络连接是否正常
3. 是否超出 API 配额

---

## 更新日志

### v2.0 (2026-02-23)

- ✨ 新增 URL 模式：一键下载并分析
- ✨ 自动提取并保存笔记链接和用户主页
- ✨ 生成的 Markdown 包含完整链接信息
- ✨ 更新下载脚本，自动保存元数据
- 🐛 修复语法错误
- 📝 完善文档

---

## 相关文件

- **分析工具**: `analysis/xhs_image_analysis.py`
- **下载脚本**: `platforms/xiaohongshu/download_xhs_images.py`
- **本指南**: `docs/XHS_IMAGE_ANALYSIS_LINKS_GUIDE.md`
