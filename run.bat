@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 网易云音乐VIP歌曲管理工具
echo ========================================
echo.

REM 检查是否已安装依赖
python -c "import pyncm, rich" 2>nul
if errorlevel 1 (
    echo [安装依赖]
    echo 正在安装所需依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo 错误: 依赖安装失败，请检查Python和pip是否正常
        pause
        exit /b 1
    )
    echo.
)

REM 运行程序
python -m netease_vip_manager.main %*

pause
