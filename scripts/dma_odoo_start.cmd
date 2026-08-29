@echo off
REM ---------------------------------------------------------------------------
REM Permanent DMA Accreditation Odoo instance.
REM Started by the scheduled task "DMA Accreditation Odoo" at logon, and
REM runnable by hand for a foreground start.
REM ---------------------------------------------------------------------------

REM The official Odoo install ships wkhtmltopdf; borrowing it from PATH is what
REM makes the letters and certificates come out as real PDFs.
set "PATH=C:\Program Files\Odoo 19.0.20260525\thirdparty;%PATH%"

set "ODOO_HOME=C:\Users\Lenovo\Documents\odoo19"
set "PYTHON=%ODOO_HOME%\.venv_odoo19\Scripts\python.exe"
set "ODOO_BIN=%ODOO_HOME%\odoo-19.0\odoo-bin"
set "CONF=%ODOO_HOME%\odoo19_dma_service.conf"

cd /d "%ODOO_HOME%"

REM Restart automatically if the server ever exits.
:run
"%PYTHON%" "%ODOO_BIN%" -c "%CONF%"
timeout /t 10 /nobreak >nul
goto run
