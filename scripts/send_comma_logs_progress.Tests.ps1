#requires -Version 5.1

# [transfer progress] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot 'send_comma_logs.ps1'

function Import-ScriptFunction {
  param(
    [Parameter(Mandatory = $true)]
    [System.Management.Automation.Language.ScriptBlockAst]$ScriptAst,

    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  $functionAst = $ScriptAst.Find({
      param($node)
      $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $Name
    }, $true)

  if ($null -eq $functionAst) {
    throw "Funzione richiesta non trovata: $Name"
  }

  Set-Item -Path "Function:\global:$Name" -Value $functionAst.Body.GetScriptBlock()
}

function Assert-Equal {
  param(
    [Parameter(Mandatory = $true)]$Expected,
    [Parameter(Mandatory = $true)]$Actual,
    [Parameter(Mandatory = $true)][string]$Because
  )

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

  try {
    return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
  }
  finally {
    $listener.Stop()
  }
}

function Start-UploadListenerJob {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port,

    [Parameter(Mandatory = $true)]
    [int]$StatusCode,

    [int]$ResponseDelayMilliseconds = 0
  )

  return Start-Job -ScriptBlock {
    param($ListenerPort, $ResponseStatusCode, $ResponseDelayMilliseconds)

    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://127.0.0.1:$ListenerPort/")
    $listener.Start()
    [pscustomobject]@{ Kind = 'Ready' }

    try {
      $context = $listener.GetContext()
      $receivedBytes = 0L
      $buffer = New-Object byte[] 65536

      while (($read = $context.Request.InputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $receivedBytes += $read
      }

      $result = [pscustomobject]@{
        Kind = 'Result'
        Bytes = $receivedBytes
        Token = $context.Request.Headers['X-Auth']
        Method = $context.Request.HttpMethod
        RawUrl = $context.Request.RawUrl
      }
      if ($ResponseDelayMilliseconds -gt 0) {
        Start-Sleep -Milliseconds $ResponseDelayMilliseconds
      }
      $context.Response.StatusCode = $ResponseStatusCode
      $context.Response.Close()
      $result
    }
    finally {
      $listener.Stop()
      $listener.Close()
    }
  } -ArgumentList $Port, $StatusCode, $ResponseDelayMilliseconds
}

function Wait-UploadListenerReady {
  param(
    [Parameter(Mandatory = $true)]
    [System.Management.Automation.Job]$Job
  )

  $deadline = [DateTime]::UtcNow.AddSeconds(10)
  while ([DateTime]::UtcNow -lt $deadline) {
    $ready = Receive-Job -Job $Job -Keep | Where-Object { $_.Kind -eq 'Ready' }
    if ($null -ne $ready) {
      return
    }
    Start-Sleep -Milliseconds 100
  }

  throw 'Il server HTTP locale non si e avviato entro 10 secondi.'
}

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
  'ConvertTo-FileBrowserResourcePath',
  'ConvertTo-PosixShellLiteral',
  'Get-RemoteFileListingCommand',
  'Get-RemoteFileReadCommand',
  'Get-RequiredFileBrowserDirectories',
  'Get-TransferPercent',
  'Get-TransferStatus',
  'Copy-StreamWithProgress',
  'Initialize-ProgressReadStreamType',
  'New-FileBrowserHttpClient',
  'Ensure-FileBrowserDirectory',
  'Send-FileBrowserFile'
) | ForEach-Object {
  Import-ScriptFunction -ScriptAst $scriptAst -Name $_
}

$listingText = "12`tsegment 1/rlog.zst`034`tsegment-2/qlog.zst`0"
$remoteFiles = @(ConvertFrom-RemoteFileListing -ListingText $listingText)
Assert-Equal -Expected 2 -Actual $remoteFiles.Count `
  -Because 'il listing remoto deve produrre una voce per ogni file'
Assert-Equal -Expected 12 -Actual $remoteFiles[0].Size `
  -Because 'la dimensione del file deve essere letta dal listing'
