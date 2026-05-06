$ErrorActionPreference = "Stop"

$AppName = "Overseer"

# User-specific locations outside the install directory
$ConfigDir = Join-Path $env:APPDATA $AppName # evals to AppData/Roaming
$CacheDir  = Join-Path $env:LOCALAPPDATA "$AppName\Cache"
$ModelsDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Overseer"

function Remove-IfExists {
    param([string]$Path)

    if (Test-Path $Path) {
        Remove-Item -Recurse -Force $Path
        Write-Host "Removed: $Path"
    }
}

function Confirm-Action {
    param([string]$Prompt)

    $reply = Read-Host "$Prompt [y/N]"
    return $reply -match '^(y|yes)$'
}

Write-Host "Removing optional user data for $AppName..."
if (Confirm-Action "Delete your config files in $ConfigDir?") {
    Remove-IfExists $ConfigDir
}

if (Confirm-Action "Delete your models in $ModelsDir?") {
    Remove-IfExists $ModelsDir
}
Write-Host "Optional data cleanup complete."
