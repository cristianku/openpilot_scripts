#requires -Version 5.1

# [comma host] - START
param(
  [Parameter(Mandatory = $true)]
  [ValidateNotNullOrEmpty()]
  [string]$COMMA_HOST
)
# [comma host] - END

# [comma logs] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ===== CONFIG =====
$CommaUser = 'comma'

$FileBrowser = 'https://drive.14bodhi.com'
$FbUser = 'joseph'
$FbPassword = 'mokby5-tIvmuk-buknez'

$RemotePath = '/data/media/0/realdata'

# [file listing] - START
function ConvertFrom-RemoteFileListing {
  param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$ListingText
  )

  foreach ($record in $ListingText.Split([char]0, [System.StringSplitOptions]::RemoveEmptyEntries)) {
    if ([string]::IsNullOrWhiteSpace($record)) {
      continue
    }

    $separator = $record.IndexOf("`t")
    if ($separator -le 0 -or $separator -eq ($record.Length - 1)) {
      throw "Record non valido nel listing remoto: $record"
    }

    [long]$size = 0
    if (-not [long]::TryParse($record.Substring(0, $separator), [ref]$size) -or $size -lt 0) {
      throw "Dimensione non valida nel listing remoto: $record"
    }

    $relativePath = $record.Substring($separator + 1).Replace('\', '/')
    $segments = @($relativePath.Split('/'))
    if ($relativePath.StartsWith('/') -or
        $segments.Count -eq 0 -or
        $segments.Where({ [string]::IsNullOrEmpty($_) -or $_ -eq '.' -or $_ -eq '..' }).Count -ne 0) {
      throw "Percorso non sicuro nel listing remoto: $relativePath"
    }

    [pscustomobject]@{
      Size = $size
      RelativePath = $relativePath
    }
  }
}

# [nnlc logs] - START
function Test-NnlcTrainingLogPath {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$RelativePath
  )

  $fileName = $RelativePath.Substring($RelativePath.LastIndexOf('/') + 1)
  return $fileName -cin @('rlog.zst', 'rlog.bz2', 'rlog')
}
# [nnlc logs] - END

function ConvertTo-FileBrowserResourcePath {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$RelativePath
  )

  $normalizedPath = $RelativePath.Replace('\', '/')
  $segments = @($normalizedPath.Split('/'))
  if ($normalizedPath.StartsWith('/') -or
      $segments.Count -eq 0 -or
      $segments.Where({ [string]::IsNullOrEmpty($_) -or $_ -eq '.' -or $_ -eq '..' }).Count -ne 0) {
    throw "Percorso FileBrowser non sicuro: $RelativePath"
  }

  $encodedSegments = @($segments | ForEach-Object { [System.Uri]::EscapeDataString($_) })
  return '/' + [string]::Join('/', $encodedSegments)
}

function Get-RequiredFileBrowserDirectories {
  param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$DestinationRoot,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$FileRelativePath
  )

  $rootSegments = @($DestinationRoot.Replace('\', '/').Split('/'))
  $fileSegments = @($FileRelativePath.Replace('\', '/').Split('/'))
  if ($fileSegments.Count -lt 1) {
    throw "Percorso file non valido: $FileRelativePath"
  }

  $allDirectorySegments = @($rootSegments + $fileSegments[0..([Math]::Max(0, $fileSegments.Count - 2))])
  if ($fileSegments.Count -eq 1) {
    $allDirectorySegments = $rootSegments
  }

  for ($index = 0; $index -lt $allDirectorySegments.Count; $index++) {
    [string]::Join('/', $allDirectorySegments[0..$index])
  }
}

function ConvertTo-PosixShellLiteral {
  param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$Value
  )

  if ($Value.IndexOf([char]0) -ge 0) {
    throw 'Un comando remoto non puo contenere caratteri NUL.'
  }

  $singleQuoteEscape = "'" + '"' + "'" + '"' + "'"
  return "'" + $Value.Replace("'", $singleQuoteEscape) + "'"
}

function Get-RemoteFileListingCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RemotePath
  )

  $remotePathLiteral = ConvertTo-PosixShellLiteral -Value $RemotePath
  return "find $remotePathLiteral -type f -printf '%s`t%P\0'"
}

