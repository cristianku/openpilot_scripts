#requires -Version 5.1

# [file listing] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot 'send_comma_logs.ps1'
$tokens = $null
$parseErrors = $null
$scriptAst = [System.Management.Automation.Language.Parser]::ParseFile(
  $scriptPath,
  [ref]$tokens,
  [ref]$parseErrors
)

if ($parseErrors.Count -ne 0) {
  throw "Lo script principale non e sintatticamente valido: $($parseErrors[0].Message)"
}

@(
  'ConvertFrom-RemoteFileListing',
  'Test-NnlcTrainingLogPath'
) | ForEach-Object {
  $functionName = $_
  $functionAst = $scriptAst.Find({
      param($node)
      $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $functionName
    }, $true)

  if ($null -eq $functionAst) {
    throw "Funzione $functionName non trovata."
  }

  Set-Item -Path "Function:\global:$functionName" -Value $functionAst.Body.GetScriptBlock()
}

$listingText = "12`tsegment/rlog.zst`0`r`n"
$remoteFiles = @(ConvertFrom-RemoteFileListing -ListingText $listingText)

if ($remoteFiles.Count -ne 1) {
  throw "Atteso un file dal listing con CRLF finale, ottenuti $($remoteFiles.Count)."
}
if ($remoteFiles[0].Size -ne 12 -or $remoteFiles[0].RelativePath -ne 'segment/rlog.zst') {
  throw 'Il record valido e stato alterato durante il parsing.'
}

$malformedRejected = $false
try {
  ConvertFrom-RemoteFileListing -ListingText "record-malformato`0" | Out-Null
}
catch {
  $malformedRejected = $true
}

if (-not $malformedRejected) {
  throw 'Un record non vuoto e malformato deve continuare a essere rifiutato.'
}

$candidatePaths = @(
  'route-1/rlog.zst',
  'route-2/rlog.bz2',
  'route-3/rlog',
  'route-4/qlog.zst',
  'route-5/fcamera.hevc',
  'route-6/ecamera.hevc',
  'route-7/dcamera.hevc',
  'route-8/qcamera.ts',
  'route-9/RLOG.ZST',
  'route-10/Rlog.bz2'
)
$trainingLogs = @($candidatePaths | Where-Object { Test-NnlcTrainingLogPath -RelativePath $_ })

if ($trainingLogs.Count -ne 3) {
  throw "Attesi soltanto i tre formati rlog NNLC, ottenuti $($trainingLogs.Count) file."
}
if ($trainingLogs[0] -ne 'route-1/rlog.zst' -or
    $trainingLogs[1] -ne 'route-2/rlog.bz2' -or
    $trainingLogs[2] -ne 'route-3/rlog') {
  throw 'Il filtro NNLC ha incluso file camera/qlog o escluso un formato rlog supportato.'
}

Write-Host 'PASS: parsing e filtro listing remoto per NNLC'
# [file listing] - END
