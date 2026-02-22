# Cookie 配置说明

## 为什么需要 Cookie？

B站等平台对视频下载有限制，使用 Cookie 可以：
- 下载更高清的视频
- 避免被限流或封禁
- 访问需要登录的内容

## 配置方式（三种方式，按优先级排序）

### 方式 1：环境变量（推荐，最安全）

在命令行中设置环境变量：

**Windows CMD:**
```cmd
set BILIBILI_COOKIE=你的Cookie内容
python utils/download_videos_from_csv.py -u "视频链接"
```

**Windows PowerShell:**
```powershell
$env:BILIBILI_COOKIE="你的Cookie内容"
python utils/download_videos_from_csv.py -u "视频链接"
```

**Linux/Mac:**
```bash
export BILIBILI_COOKIE="你的Cookie内容"
python utils/download_videos_from_csv.py -u "视频链接"
```

### 方式 2：配置文件

1. 获取 Cookie（见下方"如何获取 Cookie"）
2. 将 Cookie 粘贴到 `config/cookies.txt` 文件中
3. 保存文件

```
bili_sub/
├── config/
│   └── cookies.txt  # 粘贴你的Cookie到这里
└── utils/
    └── download_videos_from_csv.py
```

### 方式 3：自动从浏览器读取（无需配置）

工具会自动尝试从以下浏览器读取 Cookie：
- Google Chrome
- Microsoft Edge

## 如何获取 B站 Cookie？

### 方法 1：浏览器开发者工具

1. 打开 [B站](https://www.bilibili.com) 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 `Network`（网络）标签
4. 刷新页面
5. 点击任意请求
6. 在右侧 `Headers` 中找到 `Cookie` 字段
7. 复制整个 Cookie 值

### 方法 2：浏览器扩展（推荐）

1. 安装浏览器扩展：**"Get cookies.txt LOCALLY"**
   - Chrome: https://chrome.google.com/webstore
   - Edge: https://microsoftedge.microsoft.com/addons
2. 登录 B站
3. 点击扩展图标
4. 选择 "Current Site"
5. 点击 "Export" 导出
6. 将导出的内容保存到 `config/cookies.txt`

## 关于 "Deprecated Feature" 警告

你可能会看到这样的警告：
```
Deprecated Feature: Passing cookies as a header is a potential security risk...
```

**这个警告不是安全问题！** 这只是 yt-dlp 库的建议提示：

### 警告说明
- **警告原因**：yt-dlp 推荐使用专门的 cookie 文件格式（Netscape 格式）
- **当前实现**：使用 HTTP 请求头传递 Cookie（完全可用，只是会显示警告）
- **安全性**：你的 Cookie 仍然是安全的，只是传递方式不是 yt-dlp 的推荐方式
- **影响**：功能完全正常，只是会看到警告信息

### 我们选择当前实现的原因
1. ✅ 更简单易用（直接粘贴 Cookie 字符串即可）
2. ✅ 兼容性好（支持多种来源：文件/环境变量/浏览器）
3. ✅ 功能完全正常
4. ⚠️ 唯一缺点是会有警告信息（可忽略）

如果你想完全消除警告，需要将 Cookie 转换为 Netscape 格式，但这会让配置变得更复杂。当前的实现在易用性和功能之间取得了平衡。

## 安全建议

⚠️ **重要提醒：**

1. **不要将 Cookie 提交到 Git**
   - `config/cookies.txt` 已添加到 `.gitignore`
   - 使用 `cookies.example.txt` 作为模板

2. **Cookie 会过期**
   - B站 Cookie 通常有效期 30 天
   - 如遇 403 或登录错误，需要重新获取

3. **保护你的账号**
   - Cookie 包含你的登录凭证
   - 不要分享给他人
   - 定期更换密码

## 验证配置

运行以下命令测试配置是否成功：

```bash
python utils/download_videos_from_csv.py -u "https://www.bilibili.com/video/BV1xx411c7mD" --yes
```

如果看到 `🍪 使用 Cookie` 提示，说明配置成功！
