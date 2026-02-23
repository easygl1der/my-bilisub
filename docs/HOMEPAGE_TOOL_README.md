# B站首页推荐工具 - 使用说明

## 一体化工具：`bilibili_homepage_tool.py`

这个工具整合了首页爬取和AI分析功能，一个命令完成所有操作。

### 安装依赖

```bash
pip install playwright
playwright install chromium
```

### 基本使用

```bash
# 默认配置运行（刷新10次，最多100个视频）
# 会提示在浏览器中手动登录B站
python bilibili_homepage_tool.py

# 跳过登录提示（使用未登录状态）
python bilibili_homepage_tool.py --no-login

# 使用 Cookie 登录（无需手动登录）
# 先将 Cookie 保存到 config/cookies.txt
python bilibili_homepage_tool.py

# 指定刷新次数和最大视频数
python bilibili_homepage_tool.py --refresh 15 --max-videos 150

# 无头模式（后台运行，不打开浏览器）
# 需要提前配置好 Cookie
python bilibili_homepage_tool.py --headless

# 仅爬取数据，不做AI分析
python bilibili_homepage_tool.py --no-analyze

# 仅分析已有数据
python bilibili_homepage_tool.py --analyze-only --input output/homepage/homepage_videos_20250222.csv

# 指定Gemini模型（flash-lite/flash/pro）
python bilibili_homepage_tool.py --model flash

# 指定输出文件
python bilibili_homepage_tool.py --output my_report.md
```

### 登录方式

工具支持三种登录方式：

#### 方式1：手动登录（推荐，默认）
```bash
python bilibili_homepage_tool.py
```
1. 程序会打开浏览器
2. 在浏览器中扫码或账号登录B站
3. 登录成功后程序自动继续
4. 登录状态会保存，下次无需重新登录

#### 方式2：Cookie 登录（适合自动化）
1. 获取 B站 Cookie（参考 [BILIBILI_COOKIE_GUIDE.md](BILIBILI_COOKIE_GUIDE.md)）
2. 保存到 `config/cookies.txt`
3. 运行：
```bash
python bilibili_homepage_tool.py
```

#### 方式3：未登录模式
```bash
python bilibili_homepage_tool.py --no-login
```
- 无需登录
- 只能获取通用推荐
- 可能重复推荐相同视频

### 输出文件

运行后会生成以下文件：
- `output/homepage/homepage_videos_时间戳.csv` - 视频数据（CSV格式）
- `output/homepage/homepage_videos_时间戳.json` - 视频数据（JSON格式）
- `output/homepage/homepage_analysis_时间戳.md` - AI分析报告

### 视频数据字段

每个视频包含以下信息：
- `bvid` - 视频BV号
- `title` - 视频标题
- `uploader` - UP主名称
- `uploader_url` - UP主主页链接
- `video_url` - 视频链接
- `cover_url` - 封面图片链接
- `timestamp` - 采集时间

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--refresh` / `-r` | 首页刷新次数 | 10 |
| `--max-videos` / `-M` | 最大采集视频数 | 100 |
| `--headless` | 无头模式运行 | False |
| `--no-login` | 跳过登录提示 | False |
| `--no-analyze` | 仅爬取，不分析 | False |
| `--analyze-only` | 仅分析模式 | False |
| `--input` / `-i` | 输入文件路径 | - |
| `--model` / `-m` | Gemini模型 | flash-lite |
| `--output` / `-o` | 输出报告路径 | 自动生成 |

## 使用示例

### 1. 首次使用（手动登录）
```bash
python bilibili_homepage_tool.py
```
按提示在浏览器中登录，登录状态会保存。

### 2. 后续使用（自动登录）
```bash
python bilibili_homepage_tool.py
```
无需重新登录，使用保存的登录状态。

### 3. 快速测试
```bash
python bilibili_homepage_tool.py --no-login --refresh 2 --max-videos 10 --no-analyze
```

### 4. 深度采集（更多视频）
```bash
python bilibili_homepage_tool.py --refresh 20 --max-videos 200
```

### 5. 服务器运行（无头模式 + Cookie）
```bash
# 1. 先手动登录一次获取状态
python bilibili_homepage_tool.py --refresh 1

# 2. 然后使用无头模式
python bilibili_homepage_tool.py --headless --refresh 5 --max-videos 50
```

### 6. 分析历史数据
```bash
python bilibili_homepage_tool.py --analyze-only --input output/homepage/homepage_videos_20250222.csv
```

## 配置说明

### 修改默认配置
编辑 `bilibili_homepage_tool.py` 中的 `Config` 类：

```python
class Config:
    HOMEPAGE_URL = "https://www.bilibili.com"
    DEFAULT_REFRESH_COUNT = 10  # 默认刷新次数
    DEFAULT_MAX_VIDEOS = 100    # 默认最大视频数
    HEADLESS = False            # 默认是否无头模式
    COOKIE_FILE = ...           # Cookie 文件路径
    USER_DATA_DIR = ...         # 浏览器数据目录（保存登录状态）
```

## 故障排查

### 问题1: 未安装playwright
```bash
pip install playwright
playwright install chromium
```

### 问题2: 无法访问B站
- 检查网络连接
- 如需代理，请修改代码添加代理配置

### 问题3: 登录失败
- 检查 `browser_data/bilibili_homepage/` 目录权限
- 删除该目录后重新登录
- 使用 `--no-login` 跳过登录

### 问题4: AI分析失败
- 确保已配置 Gemini API Key
- 检查 `analysis/gemini_subtitle_summary.py` 是否存在
- 尝试使用 `--no-analyze` 跳过分析

## 高级用法

### 自定义AI分析提示词
编辑 `GeminiAnalyzer.analyze()` 方法中的 `prompt` 变量

### 批量处理多个数据文件
```bash
for file in output/homepage/homepage_videos_*.csv; do
    python bilibili_homepage_tool.py --analyze-only --input "$file"
done
```

## 相关文件

- `bilibili_homepage_tool.py` - 主工具（推荐使用）
- `analysis/homepage_analyzer.py` - 独立分析工具
- `MediaCrawler/test_homepage.py` - MediaCrawler首页爬取脚本
- `docs/BILIBILI_COOKIE_GUIDE.md` - Cookie 获取指南
