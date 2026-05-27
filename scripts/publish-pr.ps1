$branch = "feature/cdyp7-rvs-dashboard-test"

Write-Host "Creating branch: $branch"
git checkout -b $branch

Write-Host "Adding files..."
git add .

Write-Host "Commit changes..."
git commit -m "CDYP7: RV&S dashboard gateway fix + item detail + packaging"

Write-Host "Running CI checks..."
.\scripts\ci-check.ps1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ CI failed. Fix issues before push."
    exit 1
}

Write-Host "Push to origin..."
git push origin $branch

Write-Host "✅ Branch pushed. Create PR on GitHub/Azure DevOps."