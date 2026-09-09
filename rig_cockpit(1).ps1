# rig_cockpit.ps1 - PC COCKPIT one-click launcher (eye-is-arbiter).
# 1) runs the wholeness check on the Jetson (rig_check.sh) and shows it HERE
# 2) if whole, starts JUST the kiosk server on the Jetson (not Firefox-on-Jetson)
# 3) opens the kiosk in THIS PC browser
# Uses the passwordless ssh rig set up 2026-09-09. Does not power the L2, does not auto-heal.

$rig = "192.168.0.204"
$Host.UI.RawUI.WindowTitle = "RIG COCKPIT"
Write-Host "=== RIG COCKPIT ===" -ForegroundColor Cyan

# ---- STAGE 1: wholeness check on the Jetson, shown here ----
Write-Host ""
Write-Host ">>> STAGE 1: stack wholeness check (on the Jetson)..." -ForegroundColor Yellow
$check = ssh rig "bash ~/rig_check.sh" 2>&1
$check | ForEach-Object { Write-Host "    $_" }
$checkText = ($check -join "`n")
if ($checkText -notlike "*ALL GREEN*") {
    Write-Host ""
    Write-Host "!!! Stack is NOT whole - see RED lines and FIX above. Cockpit STOPS." -ForegroundColor Red
    Write-Host "    (Will not open a broken kiosk. Fix on the Jetson, then re-run.)" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
Write-Host ">>> STAGE 1 PASSED - stack whole." -ForegroundColor Green

# ---- STAGE 2: start JUST the server on the Jetson (no Firefox there), if not already up ----
Write-Host ""
Write-Host ">>> STAGE 2: ensuring the kiosk server runs on the Jetson..." -ForegroundColor Yellow
ssh rig "pgrep -f rig_kiosk_server.py >/dev/null || (nohup python3 ~/Desktop/rig_kiosk_server.py > ~/Desktop/kiosk.log 2>&1 &)" 2>&1 | ForEach-Object { Write-Host "    $_" }

# ---- STAGE 3: wait for it to answer, then open the kiosk on THIS PC ----
Write-Host ""
Write-Host ">>> Waiting for the server to answer at $rig ..." -ForegroundColor Yellow
$up = $false
for ($i=0; $i -lt 12; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://$($rig):8080/data" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch { }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
}
Write-Host ""
if ($up) {
    Write-Host ">>> Server UP - opening the kiosk on this PC." -ForegroundColor Green
    Start-Process "http://$($rig):8080/kiosk"
    Write-Host "    Kiosk open. For a capture: power the L2, run rig_start_lean.sh and a capture, then WALK." -ForegroundColor DarkGray
} else {
    Write-Host ">>> Server not answering. Is the Jetson on the network? Check kiosk.log on the Jetson." -ForegroundColor Yellow
    Write-Host "    You can also just open:  http://$($rig):8080/kiosk"
}
Read-Host "Press Enter to close this window"
