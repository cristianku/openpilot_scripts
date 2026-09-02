#requires -Version 5.1

# [comma logs] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ===== CONFIG =====
$CommaHost = '192.168.1.123' # <-- IP del comma
$CommaUser = 'comma'

$FileBrowser = 'https://drive.farm.14bodhi.com'
$FbUser = 'user'
$FbPassword = 'password'

$RemotePath = '/data/media/0/realdata'

function Send-FileBrowserFile {
  param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [Parameter(Mandatory = $true)]
    [string]$LocalPath,

    [Parameter(Mandatory = $true)]
    [string]$RemoteName
  )

  Add-Type -AssemblyName System.Net.Http

  $client = New-Object System.Net.Http.HttpClient
  $stream = $null
  $content = $null
  $response = $null

  try {
    $client.DefaultRequestHeaders.Add('X-Auth', $Token)
    $stream = [System.IO.File]::OpenRead($LocalPath)
    $content = New-Object System.Net.Http.StreamContent -ArgumentList (, $stream)
    $escapedName = [System.Uri]::EscapeDataString($RemoteName)
    $uploadUrl = '{0}/api/resources/{1}' -f $BaseUrl.TrimEnd('/'), $escapedName
    $response = $client.PostAsync($uploadUrl, $content).GetAwaiter().GetResult()

    if (-not $response.IsSuccessStatusCode) {
      $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
      throw "Upload FileBrowser fallito ($([int]$response.StatusCode)): $responseBody"
    }
  }
  finally {
    if ($null -ne $response) { $response.Dispose() }
    if ($null -ne $content) { $content.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
    $client.Dispose()
  }
}

$sshCommand = Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
if ($null -eq $sshCommand) {
  $sshCommand = Get-Command 'ssh' -ErrorAction SilentlyContinue
}
if ($null -eq $sshCommand) {
  throw 'Comando ssh non trovato. Installa o abilita il client OpenSSH.'
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$backup = Join-Path ([System.IO.Path]::GetTempPath()) "comma-$timestamp.tar.gz"
$remoteTarget = "$CommaUser@$CommaHost"
$remoteSeparator = $RemotePath.LastIndexOf('/')

if ($remoteSeparator -le 0 -or $remoteSeparator -eq ($RemotePath.Length - 1)) {
  throw "REMOTE_PATH non valido: $RemotePath"
}

$remoteParent = $RemotePath.Substring(0, $remoteSeparator)
$remoteName = $RemotePath.Substring($remoteSeparator + 1)
$uploadCompleted = $false

Write-Host '=== Test connessione al comma ==='
& $sshCommand.Source -o BatchMode=yes -o ConnectTimeout=10 $remoteTarget "echo 'Comma connected'"
if ($LASTEXITCODE -ne 0) {
  throw "Connessione SSH al comma fallita (codice $LASTEXITCODE)."
}

Write-Host '=== Estrazione dati dal comma ==='
$archiveArguments = "-o BatchMode=yes `"$remoteTarget`" `"tar -C '$remoteParent' -czf - '$remoteName'`""

try {
  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $sshCommand.Source
  $startInfo.Arguments = $archiveArguments
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true

  $archiveProcess = New-Object System.Diagnostics.Process
  $archiveProcess.StartInfo = $startInfo
  $backupStream = $null

  try {
    if (-not $archiveProcess.Start()) {
      throw 'Impossibile avviare ssh.exe per creare il backup.'
    }

    $sshErrorTask = $archiveProcess.StandardError.ReadToEndAsync()
    $backupStream = [System.IO.File]::Create($backup)
    $archiveProcess.StandardOutput.BaseStream.CopyTo($backupStream)
    $backupStream.Dispose()
    $backupStream = $null

    $archiveProcess.WaitForExit()
    $sshError = $sshErrorTask.GetAwaiter().GetResult().Trim()
    $archiveExitCode = $archiveProcess.ExitCode
  }
  finally {
    if ($null -ne $backupStream) { $backupStream.Dispose() }
    $archiveProcess.Dispose()
  }

  if ($archiveExitCode -ne 0) {
    throw "Estrazione remota fallita (codice $archiveExitCode). $sshError"
  }

  $backupInfo = Get-Item -LiteralPath $backup
  if ($backupInfo.Length -eq 0) {
    throw 'Il backup creato e vuoto.'
  }

  Write-Host 'Backup creato:'
  Write-Host ("{0} ({1:N1} MB)" -f $backupInfo.FullName, ($backupInfo.Length / 1MB))

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

  Write-Host '=== Upload ==='
  $uploadName = "comma-$timestamp.tar.gz"
  Send-FileBrowserFile -BaseUrl $FileBrowser -Token $token -LocalPath $backup -RemoteName $uploadName
  $uploadCompleted = $true

  Write-Host
  Write-Host '=== Upload completato ==='
}
finally {
  if ($uploadCompleted -and (Test-Path -LiteralPath $backup)) {
    Remove-Item -LiteralPath $backup -Force
    Write-Host 'Backup locale eliminato.'
  }
}
# [comma logs] - END
