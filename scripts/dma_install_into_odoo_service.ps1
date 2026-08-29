<#
  Adds the DMA Accreditation addon to the OFFICIAL Odoo 19 Windows service
  (odoo-server-19.0), so the module is served on port 8069 by a real service
  that starts before anyone logs in.

  MUST BE RUN AS ADMINISTRATOR:
      Right-click Windows Terminal -> Run as administrator, then:
      powershell -ExecutionPolicy Bypass -File "C:\Users\Lenovo\Documents\odoo19\scripts\dma_install_into_odoo_service.ps1"

  It is safe to run twice: the addons path is only added if it is missing, and
  the configuration file is backed up first.
#>
$ErrorActionPreference = 'Stop'

$conf    = 'C:\Program Files\Odoo 19.0.20260525\server\odoo.conf'
$addons  = 'C:\Users\Lenovo\Documents\odoo19\custom_addons'
$service = 'odoo-server-19.0'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'This script must be run as Administrator.'
}
if (-not (Test-Path $conf))   { throw "Odoo configuration not found: $conf" }
if (-not (Test-Path $addons)) { throw "Addons directory not found: $addons" }

$backup = "$conf.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item $conf $backup
Write-Host "Backed up configuration to $backup"

$lines = Get-Content $conf
$done  = $false
$out = foreach ($line in $lines) {
    if ($line -match '^\s*addons_path\s*=' -and -not $done) {
        $done = $true
        if ($line -like "*$addons*") {
            Write-Host 'Addons path already present, leaving it unchanged.'
            $line
        } else {
            Write-Host 'Adding the DMA addons path.'
            "$line,$addons"
        }
    } else { $line }
}
if (-not $done) { $out += "addons_path = $addons" }
Set-Content -Path $conf -Value $out -Encoding ASCII

Write-Host 'Restarting the Odoo service...'
Restart-Service -Name $service -Force
Start-Sleep -Seconds 20
$svc = Get-Service -Name $service
Write-Host "Service $($svc.Name) is $($svc.Status)."

Write-Host ''
Write-Host 'Next: open http://localhost:8069, pick the dma_accreditation database'
Write-Host '(or create a new one), then Apps -> Update Apps List -> install'
Write-Host '"DMA Accreditation".'
