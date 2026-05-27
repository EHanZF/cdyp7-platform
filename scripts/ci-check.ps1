Write-Host "Checking merge compatibility with origin/main..."
git fetch origin main

git merge origin/main --no-commit --no-ff

if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge conflict detected! Resolve before pushing." -ForegroundColor Red
    exit 1
}

if (Test-Path ".git/MERGE_HEAD") {
    git merge --abort
} else {
    Write-Host "No merge in progress; branch already compatible with origin/main."
}