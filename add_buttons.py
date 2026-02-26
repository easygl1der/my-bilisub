#!/usr/bin/env python3
"""Add quick button commands to help-bot.py"""

# Read the file
with open("bots/help-bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find insertion point (after state.clear() and before async def cmd_ask)
insert_marker = '    state.clear()\n    async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):'
insert_pos = content.find(insert_marker)

if insert_pos == -1:
    print("Insertion point not found")
else:
    # Prepare new code to insert
    new_code = """


# ==================== Quick Button Commands ====================

async def cmd_btn_subtitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """B站字幕分析 - with model selection"""
    user_id = update.effective_user.id

    # Check authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Check if URL is provided
    url_arg = " ".join(context.args) if context.args else ""

    if not url_arg:
        # Show model selection buttons
        keyboard = InlineKeyboardMarkup([
            [
                [
                    InlineKeyboardButton("🔥 Flash Lite", callback_data=f"subtitle_flash-lite_{url_arg}" if url_arg else "subtitle_flash-lite"),
                    InlineKeyboardButton("⚡ Flash", callback_data=f"subtitle_flash_{url_arg}" if url_arg else "subtitle_flash"),
                    InlineKeyboardButton("💎 Pro", callback_data=f"subtitle_pro_{url_arg}" if url_arg else "subtitle_pro")
                ]
            ]
        ])

        help_text = """🎯 **B站字幕分析**

选择 Gemini 模型：
• 🔥 Flash Lite（快速，默认）
• ⚡ Flash（中等）
• 💎 Pro（高级）

如未提供 URL，请使用：`/ask 分析字幕 <视频链接>`
"""
        await update.message.reply_text(help_text, reply_markup=keyboard)

    else:
        # User provided URL and model
        # Map button callback data to model
        model_map = {
            "flash-lite": "flash-lite",
            "flash": "flash",
            "pro": "pro"
        }

        # Extract model from callback_data
        # Format: subtitle_<model>_<url_or_other>
        # e.g., "subtitle_flash-lite_https://..." or "subtitle_flash_pro" (no URL provided)

        # We'll use a simple approach: just call /ask with the model parameter
        parts = url_arg.split('_', 2) if '_' in url_arg else [url_arg]
        model = parts[0] if len(parts) > 0 else "flash-lite"

        # Build new command args for /ask
        # This is a bit complex, let me simplify by just showing the help again
        await update.message.reply_text(f"✅ 已选择：{model_map.get(model, model)} 模型\\n\\n正在执行...")

        # Store the selection in user's history for context
        state = get_user_state(user_id)
        state.history.append(f"字幕分析使用 {model} 模型")

        # Call /ask with the model parameter
        # To keep it simple, we'll just add the model to the args
        new_args = [url_arg, "--model", model]

        # Redirect to /ask
        await cmd_ask(update, context, user_input=" ".join(new_args))


async def cmd_btn_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """生成学习笔记 - with common options"""
    user_id = update.effective_user.id

    # Check authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Show options
    keyboard = InlineKeyboardMarkup([
        [
                [
                    InlineKeyboardButton("✨ 默认设置", callback_data="notes_default"),
                    InlineKeyboardButton("🎨 自定义参数", callback_data="notes_custom")
                ]
            ]
        ])

    help_text = """📝 **生成学习笔记**

选择模式：
• ✨ 默认设置 - flash-lite 模型，启用智能检测
• 🎨 自定义参数 - 可选择模型、关键帧等

如需自定义，回复：`自定义 <参数>`
例如：
• 自定义 flash 模型：`自定义 pro`
• 自定义 12 个关键帧：`自定义 --keyframes 12`
• 自定义并禁用智能检测：`自定义 --no-gemini`

如未提供 URL，请使用：`/ask 生成学习笔记 <视频链接>`
"""
        await update.message.reply_text(help_text, reply_markup=keyboard)

    else:
        # Custom parameters
        # Store in state for custom execution
        state = get_user_state(user_id)
        state.history.append(f"学习笔记自定义参数：{url_arg}")

        # Redirect to /ask with custom args
        new_args = [url_arg] + ["--model", "pro"]
        await cmd_ask(update, context, user_input=" ".join(new_args))


async def cmd_btn_bili(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """刷B站推荐"""
    user_id = update.effective_user.id

    # Check authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Show options
    keyboard = InlineKeyboardMarkup([
            [
                [
                    InlineKeyboardButton("📊 刷30次", callback_data="bili_30"),
                    InlineKeyboardButton("📊 刷50次", callback_data="bili_50")
                ]
            ]
        ])

    help_text = """🎬 **刷B站首页推荐**

选择刷新次数：
• 📊 刷新 30 次
• 📊 刷新 50 次

如需其他设置（模型、视频数），回复：`自定义`+具体参数
"""
        await update.message.reply_text(help_text, reply_markup=keyboard)

    else:
        # Custom parameters
        state = get_user_state(user_id)
        state.history.append(f"B站首页自定义参数：{url_arg}")

        # Parse custom params (format: refresh_count=max_videos=model=...)
        # For simplicity, just use /ask
        await cmd_ask(update, context, user_input=url_arg)


async def cmd_btn_xhs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """刷小红书推荐"""
    user_id = update.effective_user.id

    # Check authorization
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ 未授权用户")
        return

    # Show options
    keyboard = InlineKeyboardMarkup([
            [
                [
                    InlineKeyboardButton("📊 刷30次", callback_data="xhs_30"),
                    InlineKeyboardButton("📊 刷50次", callback_data="xhs_50")
                ]
            ]
        ])

    help_text = """🌸 **刷小红书推荐**

选择刷新次数：
• 📊 刷30 次
• 📊 刷新 50 次

如需其他设置（模型、笔记数），回复：`自定义`+具体参数
"""
        await update.message.reply_text(help_text, reply_markup=keyboard)

    else:
        # Custom parameters
        state = get_user_state(user_id)
        state.history.append(f"小红书自定义参数：{url_arg}")

        await cmd_ask(update, context, user_input=url_arg)


# ==================== Main ====================

if __name__ == "__main__":
    print("Script completed. Please manually update help-bot.py with the new code.")
"""

# Write back
with open("bots/help-bot.py", "w", encoding="utf-8") as f:
    # Insert the new code at the correct position
    f.write(content[:insert_pos] + new_code + content[insert_pos:])
