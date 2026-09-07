#requires -Version 5.1

# [comma host] - START
param(
  [Parameter(Mandatory = $true)]
  [ValidateNotNullOrEmpty()]
  [string]$COMMA_HOST,

  # [zip resume] - START
  [string]$CacheDirectory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'comma-log-upload')
  # [zip resume] - END
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

# [resume] - START
function Select-LatestFileBrowserBackupName {
  param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyCollection()]
    [object[]]$Items
  )

  $candidates = foreach ($item in $Items) {
    if (-not $item.isDir -or $item.name -notmatch '^comma-(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$') {
      continue
    }

    $parsedTimestamp = [DateTime]::MinValue
    if ([DateTime]::TryParseExact(
        $Matches[1],
        'yyyy-MM-dd_HH-mm-ss',
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::None,
        [ref]$parsedTimestamp)) {
      [pscustomobject]@{
        Name = [string]$item.name
        Timestamp = $parsedTimestamp
      }
    }
  }

  $latest = $candidates | Sort-Object Timestamp -Descending | Select-Object -First 1
  if ($null -eq $latest) {
    return $null
  }

  return $latest.Name
}

function Get-FileTransferDecision {
  param(
    [Parameter(Mandatory = $true)]
    [long]$ExpectedBytes,

    [long]$ExistingBytes
  )

  if (-not $PSBoundParameters.ContainsKey('ExistingBytes')) {
    return 'Upload'
  }

  if ($ExistingBytes -eq $ExpectedBytes) {
    return 'Skip'
  }

  throw "File gia presente su Drive con dimensione diversa: $ExistingBytes byte invece di $ExpectedBytes."
}

function Invoke-FileTransferWithRetry {
  param(
    [Parameter(Mandatory = $true)]
    [long]$InitialExpectedBytes,

    [Parameter(Mandatory = $true)]
    [scriptblock]$TransferAction,

    [Parameter(Mandatory = $true)]
    [scriptblock]$RefreshExpectedBytes,

    [ValidateRange(1, 10)]
    [int]$MaxAttempts = 3,

    [ValidateRange(0, 60000)]
    [int]$RetryDelayMilliseconds = 2000
  )

  [long]$expectedBytes = $InitialExpectedBytes

  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    try {
      return & $TransferAction $expectedBytes
    }
    catch {
      $transferErrorMessage = $_.Exception.Message
      if ($attempt -eq $MaxAttempts) {
        throw
      }

      Write-Warning ("Trasferimento fallito al tentativo {0}/{1}: {2}" -f `
          $attempt, $MaxAttempts, $transferErrorMessage)
      if ($RetryDelayMilliseconds -gt 0) {
        Start-Sleep -Milliseconds $RetryDelayMilliseconds
      }

      for ($refreshAttempt = 1; $refreshAttempt -le $MaxAttempts; $refreshAttempt++) {
        try {
          $expectedBytes = [long](& $RefreshExpectedBytes)
          break
        }
        catch {
          if ($refreshAttempt -eq $MaxAttempts) {
            throw ("Trasferimento fallito: {0} Rilettura dimensione fallita dopo {1} tentativi: {2}" -f `
                $transferErrorMessage, $MaxAttempts, $_.Exception.Message)
          }

          Write-Warning ("Rilettura dimensione fallita al tentativo {0}/{1}: {2}" -f `
              $refreshAttempt, $MaxAttempts, $_.Exception.Message)
          if ($RetryDelayMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $RetryDelayMilliseconds
          }
        }
      }
    }
  }
}

# [auth retry] - START
function Invoke-FileBrowserAuthenticatedRequest {
  param(
    $Client, $Session, [string]$Method, [string]$Url,
    [hashtable]$Headers = @{}, [byte[]]$Bytes,
    [string]$ContentType = 'application/octet-stream'
  )

  for ($attempt = 0; $attempt -lt 2; $attempt++) {
    # Un nuovo messaggio e un nuovo corpo per ogni tentativo HTTP.
    $request = New-Object System.Net.Http.HttpRequestMessage(
      (New-Object System.Net.Http.HttpMethod($Method)), $Url)
    try {
      $request.Headers.Add('X-Auth', [string]$Session.Token)
      foreach ($key in $Headers.Keys) { $request.Headers.Add($key, [string]$Headers[$key]) }
      if ($null -ne $Bytes) {
        $request.Content = New-Object System.Net.Http.ByteArrayContent -ArgumentList (, $Bytes)
        $request.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new($ContentType)
      }
      $response = $Client.SendAsync($request).GetAwaiter().GetResult()
    } finally { $request.Dispose() }

    if ([int]$response.StatusCode -ne 401) { return $response }
    $response.Dispose()
    if ($attempt -eq 1) {
      throw [System.Security.Authentication.AuthenticationException]::new(
        'FileBrowser HTTP 401 anche dopo un nuovo login. Verificare autenticazione e configurazione del server; ZIP e stato restano in cache.')
    }

    Write-Warning 'FileBrowser HTTP 401: effettuo un nuovo login e riprovo la richiesta.'
    $body = @{ username = $Session.Username; password = $Session.Password } | ConvertTo-Json -Compress
    try {
      $newToken = [string](Invoke-RestMethod -Method Post `
          -Uri "$($Session.BaseUrl.TrimEnd('/'))/api/login" -ContentType 'application/json' -Body $body)
    }
    catch {
      throw [System.Security.Authentication.AuthenticationException]::new(
        'Nuovo login FileBrowser fallito dopo HTTP 401. Verificare credenziali e accesso al server; ZIP e stato restano in cache.')
    }
    if ([string]::IsNullOrWhiteSpace($newToken)) {
      throw [System.Security.Authentication.AuthenticationException]::new('Nuovo login FileBrowser: token vuoto.')
    }
    # Oggetto condiviso: tutti i client usano il token aggiornato alla richiesta successiva.
    $Session.Token = $newToken.Trim()
  }
}
# [auth retry] - END