function Get-RemoteFileReadCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteFilePath
  )

  $encodedPath = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($RemoteFilePath))
  return "printf '%s' '$encodedPath' | base64 -d | xargs -0 cat --"
}

function Invoke-SshTextCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$SshPath,

    [Parameter(Mandatory = $true)]
    [string]$RemoteTarget,

    [Parameter(Mandatory = $true)]
    [string]$RemoteCommand
  )

  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $SshPath
  $startInfo.Arguments = "-o BatchMode=yes -o ConnectTimeout=10 `"$RemoteTarget`" `"$RemoteCommand`""
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true
  $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $startInfo

  try {
    if (-not $process.Start()) {
      throw 'Impossibile avviare ssh per il comando remoto.'
    }

    $outputTask = $process.StandardOutput.ReadToEndAsync()
    $errorTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $output = $outputTask.GetAwaiter().GetResult()
    $errorOutput = $errorTask.GetAwaiter().GetResult().Trim()

    if ($process.ExitCode -ne 0) {
      throw "Comando SSH fallito (codice $($process.ExitCode)). $errorOutput"
    }

    return $output
  }
  finally {
    $process.Dispose()
  }
}
# [file listing] - END

# [transfer progress] - START
function Get-TransferPercent {
  param(
    [Parameter(Mandatory = $true)]
    [long]$TransferredBytes,

    [Parameter(Mandatory = $true)]
    [long]$TotalBytes
  )

  if ($TotalBytes -le 0) {
    return -1
  }

  return [int][Math]::Min(100, [Math]::Max(0, [Math]::Floor(($TransferredBytes * 100.0) / $TotalBytes)))
}

