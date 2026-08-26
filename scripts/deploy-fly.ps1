# Deploy ai-travel-helper to Fly.io
$ErrorActionPreference = "Continue"
$env:Path = "D:\Google\fly\bin;" + $env:Path

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
$AppName = "ai-travel-helper-kitty"

Write-Host "Working dir: $Root" -ForegroundColor Cyan
Write-Host "==> Check login..." -ForegroundColor Cyan
flyctl auth whoami
if ($LASTEXITCODE -ne 0) {
  Write-Host "Not logged in. Run: flyctl auth login" -ForegroundColor Red
  exit 1
}

$EnvFile = Join-Path $Root "backend\.env"
if (-not (Test-Path $EnvFile)) {
  Write-Host "Missing backend\.env" -ForegroundColor Red
  exit 1
}

$vars = @{}
Get-Content $EnvFile -Encoding UTF8 | ForEach-Object {
  $line = $_.Trim()
  if (-not $line) { return }
  if ($line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
  $vars[$k] = $v
}

foreach ($k in @("DEEPSEEK_API_KEY", "AMAP_API_KEY", "API_SECRET_KEY")) {
  $ok = $vars.ContainsKey($k) -and $vars[$k] -and ($vars[$k] -notmatch "your-|change-me|sk-your")
  if (-not $ok) {
    Write-Host "backend\.env missing valid $k" -ForegroundColor Red
    exit 1
  }
}

Write-Host "==> Ensure app exists..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
flyctl status -a $AppName 2>&1 | Out-Null
$statusCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($statusCode -ne 0) {
  Write-Host "Creating app $AppName ..." -ForegroundColor Yellow
  flyctl apps create $AppName
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Create app failed. Change app name in fly.toml and retry." -ForegroundColor Red
    exit 1
  }
}

Write-Host "==> Set secrets..." -ForegroundColor Cyan
flyctl secrets set ("DEEPSEEK_API_KEY=" + $vars["DEEPSEEK_API_KEY"]) -a $AppName --stage
flyctl secrets set ("AMAP_API_KEY=" + $vars["AMAP_API_KEY"]) -a $AppName --stage
flyctl secrets set ("API_SECRET_KEY=" + $vars["API_SECRET_KEY"]) -a $AppName --stage
flyctl secrets set "CORS_ALLOW_ORIGINS=*" -a $AppName --stage
if ($vars.ContainsKey("DEEPSEEK_BASE_URL") -and $vars["DEEPSEEK_BASE_URL"]) {
  flyctl secrets set ("DEEPSEEK_BASE_URL=" + $vars["DEEPSEEK_BASE_URL"]) -a $AppName --stage
}

$amapJs = $vars["AMAP_API_KEY"]
if ($vars.ContainsKey("VITE_AMAP_KEY") -and $vars["VITE_AMAP_KEY"]) {
  $amapJs = $vars["VITE_AMAP_KEY"]
}
$amapSec = ""
if ($vars.ContainsKey("VITE_AMAP_SECURITY_CODE") -and $vars["VITE_AMAP_SECURITY_CODE"]) {
  $amapSec = $vars["VITE_AMAP_SECURITY_CODE"]
} elseif ($vars.ContainsKey("AMAP_SECURITY_CODE") -and $vars["AMAP_SECURITY_CODE"]) {
  $amapSec = $vars["AMAP_SECURITY_CODE"]
}

Write-Host "==> fly deploy..." -ForegroundColor Cyan
$argBase = "VITE_API_BASE_URL="
$argSecret = "VITE_API_SECRET_KEY=" + $vars["API_SECRET_KEY"]
$argAmap = "VITE_AMAP_KEY=" + $amapJs
$argSecCode = "VITE_AMAP_SECURITY_CODE=" + $amapSec

flyctl deploy -a $AppName --build-arg $argBase --build-arg $argSecret --build-arg $argAmap --build-arg $argSecCode --ha=false
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done: https://ai-travel-helper-kitty.fly.dev" -ForegroundColor Green
flyctl apps open -a $AppName