function Get-FileBrowserResource {
  param(
    [Parameter(Mandatory = $true)]
    [object]$Client,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$RemoteName,

    # [auth retry] - START
    [object]$Session = $null
    # [auth retry] - END
  )

  if ([string]::IsNullOrEmpty($RemoteName)) {
    $resourcePath = '/'
  }
  else {
    $resourcePath = ConvertTo-FileBrowserResourcePath -RelativePath $RemoteName
  }

  $resourceUrl = '{0}/api/resources{1}' -f $BaseUrl.TrimEnd('/'), $resourcePath
  $response = $null
  try {
    # [auth retry] - START
    if ($null -ne $Session) {
      $response = Invoke-FileBrowserAuthenticatedRequest -Client $Client -Session $Session -Method GET -Url $resourceUrl
    }
    else { $response = $Client.GetAsync($resourceUrl).GetAwaiter().GetResult() }
    # [auth retry] - END
    if ($response.StatusCode -eq [System.Net.HttpStatusCode]::NotFound) {
      return $null
    }
    if (-not $response.IsSuccessStatusCode) {
      $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
      throw "Lettura FileBrowser fallita ($([int]$response.StatusCode)): $responseBody"
    }

    $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    return $responseBody | ConvertFrom-Json
  }
  finally {
    if ($null -ne $response) { $response.Dispose() }
  }
}
# [resume] - END

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
    [string]$RemoteFilePath,

    # [zip resume] - START
    [ValidateRange(0, [long]::MaxValue)]
    [long]$OffsetBytes = 0
    # [zip resume] - END
  )

  $encodedPath = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($RemoteFilePath))
  # [zip resume] - START
  if ($OffsetBytes -gt 0) {
    return "printf '%s' '$encodedPath' | base64 -d | xargs -0 tail -c +$($OffsetBytes + 1) --"
  }
  return "printf '%s' '$encodedPath' | base64 -d | xargs -0 cat --"
  # [zip resume] - END
}

