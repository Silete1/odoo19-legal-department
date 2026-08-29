@echo off
REM Stop the permanent DMA Accreditation instance, including the restart loop
REM in dma_odoo_start.cmd. Run dma_odoo_start.cmd (or log out and back in) to
REM bring it back.
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*dma_odoo_start.cmd*' -or $_.CommandLine -like '*odoo19_dma_service.conf*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo DMA Accreditation Odoo stopped.
