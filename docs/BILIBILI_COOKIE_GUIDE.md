# B站首页推荐工具 - Cookie 配置指南

## 为什么需要 Cookie？

B站的首页推荐是基于用户历史行为的个性化推荐。如果不使用登录状态（Cookie），只能获取通用推荐，可能无法反映你的真实兴趣偏好。

## 获取 B站 Cookie 的方法

### 方法一：使用浏览器开发者工具（推荐）

1. **打开浏览器**，访问 [B站首页](https://www.bilibili.com) 并**登录**

2. **打开开发者工具**：
   - Chrome/Edge: 按 `F12` 或 `Ctrl+Shift+I`
   - Firefox: 按 `F12` 或 `Ctrl+Shift+I`

3. **切换到 Application (应用) 标签**：
   - Chrome/Edge: Application → Storage → Cookies
   - Firefox: Storage → Cookies

4. **找到 bilibili.com**，点击展开

5. **复制 Cookie**：
   - 方法 A: 选中所有 Cookie，右键 → "Copy all cookies as JSON"
   - 方法 B: 手动复制重要的 Cookie（推荐）

6. **重要的 Cookie 字段**（至少包含这些）：
   - `SESSDATA` - 会话ID（最重要）
   - `bili_jct` - CSRF token
   - `DedeUserID` - 用户ID
   - `DedeUserID__ckMd5` - 用户ID的MD5
   - `sid` - 会话ID

### 方法二：使用浏览器插件（简单）

安装 "Get cookies.txt" 或 "EditThisCookie" 等浏览器插件：

1. 安装插件后访问 B站并登录
2. 点击插件图标
3. 导出/复制 Cookie
4. 保存到文件

### 方法三：从网络请求复制

1. 登录 B站后，打开开发者工具 (F12)
2. 切换到 "Network" (网络) 标签
3. 刷新页面
4. 点击任意请求
5. 在 Headers 中找到 "Cookie" 字段
6. 复制整个 Cookie 字符串

## 保存 Cookie

1. 在项目根目录创建 `config` 文件夹（如果不存在）
2. 创建 `cookies.txt` 文件：`config/cookies.txt`
3. 将复制的 Cookie 粘贴到文件中

**格式示例**：
```
SESSDATA=xxxxx; bili_jct=xxxxx; DedeUserID=xxxxx; DedeUserID__ckMd5=xxxxx; sid=xxxxx
```

或每行一个：
```
SESSDATA=xxxxx
bili_jct=xxxxx
DedeUserID=xxxxx
```

## 使用 Cookie 运行工具

配置好 Cookie 后，正常运行即可：

```bash
python bilibili_homepage_tool.py
```

工具会自动加载 `config/cookies.txt` 中的 Cookie。

## 注意事项

### Cookie 有效期
- B站的 Cookie 通常有效期为 **1个月**左右
- 如果发现推荐内容不对或工具报错，可能需要重新获取 Cookie

### 安全建议
- ⚠️ **不要将 Cookie 文件分享给他人或上传到公开仓库**
- Cookie 包含你的登录信息，泄露后他人可访问你的账号
- 建议将 `config/cookies.txt` 添加到 `.gitignore`

### 无 Cookie 模式
如果没有 Cookie，工具仍然可以运行，但：
- 只能获取通用推荐
- 无法获取个性化内容
- 可能重复推荐相同视频

## 常见问题

### Q: 如何确认 Cookie 是否有效？
A: 运行工具后，如果看到 "✅ 已检测到登录状态" 说明 Cookie 有效。

### Q: Cookie 失效了怎么办？
A: 重新登录 B站，按上述步骤重新获取 Cookie。

### Q: 能否使用多个账号的 Cookie？
A: 每次运行只能使用一个账号的 Cookie。如需对比多个账号，可以：
1. 保存不同账号的 Cookie 为不同文件（如 `cookies1.txt`, `cookies2.txt`）
2. 修改配置文件中的 Cookie 路径
3. 分别运行

## 文件位置

```
biliSub/
├── bilibili_homepage_tool.py
├── config/
│   └── cookies.txt          # ← 将 Cookie 保存在这里
├── output/
│   └── homepage/
└── docs/
    └── BILIBILI_COOKIE_GUIDE.md
```

## 快速测试

测试 Cookie 是否配置成功：

```bash
# 测试运行（少量视频）
python bilibili_homepage_tool.py --no-analyze --refresh 2 --max-videos 10
```

如果看到 "✅ 已检测到登录状态"，说明配置成功！
