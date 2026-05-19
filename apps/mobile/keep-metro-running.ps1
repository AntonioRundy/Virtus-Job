# Virtus Job — Metro Persistent Monitor (SDK 54)
# Keeps Metro running 24/7 in LAN mode. Auto-restarts on crash.
# Phone connects via: exp://192.168.1.11:8081

$ScriptDir = "C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\apps\mobile"
$LogFile   = "$ScriptDir\metro-monitor.log"
$LanIp     = "192.168.1.11"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

function Is-MetroRunning {
    # Verificar se a porta 8081 está a aceitar ligações
    # (não usa CommandLine que requer privilégios de admin)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 8081)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

function Start-Metro {
    Log "Starting Metro SDK 54 (LAN mode)..."
    Set-Location $ScriptDir
    Remove-Item "$ScriptDir\.expo" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$ScriptDir\node_modules\.cache" -Recurse -Force -ErrorAction SilentlyContinue
    $env:EXPO_PUBLIC_API_URL = "http://${LanIp}:8000"
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c npx expo start --host lan --port 8081 --clear 2>&1 >> `"$LogFile`"" `
        -WorkingDirectory $ScriptDir `
        -WindowStyle Hidden
    Start-Sleep -Seconds 12
    Log "Metro started — URL: exp://${LanIp}:8081"
}

Log "=== Virtus Job Metro Monitor STARTED (SDK 54) ==="
Log "LAN URL: exp://${LanIp}:8081  API: http://${LanIp}:8000"

$restartCount = 0
while ($true) {
    if (-not (Is-MetroRunning)) {
        $restartCount++
        Log "Metro not running (restart #$restartCount)"
        Start-Metro
    }
    Start-Sleep -Seconds 30
}