#requires -Version 5.1
# Create a review snapshot. Original project files are not changed.
# Real .env files, dependency folders, logs, databases and binary assets are excluded.
# Review hardcoded credentials in source files before sharing the resulting ZIP.
[CmdletBinding()]
param([string]$ProjectPath = '')

$ErrorActionPreference = 'Stop'

# Resolve the default in the script body, not in the parameter declaration.
# Passing -ProjectPath explicitly is supported and takes precedence.
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $ProjectPath = $PSScriptRoot
    } elseif (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
        $ProjectPath = [System.IO.Path]::GetDirectoryName($PSCommandPath)
    } else {
        $ProjectPath = (Get-Location).Path
    }
}
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    throw 'Project path is empty. Run again with -ProjectPath "D:\dentflow".'
}
$resolvedRoot = Resolve-Path -LiteralPath $ProjectPath -ErrorAction Stop
if ($resolvedRoot.Provider.Name -ne 'FileSystem') {
    throw 'ProjectPath must point to a local file-system folder.'
}
$root = $resolvedRoot.ProviderPath
if ([string]::IsNullOrWhiteSpace($root)) {
    throw 'Could not resolve the project folder. Specify -ProjectPath explicitly.'
}
if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    throw ('Project folder was not found: ' + $root)
}
# Keep the volume root intact; use a separate prefix for ZIP entry names.
$rootPrefix = $root.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
Write-Host ('Project folder: ' + $root)
if (-not (Test-Path -LiteralPath (Join-Path $root 'frontend') -PathType Container)) {
    throw 'Run this script from the DentFlow folder containing frontend and backend.'
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'backend') -PathType Container)) {
    throw 'The backend folder was not found. Select the DentFlow project root.'
}

$excludedDirs = @(
    '.git', 'node_modules', '.next', '.venv', 'venv', 'env', '__pycache__',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', '.turbo', '.cache',
    'dist', 'build', 'coverage', 'htmlcov', 'out', 'logs', 'log',
    'backups', 'backup', 'dumps', 'dump', 'data', 'pgdata', 'postgres-data',
    'redis-data', 'uploads', 'secrets', 'credentials', 'certs', '.ssh',
    '.idea', '.vscode', '$RECYCLE.BIN', 'System Volume Information'
)
$allowedExtensions = @(
    '.py', '.pyi', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.mts', '.cts',
    '.css', '.scss', '.sass', '.html', '.htm', '.md', '.mdx', '.rst',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.sh', '.ps1', '.bat', '.cmd', '.example'
)
$allowedNames = @(
    'Dockerfile', 'Makefile', 'Caddyfile', '.dockerignore', '.gitignore',
    '.gitattributes', '.editorconfig', 'requirements.txt', 'requirements-dev.txt',
    'requirements-test.txt', 'requirements-prod.txt'
)

$items = New-Object 'System.Collections.Generic.List[System.IO.FileInfo]'
$directories = New-Object 'System.Collections.Generic.Stack[string]'
$directories.Push($root)
while ($directories.Count -gt 0) {
    $directory = $directories.Pop()
    foreach ($item in (Get-ChildItem -LiteralPath $directory -Force)) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            continue
        }
        if ($item.PSIsContainer) {
            if ($excludedDirs -notcontains $item.Name) { $directories.Push($item.FullName) }
            continue
        }
        if ($item.FullName -eq $PSCommandPath) { continue }
        if ($item.Name -like 'collect-dentflow-sources*.ps1') { continue }
        if ($item.Name -like '.env*' -and $item.Name -notlike '*.example') { continue }
        if ($item.Name -match '(?i)(credentials|service[-_]?account|secrets?)\.(json|ya?ml|ini|conf)$') { continue }
        if ($item.Name -match '(?i)(\.bak\.|\.backup\.|\.old\.|\.log$)') { continue }
        if (($allowedExtensions -contains $item.Extension.ToLowerInvariant()) -or
            ($allowedNames -contains $item.Name) -or ($item.Name -like 'Dockerfile.*')) {
            if ($item.Length -gt 5MB) {
                Write-Warning ('Skipped file larger than 5 MB: ' + $item.Name)
                continue
            }
            $items.Add($item)
        }
    }
}
if ($items.Count -eq 0) { throw 'No source files were found.' }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$name = 'dentflow-sources-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0,6)) + '.zip'
$destination = Join-Path $root $name
$zip = [System.IO.Compression.ZipFile]::Open($destination, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($item in ($items | Sort-Object FullName)) {
        $relative = $item.FullName.Substring($rootPrefix.Length).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $item.FullName, $relative, [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally {
    $zip.Dispose()
}
Write-Host ''
Write-Host ('Created source snapshot: ' + $destination) -ForegroundColor Green
Write-Host ('Source files: ' + $items.Count)
Write-Host 'Your original project files were not changed.'
Write-Host 'Excluded: real .env files, dependencies, logs, databases and binary assets.'
Write-Host 'IMPORTANT: Review source code and example config files for hardcoded secrets before sharing.'
Write-Host 'This is a review snapshot, not a complete backup or a deployment package.'