Assert-Equal -Expected 'segment 1/rlog.zst' -Actual $remoteFiles[0].RelativePath `
  -Because 'gli spazi nel percorso remoto devono essere preservati'
Assert-Equal -Expected 'segment-2/qlog.zst' -Actual $remoteFiles[1].RelativePath `
  -Because 'i percorsi annidati devono essere preservati'

$unsafeListingRejected = $false
try {
  ConvertFrom-RemoteFileListing -ListingText "5`t../escape.zst`0" | Out-Null
}
catch {
  $unsafeListingRejected = $true
}
Assert-Equal -Expected $true -Actual $unsafeListingRejected `
  -Because 'un percorso remoto non deve poter uscire dalla cartella destinazione'

$resourcePath = ConvertTo-FileBrowserResourcePath -RelativePath 'comma-test/realdata/segment 1/rlog.zst'
Assert-Equal -Expected '/comma-test/realdata/segment%201/rlog.zst' -Actual $resourcePath `
  -Because 'FileBrowser deve ricevere segmenti codificati mantenendo la gerarchia'

$listingCommand = Get-RemoteFileListingCommand -RemotePath '/data/media/0/realdata'
Assert-Equal -Expected "find '/data/media/0/realdata' -type f -printf '%s`t%P\0'" -Actual $listingCommand `
  -Because 'il comma deve soltanto elencare i file senza creare o comprimere archivi'
$quotedRemotePath = "/data/media/0/realdata/route one's/rlog.zst"
$encodedRemotePath = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($quotedRemotePath))
$readCommand = Get-RemoteFileReadCommand -RemoteFilePath $quotedRemotePath
Assert-Equal -Expected "printf '%s' '$encodedRemotePath' | base64 -d | xargs -0 cat --" -Actual $readCommand `
  -Because 'ogni file deve essere letto singolarmente senza esporre il nome al quoting di ssh.exe'
Assert-Equal -Expected $false -Actual $readCommand.Contains($quotedRemotePath) `
  -Because 'apostrofi e spazi nel nome non devono entrare letteralmente nella command line SSH'

$requiredDirectories = @(Get-RequiredFileBrowserDirectories `
    -DestinationRoot 'comma-test/realdata' `
    -FileRelativePath 'route one/segment/rlog.zst')
Assert-Equal -Expected 4 -Actual $requiredDirectories.Count `
  -Because 'devono essere create la radice e tutte le cartelle parent'
Assert-Equal -Expected 'comma-test' -Actual $requiredDirectories[0] `
  -Because 'la prima cartella deve essere la radice del trasferimento'
Assert-Equal -Expected 'comma-test/realdata/route one/segment' -Actual $requiredDirectories[3] `
  -Because 'l ultima cartella deve essere il parent del file'

Assert-Equal -Expected 25 -Actual (Get-TransferPercent -TransferredBytes 250 -TotalBytes 1000) `
  -Because 'la percentuale deve riflettere i byte trasferiti'
Assert-Equal -Expected 100 -Actual (Get-TransferPercent -TransferredBytes 1200 -TotalBytes 1000) `
  -Because 'la percentuale non deve superare 100'
