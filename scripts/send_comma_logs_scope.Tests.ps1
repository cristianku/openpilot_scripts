#requires -Version 5.1
# [retry scope] - START
# Eseguire con -File: le funzioni devono restare nello scope dello script, non globali.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $PSScriptRoot 'send_comma_logs.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$definitions = foreach ($name in @('Invoke-FileTransferWithRetry', 'Get-RemoteFileSizeCommand')) {
  $node = $ast.Find({
      param($n)
      $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name
    }, $true)
  $node.Extent.Text
}
$assignments = @($ast.FindAll({
    param($n)
    $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
      $n.Left.Extent.Text -in @('$downloadAction', '$refreshSizeAction')
  }, $true))
if ($assignments.Count -ne 2) { throw 'Callback attesi non trovati' }
# Un file fisico conserva lo scope reale di -File; ScriptBlock.Create mascherava il difetto.
$fixture = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# FUNCTIONS
function Assert-Equal($Expected, $Actual) {
  if ($Expected -ne $Actual) { throw "Expected '$Expected', got '$Actual'" }
}
function Receive-RemoteFile {
  param($SshPath, $RemoteTarget, $RemoteFilePath, $ExpectedBytes, $LocalPath, $Activity)
  Assert-Equal 'ssh-test' $SshPath
  Assert-Equal 'comma@test' $RemoteTarget
  Assert-Equal "/realdata/route--$script:segment/rlog.zst" $RemoteFilePath
  Assert-Equal "local-$script:segment.part" $LocalPath
  $script:transfers++
  if ($script:transfers -eq 1) { throw 'Interruzione SSH simulata' }
  Assert-Equal 48 $ExpectedBytes
  return $ExpectedBytes
}
function Invoke-SshTextCommand {
  param($SshPath, $RemoteTarget, $RemoteCommand)
  Assert-Equal 'ssh-test' $SshPath
  Assert-Equal 'comma@test' $RemoteTarget
  if (-not $RemoteCommand.EndsWith("| xargs -0 stat -c '%s' --")) { throw 'Comando stat mancante' }
  $script:refreshes++
  if ($script:refreshes -eq 1) { throw 'Interruzione stat simulata' }
  return '48'
}
$sshCommand = [pscustomobject]@{ Source = 'ssh-test' }
$remoteTarget = 'comma@test'
$remoteFiles = @(1, 2)
foreach ($script:segment in @(199, 200)) {
  $script:transfers = 0
  $script:refreshes = 0
  $fileIndex = $script:segment
  $relativePath = "route--$script:segment/rlog.zst"
  $remoteFilePath = "/realdata/$relativePath"
  $localPath = "local-$script:segment.part"
  # CALLBACKS
  $result = Invoke-FileTransferWithRetry -InitialExpectedBytes 64 `
    -TransferAction $downloadAction -RefreshExpectedBytes $refreshSizeAction -RetryDelayMilliseconds 0
  Assert-Equal 48 $result
  Assert-Equal 2 $script:transfers
  Assert-Equal 2 $script:refreshes
}
Write-Host 'PASS: callback download e stat nello scope dello script, retry e due log consecutivi'
'@
$fixture = $fixture.Replace('# FUNCTIONS', ($definitions -join "`n"))
$fixture = $fixture.Replace('# CALLBACKS', (($assignments | ForEach-Object { $_.Extent.Text }) -join "`n"))
$fixturePath = Join-Path ([IO.Path]::GetTempPath()) ("comma-scope-{0}.ps1" -f [Guid]::NewGuid().ToString('N'))
try {
  [IO.File]::WriteAllText($fixturePath, $fixture)
  & $fixturePath
}
finally { Remove-Item -LiteralPath $fixturePath -Force }
# [retry scope] - END
