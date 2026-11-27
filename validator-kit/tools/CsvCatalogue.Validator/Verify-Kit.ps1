param([Parameter(Mandatory=$true)][string]$KitRoot)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($KitRoot)
foreach($line in Get-Content -LiteralPath (Join-Path $root 'SHA256SUMS')) {
    $parts=$line -split '  ',2
    if($parts.Count -ne 2 -or $parts[0] -notmatch '^[a-f0-9]{64}$'){throw 'Invalid hash manifest'}
    $path=[IO.Path]::GetFullPath((Join-Path $root $parts[1]))
    if(-not $path.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside kit'}
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $parts[0]){throw "Integrity mismatch: $($parts[1])"}
}
Write-Output 'Kit source integrity verified. This checks transport integrity, not publisher authenticity.'
