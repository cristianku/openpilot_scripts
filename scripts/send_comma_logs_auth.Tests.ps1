#requires -Version 5.1
# [auth retry] - START
param([string]$ScriptPath = (Join-Path $PSScriptRoot 'send_comma_logs.ps1'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
  $ScriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false) |
  ForEach-Object { Set-Item "Function:\script:$($_.Name)" $_.Body.GetScriptBlock() }
function Assert-Equal($Expected, $Actual) {
  if ($Expected -ne $Actual) { throw "Expected '$Expected', got '$Actual'" }
}
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
  $logins = 0
  $directories = 0
  $heads = 0
  $patches = 0
  $denied = 0
  $metadata = 0
  $blockedTus = 0
  $activeToken = 'token-0'
  try {
    while ($true) {
      $ctx = $server.GetContext()
      $req = $ctx.Request
      $res = $ctx.Response
      $body = $null
      $path = $req.Url.AbsolutePath
      if ($path -eq '/stop') { $res.Close(); break }
      if ($path -eq '/api/login') {
        $reader = New-Object IO.StreamReader($req.InputStream)
        try { $credentials = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        if ($credentials.username -ne 'test-user' -or $credentials.password -ne 'test-password') {
          throw 'Credenziali di test errate'
        }
        $logins++
        $activeToken = "token-$logins"
        $res.ContentType = 'text/plain'
        $body = [Text.Encoding]::UTF8.GetBytes($activeToken)
      }
      elseif ($path -eq '/api/resources/backup/') {
        $directories++
        if ($directories -eq 1 -or $req.Headers['X-Auth'] -ne $activeToken) { $res.StatusCode = 401 }
        else { $res.StatusCode = 200 }
      }
      elseif ($path -eq '/api/resources/backup/log.zip') {
        $metadata++
        if ($req.Headers['X-Auth'] -ne $activeToken) { throw 'Il client metadata usa ancora il vecchio token' }
        $res.ContentType = 'application/json'
        $body = [Text.Encoding]::UTF8.GetBytes('{"isDir":false,"size":123}')
      }
      elseif ($path -eq '/api/tus/backup/log.zip' -and $req.HttpMethod -eq 'HEAD') {
        $heads++
        if ($heads -eq 1) { $res.StatusCode = 401 }
        else {
          if ($req.Headers['X-Auth'] -ne $activeToken) { throw 'HEAD non usa il nuovo token' }
          $res.Headers.Add('Upload-Offset', '7')
          $res.Headers.Add('Upload-Length', '123')
        }
      }
      elseif ($path -eq '/api/tus/backup/log.zip' -and $req.HttpMethod -eq 'PATCH') {
        $patches++
        $data = New-Object IO.MemoryStream
        $req.InputStream.CopyTo($data)
        if ([Convert]::ToBase64String($data.ToArray()) -ne 'AQIDBA==') { throw 'Il retry ha perso il corpo PATCH' }
        $data.Dispose()
        if ($req.Headers['Upload-Offset'] -ne '7') { throw 'Offset cambiato durante il rinnovo' }
        if ($req.Headers['Tus-Resumable'] -ne '1.0.0') { throw 'Header TUS mancante' }
        if ($patches -eq 1) { $res.StatusCode = 401 }
        else {
          if ($req.Headers['X-Auth'] -ne $activeToken) { throw 'PATCH non usa il nuovo token' }
          $res.StatusCode = 204
          $res.Headers.Add('Upload-Offset', '11')
        }
      }
      elseif ($path.StartsWith('/api/resources/blocked.')) { $res.StatusCode = 404 }
      elseif ($path.StartsWith('/api/tus/blocked.')) { $blockedTus++; $res.StatusCode = 401 }
      elseif ($path -eq '/api/resources/denied/') { $denied++; $res.StatusCode = 401 }
      elseif ($path -eq '/api/resources/forbidden/') { $res.StatusCode = 403 }
      else { throw "Richiesta inattesa: $($req.HttpMethod) $path" }
      if ($null -ne $body) { $res.OutputStream.Write($body, 0, $body.Length) }
      $res.Close()
    }
    [pscustomobject]@{ Logins = $logins; Directories = $directories; Heads = $heads; Patches = $patches; Denied = $denied; Metadata = $metadata; BlockedTus = $blockedTus }
  } finally { $server.Close() }
}
$client = New-FileBrowserHttpClient -Timeout ([TimeSpan]::FromSeconds(10))
$baseUrl = "http://127.0.0.1:$port"
$serverStopped = $false
$session = [pscustomobject]@{ BaseUrl = $baseUrl; Username = 'test-user'; Password = 'test-password'; Token = 'expired' }
try {
  $deadline = (Get-Date).AddSeconds(10)
  while (-not (Receive-Job $job -Keep | Where-Object { $_ -eq 'Ready' })) {
    if ((Get-Date) -gt $deadline) { throw 'Listener timeout' }
    Start-Sleep -Milliseconds 100
  }
  $directoryArgs = @{ BaseUrl = $baseUrl; Token = 'expired'; RemoteDirectory = 'backup' }
  # Consente anche il controllo negativo sulla versione precedente, fino al vero HTTP 401.
  if ((Get-Command Ensure-FileBrowserDirectory).Parameters.ContainsKey('Session')) { $directoryArgs.Session = $session }
  Ensure-FileBrowserDirectory @directoryArgs
  Assert-Equal 'token-1' $session.Token
  $client.DefaultRequestHeaders.Add('X-Auth', 'expired')
  $resource = Get-FileBrowserResource -Client $client -BaseUrl $baseUrl -RemoteName 'backup/log.zip' -Session $session
  Assert-Equal 123 $resource.size
  $response = Invoke-TusRequest -Client $client -Method HEAD -Url "$baseUrl/api/tus/backup/log.zip" -Session $session
  try { Assert-Equal 200 ([int]$response.StatusCode) } finally { $response.Dispose() }
  Assert-Equal 'token-2' $session.Token
  $response = Invoke-TusRequest -Client $client -Method PATCH -Url "$baseUrl/api/tus/backup/log.zip" `
    -Headers @{ 'Upload-Offset' = 7 } -Bytes ([byte[]](1, 2, 3, 4)) -Session $session
  try { Assert-Equal 204 ([int]$response.StatusCode) } finally { $response.Dispose() }
  Assert-Equal 'token-3' $session.Token
  $message = ''
  try { Ensure-FileBrowserDirectory -BaseUrl $baseUrl -Token 'expired' -RemoteDirectory 'denied' -Session $session }
  catch { $message = $_.Exception.Message }
  if ($message -notmatch '401.*nuovo login') { throw "Diagnostica 401 persistente mancante: $message" }
  $message = ''
  try { Ensure-FileBrowserDirectory -BaseUrl $baseUrl -Token 'expired' -RemoteDirectory 'forbidden' -Session $session }
  catch { $message = $_.Exception.Message }
  if ($message -notmatch '403') { throw "Il 403 deve restare un errore permessi: $message" }
  $zipPath = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString('N') + '.zip')
  try {
    [IO.File]::WriteAllBytes($zipPath, [byte[]](1, 2, 3, 4))
    $hash = (Get-FileHash -LiteralPath $zipPath).Hash.ToLowerInvariant()
    $message = ''
    try {
      Send-FileBrowserZip -BaseUrl $baseUrl -Token 'expired' -LocalPath $zipPath `
        -RemoteName "blocked.$hash.zip" -Session $session -MaxAttempts 3 -RetryDelayMilliseconds 0
    } catch { $message = $_.Exception.Message }
    if ($message -notmatch '401.*nuovo login') { throw "Upload deve fermarsi dopo il nuovo login rifiutato: $message" }
    Assert-Equal $true (Test-Path -LiteralPath $zipPath)
  } finally { Remove-Item -LiteralPath $zipPath -Force }
  $stop = $client.GetAsync("$baseUrl/stop").GetAwaiter().GetResult()
  $stop.Dispose()
  $serverStopped = $true
  Wait-Job $job -Timeout 10 | Out-Null
  Assert-Equal 'Completed' $job.State
  $stats = @(Receive-Job $job)[-1]
  Assert-Equal 5 $stats.Logins
  Assert-Equal 2 $stats.Directories
  Assert-Equal 2 $stats.Heads
  Assert-Equal 2 $stats.Patches
  Assert-Equal 2 $stats.Denied
  Assert-Equal 1 $stats.Metadata
  Assert-Equal 2 $stats.BlockedTus
  Write-Host 'PASS: rinnovo 401 cartella, token condiviso, HEAD/PATCH con offset e corpo preservati, stop al secondo 401, nessun rinnovo su 403'
} finally {
  if (-not $serverStopped) { try {
    $stop = $client.GetAsync("$baseUrl/stop").GetAwaiter().GetResult()
    $stop.Dispose()
  } catch { } }
  $client.Dispose()
  Stop-Job $job
  Remove-Job $job -Force
}
# [auth retry] - END
