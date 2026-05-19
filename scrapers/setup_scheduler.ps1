# Virtus Job — Setup do Agendador Diário JDA
# Executa: powershell -ExecutionPolicy Bypass -File scrapers\setup_scheduler.ps1
#
# Cria duas tarefas no Windows Task Scheduler:
#   - VirtusJob-JDA-Daily   : todos os dias às 07:30
#   - VirtusJob-JDA-Check   : todos os dias às 14:00 (re-corre se manhã falhou)

$ProjectRoot = "C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job"
$PythonExe   = "$ProjectRoot\scrapers\.venv\Scripts\python.exe"
$Script      = "$ProjectRoot\scrapers\jda_daily.py"
$LogDir      = "$ProjectRoot\logs"

# Verificar que o ambiente existe
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv não encontrado: $PythonExe"
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── Acção comum ──────────────────────────────────────────────────────────────

$RunScript = @"
Set-Location '$ProjectRoot'
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONPATH = '$ProjectRoot\apps\api;$ProjectRoot'
`$env:DATABASE_URL = 'postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job'
`$env:EXPO_PUBLIC_API_URL = 'http://192.168.1.11:8000'

# Carregar ANTHROPIC_API_KEY do .env
`$envContent = Get-Content '$ProjectRoot\.env' | Where-Object { `$_ -match '^ANTHROPIC_API_KEY=' }
if (`$envContent) {
    `$env:ANTHROPIC_API_KEY = `$envContent.Split('=', 2)[1].Trim()
}

`$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "`$timestamp Starting JDA Daily Pipeline..."

& '$PythonExe' '$Script' 2>&1 | Tee-Object -FilePath '$LogDir\jda_scheduler.log' -Append
"@

$RunScriptPath = "$ProjectRoot\scrapers\run_jda_daily.ps1"
$RunScript | Out-File -FilePath $RunScriptPath -Encoding UTF8
Write-Host "Script de execução criado: $RunScriptPath"

# ── Tarefa 1: 07:30 diário ───────────────────────────────────────────────────

$action1 = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$RunScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$trigger1 = New-ScheduledTaskTrigger -Daily -At "07:30"

$settings1 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -WakeToRun $false

Register-ScheduledTask `
    -TaskName   "VirtusJob-JDA-Daily" `
    -TaskPath   "\VirtusJob\" `
    -Action     $action1 `
    -Trigger    $trigger1 `
    -Settings   $settings1 `
    -Description "Captura diária do Jornal de Angola às 07:30" `
    -RunLevel   Limited `
    -Force | Out-Null

Write-Host "Tarefa criada: VirtusJob-JDA-Daily (07:30 diário)"

# ── Tarefa 2: 14:00 (re-corre se manhã falhou) ────────────────────────────────

$action2 = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$RunScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$trigger2 = New-ScheduledTaskTrigger -Daily -At "14:00"

Register-ScheduledTask `
    -TaskName   "VirtusJob-JDA-Retry" `
    -TaskPath   "\VirtusJob\" `
    -Action     $action2 `
    -Trigger    $trigger2 `
    -Settings   $settings1 `
    -Description "Re-execução diária JDA às 14:00 (se manhã falhou, skip se OK)" `
    -RunLevel   Limited `
    -Force | Out-Null

Write-Host "Tarefa criada: VirtusJob-JDA-Retry (14:00 diário)"

# ── Verificar ────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== Tarefas registadas ==="
Get-ScheduledTask -TaskPath "\VirtusJob\" | Format-Table TaskName, State -AutoSize

Write-Host ""
Write-Host "Para executar agora manualmente:"
Write-Host "  Start-ScheduledTask -TaskName 'VirtusJob-JDA-Daily' -TaskPath '\VirtusJob\'"
Write-Host ""
Write-Host "Para remover:"
Write-Host "  Unregister-ScheduledTask -TaskName 'VirtusJob-JDA-Daily' -TaskPath '\VirtusJob\' -Confirm:`$false"
Write-Host "  Unregister-ScheduledTask -TaskName 'VirtusJob-JDA-Retry' -TaskPath '\VirtusJob\' -Confirm:`$false"
