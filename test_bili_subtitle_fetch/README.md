# B站字幕获取测试

测试两种获取 B 站视频字幕的方法。

---

## 方法一：bilibili-api-python

### 环境准备

```bash
pip install bilibili-api-python
```

### 配置 Cookie

从浏览器 F12 → Application → Cookies → bilibili.com 获取以下三个值：

- `SESSDATA`
- `bili_jct`
- `buvid3`

然后编辑 `test_bilibili_api.py`，填入你的 Cookie：

```python
credential = Credential(
    sessdata="YOUR_SESSDATA",  # 替换
    bili_jct="YOUR_BILI_JCT",  # 替换
    buvid3="YOUR_BUVID3"       # 替换
)
```

### 运行测试

```bash
python test_bilibili_api.py
```

### 输出

- `{bvid}_{lang}.json` - 原始 JSON 格式
- `{bvid}_{lang}.txt` - 纯文本格式
- `{bvid}_{lang}.srt` - SRT 字幕格式

---

## 方法二：yt-dlp

### 环境准备

```bash
pip install yt-dlp
```

### 运行测试

```bash
# 使用默认配置 (BV1oQZ7B9EB4, zh-Hans)
python test_ytdlp.py

# 指定视频
python test_ytdlp.py BV1oQZ7B9EB4

# 指定视频和语言
python test_ytdlp.py BV1oQZ7B9EB4 zh-Hans
```

### Cookie 说明

`--cookies-from-browser chrome` 会自动从已登录的 Chrome 读取 Cookie，无需手动填写。

如需使用其他浏览器，编辑 `test_ytdlp.py` 中的 `BROWSER` 变量：

```python
BROWSER = "chrome"  # 可选: firefox, edge, safari
```

---

## 对比

| 特性 | bilibili-api-python | yt-dlp |
|------|---------------------|--------|
| 依赖 | bilibili-api-python | yt-dlp |
| Cookie 配置 | 手动填写 3 个值 | 自动从浏览器读取 |
| API 调用 | ✅ 异步 API | ✅ 命令行 + Python |
| 字幕格式 | JSON 原始格式 | 支持多种格式 |
| 自动字幕 | ✅ 支持 | ✅ 支持 |
| 适用场景 | 程序集成 | 快速测试/命令行 |

---

## 字幕格式

### bilibili-api-python 返回结构

```json
{
  "body": [
    {
      "from": 0.0,      // 开始时间(秒)
      "to": 5.0,        // 结束时间(秒)
      "content": "字幕内容"
    }
  ]
}
```

### yt-dlp 返回结构 (json3)

```json
{
  "events": [
    {
      "tStart": 1000,      // 开始时间(毫秒)
      "dDurationMs": 5000, // 持续时间(毫秒)
      "secontent": "字幕内容"
    }
  ]
}
```

---

## 测试视频

默认测试视频: `BV1oQZ7B9EB4`

可自行修改脚本中的 `TEST_BVID` 变量。