Assert-Equal -Expected -1 -Actual (Get-TransferPercent -TransferredBytes 0 -TotalBytes 0) `
  -Because 'una dimensione totale sconosciuta deve produrre avanzamento indeterminato'

$sourceBytes = [byte[]](0..255) * 8192
$inputStream = New-Object System.IO.MemoryStream -ArgumentList (, $sourceBytes)
$outputStream = New-Object System.IO.MemoryStream
$progressEvents = New-Object 'System.Collections.Generic.List[object]'
$progressWriter = {
  param($Activity, $Status, $PercentComplete, $Completed)
  $progressEvents.Add([pscustomobject]@{
      Activity = $Activity
      Status = $Status
      PercentComplete = $PercentComplete
      Completed = $Completed
    })
}.GetNewClosure()

try {
  $copiedBytes = Copy-StreamWithProgress `
    -InputStream $inputStream `
    -OutputStream $outputStream `
    -Activity 'Test copy' `
    -TotalBytes $sourceBytes.Length `
    -ProgressWriter $progressWriter `
    -BufferSize 65536 `
    -ProgressIntervalMilliseconds 0

  Assert-Equal -Expected $sourceBytes.Length -Actual $copiedBytes `
    -Because 'la copia deve riportare tutti i byte trasferiti'
  Assert-Equal -Expected $sourceBytes.Length -Actual $outputStream.Length `
    -Because 'la destinazione deve contenere tutti i byte della sorgente'
  Assert-Equal -Expected $true -Actual $progressEvents[$progressEvents.Count - 1].Completed `
    -Because 'la progress bar deve ricevere un evento finale'
  Assert-Equal -Expected 0 -Actual $progressEvents[0].PercentComplete `
    -Because 'il download di un file elencato deve iniziare da zero'
  Assert-Equal -Expected 100 -Actual $progressEvents[$progressEvents.Count - 2].PercentComplete `
    -Because 'il download completo deve mostrare cento prima di chiudersi'
}
finally {
  $inputStream.Dispose()
  $outputStream.Dispose()
}

$truncatedInput = New-Object System.IO.MemoryStream -ArgumentList (, ([byte[]](1..32)))
$truncatedOutput = New-Object System.IO.MemoryStream
$truncatedProgressEvents = New-Object 'System.Collections.Generic.List[object]'
$truncatedProgressWriter = {
  param($Activity, $Status, $PercentComplete, $Completed)
  $truncatedProgressEvents.Add([pscustomobject]@{
      Activity = $Activity
      Status = $Status
      PercentComplete = $PercentComplete
      Completed = $Completed
    })
}.GetNewClosure()
$truncatedMessage = $null

try {
  try {
    Copy-StreamWithProgress `
      -InputStream $truncatedInput `
      -OutputStream $truncatedOutput `
      -Activity 'Test truncated copy' `
      -TotalBytes 64 `
      -ProgressWriter $truncatedProgressWriter `
      -BufferSize 1024 `
      -ProgressIntervalMilliseconds 0 | Out-Null
  }
  catch {
    $truncatedMessage = $_.Exception.Message
  }

  Assert-Equal -Expected $true -Actual ($truncatedMessage -like '*attesi 64 byte, ricevuti 32*') `
    -Because 'un file cambiato o troncato durante il download deve fermare il trasferimento'
  Assert-Equal -Expected $true -Actual $truncatedProgressEvents[$truncatedProgressEvents.Count - 1].Completed `
    -Because 'la progress bar del download deve chiudersi anche in caso di errore'
  Assert-Equal -Expected $false -Actual ($truncatedProgressEvents.PercentComplete -contains 100) `
    -Because 'un download troncato non deve mostrare un falso 100 percento'
}
finally {
  $truncatedInput.Dispose()
  $truncatedOutput.Dispose()
}

$validatorInput = New-Object System.IO.MemoryStream -ArgumentList (, ([byte[]](1..32)))
$validatorOutput = New-Object System.IO.MemoryStream
$validatorProgressEvents = New-Object 'System.Collections.Generic.List[object]'
$validatorProgressWriter = {
  param($Activity, $Status, $PercentComplete, $Completed)
  $validatorProgressEvents.Add([pscustomobject]@{
      Activity = $Activity
      Status = $Status
      PercentComplete = $PercentComplete
      Completed = $Completed
    })
}.GetNewClosure()
$validatorMessage = $null

try {
  try {
    Copy-StreamWithProgress `
      -InputStream $validatorInput `
      -OutputStream $validatorOutput `
      -Activity 'Test failed completion validation' `
      -TotalBytes 32 `
      -CompletionValidator { throw 'SSH exit failure' } `
      -ProgressWriter $validatorProgressWriter `
      -BufferSize 1024 `
      -ProgressIntervalMilliseconds 0 | Out-Null
  }
  catch {
    $validatorMessage = $_.Exception.Message
  }

  Assert-Equal -Expected 'SSH exit failure' -Actual $validatorMessage `
    -Because 'la validazione SSH deve poter bloccare il completamento del download'
  Assert-Equal -Expected $false -Actual ($validatorProgressEvents.PercentComplete -contains 100) `
    -Because 'un exit code SSH fallito non deve produrre un falso 100 percento'
  Assert-Equal -Expected $true -Actual $validatorProgressEvents[$validatorProgressEvents.Count - 1].Completed `
    -Because 'la barra deve chiudersi anche quando fallisce la validazione SSH'
}
finally {
  $validatorInput.Dispose()
  $validatorOutput.Dispose()
}

