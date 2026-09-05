#requires -Version 5.1

# [resume] - START
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

function Import-ScriptFunction {
  param([string]$Name)

  $functionAst = $scriptAst.Find({
      param($node)
      $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq $Name
    }, $true)

  if ($null -eq $functionAst) {
    throw "Assertion fallita: funzione richiesta non trovata: $Name"
  }

  Set-Item -Path "Function:\global:$Name" -Value $functionAst.Body.GetScriptBlock()
}

function Assert-Equal {
  param($Expected, $Actual, [string]$Because)

  if ($Expected -ne $Actual) {
    throw "Assertion fallita: $Because. Atteso '$Expected', ottenuto '$Actual'."
  }
}

function Get-FreeTcpPort {
  $listener = New-Object System.Net.Sockets.TcpListener -ArgumentList (
    [System.Net.IPAddress]::Loopback,
    0
  )
  $listener.Start()
  try { return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
  finally { $listener.Stop() }
}

function Wait-ListenerReady {
  param([System.Management.Automation.Job]$Job)

  $deadline = [DateTime]::UtcNow.AddSeconds(10)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Receive-Job -Job $Job -Keep | Where-Object { $_.Kind -eq 'Ready' }) {
      return
    }
    Start-Sleep -Milliseconds 100
  }
  throw 'Il server HTTP locale non si e avviato.'
}

@(
  'Select-LatestFileBrowserBackupName',
  'Get-FileTransferDecision',
  'Invoke-FileTransferWithRetry',
  'ConvertTo-FileBrowserResourcePath',
  'ConvertTo-PosixShellLiteral',
  'Get-FileBrowserResource',
  'Get-RemoteFileSizeCommand',
  'New-FileBrowserHttpClient',
  'Get-TransferPercent',
  'Get-TransferStatus',
  'Copy-StreamWithProgress'
) | ForEach-Object { Import-ScriptFunction -Name $_ }

$rootItems = @(
  [pscustomobject]@{ name = 'documenti'; isDir = $true },
  [pscustomobject]@{ name = 'comma-2026-09-04_22-04-14'; isDir = $true },
  [pscustomobject]@{ name = 'comma-2026-09-04_22-12-01'; isDir = $true },
  [pscustomobject]@{ name = 'comma-2026-09-05_99-99-99'; isDir = $true },
  [pscustomobject]@{ name = 'comma-2026-09-05_10-00-00'; isDir = $false }
)
$latestBackup = Select-LatestFileBrowserBackupName -Items $rootItems
Assert-Equal -Expected 'comma-2026-09-04_22-12-01' -Actual $latestBackup `
  -Because 'la ripresa deve scegliere la cartella timestamp valida piu recente'

$noBackup = Select-LatestFileBrowserBackupName -Items @(
  [pscustomobject]@{ name = 'documenti'; isDir = $true }
)
Assert-Equal -Expected $null -Actual $noBackup `
  -Because 'senza backup esistente deve essere possibile crearne uno nuovo'

Assert-Equal -Expected 'Upload' -Actual (Get-FileTransferDecision -ExpectedBytes 64) `
  -Because 'un file assente su Drive deve essere caricato'
Assert-Equal -Expected 'Skip' -Actual (Get-FileTransferDecision -ExpectedBytes 64 -ExistingBytes 64) `
  -Because 'un file gia completo su Drive deve essere saltato'

$mismatchMessage = $null
try {
  Get-FileTransferDecision -ExpectedBytes 64 -ExistingBytes 32 | Out-Null
}
catch {
  $mismatchMessage = $_.Exception.Message
}
Assert-Equal -Expected $true -Actual ($mismatchMessage -like '*32*64*') `
  -Because 'un file Drive di dimensione diversa non deve essere scambiato per completo'

$retryState = [pscustomobject]@{ Attempts = 0; Refreshes = 0 }
$transferred = Invoke-FileTransferWithRetry `
  -InitialExpectedBytes 64 `
  -MaxAttempts 3 `
  -RetryDelayMilliseconds 0 `
  -TransferAction {
    param($expectedBytes)
    $retryState.Attempts++
    if ($retryState.Attempts -eq 1) {
      throw 'stream interrotto'
    }
    return $expectedBytes
  } `
  -RefreshExpectedBytes {
    $retryState.Refreshes++
    return 32
  }
Assert-Equal -Expected 2 -Actual $retryState.Attempts `
  -Because 'un trasferimento interrotto deve essere ritentato'
Assert-Equal -Expected 1 -Actual $retryState.Refreshes `
  -Because 'prima del nuovo tentativo la dimensione remota deve essere riletta'
Assert-Equal -Expected 32 -Actual $transferred `
  -Because 'il retry deve usare la dimensione remota aggiornata'

$refreshRetryState = [pscustomobject]@{ Transfers = 0; Refreshes = 0 }
$transferredAfterRefreshFailure = Invoke-FileTransferWithRetry `
  -InitialExpectedBytes 64 `
  -MaxAttempts 3 `
  -RetryDelayMilliseconds 0 `
  -TransferAction {
    param($expectedBytes)
    $refreshRetryState.Transfers++
    if ($refreshRetryState.Transfers -eq 1) {
      throw 'download SSH interrotto'
    }
    return $expectedBytes
  } `
  -RefreshExpectedBytes {
    $refreshRetryState.Refreshes++
    if ($refreshRetryState.Refreshes -eq 1) {
      throw 'stat SSH interrotto'
    }
    return 48
  }
