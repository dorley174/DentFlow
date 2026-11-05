$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Установите и запустите Docker Desktop: https://docs.docker.com/get-started/get-docker/'
}
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose не найден. Обновите Docker Desktop.' }
if (-not (Test-Path '.env')) {
    $template = [IO.File]::ReadAllText((Join-Path $PSScriptRoot '.env.example'))
    foreach ($key in @('POSTGRES_PASSWORD', 'SECRET_KEY')) {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        $value = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        $template = [regex]::Replace($template, '(?m)^' + $key + '=.*$', $key + '=' + $value)
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $template, (New-Object Text.UTF8Encoding($false)))
}
docker compose up -d --build --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Запуск не завершён. Выполните docker compose logs --tail=100 backend frontend' }
Write-Host 'DentFlow запущен: http://localhost:8080'
Write-Host 'Вход: admin@dentflow.local / Admin-Demo-2026!'
Start-Process 'http://localhost:8080'
