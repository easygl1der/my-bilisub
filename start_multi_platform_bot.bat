@echo off
REM 多平台Bot启动脚本

echo ======================================================================
echo   多平台内容分析Bot启动脚本
echo ======================================================================
echo.

cd /d %~dp0

echo [1/3] 检查Bot配置...
python test_multi_platform_bot.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ 配置验证失败，请检查配置文件
    pause
    exit /b 1
)

echo.
echo [2/3] 检查python-telegram-bot...
python -c "import telegram" 2>nul
if %errorlevel% neq 0 (
    echo   python-telegram-bot未安装，正在安装...
    echo   这可能需要几分钟...
    pip install python-telegram-bot --quiet
    if %errorlevel% neq 0 (
        echo   ❌ 安装失败
        echo   💡 请手动安装: pip install python-telegram-bot
        pause
        exit /b 1
    )
    echo   ✅ 安装成功
) else (
    echo   ✅ python-telegram-bot已安装
)

echo.
echo [3/3] 启动Bot...
echo.
echo 🤖 Bot正在启动...
echo 💡 按 Ctrl+C 停止Bot
echo.
python bot\multi_platform_summary_bot.py

if %errorlevel% neq 0 (
    echo.
    echo ======================================================================
    echo   启动失败
    echo ======================================================================
    echo.
    echo 💡 可能的原因:
    echo   1. Bot Token配置错误
    echo   2. 网络连接问题
    echo   3. python-telegram-bot版本不兼容
    echo.
    echo 💡 解决方法:
    echo   1. 检查config\bot_config.json中的bot_token
    echo   2. 运行 python test_multi_platform_bot.py 验证配置
    echo   3. 重新安装: pip install python-telegram-bot --force-reinstall
    echo.
    pause
)
