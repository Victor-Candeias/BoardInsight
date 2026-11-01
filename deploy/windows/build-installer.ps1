<#
BoardInsight — gera o instalador Windows (.exe) em Windows (equivalente nativo de build-installer.sh).

Uso (a partir de qualquer pasta):
  deploy\windows\build-installer.ps1 [-SkipFrontend]

Requisitos: Node.js/npm, Python 3 com pip e SDK .NET 8+ no PATH. O Inno Setup é descarregado para a cache
($env:BOARDINSIGHT_BUILD_CACHE ou %LOCALAPPDATA%\boardinsight-windows-build) e instalado sem admin.
Cada download é verificado com o SHA256 de versions.env. Saída: dist\windows\BoardInsight-Setup-<versão>.exe
#>
param([switch]$SkipFrontend)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Root = (Resolve-Path "$Here\..\..").Path
$Cache = if ($env:BOARDINSIGHT_BUILD_CACHE) { $env:BOARDINSIGHT_BUILD_CACHE } else { Join-Path $env:LOCALAPPDATA "boardinsight-windows-build" }
$Downloads = Join-Path $Cache "downloads"
$Stage = Join-Path $Cache "stage"
$App = Join-Path $Stage "app"
$OutDir = if ($env:OUT_DIR) { $env:OUT_DIR } else { Join-Path $Root "dist\windows" }

function Log($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Run($exe, [string[]]$args_) {
  & $exe @args_
  if ($LASTEXITCODE -ne 0) { throw "falhou: $exe $($args_ -join ' ') (código $LASTEXITCODE)" }
}

$V = @{}
Get-Content "$Here\versions.env" | Where-Object { $_ -match '^\s*([A-Z0-9_]+)=(.+)$' } | ForEach-Object { $V[$Matches[1]] = $Matches[2].Trim() }

function Fetch($url, $sha) {
  $file = Join-Path $Downloads ([IO.Path]::GetFileName($url))
  New-Item -ItemType Directory -Force $Downloads | Out-Null
  if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash -ne $sha) {
    Log "a descarregar $([IO.Path]::GetFileName($url))"
    Invoke-WebRequest -Uri $url -OutFile "$file.part" -UseBasicParsing
    Move-Item -Force "$file.part" $file
    if ((Get-FileHash $file -Algorithm SHA256).Hash -ne $sha) { throw "SHA256 inválido: $file (atualizar versions.env?)" }
  }
  $file
}

$Version = [regex]::Match((Get-Content "$Root\backend\app\__init__.py" -Raw), '__version__ = "(.+?)"').Groups[1].Value
Log "BoardInsight $Version"

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force $App, "$Stage\winsw", "$Stage\redist", "$Stage\setup", $OutDir | Out-Null

# 1. Frontend
if (-not $SkipFrontend) {
  Log "frontend: build de produção"
  Push-Location "$Root\frontend"
  try {
    Run npm.cmd @("ci", "--no-audit", "--no-fund")
    Run npm.cmd @("run", "build")
  } finally { Pop-Location }
}
if (-not (Test-Path "$Root\frontend\dist\index.html")) { throw "frontend\dist em falta (correr sem -SkipFrontend)" }
New-Item -ItemType Directory -Force "$App\frontend" | Out-Null
Copy-Item -Recurse "$Root\frontend\dist" "$App\frontend\dist"

# 2. Python embeddable + dependências + backend
Log "python $($V.PYTHON_VERSION) embeddable (win_amd64)"
Expand-Archive -Path (Fetch $V.PYTHON_URL $V.PYTHON_SHA256) -DestinationPath "$App\python"
# O ._pth substitui sys.path: stdlib, site-packages e o backend.
[IO.File]::WriteAllText("$App\python\python313._pth", (("python313.zip", ".", "Lib\site-packages", "..\backend", "import site") -join "`r`n") + "`r`n")
$Site = "$App\python\Lib\site-packages"
Run python @("-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-deps", "--only-binary=:all:",
  "--platform", "win_amd64", "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313",
  "--target", $Site, "-r", "$Root\backend\requirements.lock", "-r", "$Here\requirements-windows.txt")
