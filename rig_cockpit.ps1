# rig_cockpit.ps1 — PC COCKPIT one-click launcher (eye-is-arbiter).
# 1) runs the wholeness check on the Jetson (rig_check.sh) and shows it HERE;
# 2) if whole, starts JUST the kiosk server on the Jetson (NOT Firefox-on-Jetson);
# 3) opens the kiosk in THIS PC's browser.
# Uses the passwordless ssh rig set up 2026-09-09. Does not power the L2, does not auto-heal.

$rig = "192.168.0.204"
$Host.UI.RawUI.WindowTitle = "RIG COCKPIT"
Write-Host "=== RIG COCKPIT ===" -ForegroundColor Cyan

# ---- STAGE 1: wholeness check on the Jetson, shown here ----
Write-Host "`n>>> STAGE 1: stack wholeness check (on the Jetson)..." -ForegroundColor Yellow
$check = ssh rig "bash ~/rig_check.sh" 2>&1
$check | ForEach-Object { Write-Host "    $_" }
if ($check -notmatch "ALL GREEN") {
    Write-Host "`n!!! Stack is NOT whole — see RED lines + FIX above. Cockpit STOPS (won't open a broken kiosk)." -ForegroundColor Red
    Read-Host "`nPress Enter to close"
    exit 1
}
Write-Host ">>> STAGE 1 PASSED — stack whole." -ForegroundColor Green

# ---- STAGE 2: start JUST the server on the Jetson (no Firefox-on-Jetson), if not already up ----
Write-Host "`n>>> STAGE 2: ensuring the kiosk server is running on the Jetson..." -ForegroundColor Yellow
# start server in background on the Jetson only if not already running; do NOT launch firefox there
ssh rig "pgrep -f rig_kiosk_server.py >/dev/null || (nohup python3 ~/Desktop/rig_kiosk_server.py > ~/Desktop/kiosk.log 2>&1 &)" 2>&1 | ForEach-Object { Write-Host "    $_" }

# ---- STAGE 3: wait for it to answer, then open the kiosk on THIS PC ----
Write-Host "`n>>> Waiting for the server to answer at $rig ..." -ForegroundColor Yellow
$up = $false
for ($i=0; $i -lt 12; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://$($rig):8080/data" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch { }
    Write-Host "." -NoNewline; Start-Sleep -Seconds 2
}
Write-Host ""
if ($up) {
    Write-Host ">>> Server UP — opening the kiosk on this PC." -ForegroundColor Green
    Start-Process "http://$($rig):8080/kiosk"
    Write-Host "`n    Kiosk open on the PC. For a capture: power the L2, run rig_start_lean.sh + a capture" -ForegroundColor DarkGray
    Write-Host "    on the Jetson (or via ssh), then WALK to fill the coverage MAP." -ForegroundColor DarkGray
} else {
    Write-Host ">>> Server not answering. Check the Jetson (is it on the network? see ~/Desktop/kiosk.log)." -ForegroundColor Yellow
    Write-Host "    You can also just open:  http://$($rig):8080/kiosk"
}
Read-Host "`nPress Enter to close this window"
