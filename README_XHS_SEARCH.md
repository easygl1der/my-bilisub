# 小红书搜索测试工具

## 功能概述

这是一个完整的小红书搜索测试工具，支持多种搜索方式和全面的测试功能：

### 主要功能

1. **关键词搜索** - 搜索特定关键词的笔记
2. **用户搜索** - 搜索特定用户的笔记
3. **标签搜索** - 搜索特定标签的内容
4. **综合测试** - 包含所有搜索方式的测试套件

## 文件结构

```
D:\桌面\biliSub\
├── test_xhs_search.py          # 主测试文件
├── config/
│   └── cookies.txt             # Cookie配置文件
└── output/
    └── xhs_search_test/        # 测试结果输出目录
        ├── test_keyword_search_*.json
        ├── test_user_search_*.json
        ├── test_tag_search_*.json
        └── test_comprehensive_*.json
```

## 使用方法

### 前置要求

1. **安装依赖**
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **配置Cookie**
   - 打开 `config/cookies.txt`
   - 从浏览器复制小红书Cookie并粘贴到 `[xiaohongshu]` 部分
   - 关键Cookie: `a1`, `web_session`, `webId`

### 基本使用

```bash
# 运行所有测试
python test_xhs_search.py

# 运行关键词搜索测试
python test_xhs_search.py --test keyword --keyword "旅行"

# 运行用户搜索测试
python test_xhs_search.py --test user --user-id "5e7c3a8c0000000001006e32"

# 运行标签搜索测试
python test_xhs_search.py --test tag --tag "美食"

# 使用无头模式（后台运行）
python test_xhs_search.py --headless

# 指定最多获取的笔记数
python test_xhs_search.py --max-notes 50
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--test` | 测试类型: `keyword`, `user`, `tag`, `all` | `all` |
| `--keyword` | 搜索关键词 | `旅行` |
| `--user-id` | 用户ID | `5e7c3a8c0000000001006e32` |
| `--tag` | 标签名称 | `美食` |
| `--headless` | 使用无头模式 | `False` |
| `--max-notes` | 最多获取的笔记数 | `20` |

## 测试输出

### 控制台输出

测试运行时会显示：
- ✅ 测试进度和状态
- 📋 搜索结果摘要（显示前5条）
- 📊 统计信息（成功/失败/总计）
- ⏱️ 测试耗时

### JSON结果文件

每个测试都会生成一个JSON文件，包含：
- 测试元数据（名称、时间、耗时）
- 统计信息（成功数、失败数、总数）
- 详细结果列表

示例输出目录：
```
output/xhs_search_test/
├── test_keyword_search_旅行_20260224_153045.json
├── test_user_search_5e7c3a8c0000000001006e32_20260224_153125.json
├── test_tag_search_美食_20260224_153205.json
└── test_comprehensive_20260224_153245.json
```

## API参考

### XHSSearcher 类

主要搜索类，提供以下方法：

```python
class XHSSearcher:
    async def search_by_keyword(self, keyword: str, max_notes: int = 20) -> List[Dict]:
        """通过关键词搜索"""

    async def search_by_user(self, user_id: str, max_notes: int = 20) -> List[Dict]:
        """通过用户ID搜索用户笔记"""

    async def search_by_tag(self, tag: str, max_notes: int = 20) -> List[Dict]:
        """通过标签搜索"""
```

### 返回数据格式

每个笔记包含以下字段：

```json
{
  "url": "完整URL链接",
  "noteId": "24位笔记ID",
  "title": "笔记标题",
  "author": "作者名称",
  "likes": "点赞数",
  "type": "image|video",
  "xsecToken": "安全令牌",
  "xsecSource": "来源标识"
}
```

## 测试用例

### 1. 关键词搜索测试

```python
async def test_keyword_search(browser: XHSBrowser, keyword: str = "旅行") -> List[Dict]:
    """测试关键词搜索功能"""
```

