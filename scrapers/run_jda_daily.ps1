Set-Location 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\apps\api;C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job'
$env:DATABASE_URL = 'postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job'
$env:EXPO_PUBLIC_API_URL = 'http://192.168.1.11:8000'

# Carregar ANTHROPIC_API_KEY do .env
$envContent = Get-Content 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\.env' | Where-Object { $_ -match '^ANTHROPIC_API_KEY=' }
if ($envContent) {
    $env:ANTHROPIC_API_KEY = $envContent.Split('=', 2)[1].Trim()
}

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "$timestamp Starting JDA Daily Pipeline..."

& 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\scrapers\.venv\Scripts\python.exe' 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\scrapers\jda_daily.py' 2>&1 | Tee-Object -FilePath 'C:\Users\LENOVO\Documents\2026\my-softwaree\virtus-job\logs\jda_scheduler.log' -Append
