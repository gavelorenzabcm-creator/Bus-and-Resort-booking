$ErrorActionPreference = 'Continue'

function Test-Endpoint {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Url,
    [ValidateSet('GET','POST')][string]$Method = 'GET',
    [int]$TimeoutSec = 10,
    [switch]$IsApi,
    [switch]$AllowRedirects
  )

  $sw = [Diagnostics.Stopwatch]::StartNew()
  $resp = $null
  $statusCode = $null
  $redirectLocation = ''
  $jsonOk = $false
  $jsonKeys = @()
  $bodyText = ''

  try {
    $redir = if ($AllowRedirects) { 5 } else { 0 }

    if ($Method -eq 'GET') {
      $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec $TimeoutSec -Uri $Url -Method Get -MaximumRedirection $redir -ErrorAction Stop
    } else {
      $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec $TimeoutSec -Uri $Url -Method Post -MaximumRedirection $redir -ErrorAction Stop
    }

    $statusCode = $resp.StatusCode
    if ($resp.Headers.ContainsKey('Location')) {
      $redirectLocation = $resp.Headers['Location']
    }

    if ($IsApi) {
      try {
        $parsed = $resp.Content | ConvertFrom-Json -ErrorAction Stop
        $jsonOk = $true
        if ($null -ne $parsed -and ($parsed -is [System.Array])) {
          $jsonKeys = @('[array]')
        } elseif ($null -ne $parsed) {
          $jsonKeys = ($parsed.psobject.Properties | ForEach-Object { $_.Name })
        }
      } catch {
        $jsonOk = $false
      }
    }

    if ($statusCode -eq 500 -and $resp.Content) {
      $bodyText = $resp.Content
    }
  }
  catch {
    $ex = $_.Exception
    $statusCode = $null
    if ($ex.Response -and $ex.Response.StatusCode) {
      $statusCode = [int]$ex.Response.StatusCode
    }
    if ($ex.Response -and $ex.Response.Headers -and $ex.Response.Headers['Location']) {
      $redirectLocation = $ex.Response.Headers['Location']
    }

    try {
      if ($ex.Response -and $ex.Response.GetResponseStream()) {
        $reader = New-Object System.IO.StreamReader($ex.Response.GetResponseStream())
        $bodyText = $reader.ReadToEnd()
      }
    } catch {
      $bodyText = ''
    }

    if ($IsApi -and $bodyText) {
      try {
        $parsed = $bodyText | ConvertFrom-Json -ErrorAction Stop
        $jsonOk = $true
        if ($null -ne $parsed -and ($parsed -is [System.Array])) {
          $jsonKeys = @('[array]')
        } elseif ($null -ne $parsed) {
          $jsonKeys = ($parsed.psobject.Properties | ForEach-Object { $_.Name })
        }
      } catch {
        $jsonOk = $false
      }
    }
  }
  finally {
    $sw.Stop()
  }

  $elapsedMs = $sw.ElapsedMilliseconds

  $passed = $false
  if ($statusCode -ne $null) {
    if ($IsApi) {
      $passed = ($statusCode -eq 200 -and $jsonOk)
    } else {
      # For UI routes: accept 200 OR 302 redirect (e.g. unauthenticated dashboard -> login)
      $passed = ($statusCode -eq 200) -or ($statusCode -eq 302) -or ($statusCode -eq 301) -or ($statusCode -eq 303)
    }
  }

  $result = [PSCustomObject]@{
    Name = $Name
    Url = $Url
    Status = $statusCode
    TimeMs = $elapsedMs
    Redirect = $redirectLocation
    IsApi = [bool]$IsApi
    JsonOk = $jsonOk
    JsonKeys = if ($jsonKeys) { ($jsonKeys -join ',') } else { '' }
    Passed = $passed
    Body500 = if ($statusCode -eq 500 -and $bodyText) { $bodyText } else { '' }
  }

  return $result
}

function Print-ResultRow {
  param([Parameter(Mandatory=$true)]$r)
  $redir = if ($r.Redirect) { " Redirect=$($r.Redirect)" } else { '' }
  $json = ''
  if ($r.IsApi) {
    $json = " JsonOk=$($r.JsonOk) JsonKeys=$($r.JsonKeys)"
  }
  $status = if ($r.Status -ne $null) { $r.Status } else { 'ERR' }
  $passed = if ($r.Passed) { 'PASS' } else { 'FAIL' }
  Write-Output ("[{0}] {1} -> HTTP {2} in {3}ms{4}{5}" -f $passed, $r.Name, $status, $r.TimeMs, $redir, $json)
  if ($status -eq 500 -and $r.Body500) {
    Write-Output "--- Response body (500) for $($r.Name) ---"
    Write-Output $r.Body500
    Write-Output "--- end body ---"
  }
}

function Wait-For {
  param([string]$url,[int]$timeoutSec=30)
  $deadline = [DateTime]::UtcNow.AddSeconds($timeoutSec)
  while([DateTime]::UtcNow -lt $deadline) {
    try {
      Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $url -Method Get -MaximumRedirection 0 -ErrorAction Stop | Out-Null
      return $true
    } catch {
      Start-Sleep -Milliseconds 300
    }
  }
  return $false
}

$mainBase = 'http://127.0.0.1:5000'
$adminBase = 'http://127.0.0.1:5001'

Write-Output 'Waiting for servers...'
$mainOk = Wait-For ($mainBase + '/') 45
$adminOk = Wait-For ($adminBase + '/admin') 45

if (-not $mainOk) { Write-Output 'Main server did not come up in time.' }
if (-not $adminOk) { Write-Output 'Admin server did not come up in time.' }

$endpoints = @()

# Corrected route paths (actual app routes)
$endpoints += @(@{Name='main /'; Url=($mainBase + '/'); IsApi=$false})
$endpoints += @(@{Name='main /bus'; Url=($mainBase + '/bus'); IsApi=$false})
$endpoints += @(@{Name='main /resort'; Url=($mainBase + '/resort'); IsApi=$false})
$endpoints += @(@{Name='main /feedback'; Url=($mainBase + '/feedback'); IsApi=$false})
$endpoints += @(@{Name='admin /admin'; Url=($adminBase + '/admin'); IsApi=$false})
$endpoints += @(@{Name='admin /dashboard'; Url=($adminBase + '/dashboard'); IsApi=$false})

# Calendar API endpoints
$endpoints += @(@{Name='calendar bus availability'; Url=($mainBase + '/api/availability/bus'); IsApi=$true})
$endpoints += @(@{Name='calendar resort availability'; Url=($mainBase + '/api/availability/resort'); IsApi=$true})

$results = @()
foreach ($e in $endpoints) {
  $r = Test-Endpoint -Name $e.Name -Url $e.Url -Method 'GET' -IsApi:([bool]$e.IsApi)
  Print-ResultRow $r
  $results += $r
}

$passed = ($results | Where-Object { $_.Passed }).Count
$total = $results.Count
$failedList = ($results | Where-Object { -not $_.Passed } | ForEach-Object { $_.Name }) -join ', '

Write-Output ''
Write-Output ('Summary: {0}/{1} passed' -f $passed,$total)
if ($failedList) {
  Write-Output ('Failed endpoints: ' + $failedList)
}

