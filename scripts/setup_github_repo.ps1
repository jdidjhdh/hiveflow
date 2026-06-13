# One-click GitHub repo setup (Discussions, topics, security, release sync)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$credInput = @"
protocol=https
host=github.com

"@
$filled = $credInput | git credential fill
$token = ($filled | Select-String '^password=(.+)$').Matches.Groups[1].Value
if (-not $token) {
    Write-Error "No GitHub token. Set GITHUB_TOKEN or log in via git credential manager."
}
$env:GITHUB_TOKEN = $token
try {
    python (Join-Path $PSScriptRoot "setup_github_repo.py")
} finally {
    Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
}
