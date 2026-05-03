param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$Url,

  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Rest
)

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = "python"
}

& $Python -m clipvault $Url @Rest