**测试内容：**
- 搜索指定关键词
- 提取搜索结果
- 验证数据完整性
- 生成测试报告

### 2. 用户搜索测试

```python
async def test_user_search(browser: XHSBrowser, user_id: str = "5e7c3a8c0000000001006e32") -> List[Dict]:
    """测试用户搜索功能"""
```

**测试内容：**
- 访问用户主页
- 提取用户笔记
- 验证用户信息
- 生成测试报告

### 3. 标签搜索测试

```python
async def test_tag_search(browser: XHSBrowser, tag: str = "美食") -> List[Dict]:
    """测试标签搜索功能"""
```

**测试内容：**
- 搜索指定标签
- 提取标签内容
- 验证标签信息
- 生成测试报告

### 4. 综合测试

```python
async def run_comprehensive_test(browser: XHSBrowser, keyword: str = None, user_id: str = None, tag: str = None):
    """运行综合测试"""
```

**测试内容：**
- 依次执行所有测试
- 汇总测试结果
- 生成综合报告

## Cookie配置指南

### 获取Cookie的方法

1. 打开Chrome浏览器
2. 访问 https://www.xiaohongshu.com 并登录
3. 按F12打开开发者工具
4. 切换到 Application 标签
5. 选择 Cookies -> https://www.xiaohongshu.com
6. 复制以下Cookie的值：
   - `a1`
   - `web_session`
   - `webId`
   - `xsecappid`

### 配置格式

在 `config/cookies.txt` 中：

```ini
[xiaohongshu]
a1=your_a1_value_here
web_session=your_web_session_value_here
webId=your_webId_value_here
xsecappid=xhs-pc-web
```

## 常见问题

### 1. Cookie过期

**症状：** 显示"检测到未登录状态"

**解决：**
1. 更新 `config/cookies.txt` 中的Cookie值
2. 确保Cookie来自已登录状态
3. 检查Cookie是否完整

### 2. 页面加载超时

**症状：** 显示"页面加载问题"

**解决：**
1. 检查网络连接
2. 增加超时时间（修改代码中的timeout值）
3. 尝试使用非无头模式查看具体情况

### 3. 未搜索到结果

**症状：** 搜索返回空列表

**原因：**
- 关键词/用户ID/标签不存在
- Cookie权限不足
- 小红书反爬机制

**解决：**
1. 确认搜索内容是否存在
2. 更新Cookie
3. 减少搜索频率

### 4. Playwright未安装

**症状：** ModuleNotFoundError: No module named 'playwright'

**解决：**
```bash
pip install playwright
playwright install chromium
```

## 注意事项

1. **Cookie有效期：** Cookie会过期，需要定期更新
2. **请求频率：** 避免高频请求，可能导致IP被封
3. **数据合规：** 仅用于学习和测试，请遵守小红书用户协议
4. **无头模式：** 生产环境建议使用 `--headless` 参数
5. **输出目录：** 测试结果会保存在 `output/xhs_search_test/` 目录

## 扩展开发

### 添加新的搜索类型

1. 在 `XHSSearcher` 类中添加新方法
2. 创建对应的测试函数
3. 在 `run_comprehensive_test` 中调用
4. 更新命令行参数解析

### 自定义数据处理

修改 `XHSSearcher` 中的提取逻辑，可以：
- 提取更多字段
- 改进内容解析
- 添加数据过滤

## 性能优化建议

1. **并发请求：** 使用asyncio实现并发搜索
2. **缓存机制：** 缓存搜索结果减少重复请求
3. **代理支持：** 添加IP代理池
4. **分页加载：** 支持翻页获取更多数据

## 许可证

本项目仅用于学习和研究目的。使用时请遵守小红书用户协议和相关法律法规。

## 更新日志

### 2026-02-24
- 初始版本发布
- 实现关键词、用户、标签搜索
- 添加综合测试功能
- 完善测试报告和日志
