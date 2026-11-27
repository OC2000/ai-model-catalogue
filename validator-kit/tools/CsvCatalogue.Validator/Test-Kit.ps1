param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$destination=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $destination){throw 'Use a new synthetic test output directory.'}
New-Item -ItemType Directory -Path $destination | Out-Null
$source=[IO.File]::ReadAllText((Join-Path $root 'src/AIConnect.Catalogue/CsvCatalogueSchema.cs'))
$header=[regex]::Match($source,'public const string Header="([^"]+)";').Groups[1].Value
if(-not $header){throw 'Production header not found'}
$row=[ordered]@{}
foreach($key in $header.Split(',')){$row[$key]=''}
foreach($key in @('entry_id','model_id','variant_id','model_name')){$row[$key]='SYNTHETIC-NEVER-PUBLISH'}
$row.schema_version='6';$row.category='light_text';$row.category_preference_order='1';$row.row_status='research'
$row.backend='CUDA';$row.memory_type='dedicated_gpu';$row.package_completeness='unknown';$row.required_files_json='[]'
$valid=Join-Path $destination 'SYNTHETIC-valid.csv'
$invalid=Join-Path $destination 'SYNTHETIC-rejected.csv'
[IO.File]::WriteAllLines($valid,([pscustomobject]$row | ConvertTo-Csv -NoTypeInformation),[Text.UTF8Encoding]::new($false))
$row.schema_version='999'
[IO.File]::WriteAllLines($invalid,([pscustomobject]$row | ConvertTo-Csv -NoTypeInformation),[Text.UTF8Encoding]::new($false))
$dll=Join-Path $root 'tools/CsvCatalogue.Validator/bin/Release/net10.0/CsvCatalogue.Validator.dll'
& dotnet $dll --csv $valid --kind synthetic --json (Join-Path $destination 'success.json') | Out-Null
if($LASTEXITCODE -ne 0){throw 'Synthetic success case failed'}
& dotnet $dll --csv $invalid --kind synthetic --json (Join-Path $destination 'rejection.json') | Out-Null
if($LASTEXITCODE -ne 1){throw 'Synthetic rejection case failed'}
& dotnet $dll --csv $valid | Out-Null
if($LASTEXITCODE -ne 2){throw 'Invocation case failed'}
Write-Output 'PASS: separate-process success, data rejection and invocation error. Synthetic files must never be published.'