function Get-TransferStatus {
  param(
    [Parameter(Mandatory = $true)]
    [long]$TransferredBytes,

    [Parameter(Mandatory = $true)]
    [TimeSpan]$Elapsed,

    [long]$TotalBytes = 0
  )

  $transferredMb = $TransferredBytes / 1MB
  $elapsedSeconds = [Math]::Max($Elapsed.TotalSeconds, 0.001)
  $speedMb = $transferredMb / $elapsedSeconds
  $elapsedText = $Elapsed.ToString('hh\:mm\:ss')

  if ($TotalBytes -gt 0) {
    return ('{0:N1} / {1:N1} MB | {2:N1} MB/s | {3}' -f `
        $transferredMb, ($TotalBytes / 1MB), $speedMb, $elapsedText)
  }

  return ('{0:N1} MB | {1:N1} MB/s | {2}' -f $transferredMb, $speedMb, $elapsedText)
}

function Copy-StreamWithProgress {
  param(
    [Parameter(Mandatory = $true)]
    [System.IO.Stream]$InputStream,

    [Parameter(Mandatory = $true)]
    [System.IO.Stream]$OutputStream,

    [Parameter(Mandatory = $true)]
    [string]$Activity,

    [long]$TotalBytes = 0,

    [scriptblock]$CompletionValidator,

    [scriptblock]$ProgressWriter,

    [ValidateRange(1024, 16777216)]
    [int]$BufferSize = 1048576,

    [ValidateRange(0, 60000)]
    [int]$ProgressIntervalMilliseconds = 250
  )

  if ($null -eq $ProgressWriter) {
    $ProgressWriter = {
      param($ProgressActivity, $Status, $PercentComplete, $Completed)

      if ($Completed) {
        Write-Progress -Activity $ProgressActivity -Completed
      }
      elseif ($PercentComplete -ge 0) {
        Write-Progress -Activity $ProgressActivity -Status $Status -PercentComplete $PercentComplete
      }
      else {
        Write-Progress -Activity $ProgressActivity -Status $Status
      }
    }
  }

  $buffer = New-Object byte[] $BufferSize
  $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
  $lastProgress = [TimeSpan]::FromMilliseconds(-$ProgressIntervalMilliseconds)
  [long]$transferredBytes = 0
  $lastProgressPercent = Get-TransferPercent -TransferredBytes 0 -TotalBytes $TotalBytes

  $status = Get-TransferStatus `
    -TransferredBytes 0 `
    -TotalBytes $TotalBytes `
    -Elapsed $stopwatch.Elapsed
  & $ProgressWriter $Activity $status $lastProgressPercent $false | Out-Null

  try {
    while ($true) {
      $readTask = $InputStream.ReadAsync($buffer, 0, $buffer.Length)

      while (-not $readTask.IsCompleted) {
        $status = Get-TransferStatus `
          -TransferredBytes $transferredBytes `
          -TotalBytes $TotalBytes `
          -Elapsed $stopwatch.Elapsed
        & $ProgressWriter $Activity $status $lastProgressPercent $false | Out-Null
        Start-Sleep -Milliseconds 250
      }

      $bytesRead = $readTask.GetAwaiter().GetResult()
      if ($bytesRead -eq 0) {
        break
      }

      $OutputStream.Write($buffer, 0, $bytesRead)
      $transferredBytes += $bytesRead

      if ($ProgressIntervalMilliseconds -eq 0 -or
          ($stopwatch.Elapsed - $lastProgress).TotalMilliseconds -ge $ProgressIntervalMilliseconds) {
        $status = Get-TransferStatus `
          -TransferredBytes $transferredBytes `
          -TotalBytes $TotalBytes `
          -Elapsed $stopwatch.Elapsed
        $lastProgressPercent = Get-TransferPercent `
          -TransferredBytes $transferredBytes `
          -TotalBytes $TotalBytes
        if ($lastProgressPercent -ge 0) {
          $lastProgressPercent = [Math]::Min(99, $lastProgressPercent)
        }
        & $ProgressWriter $Activity $status $lastProgressPercent $false | Out-Null
        $lastProgress = $stopwatch.Elapsed
      }
    }

    if ($TotalBytes -gt 0 -and $transferredBytes -ne $TotalBytes) {
      throw "Dimensione trasferita non valida: attesi $TotalBytes byte, ricevuti $transferredBytes."
    }

    if ($null -ne $CompletionValidator) {
      & $CompletionValidator | Out-Null
    }

    if ($TotalBytes -gt 0) {
      $lastProgressPercent = 100
      $status = Get-TransferStatus `
        -TransferredBytes $transferredBytes `
        -TotalBytes $TotalBytes `
        -Elapsed $stopwatch.Elapsed
      & $ProgressWriter $Activity $status $lastProgressPercent $false | Out-Null
    }

    return $transferredBytes
  }
  finally {
    $status = Get-TransferStatus `
      -TransferredBytes $transferredBytes `
      -TotalBytes $TotalBytes `
      -Elapsed $stopwatch.Elapsed
    & $ProgressWriter $Activity $status $lastProgressPercent $true | Out-Null
    $stopwatch.Stop()
  }
}

function Initialize-ProgressReadStreamType {
  if ($null -ne ('CommaProgressReadStream' -as [type])) {
    return
  }

  Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

public sealed class CommaProgressReadStream : Stream
{
    private readonly Stream inner;
    private long bytesRead;

    public CommaProgressReadStream(Stream inner)
    {
        if (inner == null) throw new ArgumentNullException("inner");
        this.inner = inner;
    }

    public long BytesRead { get { return Interlocked.Read(ref bytesRead); } }
    public override bool CanRead { get { return inner.CanRead; } }
    public override bool CanSeek { get { return inner.CanSeek; } }
    public override bool CanWrite { get { return false; } }
    public override long Length { get { return inner.Length; } }
    public override long Position {
        get { return inner.Position; }
        set { inner.Position = value; }
    }

    public override int Read(byte[] buffer, int offset, int count)
    {
        int read = inner.Read(buffer, offset, count);
        Interlocked.Add(ref bytesRead, read);
        return read;
    }

    public override async Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken)
    {
        int read = await inner.ReadAsync(buffer, offset, count, cancellationToken).ConfigureAwait(false);
        Interlocked.Add(ref bytesRead, read);
        return read;
    }

    public override void Flush() { inner.Flush(); }
    public override long Seek(long offset, SeekOrigin origin) { return inner.Seek(offset, origin); }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }

    protected override void Dispose(bool disposing)
    {
        if (disposing) inner.Dispose();
        base.Dispose(disposing);
    }
}
'@
}
# [transfer progress] - END

# [file transfer] - START
function Receive-RemoteFile {
  param(
    [Parameter(Mandatory = $true)]
    [string]$SshPath,

    [Parameter(Mandatory = $true)]
    [string]$RemoteTarget,

    [Parameter(Mandatory = $true)]
    [string]$RemoteFilePath,

    [Parameter(Mandatory = $true)]
    [long]$ExpectedBytes,

    [Parameter(Mandatory = $true)]
    [string]$LocalPath,

    [Parameter(Mandatory = $true)]
    [string]$Activity
  )

  $remoteCommand = Get-RemoteFileReadCommand -RemoteFilePath $RemoteFilePath
  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $SshPath
  $startInfo.Arguments = "-o BatchMode=yes -o ConnectTimeout=10 `"$RemoteTarget`" `"$remoteCommand`""
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $startInfo
  $localStream = $null
  $processStarted = $false

  try {
    if (-not $process.Start()) {
      throw 'Impossibile avviare ssh per trasferire il file.'
    }
    $processStarted = $true

    $errorTask = $process.StandardError.ReadToEndAsync()
    $completionValidator = {
      $process.WaitForExit()
      $errorOutput = $errorTask.GetAwaiter().GetResult().Trim()
      if ($process.ExitCode -ne 0) {
        throw "Download SSH fallito (codice $($process.ExitCode)). $errorOutput"
      }
    }.GetNewClosure()
    $localStream = [System.IO.File]::Create($LocalPath)
    $receivedBytes = Copy-StreamWithProgress `
      -InputStream $process.StandardOutput.BaseStream `
      -OutputStream $localStream `
      -Activity $Activity `
      -TotalBytes $ExpectedBytes `
      -CompletionValidator $completionValidator
    $localStream.Dispose()
    $localStream = $null

    return $receivedBytes
  }
  finally {
    if ($null -ne $localStream) { $localStream.Dispose() }
    if ($processStarted -and -not $process.HasExited) { $process.Kill() }
    $process.Dispose()
  }
}

function New-FileBrowserHttpClient {
  Add-Type -AssemblyName System.Net.Http
  $client = New-Object System.Net.Http.HttpClient
  $client.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
  return $client
}

function Ensure-FileBrowserDirectory {
  param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [Parameter(Mandatory = $true)]
    [string]$RemoteDirectory
  )

  $client = New-FileBrowserHttpClient
  $content = New-Object System.Net.Http.ByteArrayContent -ArgumentList (, [byte[]]@())
  $response = $null

  try {
    $client.DefaultRequestHeaders.Add('X-Auth', $Token)
    $resourcePath = (ConvertTo-FileBrowserResourcePath -RelativePath $RemoteDirectory) + '/'
    $directoryUrl = '{0}/api/resources{1}?override=false' -f $BaseUrl.TrimEnd('/'), $resourcePath
    $response = $client.PostAsync($directoryUrl, $content).GetAwaiter().GetResult()

    if (-not $response.IsSuccessStatusCode -and [int]$response.StatusCode -ne 409) {
      $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
      throw "Creazione cartella FileBrowser fallita ($([int]$response.StatusCode)): $responseBody"
    }
  }
  finally {
    if ($null -ne $response) { $response.Dispose() }
    $content.Dispose()
    $client.Dispose()
  }
}
# [file transfer] - END

function Send-FileBrowserFile {
  param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [Parameter(Mandatory = $true)]
    [string]$LocalPath,

    [Parameter(Mandatory = $true)]
    [string]$RemoteName,

    [scriptblock]$ProgressWriter
  )

  # [upload progress] - START
  Initialize-ProgressReadStreamType

  if ($null -eq $ProgressWriter) {
    $ProgressWriter = {
      param($ProgressActivity, $Status, $PercentComplete, $Completed)

      if ($Completed) {
        Write-Progress -Activity $ProgressActivity -Completed
      }
      else {
        Write-Progress -Activity $ProgressActivity -Status $Status -PercentComplete $PercentComplete
      }
    }
  }

  $client = New-FileBrowserHttpClient
  $stream = $null
  $trackingStream = $null
  $content = $null
  $response = $null
  $stopwatch = $null
  $progressActivity = "Upload $RemoteName"
  $lastProgressStatus = 'Avvio upload...'
  $lastProgressPercent = 0

  try {
    $client.DefaultRequestHeaders.Add('X-Auth', $Token)
    $stream = [System.IO.File]::OpenRead($LocalPath)
    $trackingStream = New-Object CommaProgressReadStream -ArgumentList (, $stream)
    $content = New-Object System.Net.Http.StreamContent -ArgumentList (, $trackingStream)
    $content.Headers.ContentLength = $stream.Length
    $resourcePath = ConvertTo-FileBrowserResourcePath -RelativePath $RemoteName
    $uploadUrl = '{0}/api/resources{1}?override=false' -f $BaseUrl.TrimEnd('/'), $resourcePath
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $lastProgressStatus = Get-TransferStatus `
      -TransferredBytes 0 `
      -TotalBytes $stream.Length `
      -Elapsed $stopwatch.Elapsed
    & $ProgressWriter $progressActivity $lastProgressStatus 0 $false | Out-Null

    $uploadTask = $client.PostAsync($uploadUrl, $content)

    while (-not $uploadTask.IsCompleted) {
      $lastProgressStatus = Get-TransferStatus `
        -TransferredBytes $trackingStream.BytesRead `
        -TotalBytes $stream.Length `
        -Elapsed $stopwatch.Elapsed
      $lastProgressPercent = [Math]::Min(99, (Get-TransferPercent `
          -TransferredBytes $trackingStream.BytesRead `
          -TotalBytes $stream.Length))
      & $ProgressWriter $progressActivity $lastProgressStatus $lastProgressPercent $false | Out-Null
      Start-Sleep -Milliseconds 250
    }

    $response = $uploadTask.GetAwaiter().GetResult()

    if (-not $response.IsSuccessStatusCode) {
      $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
      throw "Upload FileBrowser fallito ($([int]$response.StatusCode)): $responseBody"
    }

    $lastProgressStatus = Get-TransferStatus `
      -TransferredBytes $stream.Length `
      -TotalBytes $stream.Length `
      -Elapsed $stopwatch.Elapsed
    $lastProgressPercent = 100
    & $ProgressWriter $progressActivity $lastProgressStatus $lastProgressPercent $false | Out-Null
  }
  finally {
    try {
      if ($null -ne $stopwatch) { $stopwatch.Stop() }
      if ($null -ne $response) { $response.Dispose() }
      if ($null -ne $content) { $content.Dispose() }
      if ($null -ne $trackingStream) { $trackingStream.Dispose() }
      if ($null -ne $stream) { $stream.Dispose() }
      $client.Dispose()
    }
    finally {
      & $ProgressWriter $progressActivity $lastProgressStatus $lastProgressPercent $true | Out-Null
    }
  }
  # [upload progress] - END
}

$sshCommand = Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
if ($null -eq $sshCommand) {
  $sshCommand = Get-Command 'ssh' -ErrorAction SilentlyContinue
}
if ($null -eq $sshCommand) {
  throw 'Comando ssh non trovato. Installa o abilita il client OpenSSH.'
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
# [comma host] - START
$remoteTarget = "$CommaUser@$COMMA_HOST"
# [comma host] - END
$destinationRoot = "comma-$timestamp/realdata"

Write-Host '=== Test connessione al comma ==='
& $sshCommand.Source -o BatchMode=yes -o ConnectTimeout=10 $remoteTarget "echo 'Comma connected'"
if ($LASTEXITCODE -ne 0) {
  throw "Connessione SSH al comma fallita (codice $LASTEXITCODE)."
}

# [file-by-file] - START
Write-Host '=== Listing file sul comma ==='
$listingCommand = Get-RemoteFileListingCommand -RemotePath $RemotePath
$listingText = Invoke-SshTextCommand `
  -SshPath $sshCommand.Source `
  -RemoteTarget $remoteTarget `
  -RemoteCommand $listingCommand
# [nnlc logs] - START
$remoteFiles = @(ConvertFrom-RemoteFileListing -ListingText $listingText |
    Where-Object { Test-NnlcTrainingLogPath -RelativePath $_.RelativePath } |
    Sort-Object RelativePath)

if ($remoteFiles.Count -eq 0) {
  throw "Nessun rlog supportato per NNLC trovato in $RemotePath."
}
# [nnlc logs] - END

$totalBytes = [long](($remoteFiles | Measure-Object -Property Size -Sum).Sum)
Write-Host ("Trovati {0} file ({1:N1} MB)." -f $remoteFiles.Count, ($totalBytes / 1MB))

Write-Host '=== Login FileBrowser ==='
[System.Net.ServicePointManager]::SecurityProtocol = `
  [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12

$loginBody = @{
  username = $FbUser
  password = $FbPassword
} | ConvertTo-Json -Compress

$token = [string](Invoke-RestMethod `
  -Method Post `
  -Uri "$($FileBrowser.TrimEnd('/'))/api/login" `
  -ContentType 'application/json' `
  -Body $loginBody)

if ([string]::IsNullOrWhiteSpace($token)) {
  throw 'Impossibile ottenere il token FileBrowser.'
}

$createdDirectories = New-Object 'System.Collections.Generic.HashSet[string]'
$fileIndex = 0

foreach ($remoteFile in $remoteFiles) {
  $fileIndex++
  $relativePath = $remoteFile.RelativePath
  $remoteFilePath = $RemotePath.TrimEnd('/') + '/' + $relativePath
  $destinationPath = $destinationRoot + '/' + $relativePath
  $localPath = Join-Path `
    ([System.IO.Path]::GetTempPath()) `
    ("comma-{0}-{1}.part" -f $timestamp, [Guid]::NewGuid().ToString('N'))
  $uploadCompleted = $false

  Write-Host
  Write-Host ("=== File {0}/{1}: {2} ({3:N1} MB) ===" -f `
      $fileIndex, $remoteFiles.Count, $relativePath, ($remoteFile.Size / 1MB))

  try {
    foreach ($directory in (Get-RequiredFileBrowserDirectories `
        -DestinationRoot $destinationRoot `
        -FileRelativePath $relativePath)) {
      if ($createdDirectories.Add($directory)) {
        Ensure-FileBrowserDirectory `
          -BaseUrl $FileBrowser `
          -Token $token `
          -RemoteDirectory $directory
      }
    }

    Receive-RemoteFile `
      -SshPath $sshCommand.Source `
      -RemoteTarget $remoteTarget `
      -RemoteFilePath $remoteFilePath `
      -ExpectedBytes $remoteFile.Size `
      -LocalPath $localPath `
      -Activity ("Download {0}/{1}: {2}" -f $fileIndex, $remoteFiles.Count, $relativePath) | Out-Null

    Send-FileBrowserFile `
      -BaseUrl $FileBrowser `
      -Token $token `
      -LocalPath $localPath `
      -RemoteName $destinationPath
    $uploadCompleted = $true
  }
  finally {
    if ($uploadCompleted -and (Test-Path -LiteralPath $localPath)) {
      Remove-Item -LiteralPath $localPath -Force
    }
    elseif (Test-Path -LiteralPath $localPath) {
      Write-Host "Copia locale conservata dopo l'errore: $localPath"
    }
  }
}

Write-Host
Write-Host ("=== Upload completato: {0} file ===" -f $remoteFiles.Count)
# [file-by-file] - END
# [comma logs] - END
