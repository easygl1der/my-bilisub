@echo off
REM Bot启动脚本 - conda环境（修复DLL问题）

echo ======================================================================
echo   Bot启动脚本（conda环境）
echo ======================================================================
echo.

cd /d %~dp0

echo [1/4] 激活conda环境...
call conda activate bilisub
if %errorlevel% neq 0 (
    echo   ❌ 无法激活conda环境
    echo   💡 请确保conda已安装且bilisub环境存在
    pause
    exit /b 1
)

echo.
echo [2/4] 修复pip DLL问题...
echo 正在重新安装pip...
conda install -y pip --force-reinstall

echo.
echo [3/4] 安装python-telegram-bot...
echo 这可能需要几分钟...
pip install python-telegram-bot --quiet

if %errorlevel% neq 0 (
    echo   ❌ 安装失败
    echo   💡 请尝试使用系统Python版本: start_bot_system.bat
    pause
    exit /b 1
)

echo.
echo [4/4] 启动Bot...
echo.
python start_bot.py

pause