# [resume] - START
function Get-RemoteFileSizeCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteFilePath
  )

  $encodedPath = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($RemoteFilePath))
  return "printf '%s' '$encodedPath' | base64 -d | xargs -0 stat -c '%s' --"
}
# [resume] - END

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

    # [ssh error] - START
    if ($null -ne $CompletionValidator) {
      & $CompletionValidator | Out-Null
    }

    if ($TotalBytes -gt 0 -and $transferredBytes -ne $TotalBytes) {
      throw "Dimensione trasferita non valida: attesi $TotalBytes byte, ricevuti $transferredBytes."
    }
    # [ssh error] - END

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

  # [zip resume] - START
  [long]$offset = 0
  if (Test-Path -LiteralPath $LocalPath) {
    $offset = (Get-Item -LiteralPath $LocalPath).Length
    if ($offset -gt $ExpectedBytes) {
      Remove-Item -LiteralPath $LocalPath -Force
      $offset = 0
    }
  }
  if ($offset -eq $ExpectedBytes -and (Test-Path -LiteralPath $LocalPath)) { return $offset }
  if ($offset -gt 0) { Write-Host "Ripresa download da $offset byte: $RemoteFilePath" }
  $remoteCommand = Get-RemoteFileReadCommand -RemoteFilePath $RemoteFilePath -OffsetBytes $offset
  # [zip resume] - END
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
    # [zip resume] - START
    $localStream = [System.IO.File]::Open($LocalPath, [System.IO.FileMode]::Append)
    # [zip resume] - END
    $receivedBytes = Copy-StreamWithProgress `
      -InputStream $process.StandardOutput.BaseStream `
      -OutputStream $localStream `
      -Activity $Activity `
      -TotalBytes ($ExpectedBytes - $offset) `
      -CompletionValidator $completionValidator
    $localStream.Dispose()
    $localStream = $null

    # [zip resume] - START
    if (($receivedBytes + $offset) -ne $ExpectedBytes) { throw 'Dimensione download non valida.' }
    return ($receivedBytes + $offset)
    # [zip resume] - END
  }
  finally {
    if ($null -ne $localStream) { $localStream.Dispose() }
    if ($processStarted -and -not $process.HasExited) { $process.Kill() }
    $process.Dispose()
  }
}

function New-FileBrowserHttpClient {
  param(
    [TimeSpan]$Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
  )

  Add-Type -AssemblyName System.Net.Http
  $client = New-Object System.Net.Http.HttpClient
  $client.Timeout = $Timeout
  return $client
}

function Ensure-FileBrowserDirectory {
  param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [Parameter(Mandatory = $true)]
    [string]$RemoteDirectory,

    # [auth retry] - START
    [object]$Session = $null
    # [auth retry] - END
  )

  $client = New-FileBrowserHttpClient
  $content = New-Object System.Net.Http.ByteArrayContent -ArgumentList (, [byte[]]@())
  $response = $null

  try {
    $client.DefaultRequestHeaders.Add('X-Auth', $Token)
    $resourcePath = (ConvertTo-FileBrowserResourcePath -RelativePath $RemoteDirectory) + '/'
    $directoryUrl = '{0}/api/resources{1}?override=false' -f $BaseUrl.TrimEnd('/'), $resourcePath
    # [auth retry] - START
    if ($null -ne $Session) {
      $response = Invoke-FileBrowserAuthenticatedRequest -Client $client -Session $Session `
        -Method POST -Url $directoryUrl -Bytes ([byte[]]@())
    }
    else { $response = $client.PostAsync($directoryUrl, $content).GetAwaiter().GetResult() }
    # [auth retry] - END

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

