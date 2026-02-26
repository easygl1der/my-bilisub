# Claude Code Git Worktree 完整使用指南

**适用人群**：用多个Claude Code会话开发，但仓库乱成一锅粥的你  
**核心理念**：每个Claude任务 → 独立文件夹 + 分支 → 互不干扰 + 清晰记录  
**时间投入**：学会后每次开新任务只需10秒

***

## 📋 快速开始清单（照着抄就行）

```bash
# 1. 一次性设置（项目根目录执行一次）
mkdir .worktrees
echo ".worktrees/" >> .gitignore

# 2. 每天开新任务
git worktree add .worktrees/任务名 -b 分支名
cd .worktrees/任务名 && claude

# 3. 任务完成清理
cd ../..
git merge 分支名
git worktree remove .worktrees/任务名
git branch -d 分支名
git worktree prune
```

***

## 🎬 完整操作流程（老奶奶都能看懂版）

### 第一步：项目初始化（做一次就够）
```bash
cd ~/Projects/你的项目名
mkdir .worktrees          # 专门放Claude"独立房间"的文件夹
echo ".worktrees/" >> .gitignore  # 告诉Git忽略这些房间
```

### 第二步：开新Claude任务（每天重复用）
今天要做3件事？3个终端窗口：

**终端1 - 修登录bug**：
```bash
git worktree add .worktrees/fix-login -b fix/login-bug
cd .worktrees/fix-login && claude
```

**终端2 - 加支付功能**：
```bash
git worktree add .worktrees/feature-pay -b feature/payment
cd .worktrees/feature-pay && claude  
```

**终端3 - 优化首页**：
```bash
git worktree add .worktrees/refactor-home -b refactor/homepage
cd .worktrees/refactor-home && claude
```

**🎉 效果**：3个Claude各自在独立文件夹，完全互不干扰！

### 第三步：工作中记录进度
每个Claude终端里：
```
"帮我commit一下，写清晰的commit message"
```
或手动：
```bash
git add .
git commit -m "fix: 登录按钮点击无反应已修复"
```

### 第四步：任务完成，合并清理
回到主项目目录：
```bash
cd ~/Projects/你的项目名

# 合并成功的任务
git merge fix/login-bug

# 删掉这个"房间"
git worktree remove .worktrees/fix-login
git branch -d fix/login-bug

# 清理残留
git worktree prune
```

***

## 🔍 常用状态查询命令

```bash
# 查看所有正在运行的Claude房间
git worktree list

# 查看今天都干了什么（任意房间都能看）
git log --oneline -10

# 当前房间状态
git status

# 所有房间一览（路径+分支）
git worktree list --porcelain
```

***

## ⚠️ 三个必知注意事项

| 问题 | 解决 |
|------|------|
| **同一个分支不能同时开两个房间** | 用 `-b 新分支名` 创建新分支 |
| **新房间要重新装依赖** | `pip install -r requirements.txt` 或 `npm install` |
| **Claude卡住了** | `/clear` 清上下文，或直接删房间重来 |

***

## 💡 进阶技巧

### 1. 批量开房间脚本
保存为 `new-task.sh`：
```bash
#!/bin/bash
TASK_NAME=$1
BRANCH_NAME=$2
git worktree add .worktrees/$TASK_NAME -b $BRANCH_NAME
cd .worktrees/$TASK_NAME && claude
```
用法：`./new-task.sh fix-api "fix/api-v2"`

### 2. 一键清理失败任务
```bash
# 查看所有房间
git worktree list

# 删掉不要的
git worktree remove .worktrees/失败任务名
git branch -d 失败分支名
```

### 3. 每日回顾脚本
```bash
git log --since="1 day ago" --oneline --graph
```

***

## 🎯 为什么这套流程解决你的所有问题？

| 你之前的问题 | Worktree如何解决 |
|-------------|--------------------|
| 不知道改了什么 | 每个commit都有清晰记录，`git log` 一览无余 |
| 失败代码污染仓库 | 失败任务直接删分支，主仓库永远干净 |
| 新Claude读到旧垃圾代码 | 每个房间独立分支，互不干扰 |
| 回顾时迷失方向 | 每个分支名就是任务说明，按分支名就知道干了啥 |

***

## 📱 速查表（打印保存）

```
🚀 开新任务：
git worktree add .worktrees/任务名 -b 分支名

📝 记录进度：
git commit -m "做了什么"

🔍 查看进度：
git log --oneline

✅ 任务完成：
git merge 分支名 && git worktree remove .worktrees/任务名

🧹 清理：
git worktree prune
```

***

**保存这份文档到项目根目录的 `WORKTREE.md`，让每个Claude都能读懂你的工作流！** 🎉

现在把这个md文件保存到你项目根目录，以后每次Claude启动前让它先读一遍，保证它永远知道你的工作习惯！