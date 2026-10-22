<#
.SYNOPSIS
  Push or pull pl_refresh without keeping environment-specific values in fabric/ (docs/setup.md section 8).

.DESCRIPTION
  fabric/pl_refresh.DataPipeline/pipeline-content.json keeps two placeholders instead of real values:
    __U2_SQL_SERVER__        wh_gold SQL endpoint host  (from $env:U2_SQL_SERVER, see docs/setup.md section 2)
    __U2_PBI_CONNECTION_ID__ Power BI connection id used by the "Refresh semantic model" activity
                             (from $env:U2_PBI_CONNECTION_ID)
  -Action import : copies the folder to a temp dir, fills the placeholders, runs fab import, removes the temp copy.
  -Action export : runs fab export to a temp dir, puts the placeholders back, copies the result into fabric/.

.EXAMPLE
  $env:U2_SQL_SERVER = [Environment]::GetEnvironmentVariable('U2_SQL_SERVER','User')
  $env:U2_PBI_CONNECTION_ID = '<connection id>'
  ./scripts/pipeline.ps1 -Action import
#>
param(
    [Parameter(Mandatory)] [ValidateSet('import', 'export')] [string] $Action,
    [string] $Workspace = 'U2 Live Analytics.Workspace',
    [string] $Item = 'pl_refresh.DataPipeline'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$local = Join-Path $root "fabric/$Item"
$values = [ordered]@{
    '__U2_SQL_SERVER__'        = $env:U2_SQL_SERVER
    '__U2_PBI_CONNECTION_ID__' = $env:U2_PBI_CONNECTION_ID
}
foreach ($k in $values.Keys) {
    if (-not $values[$k]) { throw "Set the environment variable for $k first (see the script header)." }
}
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("u2_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)
try {
    if ($Action -eq 'import') {
        Copy-Item $local -Destination $tmp -Recurse
        $file = Join-Path $tmp "$Item/pipeline-content.json"
        $text = [IO.File]::ReadAllText($file)
        foreach ($k in $values.Keys) { $text = $text.Replace($k, $values[$k]) }
        [IO.File]::WriteAllText($file, $text, $utf8)
        fab import "/$Workspace/$Item" -i (Join-Path $tmp $Item) -f
    }
    else {
        fab export "/$Workspace/$Item" -o $tmp -f
        $file = Join-Path $tmp "$Item/pipeline-content.json"
        $text = [IO.File]::ReadAllText($file).Replace("`r", "")
        foreach ($k in $values.Keys) { $text = $text.Replace($values[$k], $k) }
        [IO.File]::WriteAllText($file, $text, $utf8)
        Copy-Item (Join-Path $tmp "$Item/*") -Destination $local -Recurse -Force
        Copy-Item (Join-Path $tmp "$Item/.platform") -Destination $local -Force
    }
}
finally {
    Remove-Item $tmp -Recurse -Force   # temp copy created by this script only
}
