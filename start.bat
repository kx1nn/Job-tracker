@echo off
chcp 65001 >nul
title 求职投递看板
cd /d "%~dp0"

REM ========== 如果看板已在后台运行：直接打开浏览器，本窗口退出 ==========
set RUNNING=
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8877" ^| findstr "LISTENING"') do set RUNNING=1
if defined RUNNING (
    start "" http://127.0.0.1:8877/
    exit
)

REM ========== 检查 Python ==========
where pythonw >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 pythonw，请先安装 Python 3.8+ 并勾选 "Add to PATH"
    pause
    exit
)

REM ========== 后台启动服务（无窗口，关掉本窗口也不影响） ==========
start "" pythonw.exe app\server.py

REM 等待服务就绪（最多约 10 秒）
set OK=
for /l %%i in (1,1,10) do (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8877" ^| findstr "LISTENING"') do set OK=1
    if defined OK goto ready
    timeout /t 1 /nobreak >nul
)
:ready
if not defined OK (
    echo [错误] 看板服务启动失败，请打开「服务错误.log」查看原因
    pause
    exit
)

REM 浏览器由 server 自动打开（若未弹出，手动访问 http://127.0.0.1:8877/）
echo.
echo  ✅ 看板已启动，浏览器将自动打开
echo.
echo  提示：本窗口现在可以关掉，看板会在后台继续运行。
echo  关闭浏览器标签也不影响，随时重新打开 http://127.0.0.1:8877/ 即可。
echo  只有电脑关机后，才需要再次双击本文件启动。
echo.
timeout /t 4 /nobreak >nul
exit
