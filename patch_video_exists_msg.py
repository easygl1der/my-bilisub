#!/usr/bin/env python3
"""
补丁脚本：修复视频已存在时的消息提示
"""
import re

# Read the file
with open('bots/help-bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 搜索模式
old_pattern = r'''                else:\s*await query\.message\.reply_text\(\s*f"✅ 执行完成！\\n\\n没有生成新的文件。"\s*\)\s*state\.clear\(\)'''

new_text = '''                else:
                    # Check if output mentions "video already exists" or "skipped download"
                    video_exists_msg = ""
                    if "视频已存在" in raw_output or "跳过下载" in raw_output:
                        video_exists_msg = "\\n📹 视频已下载，跳过重复下载。"
                    elif "笔记已存在" in raw_output or "skip" in raw_output.lower():
                        video_exists_msg = "\\n📝 内容已存在，跳过重复处理。"

                    if video_exists_msg:
                        await query.message.reply_text(
                            f"✅ 执行完成！{video_exists_msg}"
                        )
                    else:
                        await query.message.reply_text(
                            f"✅ 执行完成！\\n\\n没有生成新的文件。"
                        )
                    state.clear()'''

# 使用 re.DOTALL 标志来匹配多行模式
if re.search(r'''                else:\s*await query\.message\.reply_text\(\s*f"✅ 执行完成！\\n\\n没有生成新的文件。"\s*\)\s*state\.clear\(\)''', content, re.MULTILINE):
    content = re.sub(
        r'''                else:\s*await query\.message\.reply_text\(\s*f"✅ 执行完成！\\n\\n没有生成新的文件。"\s*\)\s*state\.clear\(\)''',
        new_text,
        content,
        flags=re.MULTILINE
    )
    with open('bots/help-bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 补丁应用成功！')
    print('现在当视频已存在时，会显示"📹 视频已下载，跳过重复下载。"')
else:
    print('❌ 未找到目标代码，可能已被修改')