$timeoutClient = New-FileBrowserHttpClient
try {
  Assert-Equal -Expected ([System.Threading.Timeout]::InfiniteTimeSpan) -Actual $timeoutClient.Timeout `
    -Because 'un file grande o una connessione lenta non devono essere interrotti dopo cento secondi'
}
finally {
  $timeoutClient.Dispose()
}

Initialize-ProgressReadStreamType
$uploadSource = New-Object System.IO.MemoryStream -ArgumentList (, $sourceBytes)
$trackingStream = New-Object CommaProgressReadStream -ArgumentList (, $uploadSource)
$uploadDestination = New-Object System.IO.MemoryStream

try {
  $trackingStream.CopyTo($uploadDestination)
  Assert-Equal -Expected $sourceBytes.Length -Actual $trackingStream.BytesRead `
    -Because 'lo stream di upload deve contare i byte letti da HttpClient'
  Assert-Equal -Expected $sourceBytes.Length -Actual $uploadDestination.Length `
    -Because 'lo stream di upload non deve alterare i dati'
}
finally {
  $trackingStream.Dispose()
  $uploadDestination.Dispose()
}

if (-not (Get-Command Send-FileBrowserFile).Parameters.ContainsKey('ProgressWriter')) {
  throw 'Send-FileBrowserFile non espone ancora gli eventi di progressione verificabili.'
}

$listenerPort = Get-FreeTcpPort
$listenerUrl = "http://127.0.0.1:$listenerPort"
$uploadPath = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllBytes($uploadPath, $sourceBytes)
$uploadProgressEvents = New-Object 'System.Collections.Generic.List[object]'
$uploadProgressWriter = {
  param($Activity, $Status, $PercentComplete, $Completed)
  $uploadProgressEvents.Add([pscustomobject]@{
      Activity = $Activity
      Status = $Status
      PercentComplete = $PercentComplete
      Completed = $Completed
    })
}.GetNewClosure()
$listenerJob = Start-UploadListenerJob -Port $listenerPort -StatusCode 200

try {
  Wait-UploadListenerReady -Job $listenerJob
  Send-FileBrowserFile `
    -BaseUrl $listenerUrl `
    -Token 'test-token' `
    -LocalPath $uploadPath `
    -RemoteName 'comma-test/realdata/segment 1/rlog.zst' `
    -ProgressWriter $uploadProgressWriter

  if (-not (Wait-Job -Job $listenerJob -Timeout 10)) {
    throw 'Il server HTTP locale non ha completato la ricezione.'
  }

  $uploadResult = Receive-Job -Job $listenerJob | Where-Object { $_.Kind -eq 'Result' }
  Assert-Equal -Expected $sourceBytes.Length -Actual $uploadResult.Bytes `
    -Because 'HttpClient deve inviare tutto il file attraverso lo stream monitorato'
  Assert-Equal -Expected 'test-token' -Actual $uploadResult.Token `
    -Because 'il monitoraggio non deve rimuovere il token FileBrowser'
  Assert-Equal -Expected '/api/resources/comma-test/realdata/segment%201/rlog.zst?override=false' `
    -Actual $uploadResult.RawUrl `
    -Because 'l upload deve conservare le cartelle e codificare ogni nome'
  Assert-Equal -Expected 0 -Actual $uploadProgressEvents[0].PercentComplete `
    -Because 'la progress bar di upload deve iniziare esplicitamente da zero'
  Assert-Equal -Expected 100 -Actual $uploadProgressEvents[$uploadProgressEvents.Count - 2].PercentComplete `
    -Because 'un upload riuscito deve mostrare esplicitamente il 100 percento'
  Assert-Equal -Expected $false -Actual $uploadProgressEvents[$uploadProgressEvents.Count - 2].Completed `
    -Because 'il 100 percento deve essere visibile prima della chiusura'
  Assert-Equal -Expected $true -Actual $uploadProgressEvents[$uploadProgressEvents.Count - 1].Completed `
    -Because 'la progress bar di upload deve essere chiusa dopo il successo'
}
finally {
  Stop-Job -Job $listenerJob -ErrorAction SilentlyContinue
  Remove-Job -Job $listenerJob -Force -ErrorAction SilentlyContinue
}