# [zip resume] - START
function New-LogZip {
  param([string]$LocalPath, [string]$ZipPath, [string]$EntryName)

  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $temporaryZip = "$ZipPath.tmp"
  $stream = $null
  $archive = $null
  try {
    $stream = [IO.File]::Create($temporaryZip)
    $archive = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create)
    $entry = $archive.CreateEntry($EntryName, [IO.Compression.CompressionLevel]::Optimal)
    # Timestamp fisso: stessi dati producono gli stessi byte anche dopo un riavvio.
    $entry.LastWriteTime = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
    $inputStream = [IO.File]::OpenRead($LocalPath)
    try {
      $outputStream = $entry.Open()
      try { $inputStream.CopyTo($outputStream) }
      finally { $outputStream.Dispose() }
    } finally { $inputStream.Dispose() }
    $archive.Dispose()
    $archive = $null
    $stream.Dispose()
    $stream = $null
    Move-Item -LiteralPath $temporaryZip -Destination $ZipPath -Force
  }
  finally {
    if ($null -ne $archive) { $archive.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
    if (Test-Path -LiteralPath $temporaryZip) { Remove-Item -LiteralPath $temporaryZip -Force }
  }
}

function Invoke-TusRequest {
  # [auth retry] - START
  param($Client, [string]$Method, [string]$Url, [hashtable]$Headers = @{}, [byte[]]$Bytes, $Session = $null)

  if ($null -ne $Session) {
    $authHeaders = @{ 'Tus-Resumable' = '1.0.0' }
    foreach ($key in $Headers.Keys) { $authHeaders[$key] = $Headers[$key] }
    return Invoke-FileBrowserAuthenticatedRequest -Client $Client -Session $Session -Method $Method `
      -Url $Url -Headers $authHeaders -Bytes $Bytes -ContentType 'application/offset+octet-stream'
  }
  # [auth retry] - END

  $request = New-Object System.Net.Http.HttpRequestMessage(
    (New-Object System.Net.Http.HttpMethod($Method)), $Url)
  try {
    $request.Headers.Add('Tus-Resumable', '1.0.0')
    foreach ($key in $Headers.Keys) { $request.Headers.Add($key, [string]$Headers[$key]) }
    if ($null -ne $Bytes) {
      $request.Content = New-Object System.Net.Http.ByteArrayContent -ArgumentList (, $Bytes)
      $request.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/offset+octet-stream')
    }
    return $Client.SendAsync($request).GetAwaiter().GetResult()
  } finally { $request.Dispose() }
}

function Send-FileBrowserZip {
  param(
    [string]$BaseUrl, [string]$Token, [string]$LocalPath, [string]$RemoteName,
    [ValidateRange(1, 10)][int]$MaxAttempts = 3,
    # [auth retry] - START
    [ValidateRange(0, 60000)][int]$RetryDelayMilliseconds = 2000,
    [object]$Session = $null
    # [auth retry] - END
  )

  # Il nome contiene SHA-256 dello ZIP: un parziale appartiene agli stessi byte.
  $zipHash = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if (-not $RemoteName.EndsWith(".$zipHash.zip")) { throw 'Nome ZIP privo del checksum corretto.' }
  $client = New-FileBrowserHttpClient -Timeout ([TimeSpan]::FromMinutes(5))
  $stream = [IO.File]::OpenRead($LocalPath)
  $url = $BaseUrl.TrimEnd('/') + '/api/tus' + (ConvertTo-FileBrowserResourcePath $RemoteName)
  $activity = "Upload ZIP: $RemoteName"
  try {
    $client.DefaultRequestHeaders.Add('X-Auth', $Token)
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
      try {
        $existing = Get-FileBrowserResource -Client $client -BaseUrl $BaseUrl -RemoteName $RemoteName -Session $Session
        if ($null -ne $existing -and $existing.isDir) { throw 'Una cartella occupa il percorso ZIP.' }
        if ($null -ne $existing -and [long]$existing.size -eq $stream.Length) { return }

        $head = Invoke-TusRequest -Client $client -Method HEAD -Url $url -Session $Session
        try {
          if ([int]$head.StatusCode -eq 404) {
            # Sessione assente/scaduta: ricrea soltanto questo ZIP, mai i precedenti.
            if ($null -ne $existing) { Write-Warning 'Sessione TUS scaduta: reinvio soltanto lo ZIP incompleto.' }
            $create = Invoke-TusRequest -Client $client -Method POST -Url "$url`?override=true" `
              -Headers @{ 'Upload-Length' = $stream.Length } -Session $Session
            try {
              if ([int]$create.StatusCode -ne 201) {
                throw "Creazione TUS fallita (HTTP $([int]$create.StatusCode)). Verificare supporto TUS e permessi FileBrowser."
              }
              [long]$offset = 0
            } finally { $create.Dispose() }
          }
          elseif ($head.IsSuccessStatusCode) {
            [long]$offset = [long](@($head.Headers.GetValues('Upload-Offset'))[0])
            [long]$length = [long](@($head.Headers.GetValues('Upload-Length'))[0])
            if ($length -ne $stream.Length -or $offset -lt 0 -or $offset -gt $length) {
              throw 'Offset o lunghezza TUS incompatibili con lo ZIP locale.'
            }
          }
          else { throw "Verifica TUS fallita (HTTP $([int]$head.StatusCode))." }
        } finally { $head.Dispose() }

        Write-Host "Upload da $offset / $($stream.Length) byte"
        $stream.Position = $offset
        while ($offset -lt $stream.Length) {
          $count = [int][Math]::Min(4MB, $stream.Length - $offset)
          $buffer = New-Object byte[] $count
          $read = 0
          while ($read -lt $count) {
            $n = $stream.Read($buffer, $read, $count - $read)
            if ($n -eq 0) { throw 'ZIP locale troncato durante la lettura.' }
            $read += $n
          }
          $response = Invoke-TusRequest -Client $client -Method PATCH -Url $url `
            -Headers @{ 'Upload-Offset' = $offset } -Bytes $buffer -Session $Session
          try {
            if ([int]$response.StatusCode -ne 204) { throw "Upload TUS fallito (HTTP $([int]$response.StatusCode))." }
            [long]$confirmed = [long](@($response.Headers.GetValues('Upload-Offset'))[0])
            if ($confirmed -ne ($offset + $count)) { throw 'Offset TUS non confermato dal server.' }
            $offset = $confirmed
          } finally { $response.Dispose() }
          Write-Progress -Activity $activity -Status "$offset / $($stream.Length) byte confermati" `
            -PercentComplete (Get-TransferPercent $offset $stream.Length)
        }
        $verified = Get-FileBrowserResource -Client $client -BaseUrl $BaseUrl -RemoteName $RemoteName -Session $Session
        if ($null -eq $verified -or $verified.isDir -or [long]$verified.size -ne $stream.Length) {
          throw 'Verifica finale ZIP su FileBrowser fallita.'
        }
        return
      }
      catch {
        # [auth retry] - START
        if ($_.Exception -is [System.Security.Authentication.AuthenticationException]) { throw }
        # [auth retry] - END
        if ($attempt -eq $MaxAttempts) { throw }
        Write-Warning "Upload interrotto: riprovo dall'offset del server. $($_.Exception.Message)"
        Start-Sleep -Milliseconds $RetryDelayMilliseconds
      }
    }
  }
  finally {
    $stream.Dispose()
    $client.Dispose()
    Write-Progress -Activity $activity -Completed
  }
}
# [zip resume] - END

