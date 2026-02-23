# GitHub 图片上传配置指南

## 功能说明

小红书图文分析工具支持将笔记图片自动上传到 GitHub，并使用 jsDelivr CDN 在 Markdown 中引用。

## 优势

✅ **快速访问** - jsDelivr CDN 全球加速
✅ **永久存储** - GitHub 仓库保存
✅ **便于分享** - Markdown 可在任何地方访问
✅ **节省空间** - 不占用本地存储

---

## 配置方法

### 方法 1：环境变量（推荐）

设置以下环境变量：

**Linux/Mac:**
```bash
export GITHUB_TOKEN="your_github_token_here"
export GITHUB_REPO="username/repo-name"
```

**Windows (PowerShell):**
```powershell
$env:GITHUB_TOKEN="your_github_token_here"
$env:GITHUB_REPO="username/repo-name"
```

**Windows (CMD):**
```cmd
set GITHUB_TOKEN=your_github_token_here
set GITHUB_REPO=username/repo-name
```

### 方法 2：配置文件

在用户主目录创建 `.github_upload_config` 文件：

**文件位置:**
- Windows: `C:\Users\你的用户名\.github_upload_config`
- Linux/Mac: `~/.github_upload_config`

**文件内容 (JSON 格式):**
```json
{
  "token": "你的 GitHub Token",
  "repo": "用户名/仓库名"
}
```

---

## 如何获取 GitHub Token

### 步骤：

1. **登录 GitHub**
   - 访问 https://github.com

2. **创建 Token**
   - 点击头像 → Settings
   - 左侧菜单最下方 → Developer settings
   - Personal access tokens → Tokens (classic)
   - Generate new token → Generate new token (classic)

3. **配置 Token**
   - Note: 填写说明（如"小红书图片上传"）
   - Expiration: 选择过期时间（建议 90 天或更长）
   - 勾选权限：
     - ✅ `repo` (完整仓库访问权限)
   - 点击 Generate token

4. **复制 Token**
   - ⚠️ **重要**：Token 只显示一次，请立即复制保存

### Token 权限说明

需要的权限：
- `repo` - 完整仓库访问权限
  - `repo:status` - 读取提交状态
  - `repo_deployment` - 访问部署状态
  - `public_repo` - 访问公共仓库
  - `repo:invite` - 接受仓库邀请

---

## 创建 GitHub 仓库

### 方法 1：通过网页创建

1. 访问 https://github.com/new
2. 填写仓库信息：
   - Repository name: 任意名称（如 `xhs-images`）
   - Description: 描述（可选）
   - Public ✅ 或 Private ⚠️
     - **Public**: jsDelivr CDN 免费加速
     - **Private**: 需要 jsDelivr 付费版
   - ⚠️ 不要勾选 "Add a README file"
3. 点击 Create repository

### 方法 2：通过 GitHub CLI

```bash
gh repo create xhs-images --public --description "小红书图片存储"
```

---

## 仓库命名格式

配置文件中的 `repo` 字段格式：

```
用户名/仓库名
```

例如：
```
zhangsan/xhs-images
```

---

## 使用方法

配置完成后，使用 `--upload-github` 参数：

```bash
# 从 URL 下载并上传图片
python analysis/xhs_image_analysis.py --url "小红书链接" --upload-github

# 分析本地文件夹并上传图片
python analysis/xhs_image_analysis.py --dir "xhs_images/用户名/笔记标题" --upload-github

# 批量分析并上传
python analysis/xhs_image_analysis.py --user-dir "xhs_images/用户名" --upload-github
```

---

## 生成的 Markdown 示例

上传成功后，Markdown 中的图片会使用 CDN 链接：

```markdown
## 🖼️ 笔记图片

### 图片 1

![标题 - 图片1](https://cdn.jsdelivr.net/gh/用户名/仓库名/assets/20260223_153045_abc123_xhs_001.jpg)

### 图片 2

![标题 - 图片2](https://cdn.jsdelivr.net/gh/用户名/仓库名/assets/20260223_153045_abc123_xhs_002.jpg)

...
```

---

## 文件存储结构

图片会上传到 GitHub 仓库的 `assets/` 目录：

```
你的仓库/
└── assets/
    ├── 20260223_153045_abc123_xhs_001.jpg
    ├── 20260223_153045_abc123_xhs_002.jpg
    └── ...
```

文件名格式：`时间戳_唯一标识_xhs_序号.扩展名`

---

## CDN 说明

工具使用 **jsDelivr CDN** 加速图片访问：

- **CDN URL 格式**: `https://cdn.jsdelivr.net/gh/用户名/仓库名/assets/文件名`
- **全球加速**: jsDelivr 在全球有 CDN 节点
- **免费额度**: 公开仓库无限制
- **缓存**: 自动缓存，访问更快

### CDN 缓存刷新

如果更新了图片但 CDN 还是旧的：
1. 等待几分钟（jsDelivr 会自动刷新）
2. 或在文件名后加版本号：`image.jpg?v=2`

---

## 注意事项

### ⚠️ 私有仓库限制

如果使用私有仓库：
- jsDelivr CDN 需要付费版
- 建议使用公开仓库存储图片

### ⚠️ Token 安全

- 不要将 Token 提交到 Git 仓库
- 定期更换 Token
- 为不同用途使用不同 Token

### ⚠️ 存储空间

- GitHub 单个仓库限制：1 GB（推荐）、10 GB（硬限制）
- 单个文件限制：100 MB
- 建议定期清理旧图片

### ⚠️ API 限流

GitHub API 有速率限制：
- 认证用户：每小时 5000 次
- 未认证：每小时 60 次
- 工具已添加重试机制

---

## 故障排查

### 问题 1：上传失败

**原因**：
- Token 无效或过期
- 仓库名格式错误
- 网络问题

**解决**：
1. 检查 Token 是否正确
2. 确认仓库名格式：`用户名/仓库名`
3. 检查网络连接

### 问题 2：CDN 链接无法访问

**原因**：
- 仓库是私有的
- CDN 还在缓存中

**解决**：
1. 将仓库设为公开
2. 等待几分钟让 CDN 刷新

### 问题 3：配置文件不生效

**原因**：
- 文件位置错误
- JSON 格式错误

**解决**：
1. 确认文件在用户主目录
2. 使用 JSON 验证工具检查格式

---

## 完整示例

### 1. 配置环境变量

```bash
# Windows PowerShell
$env:GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
$env:GITHUB_REPO="zhangsan/xhs-images"
```

### 2. 运行分析

```bash
python analysis/xhs_image_analysis.py --url "https://www.xiaohongshu.com/explore/xxxxx" --upload-github
```

### 3. 查看结果

```bash
# 输出会显示上传进度
📤 开始上传图片到 GitHub...
   仓库: zhangsan/xhs-images
   数量: 14 张
  [1/14] image_01.jpg... ✅
  [2/14] image_02.jpg... ✅
...
✅ 上传完成: 14/14 成功

# 生成的 Markdown 使用 CDN 链接
💾 结果已保存: xhs_analysis/用户名/笔记标题_20260223_153045.md
```

---

## 相关链接

- GitHub Token 创建: https://github.com/settings/tokens
- jsDelivr 官网: https://www.jsdelivr.com/
- GitHub API 文档: https://docs.github.com/en/rest

---

## 更新日志

### v2.1 (2026-02-23)

- ✨ 新增 GitHub 图片上传功能
- ✨ 支持 jsDelivr CDN 加速
- ✨ 自动替换 Markdown 中的图片链接
- 📝 添加配置文档
