# 피타고라스 전시용 실행 스크립트
# 이 PC에서 서버를 켜고 Cloudflare 터널로 외부 접속 주소를 만듭니다.
# 실행: powershell -ExecutionPolicy Bypass -File .\start-exhibition.ps1
# 종료: 이 창에서 Ctrl+C

Set-Location $PSScriptRoot
$Port = 8001

if (-not $env:TOSSINVEST_CLIENT_ID -or -not $env:TOSSINVEST_CLIENT_SECRET) {
    Write-Host "토스 키 환경변수(TOSSINVEST_CLIENT_ID, TOSSINVEST_CLIENT_SECRET)가 없습니다." -ForegroundColor Red
    Write-Host "setx 로 등록한 뒤 PowerShell 창을 새로 열고 다시 실행하세요."
    exit 1
}
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared가 설치되어 있지 않습니다. 아래 명령으로 설치한 뒤 창을 새로 여세요." -ForegroundColor Red
    Write-Host "winget install --id Cloudflare.cloudflared -e"
    exit 1
}

Write-Host "서버를 시작합니다 (http://127.0.0.1:$Port)"
$server = Start-Process python -ArgumentList "-m uvicorn server:app --host 127.0.0.1 --port $Port" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
if ($server.HasExited) {
    Write-Host "서버가 시작되지 않았습니다. 'python -m uvicorn server:app --port $Port'를 직접 실행해 오류를 확인하세요." -ForegroundColor Red
    exit 1
}

Write-Host "외부 접속 주소를 만드는 중입니다. 잠시 기다리세요."
try {
    cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$Port" 2>&1 | ForEach-Object {
        $line = "$_"
        if ($line -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $url = $Matches[0]
            Set-Content -Path (Join-Path $PSScriptRoot "tunnel-url.txt") -Value $url -Encoding UTF8
            Write-Host ""
            Write-Host "  접속 주소: $url" -ForegroundColor Green
            Write-Host "  (tunnel-url.txt 에도 저장했습니다. 이 창을 닫으면 접속이 끊깁니다.)"
            Write-Host ""
        }
    }
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Write-Host "서버와 터널을 종료했습니다."
}
