#requires -Version 5.1
# [zip resume] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $PSScriptRoot 'send_comma_logs.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false) |
  ForEach-Object { Set-Item "Function:\global:$($_.Name)" $_.Body.GetScriptBlock() }
function Assert-Equal($Expected, $Actual) {
  if ($Expected -ne $Actual) { throw "Expected '$Expected', got '$Actual'" }
}
$temp = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($temp) | Out-Null
try {
  $raw = Join-Path $temp 'raw'
  $zip = Join-Path $temp 'log.zip'
  [IO.File]::WriteAllText($raw, ('real log data ' * 1000))
  New-LogZip -LocalPath $raw -ZipPath $zip -EntryName 'route--0/rlog'
  $firstHash = (Get-FileHash $zip).Hash
  $archive = [IO.Compression.ZipFile]::OpenRead($zip)
  try {
    Assert-Equal 1 $archive.Entries.Count
    Assert-Equal 'route--0/rlog' $archive.Entries[0].FullName
    $reader = New-Object IO.StreamReader ($archive.Entries[0].Open())
    try { Assert-Equal ([IO.File]::ReadAllText($raw)) $reader.ReadToEnd() }
    finally { $reader.Dispose() }
  } finally { $archive.Dispose() }
  (Get-Item $raw).LastWriteTime = (Get-Date).AddDays(-2)
  New-LogZip -LocalPath $raw -ZipPath $zip -EntryName 'route--0/rlog'
  Assert-Equal $firstHash (Get-FileHash $zip).Hash
  if ((Get-Item $zip).Length -ge (Get-Item $raw).Length) { throw 'ZIP non compresso' }
  $source = Join-Path $temp "source one's"
  [IO.File]::WriteAllText($source, '0123456789')
  $command = Get-RemoteFileReadCommand -RemoteFilePath $source -OffsetBytes 4
  Assert-Equal '456789' (& /bin/sh -c $command)
  $fakeSsh = Join-Path $temp 'fake ssh'
  [IO.File]::WriteAllText($fakeSsh, "#!/bin/sh`nfor cmd do :; done`nexec /bin/sh -c `"`$cmd`"`n")
  & /bin/chmod +x $fakeSsh
  $partial = Join-Path $temp 'partial'
  [IO.File]::WriteAllText($partial, '0123')
  Assert-Equal 10 (Receive-RemoteFile -SshPath $fakeSsh -RemoteTarget test -RemoteFilePath $source `
      -ExpectedBytes 10 -LocalPath $partial -Activity 'Test download ripreso')
  Assert-Equal '0123456789' ([IO.File]::ReadAllText($partial))
  Assert-Equal 10 (Receive-RemoteFile -SshPath '/missing-ssh' -RemoteTarget test -RemoteFilePath $source `
      -ExpectedBytes 10 -LocalPath $partial -Activity 'Test download completo')
  Write-Host 'PASS: ZIP compresso, contenuto e nome preservati, ZIP deterministico, lettura da offset'

  $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
  $listener.Start()
  $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
  $listener.Stop()
  $job = Start-Job -ArgumentList $port -ScriptBlock {
    param($Port)
    $server = New-Object Net.HttpListener
    $server.Prefixes.Add("http://127.0.0.1:$Port/")
    $server.Start()
    'Ready'
    $data = New-Object IO.MemoryStream
    $created = $false
    $failures = 0
    $completeChecks = 0
    $length = 0
    try {
      while ($completeChecks -lt 2) {
        $ctx = $server.GetContext()
        $req = $ctx.Request
        $res = $ctx.Response
        $body = $null
        if ($req.Url.AbsolutePath.StartsWith('/api/resources/')) {
          if (-not $created) { $res.StatusCode = 404 }
          else {
            $body = [Text.Encoding]::UTF8.GetBytes('{"isDir":false,"size":' + $data.Length + '}')
            if ($data.Length -eq $length) { $completeChecks++ }
          }
        }
        elseif ($req.HttpMethod -eq 'HEAD') {
          if (-not $created) { $res.StatusCode = 404 }
          else {
            $res.Headers.Add('Upload-Offset', [string]$data.Length)
            $res.Headers.Add('Upload-Length', [string]$length)
          }
        }
        elseif ($req.HttpMethod -eq 'POST') {
          if ($created) { throw 'Il client ha ricreato un upload riprendibile!' }
          $created = $true
          $length = [long]$req.Headers['Upload-Length']
          $res.StatusCode = 201
        }
        elseif ($req.HttpMethod -eq 'PATCH') {
          $offset = [long]$req.Headers['Upload-Offset']
          if ($offset -ne $data.Length) { throw "Offset errato: $offset != $($data.Length)" }
          if ($req.ContentType -ne 'application/offset+octet-stream') { throw 'Content type errato' }
          $chunk = New-Object IO.MemoryStream
          $req.InputStream.CopyTo($chunk)
          if ($failures -lt 2) {
            $data.Write($chunk.ToArray(), 0, 7)
            $failures++
            $res.StatusCode = 500
          }
          else {
            if ($offset -ne 14) { throw 'Upload ripartito da zero' }
            $chunk.Position = 0
            $chunk.CopyTo($data)
            $res.StatusCode = 204
            $res.Headers.Add('Upload-Offset', [string]$data.Length)
          }
          $chunk.Dispose()
        }
        else { throw "Richiesta inattesa: $($req.HttpMethod)" }
        if ($null -ne $body) { $res.OutputStream.Write($body, 0, $body.Length) }
        $res.Close()
      }
      [Convert]::ToBase64String($data.ToArray())
    } finally { $data.Dispose(); $server.Close() }
  }
  try {
    $deadline = (Get-Date).AddSeconds(10)
    while (-not (Receive-Job $job -Keep | Where-Object { $_ -eq 'Ready' })) {
      if ((Get-Date) -gt $deadline) { throw 'Listener timeout' }
      Start-Sleep -Milliseconds 100
    }
    $zipName = 'route/log.' + $firstHash.ToLowerInvariant() + '.zip'
    $interrupted = $false
    try {
      Send-FileBrowserZip -BaseUrl "http://127.0.0.1:$port" -Token 'test' -LocalPath $zip `
        -RemoteName $zipName -MaxAttempts 1 -RetryDelayMilliseconds 0
    } catch { $interrupted = $true }
    Assert-Equal $true $interrupted
    Send-FileBrowserZip -BaseUrl "http://127.0.0.1:$port" -Token 'test' -LocalPath $zip `
      -RemoteName $zipName -RetryDelayMilliseconds 0
    Send-FileBrowserZip -BaseUrl "http://127.0.0.1:$port" -Token 'test' -LocalPath $zip `
      -RemoteName $zipName -RetryDelayMilliseconds 0
    Wait-Job $job -Timeout 10 | Out-Null
    Assert-Equal 'Completed' $job.State
    $result = @(Receive-Job $job)
    Assert-Equal ([Convert]::ToBase64String([IO.File]::ReadAllBytes($zip))) $result[-1]
    Write-Host 'PASS: nuovo invio da byte 7, retry da byte 14, ZIP identico e completato saltato'
  } finally { Stop-Job $job; Remove-Job $job -Force }

  # Esegue il vero ciclo principale; sostituisce soltanto comma e Drive esterni.
  # Una seconda esecuzione deve saltare tutti i download/upload gia completati.
  $script:sourcePath = $source
  $script:fakeSshPath = $fakeSsh
  $script:driveFiles = @{}
  $script:uploadCalls = 0
  $script:downloadCalls = 0
  $script:failUpload = $true
  function Get-Command { param($Name, $ErrorAction) [pscustomobject]@{ Source = $script:fakeSshPath } }
  function Invoke-RestMethod { param($Method, $Uri, $ContentType, $Body) 'test-token' }
  function Invoke-SshTextCommand {
    param($SshPath, $RemoteTarget, $RemoteCommand)
    if ($RemoteCommand.StartsWith('find ')) { return "10`troute--0/rlog`0" }
    if ($RemoteCommand.Contains('sha256sum')) { return (Get-FileHash $script:sourcePath).Hash + '  rlog' }
    if ($RemoteCommand.Contains('stat ')) { return '10' }
    throw "Comando inatteso: $RemoteCommand"
  }
  function Get-FileBrowserResource {
    param($Client, $BaseUrl, $RemoteName)
    if ($RemoteName -eq '') {
      return [pscustomobject]@{ items = @([pscustomobject]@{ name = 'comma-2026-09-01_10-00-00'; isDir = $true }) }
    }
    return $script:driveFiles[$RemoteName]
  }
  # [fixed path] - START
  function Ensure-FileBrowserDirectory {
    param($BaseUrl, $Token, $RemoteDirectory)
    if ($RemoteDirectory -ne 'realdata' -and -not $RemoteDirectory.StartsWith('realdata/')) {
      throw "Destinazione cartella errata: $RemoteDirectory"
    }
  }
  # [fixed path] - END
  function Receive-RemoteFile {
    param($SshPath, $RemoteTarget, $RemoteFilePath, $ExpectedBytes, $LocalPath, $Activity)
    $script:downloadCalls++
    Copy-Item -LiteralPath $script:sourcePath -Destination $LocalPath
    return 10
  }
  function Send-FileBrowserZip {
    param($BaseUrl, $Token, $LocalPath, $RemoteName)
    # [fixed path] - START
    if (-not $RemoteName.StartsWith('realdata/')) { throw "Destinazione upload errata: $RemoteName" }
    # [fixed path] - END
    $script:uploadCalls++
    $archive = [IO.Compression.ZipFile]::OpenRead($LocalPath)
    try { Assert-Equal 'route--0/rlog' $archive.Entries[0].FullName }
    finally { $archive.Dispose() }
    if ($script:failUpload) { throw 'Interruzione simulata prima dell upload' }
    $script:driveFiles[$RemoteName] = [pscustomobject]@{ isDir = $false; size = (Get-Item $LocalPath).Length }
  }
  $text = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'send_comma_logs.ps1'))
  $main = [scriptblock]::Create($text.Substring($text.IndexOf('$sshCommand = Get-Command')))
  $CommaUser = 'test'
  $COMMA_HOST = 'test'
  $FileBrowser = 'http://local-test'
  $FbUser = 'test'
  $FbPassword = 'test'
  $RemotePath = '/test'
  $CacheDirectory = Join-Path $temp 'cache'
  $message = ''
  try { & $main } catch { $message = $_.Exception.Message }
  Assert-Equal 'Interruzione simulata prima dell upload' $message
  Assert-Equal 1 $script:downloadCalls
  Assert-Equal 1 $script:uploadCalls
  # [fixed path] - START
  # Simula la cache Windows precedente: il vecchio backup non deve cambiare destinazione.
  $cachedZip = @(Get-ChildItem $CacheDirectory -Filter '*.zip' -Recurse)[0]
  $oldBackupState = Join-Path $cachedZip.DirectoryName 'backup.txt'
  [IO.File]::WriteAllText($oldBackupState, 'comma-2026-09-04_22-12-01')
  # [fixed path] - END
  $script:failUpload = $false
  & $main
  Assert-Equal 1 $script:downloadCalls
  Assert-Equal 2 $script:uploadCalls
  & $main
  Assert-Equal 1 $script:downloadCalls
  Assert-Equal 2 $script:uploadCalls
  Assert-Equal 0 @(Get-ChildItem $CacheDirectory -Filter '*.zip' -Recurse).Count
  Assert-Equal 1 @(Get-ChildItem $CacheDirectory -Filter '*.json' -Recurse).Count
  # Un parziale Drive non deve essere scambiato per completato.
  foreach ($key in @($script:driveFiles.Keys)) { $script:driveFiles[$key].size = 7 }
  & $main
  Assert-Equal 2 $script:downloadCalls
  Assert-Equal 3 $script:uploadCalls
  Assert-Equal 1 $script:driveFiles.Count
  # I vecchi log non compressi completi non vengono spediti una seconda volta.
  $script:driveFiles['realdata/route--0/rlog'] = [pscustomobject]@{ isDir = $false; size = 10 }
  & $main
  Assert-Equal 2 $script:downloadCalls
  Assert-Equal 3 $script:uploadCalls
  $script:driveFiles.Remove('realdata/route--0/rlog')
  [IO.File]::WriteAllText($script:sourcePath, 'abcdefghij')
  & $main
  Assert-Equal 3 $script:downloadCalls
  Assert-Equal 4 $script:uploadCalls
  Assert-Equal 2 $script:driveFiles.Count
  Write-Host 'PASS: rilancio dopo errore riusa ZIP; completati saltati; parziali riparati; vecchi log riconosciuti'
} finally { Remove-Item $temp -Recurse -Force }
# [zip resume] - END