$directoryPort = Get-FreeTcpPort
$directoryJob = Start-UploadListenerJob -Port $directoryPort -StatusCode 200
try {
  Wait-UploadListenerReady -Job $directoryJob
  Ensure-FileBrowserDirectory `
    -BaseUrl "http://127.0.0.1:$directoryPort" `
    -Token 'test-token' `
    -RemoteDirectory 'comma-test/realdata/segment 1'

  if (-not (Wait-Job -Job $directoryJob -Timeout 10)) {
    throw 'Il server HTTP locale non ha completato la creazione cartella.'
  }

  $directoryResult = Receive-Job -Job $directoryJob | Where-Object { $_.Kind -eq 'Result' }
  Assert-Equal -Expected 0 -Actual $directoryResult.Bytes `
    -Because 'la creazione cartella FileBrowser non deve inviare un file'
  Assert-Equal -Expected '/api/resources/comma-test/realdata/segment%201/?override=false' `
    -Actual $directoryResult.RawUrl `
    -Because 'la directory FileBrowser deve terminare con slash'
}
finally {
  Stop-Job -Job $directoryJob -ErrorAction SilentlyContinue
  Remove-Job -Job $directoryJob -Force -ErrorAction SilentlyContinue
}

$failurePort = Get-FreeTcpPort
$failureJob = Start-UploadListenerJob -Port $failurePort -StatusCode 500 -ResponseDelayMilliseconds 750
$failureProgressEvents = New-Object 'System.Collections.Generic.List[object]'
$failureProgressWriter = {
  param($Activity, $Status, $PercentComplete, $Completed)
  $failureProgressEvents.Add([pscustomobject]@{
      Activity = $Activity
      Status = $Status
      PercentComplete = $PercentComplete
      Completed = $Completed
    })
}.GetNewClosure()
$failureMessage = $null

try {
  Wait-UploadListenerReady -Job $failureJob

  try {
    Send-FileBrowserFile `
      -BaseUrl "http://127.0.0.1:$failurePort" `
      -Token 'test-token' `
      -LocalPath $uploadPath `
      -RemoteName 'failing-file.zst' `
      -ProgressWriter $failureProgressWriter
  }
  catch {
    $failureMessage = $_.Exception.Message
  }

  Assert-Equal -Expected $true -Actual ($failureMessage -like '*Upload FileBrowser fallito (500)*') `
    -Because 'un errore HTTP deve continuare a essere segnalato'
  Assert-Equal -Expected $true -Actual $failureProgressEvents[$failureProgressEvents.Count - 1].Completed `
    -Because 'la progress bar di upload deve chiudersi anche in caso di errore'
  Assert-Equal -Expected $false -Actual ($failureProgressEvents.PercentComplete -contains 100) `
    -Because 'un upload fallito non deve mostrare un falso 100 percento'
}
finally {
  Stop-Job -Job $failureJob -ErrorAction SilentlyContinue
  Remove-Job -Job $failureJob -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $uploadPath -Force -ErrorAction SilentlyContinue
}

Write-Host 'PASS: trasferimento file-per-file e progressione'
# [transfer progress] - END
