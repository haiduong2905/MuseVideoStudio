@echo off
rem ============================================================
rem  CHAN-DOAN.bat — chẩn đoán Muse Video Studio bằng 1 cú đúp chuột
rem  Đặt file này CẠNH MuseVideoStudio.exe (cùng thư mục), rồi đúp chuột.
rem  Nó sẽ chạy app, ghi toàn bộ thông báo lỗi vào chan-doan.log,
rem  rồi dừng lại để bạn đọc / gửi log cho trợ lý.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================
echo  CHAN DOAN Muse Video Studio
echo  Dang chay app, ghi log vao chan-doan.log ...
echo ===============================================
set QT_DEBUG_PLUGINS=1
MuseVideoStudio.exe > chan-doan.log 2>&1
echo.
echo -----------------------------------------------
echo  App da thoat (ma loi: %ERRORLEVEL%).
echo  Gui file chan-doan.log cho tro ly de duoc sua.
echo -----------------------------------------------
pause
