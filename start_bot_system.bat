@echo off
REM Bot启动脚本 - 不使用conda环境

echo ======================================================================
echo   Bot启动脚本（系统Python）
echo ======================================================================
echo.

cd /d %~dp0

echo [1/2] 检查系统Python...
python --version
if %errorlevel% neq 0 (
    echo   ❌ 系统Python未找到
    echo   💡 请安装Python或使用conda环境
    pause
    exit /b 1
)

echo.
echo [2/2] 启动Bot...
echo.

REM 使用系统Python启动Bot
python start_bot.py

if %errorlevel% neq 0 (
    echo.
    echo ======================================================================
    echo   启动失败
    echo ======================================================================
    echo.
    echo 💡 可能的原因:
    echo   1. python-telegram-bot 未安装
    echo   2. 配置文件有误
    echo.
    echo 💡 解决方法:
    echo   python -m pip install python-telegram-bot
    echo   python test_bot_config.py
    echo.
    pause
)

