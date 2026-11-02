@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 优先使用项目虚拟环境 Python，否则回退系统 python
set PY=python
if exist ".venv\Scripts\python.exe" set PY=".venv\Scripts\python.exe"

set ACTION=%1
if "%ACTION%"=="" goto menu
if /i "%ACTION%"=="first"  goto run_first
if /i "%ACTION%"=="sign"   goto run_sign
if /i "%ACTION%"=="renew"  goto run_renew
if /i "%ACTION%"=="cancel" goto run_cancel
goto menu

:menu
echo.
echo  ================================================
echo    超星图书馆座位预约工具（西安体育学院 roomid=14176）
echo  ================================================
echo    1. 抢座第一段    main.py -m first
echo    2. 签到          sign_seat.py
echo    3. 续约到闭馆    renew_seat.py
echo    4. 退座          cancel_seat.py
echo.
set /p CHOICE=请输入数字(1-4)后回车:
if "%CHOICE%"=="1" goto run_first
if "%CHOICE%"=="2" goto run_sign
if "%CHOICE%"=="3" goto run_renew
if "%CHOICE%"=="4" goto run_cancel
goto done

:run_first
%PY% main.py -u config.json -m first >> run_log.txt 2>&1
goto done

:run_sign
%PY% sign_seat.py -u config.json >> run_log.txt 2>&1
goto done

:run_renew
%PY% renew_seat.py -u config.json >> run_log.txt 2>&1
goto done

:run_cancel
%PY% cancel_seat.py -u config.json >> run_log.txt 2>&1
goto done

:done
echo.
echo 执行完毕，日志已写入 run_log.txt
pause
