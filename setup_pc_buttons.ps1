# setup_pc_buttons.ps1 — creates the THREE staged PC buttons (scripts + desktop shortcuts).
# Run once on the PC:  powershell -ExecutionPolicy Bypass -File <path>\setup_pc_buttons.ps1
# Matches the Jetson's three-button off-ramp flow: RIG CHECK -> RIG PRE-FLIGHT -> RIG KIOSK.

$home2 = "C:\Users\janes"
$desktop = [Environment]::GetFolderPath("Desktop")   # OneDrive-aware
$rig = "192.168.0.204"

# ---- write the three scripts to stable paths ----
@'
$Host.UI.RawUI.WindowTitle = "RIG CHECK"
Write-Host "=== RIG CHECK (step 1 of 3) ===" -ForegroundColor Green
Write-Host "Running wholeness check on the Jetson..." -ForegroundColor Yellow
$out = ssh rig "bash ~/rig_check.sh" 2>&1
$out | ForEach-Object { Write-Host "    $_" }
if ((($out -join "`n")) -like "*ALL GREEN*") { Write-Host "`n  SAFE TO PROCEED -> next: RIG PRE-FLIGHT" -ForegroundColor Green }
else { Write-Host "`n  STOP - fix the RED file(s) above first." -ForegroundColor Red }
Read-Host "`nPress Enter to close"
'@ | Set-Content "$home2\pc_rig_check.ps1"

@'
$Host.UI.RawUI.WindowTitle = "RIG PRE-FLIGHT"
Write-Host "=== RIG PRE-FLIGHT (step 2 of 3) ===" -ForegroundColor Cyan
Write-Host "Running pre-flight on the Jetson..." -ForegroundColor Yellow
$out = ssh rig "bash ~/rig_launch.sh" 2>&1
$out | ForEach-Object { Write-Host "    $_" }
if ((($out -join "`n")) -like "*STAGE 1 PASSED*") { Write-Host "`n  Stack whole - check the rig-status line above. If rig up -> RIG KIOSK." -ForegroundColor Green }
else { Write-Host "`n  STOP - stack not whole (see above)." -ForegroundColor Red }
Read-Host "`nPress Enter to close"
'@ | Set-Content "$home2\pc_rig_preflight.ps1"

@'
$rig = "192.168.0.204"
$Host.UI.RawUI.WindowTitle = "RIG KIOSK"
Write-Host "=== RIG KIOSK (step 3 of 3) ===" -ForegroundColor Yellow
Write-Host "Ensuring the kiosk server runs on the Jetson..." -ForegroundColor Yellow
ssh rig "pgrep -f rig_kiosk_server.py >/dev/null || (nohup python3 ~/Desktop/rig_kiosk_server.py > ~/Desktop/kiosk.log 2>&1 &)" 2>&1 | ForEach-Object { Write-Host "    $_" }
Write-Host "Waiting for the server..." -ForegroundColor Yellow
$up = $false
for ($i=0; $i -lt 12; $i++) { try { $r = Invoke-WebRequest -Uri "http://$($rig):8080/data" -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { $up=$true; break } } catch {} ; Write-Host "." -NoNewline; Start-Sleep 2 }
Write-Host ""
if ($up) { Write-Host "  Server UP - opening the kiosk on this PC." -ForegroundColor Green; Start-Process "http://$($rig):8080/kiosk" }
else { Write-Host "  Server not answering. Open manually: http://$($rig):8080/kiosk" -ForegroundColor Yellow }
Read-Host "`nPress Enter to close"
'@ | Set-Content "$home2\pc_rig_kiosk.ps1"

# ---- create the three desktop shortcuts ----
$W = New-Object -ComObject WScript.Shell
function MkLnk($name, $script) {
    $l = $W.CreateShortcut("$desktop\$name.lnk")
    $l.TargetPath = "powershell.exe"
    $l.Arguments  = "-ExecutionPolicy Bypass -File `"$home2\$script`""
    $l.WorkingDirectory = $home2
    $l.IconLocation = "powershell.exe,0"
    $l.Description = $name
    $l.Save()
    Write-Host "  created: $name.lnk"
}
MkLnk "1 RIG CHECK"      "pc_rig_check.ps1"
MkLnk "2 RIG PRE-FLIGHT" "pc_rig_preflight.ps1"
MkLnk "3 RIG KIOSK"      "pc_rig_kiosk.ps1"

Write-Host "`nDONE. Three staged buttons on the Desktop: 1 RIG CHECK -> 2 RIG PRE-FLIGHT -> 3 RIG KIOSK" -ForegroundColor Green
Read-Host "Press Enter to close"
