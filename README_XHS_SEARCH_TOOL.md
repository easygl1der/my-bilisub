# 小红书搜索工具使用说明

## 文件说明

### xhs_search_simple.py - 主搜索工具
稳定版小红书搜索工具，实现基本搜索功能。

## 功能特性

1. ✅ 搜索指定关键词
2. ✅ 支持排序方式（推荐/最新/最热）
3. ✅ 指定获取数量
4. ✅ 返回完整笔记信息（链接、标题、作者、点赞数、类型）
5. ✅ 自动保存JSON结果文件

## 使用方法

### 基本使用

```bash
# 默认搜索（推荐排序，20条）
python xhs_search_simple.py --keyword "美食"

# 搜索最新笔记
python xhs_search_simple.py --keyword "美食" --sort latest

# 搜索最热笔记
python xhs_search_simple.py --keyword "美食" --sort hot

# 指定获取数量
python xhs_search_simple.py --keyword "美食" --max-notes 50

# 使用无头模式（后台运行，不显示浏览器）
python xhs_search_simple.py --keyword "美食" --headless
```

### 命令行参数

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `--keyword` | 搜索关键词（必需） | 无 | 任意字符串 |
| `--sort` | 排序类型 | default | default, latest, hot |
| `--max-notes` | 最多获取的笔记数 | 20 | 正整数 |
| `--headless` | 使用无头模式 | False | 无 |

### 排序类型说明

- `default`: 默认/推荐排序
- `latest`: 最新排序
- `hot`: 最热/点赞数排序

**注意**: 小红书可能通过UI实现排序，URL参数可能不起作用。

## 输出结果

### 控制台输出

```
📋 搜索结果（前10条）:
======================================================================
1. 🖼️ 个人向广州美食评分汇总（目前582家）Longz6天前207
   作者: 未知作者
   点赞: 207
   链接: https://www.xiaohongshu.com/search_result/6977961f...

2. 🎬 无敌清爽吃不腻‼️酸辣柠檬干煎鸡外焦里嫩爱料理的李小姐2025-11-065.4万
   作者: 无敌清爽吃不腻‼️酸辣柠檬干煎鸡外焦里嫩
   点赞: 5.4万
   链接: https://www.xiaohongshu.com/search_result/690c2fd4...
```

### JSON结果文件

保存位置: `output/xhs_search_results/`

文件名格式: `xhs_search_{关键词}_{排序类型}_{时间戳}.json`

JSON格式:
```json
{
  "keyword": "美食",
  "sort_type": "default",
  "timestamp": "2026-02-24 13:22:30",
  "total_count": 10,
  "notes": [
    {
      "url": "完整笔记链接",
      "noteId": "24位笔记ID",
      "title": "笔记标题",
      "author": "作者名称",
      "likes": "点赞数",
      "type": "image或video",
      "xsecToken": "安全令牌",
      "xsecSource": "来源标识"
    }
  ]
}
```

## 使用示例

### 示例1: 搜索美食相关笔记

```bash
python xhs_search_simple.py --keyword "美食" --max-notes 10
```

### 示例2: 搜索最新旅行笔记

```bash
python xhs_search_simple.py --keyword "旅行" --sort latest --max-notes 15
```

### 示例3: 搜索最热门的美食笔记

```bash
python xhs_search_simple.py --keyword "美食" --sort hot --max-notes 20
```

### 示例4: 无头模式批量搜索

```bash
python xhs_search_simple.py --keyword "广州" --max-notes 50 --headless
```

## 注意事项

1. **Cookie配置**
   - 确保在 `config/cookies.txt` 中配置了有效的小红书Cookie
   - Cookie会过期，需要定期更新

2. **反爬检测**
   - 使用 `--headless` 模式可能被检测为机器人
   - 建议先用非无头模式测试，确认可用后再使用无头模式
   - 避免高频请求，可能导致IP被封

3. **排序功能**
   - 小红书搜索页面可能通过UI实现排序，URL参数可能不起作用
   - 如果需要特定排序，可能需要手动操作页面选择排序方式

4. **网络问题**
   - 如果页面加载超时，请检查网络连接
   - 可能需要增加VPN或代理

5. **结果数量**
   - 小红书可能限制每次搜索的结果数量
   - 实际获取数量可能少于指定的 `--max-notes`

## 常见问题

### Q1: 显示"检测到未登录状态"
**A**: 需要更新 `config/cookies.txt` 中的Cookie

### Q2: 页面加载超时
**A**:
- 检查网络连接
- 尝试不使用 `--headless` 参数
- 可能需要增加等待时间或使用VPN

### Q3: 找到0个笔记
**A**:
- 确认搜索关键词是否正确
- 检查小红书是否有相关内容
- 尝试使用非无头模式查看页面

### Q4: 搜索结果不完整
**A**:
- 增加 `--max-notes` 参数值
- 小红书可能限制单次搜索结果数量

## 技术细节

### 搜索URL格式
```
https://www.xiaohongshu.com/search_result?keyword={关键词}&type=51
```

### 笔记链接格式
```
https://www.xiaohongshu.com/search_result/{24位ID}?xsec_token={token}&xsec_source={source}
```

### 支持的内容类型
- `image`: 图文笔记
- `video`: 视频笔记

## 更新日志

### 2026-02-24
- 初始版本发布
- 实现基本搜索功能
- 支持排序和数量限制
- 自动保存JSON结果
