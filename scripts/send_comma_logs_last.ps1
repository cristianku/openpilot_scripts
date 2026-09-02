#requires -Version 5.1

# [comma logs] - START
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# =========================
# CONFIG
# =========================
$CommaHost = '192.168.1.XXX'
$CommaUser = 'comma'

$FbUrl = 'https://drive.farm.14bodhi.com'
$FbUser = 'user'
$FbPassword = 'PASSWORD'

$RemoteDir = '/data/media/0/realdata'

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

$scpCommand = Get-Command 'scp.exe' -ErrorAction SilentlyContinue
if ($null -eq $scpCommand) {
  $scpCommand = Get-Command 'scp' -ErrorAction SilentlyContinue
}
if ($null -eq $scpCommand) {
  throw 'Comando scp non trovato. Installa o abilita il client OpenSSH.'
}

$remoteTarget = "$CommaUser@$CommaHost"

# =========================
# TROVA ULTIMO LOG
# =========================
Write-Host 'Cerco ultimo log sul comma...'
$findCommand = "find '$RemoteDir' -type f \( -name 'rlog*' -o -name 'qlog*' \) -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-"
$latestOutput = & $sshCommand.Source -o BatchMode=yes $remoteTarget $findCommand

if ($LASTEXITCODE -ne 0) {
  throw "Ricerca remota fallita (codice $LASTEXITCODE)."
}

$latest = ($latestOutput -join "`n").Trim()
if ([string]::IsNullOrWhiteSpace($latest)) {
  throw 'Nessun rlog/qlog trovato.'
}

Write-Host 'Trovato:'
Write-Host $latest

# =========================
# COPIA DAL COMMA
# =========================
$normalizedLatest = $latest.Replace('\', '/')
$basename = $normalizedLatest.Substring($normalizedLatest.LastIndexOf('/') + 1)
$parentPath = $normalizedLatest.Substring(0, $normalizedLatest.LastIndexOf('/'))
$route = $parentPath.Substring($parentPath.LastIndexOf('/') + 1)

if ([string]::IsNullOrWhiteSpace($basename) -or [string]::IsNullOrWhiteSpace($route)) {
  throw "Percorso remoto non valido: $latest"
}

$uploadName = "$route-$basename"
$localFile = Join-Path ([System.IO.Path]::GetTempPath()) $uploadName
$uploadCompleted = $false

Write-Host
Write-Host 'Copio:'
Write-Host $localFile

try {
  & $scpCommand.Source -q "${remoteTarget}:$latest" $localFile
  if ($LASTEXITCODE -ne 0) {
    throw "Copia SCP fallita (codice $LASTEXITCODE)."
  }

  $localFileInfo = Get-Item -LiteralPath $localFile
  if ($localFileInfo.Length -eq 0) {
    throw 'Il file copiato e vuoto.'
  }
  Write-Host ("{0} ({1:N1} MB)" -f $localFileInfo.FullName, ($localFileInfo.Length / 1MB))

  # =========================
  # LOGIN FILEBROWSER
  # =========================
  Write-Host
  Write-Host 'Login FileBrowser...'
  [System.Net.ServicePointManager]::SecurityProtocol = `
    [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12

  $loginBody = @{
    username = $FbUser
    password = $FbPassword
  } | ConvertTo-Json -Compress

  $token = [string](Invoke-RestMethod `
    -Method Post `
    -Uri "$($FbUrl.TrimEnd('/'))/api/login" `
    -ContentType 'application/json' `
    -Body $loginBody)

  if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'Token FileBrowser vuoto.'
  }

  # =========================
  # UPLOAD
  # =========================
  Write-Host
  Write-Host 'Upload:'
  Write-Host $uploadName

  Send-FileBrowserFile -BaseUrl $FbUrl -Token $token -LocalPath $localFile -RemoteName $uploadName
  $uploadCompleted = $true

  Write-Host
  Write-Host 'Upload completato.'
}
finally {
  # =========================
  # CLEANUP
  # =========================
  if ($uploadCompleted -and (Test-Path -LiteralPath $localFile)) {
    Remove-Item -LiteralPath $localFile -Force
    Write-Host 'File temporaneo eliminato.'
  }
}
# [comma logs] - END
