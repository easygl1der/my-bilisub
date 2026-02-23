# MediaCrawler B站首页推荐爬虫使用指南

## 快速开始

### 1. 配置 Cookie

编辑 `MediaCrawler/config/base_config.py`，或直接使用项目根目录的 `config/cookies.txt`：

```bash
# 在 config/cookies.txt 中添加B站Cookie
SESSDATA=你的SESSDATA; bili_jct=你的bili_jct; DedeUserID=你的ID
```

### 2. 运行爬虫

```bash
cd MediaCrawler
python main.py
```

## 配置说明

### 编辑 `MediaCrawler/config/base_config.py`

关键配置项：

```python
# 平台和爬取类型
PLATFORM = "bili"  # B站
CRAWLER_TYPE = "homepage"  # 首页推荐模式

# 登录方式
LOGIN_TYPE = "cookie"  # 使用Cookie登录（推荐）

# 无头模式（后台运行）
HEADLESS = True  # 设置为False可以看到浏览器运行过程

# 爬取数量
CRAWLER_MAX_NOTES_COUNT = 100  # 最大视频数

# 是否爬评论
ENABLE_GET_COMMENTS = False  # 设为True会爬取评论（耗时）

# 数据保存格式
SAVE_DATA_OPTION = "csv"  # csv | json | db | excel
```

### 编辑 `MediaCrawler/config/bilibili_config.py`

首页推荐专用配置：

```python
# 首页推荐配置
ENABLE_HOMEPAGE_RECOMMEND = True  # 启用首页推荐
HOMEPAGE_REFRESH_COUNT = 10  # 刷新次数
HOMEPAGE_MAX_VIDEOS = 100  # 最大采集视频数
```

## 输出文件

运行后数据保存在 `MediaCrawler/output/` 目录：

```
MediaCrawler/
├── output/
│   ├── bilibili_videos_*.csv   # 视频数据
│   └── ...
```

## 数据字段

MediaCrawler 爬取的视频数据包含：

- `video_id` - 视频ID
- `title` - 视频标题
- `desc` - 视频描述
- `nickname` - UP主名称
- `user_id` - UP主 ID
- `video_url` - 视频链接
- `video_cover_url` - 封面链接
- `video_play_count` - 播放量
- `liked_count` - 点赞数
- `video_comment` - 评论数
- `video_favorite_count` - 收藏数
- 等更多字段...

## 完整示例

### 1. 基础爬取（100个视频）

```bash
cd MediaCrawler
python main.py
```

### 2. 爬取更多视频

编辑 `bilibili_config.py`:
```python
HOMEPAGE_REFRESH_COUNT = 20
HOMEPAGE_MAX_VIDEOS = 200
```

然后运行：
```bash
python main.py
```

### 3. 爬取并分析

```bash
# 1. 爬取数据
cd MediaCrawler
python main.py

# 2. 分析数据（假设输出是 bilibili_videos_20250222.csv）
cd ..
python bilibili_homepage_tool.py --analyze-only --input MediaCrawler/output/bilibili_videos_20250222.csv
```

## 常见问题

### Q: 如何获取 Cookie？
A: 参考 `docs/BILIBILI_COOKIE_GUIDE.md`

### Q: 登录失败怎么办？
A:
1. 检查 Cookie 是否过期
2. 设置 `HEADLESS = False` 查看浏览器运行过程
3. 或使用二维码登录：`LOGIN_TYPE = "qrcode"`

### Q: 为什么爬取数量不对？
A:
- B站推荐算法可能会重复推荐相同视频
- 实际去重后的数量可能少于设置值
- 增加 `HOMEPAGE_REFRESH_COUNT` 可以获取更多视频

### Q: 数据保存在哪里？
A: `MediaCrawler/output/` 目录，根据 `SAVE_DATA_OPTION` 配置保存不同格式

## 与一体化工具的区别

| 功能 | MediaCrawler | bilibili_homepage_tool.py |
|------|-------------|---------------------------|
| 登录方式 | Cookie/二维码 | 手动登录/Cookie |
| 数据字段 | 更完整（含播放量等） | 基础字段 |
| 评论爬取 | 支持 | 不支持 |
| AI 分析 | 需要手动运行 | 集成 |
| 配置复杂度 | 较高 | 较低 |

**推荐**：
- 如果只需要视频链接和标题 → 使用 `bilibili_homepage_tool.py`
- 如果需要播放量、评论等详细数据 → 使用 `MediaCrawler`

## 相关文件

- `MediaCrawler/main.py` - 主入口
- `MediaCrawler/config/base_config.py` - 基础配置
- `MediaCrawler/config/bilibili_config.py` - B站配置
- `MediaCrawler/media_platform/bilibili/core.py` - 核心爬虫代码