$sshCommand = Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
if ($null -eq $sshCommand) {
  $sshCommand = Get-Command 'ssh' -ErrorAction SilentlyContinue
}
if ($null -eq $sshCommand) {
  throw 'Comando ssh non trovato. Installa o abilita il client OpenSSH.'
}

# [fixed path] - START
$destinationRoot = 'realdata'
# [fixed path] - END
# [comma host] - START
$remoteTarget = "$CommaUser@$COMMA_HOST"
# [comma host] - END

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

# [auth retry] - START
$authSession = [pscustomobject]@{
  BaseUrl = $FileBrowser
  Username = $FbUser
  Password = $FbPassword
  Token = $token.Trim()
}
# [auth retry] - END

# [resume] - START
$resourceClient = New-FileBrowserHttpClient -Timeout ([TimeSpan]::FromSeconds(30))
try {
$resourceClient.DefaultRequestHeaders.Add('X-Auth', $token)
# [resume] - END
$createdDirectories = New-Object 'System.Collections.Generic.HashSet[string]'
$fileIndex = 0
# [resume] - START
$uploadedCount = 0
$skippedCount = 0
# [resume] - END

# [zip resume] - START
# Cache separata per dispositivo, account e server. Non dipende dal timestamp del lancio.
$cacheIdentity = "$FileBrowser`n$FbUser`n$remoteTarget`n$RemotePath"
$hasher = [Security.Cryptography.SHA256]::Create()
try { $scopeKey = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($cacheIdentity)))).Replace('-', '').ToLowerInvariant() }
finally { $hasher.Dispose() }
$cacheRoot = Join-Path $CacheDirectory $scopeKey
[IO.Directory]::CreateDirectory($cacheRoot) | Out-Null
$cacheLock = [IO.File]::Open((Join-Path $cacheRoot 'upload.lock'), [IO.FileMode]::OpenOrCreate,
  [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
# [fixed path] - START
# Ignora il vecchio backup.txt: i dati sono stati spostati nella radice realdata.
# La cache di ZIP, parziali e checksum resta valida e viene riutilizzata.
# [fixed path] - END
Write-Host "Destinazione persistente: $destinationRoot"
Write-Host "Stato e file interrotti: $cacheRoot"

foreach ($remoteFile in $remoteFiles) {
  $fileIndex++
  $relativePath = $remoteFile.RelativePath
  $remoteFilePath = $RemotePath.TrimEnd('/') + '/' + $relativePath
  $destinationPath = $destinationRoot + '/' + $relativePath
  Write-Host "=== Log $fileIndex/$($remoteFiles.Count): $relativePath ==="

  # Compatibilita con i log gia inviati senza ZIP.
  $legacy = Get-FileBrowserResource -Client $resourceClient -BaseUrl $FileBrowser -RemoteName $destinationPath -Session $authSession
  if ($null -ne $legacy -and -not $legacy.isDir -and [long]$legacy.size -eq $remoteFile.Size) {
    Write-Host 'Log originale gia completo su Drive: salto.'
    $skippedCount++
    continue
  }

  $encodedPath = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteFilePath))
  $hashText = Invoke-SshTextCommand -SshPath $sshCommand.Source -RemoteTarget $remoteTarget `
    -RemoteCommand "printf '%s' '$encodedPath' | base64 -d | xargs -0 sha256sum --"
  if ($hashText -notmatch '^\\?([a-fA-F0-9]{64})\s') { throw 'SHA-256 remoto non valido.' }
  $sourceHash = $Matches[1].ToLowerInvariant()
  $hasher = [Security.Cryptography.SHA256]::Create()
  try { $key = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes("$relativePath`n$sourceHash")))).Replace('-', '').ToLowerInvariant() }
  finally { $hasher.Dispose() }
  $localPath = Join-Path $cacheRoot "$key.part"
  $zipPath = Join-Path $cacheRoot "$key.zip"
  $statePath = Join-Path $cacheRoot "$key.json"
  $state = $null
  if (Test-Path -LiteralPath $statePath) {
    $state = [IO.File]::ReadAllText($statePath) | ConvertFrom-Json
    if ($state.SourceHash -ne $sourceHash -or $state.ZipHash -notmatch '^[a-f0-9]{64}$' -or [long]$state.ZipBytes -le 0) {
      throw "Stato ZIP locale non valido: $statePath"
    }
    $zipDestination = "$destinationPath.$($state.ZipHash).zip"
    $existing = Get-FileBrowserResource -Client $resourceClient -BaseUrl $FileBrowser -RemoteName $zipDestination -Session $authSession
    if ($null -ne $existing -and -not $existing.isDir -and [long]$existing.size -eq [long]$state.ZipBytes) {
      Write-Host 'ZIP gia completo su Drive: salto download e upload.'
      foreach ($path in @($localPath, $zipPath)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
      }
      $skippedCount++
      continue
    }
  }

  $validZip = $false
  if ($null -ne $state -and (Test-Path -LiteralPath $zipPath)) {
    $validZip = ((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $state.ZipHash)
  }
  if (-not $validZip) {
    # [retry scope] - START
    # Callback sincroni: mantengono lo scope dello script e le sue funzioni.
    # GetNewClosure li sposterebbe in un modulo che non vede gli helper locali.
    $downloadAction = {
      param($expectedBytes)
      Receive-RemoteFile -SshPath $sshCommand.Source -RemoteTarget $remoteTarget `
        -RemoteFilePath $remoteFilePath -ExpectedBytes $expectedBytes -LocalPath $localPath `
        -Activity "Download $fileIndex/$($remoteFiles.Count): $relativePath"
    }
    $refreshSizeAction = {
      $sizeText = (Invoke-SshTextCommand -SshPath $sshCommand.Source -RemoteTarget $remoteTarget `
          -RemoteCommand (Get-RemoteFileSizeCommand -RemoteFilePath $remoteFilePath)).Trim()
      [long]$size = 0
      if (-not [long]::TryParse($sizeText, [ref]$size) -or $size -lt 0) { throw 'Dimensione remota non valida.' }
      return $size
    }
    # [retry scope] - END
    Invoke-FileTransferWithRetry -InitialExpectedBytes $remoteFile.Size `
      -TransferAction $downloadAction -RefreshExpectedBytes $refreshSizeAction | Out-Null
    if ((Get-FileHash -LiteralPath $localPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceHash) {
      Remove-Item -LiteralPath $localPath -Force
      throw "Log cambiato durante il download o parziale non valido: $relativePath. Rilancia lo script per riprovare."
    }
    Write-Host 'Compressione ZIP prima dell invio...'
    New-LogZip -LocalPath $localPath -ZipPath $zipPath -EntryName $relativePath
    $state = [pscustomobject]@{
      SourceHash = $sourceHash
      ZipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
      ZipBytes = (Get-Item -LiteralPath $zipPath).Length
    }
    [IO.File]::WriteAllText("$statePath.tmp", ($state | ConvertTo-Json -Compress))
    Move-Item -LiteralPath "$statePath.tmp" -Destination $statePath -Force
    Remove-Item -LiteralPath $localPath -Force
  }

  $zipDestination = "$destinationPath.$($state.ZipHash).zip"
  foreach ($directory in (Get-RequiredFileBrowserDirectories -DestinationRoot $destinationRoot -FileRelativePath $relativePath)) {
    if ($createdDirectories.Add($directory)) {
      Ensure-FileBrowserDirectory -BaseUrl $FileBrowser -Token $token -RemoteDirectory $directory -Session $authSession
    }
  }
  # In caso di errore ZIP e stato restano nella cache per il prossimo lancio.
  Send-FileBrowserZip -BaseUrl $FileBrowser -Token $token -LocalPath $zipPath -RemoteName $zipDestination -Session $authSession
  Remove-Item -LiteralPath $zipPath -Force
  $uploadedCount++
}
}
finally { $cacheLock.Dispose() }
# [zip resume] - END

Write-Host
# [resume] - START
Write-Host ("=== Sincronizzazione completata: {0} caricati, {1} gia presenti ===" -f `
    $uploadedCount, $skippedCount)
}
finally {
  $resourceClient.Dispose()
}
# [resume] - END
# [file-by-file] - END
# [comma logs] - END