Assert-Equal -Expected 2 -Actual $refreshRetryState.Transfers `
  -Because 'un errore temporaneo durante stat non deve annullare il retry del download'
Assert-Equal -Expected 2 -Actual $refreshRetryState.Refreshes `
  -Because 'anche la rilettura della dimensione deve essere ritentata'
Assert-Equal -Expected 48 -Actual $transferredAfterRefreshFailure `
  -Because 'il download successivo deve usare la dimensione ottenuta dopo il retry di stat'

$inputStream = New-Object System.IO.MemoryStream -ArgumentList (, ([byte[]](1..32)))
$outputStream = New-Object System.IO.MemoryStream
$errorMessage = $null
try {
  try {
    Copy-StreamWithProgress `
      -InputStream $inputStream `
      -OutputStream $outputStream `
      -Activity 'Test errore SSH' `
      -TotalBytes 64 `
      -CompletionValidator { throw 'SSH exit failure' } `
      -ProgressWriter { param($Activity, $Status, $PercentComplete, $Completed) } `
      -BufferSize 1024 `
      -ProgressIntervalMilliseconds 0 | Out-Null
  }
  catch {
    $errorMessage = $_.Exception.Message
  }
}
finally {
  $inputStream.Dispose()
  $outputStream.Dispose()
}
Assert-Equal -Expected 'SSH exit failure' -Actual $errorMessage `
  -Because 'un errore SSH deve essere mostrato prima dell errore secondario di dimensione'

$listenerPort = Get-FreeTcpPort
$listenerJob = Start-Job -ScriptBlock {
  param($Port)
  $listener = New-Object System.Net.HttpListener
  $listener.Prefixes.Add("http://127.0.0.1:$Port/")
  $listener.Start()
  [pscustomobject]@{ Kind = 'Ready' }
  try {
    $foundContext = $listener.GetContext()
    $foundBody = [System.Text.Encoding]::UTF8.GetBytes('{"name":"rlog.zst","size":64,"isDir":false}')
    $foundContext.Response.StatusCode = 200
    $foundContext.Response.ContentType = 'application/json'
    $foundContext.Response.OutputStream.Write($foundBody, 0, $foundBody.Length)
    $foundContext.Response.Close()
    [pscustomobject]@{ Kind = 'Request'; RawUrl = $foundContext.Request.RawUrl }

    $missingContext = $listener.GetContext()
    $missingContext.Response.StatusCode = 404
    $missingContext.Response.Close()
    [pscustomobject]@{ Kind = 'Request'; RawUrl = $missingContext.Request.RawUrl }
  }
  finally {
    $listener.Stop()
    $listener.Close()
  }
} -ArgumentList $listenerPort
$resourceClient = New-Object System.Net.Http.HttpClient
try {
  Wait-ListenerReady -Job $listenerJob
  $foundResource = Get-FileBrowserResource `
    -Client $resourceClient `
    -BaseUrl "http://127.0.0.1:$listenerPort" `
    -RemoteName 'comma-test/realdata/segment 1/rlog.zst'
  $missingResource = Get-FileBrowserResource `
    -Client $resourceClient `
    -BaseUrl "http://127.0.0.1:$listenerPort" `
    -RemoteName 'comma-test/realdata/missing/rlog.zst'

  Assert-Equal -Expected 64 -Actual $foundResource.size `
    -Because 'la verifica Drive deve leggere la dimensione reale del file'
  Assert-Equal -Expected $null -Actual $missingResource `
    -Because 'un 404 Drive deve indicare che il file va caricato'
  Wait-Job -Job $listenerJob -Timeout 10 | Out-Null
  $requests = @(Receive-Job -Job $listenerJob | Where-Object { $_.Kind -eq 'Request' })
  Assert-Equal -Expected '/api/resources/comma-test/realdata/segment%201/rlog.zst' `
    -Actual $requests[0].RawUrl `
    -Because 'il controllo Drive deve codificare correttamente il percorso'
}
finally {
  $resourceClient.Dispose()
  Stop-Job -Job $listenerJob -ErrorAction SilentlyContinue
  Remove-Job -Job $listenerJob -Force -ErrorAction SilentlyContinue
}

$sizeCommand = Get-RemoteFileSizeCommand `
  -RemoteFilePath "/data/media/0/realdata/route one's/rlog.zst"
$encodedSizePath = [Convert]::ToBase64String(
  [System.Text.Encoding]::UTF8.GetBytes("/data/media/0/realdata/route one's/rlog.zst")
)
Assert-Equal -Expected "printf '%s' '$encodedSizePath' | base64 -d | xargs -0 stat -c '%s' --" `
  -Actual $sizeCommand `
  -Because 'il refresh della dimensione deve attraversare ssh.exe senza quoting fragile'
Assert-Equal -Expected $false -Actual $sizeCommand.Contains("route one's") `
  -Because 'il percorso con apostrofo non deve entrare letteralmente nella command line SSH'

$metadataClient = New-FileBrowserHttpClient -Timeout ([TimeSpan]::FromSeconds(30))
try {
  Assert-Equal -Expected ([TimeSpan]::FromSeconds(30)) -Actual $metadataClient.Timeout `
    -Because 'i controlli metadata Drive non devono poter restare bloccati per sempre'
}
finally {
  $metadataClient.Dispose()
}

Write-Host 'PASS: ripresa FileBrowser e retry trasferimento'
# [resume] - END