if (Test-Path "$Site\bin") { Remove-Item -Recurse -Force "$Site\bin" }
New-Item -ItemType Directory -Force "$App\backend\app" | Out-Null
robocopy "$Root\backend\app" "$App\backend\app" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }

# 3. App desktop (WPF + WebView2)
Log "app desktop (WPF, .NET Framework 4.7.2)"
New-Item -ItemType Directory -Force "$Stage\src\frontend\public" | Out-Null
robocopy "$Root\desktop" "$Stage\src\desktop" /E /XD bin obj .vs /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }
Copy-Item -Recurse "$Root\frontend\public\brand" "$Stage\src\frontend\public\brand"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"; $env:DOTNET_NOLOGO = "1"
Run dotnet @("publish", "$Stage\src\desktop\BoardInsight.Desktop\BoardInsight.Desktop.csproj", "-c", "Release", "-nologo", "-v", "q", "-p:Version=$Version", "-o", "$App\desktop")
if (-not (Test-Path "$App\desktop\BoardInsight.exe")) { throw "dotnet publish não gerou BoardInsight.exe" }
Copy-Item "$Root\desktop\BoardInsight.Desktop\BoardInsight.ico" "$Stage\setup\BoardInsight.ico"

# 4. MongoDB, VC++ Redistributable, WinSW e ficheiros de serviço
Log "mongodb $($V.MONGODB_VERSION) (mongod.exe)"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$wanted = @{ "bin/mongod.exe" = "$App\mongodb\bin"; "LICENSE-Community.txt" = "$App\mongodb"; "MPL-2" = "$App\mongodb";
  "THIRD-PARTY-NOTICES" = "$App\mongodb"; "README" = "$App\mongodb"; "bin/vc_redist.x64.exe" = "$Stage\redist" }
$zip = [IO.Compression.ZipFile]::OpenRead((Fetch $V.MONGODB_URL $V.MONGODB_SHA256))
try {
  foreach ($entry in $zip.Entries) {
    $rel = ($entry.FullName -split "/", 2)[-1]
    if ($wanted.ContainsKey($rel)) {
      $dir = $wanted[$rel]; $wanted.Remove($rel)
      New-Item -ItemType Directory -Force $dir | Out-Null
      [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $dir (Split-Path $rel -Leaf)), $true)
    }
  }
} finally { $zip.Dispose() }
if ($wanted.Count) { throw "em falta no ZIP do MongoDB: $($wanted.Keys -join ', ')" }
Copy-Item (Fetch $V.WINSW_URL $V.WINSW_SHA256) "$Stage\winsw\WinSW-x64.exe"
Copy-Item "$Here\services\*.xml", "$Here\sync.cmd" $App
New-Item -ItemType Directory -Force "$App\config" | Out-Null
Copy-Item "$Here\env.windows" "$App\config\env.windows"

# 5. Inno Setup
$IsccDir = Join-Path $Cache "innosetup-$($V.INNOSETUP_VERSION)"
if (-not (Test-Path "$IsccDir\ISCC.exe")) {
  Log "inno setup $($V.INNOSETUP_VERSION)"
  $setup = Fetch $V.INNOSETUP_URL $V.INNOSETUP_SHA256
  Start-Process -Wait -FilePath $setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=$IsccDir"
  if (-not (Test-Path "$IsccDir\ISCC.exe")) { throw "falhou a instalação do Inno Setup" }
}
Log "a compilar o instalador (Inno Setup; demora alguns minutos)"
Run "$IsccDir\ISCC.exe" @("/Q", "/DAppVersion=$Version", "/DStageDir=$Stage", "/O$OutDir", "$Here\boardinsight.iss")
$Exe = Join-Path $OutDir "BoardInsight-Setup-$Version.exe"
if (-not (Test-Path $Exe)) { throw "o ISCC não gerou $Exe" }
$hash = (Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText("$Exe.sha256", "$hash  $(Split-Path $Exe -Leaf)`n")
if ($env:KEEP_STAGE -ne "1") { Remove-Item -Recurse -Force $Stage }
Log ("instalador: {0} ({1:N0} MB)" -f $Exe, ((Get-Item $Exe).Length / 1MB))
