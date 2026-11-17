# Aplica la configuración del repo a Hermes (idempotente).
#  - config\hermes\ajustes.txt  -> `hermes config set clave valor`
#  - skills\*                   -> %LOCALAPPDATA%\hermes\skills\
#  - config\hermes\SOUL.md      -> %LOCALAPPDATA%\hermes\SOUL.md (si existe)
#  - secretos\.env              -> claves fusionadas en %LOCALAPPDATA%\hermes\.env
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$hermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$hermes = Join-Path $hermesHome "bin\hermes.exe"
$cfg = Join-Path $hermesHome "config.yaml"

# Copia de seguridad diaria de config.yaml (una por día, no se acumulan en la misma fecha)
$bak = "$cfg.$(Get-Date -Format yyyy-MM-dd).bak"
if ((Test-Path $cfg) -and -not (Test-Path $bak)) { Copy-Item $cfg $bak }

# 1. Ajustes
foreach ($linea in Get-Content (Join-Path $repo "config\hermes\ajustes.txt") -Encoding UTF8) {
    $l = $linea.Trim()
    if (-not $l -or $l.StartsWith("#")) { continue }
    $clave, $valor = $l -split "\s+", 2
    $actual = try { (& $hermes config get $clave 2>$null | Out-String).Trim() } catch { "" }  # clave sin valor
    if ($actual -ne $valor) {
        # PS 5.1 quita las comillas dobles al pasar argumentos a un .exe: hay que escaparlas
        & $hermes config set $clave ($valor -replace '"', '\"') | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "hermes config set $clave fallo" }
        Write-Output "ajuste: $clave = $valor"
    }
}

# 2. Skills propias
$skills = Join-Path $repo "skills"
if (Test-Path $skills) {
    foreach ($d in Get-ChildItem $skills -Directory) {
        $dest = Join-Path $hermesHome "skills\$($d.Name)"
        New-Item -ItemType Directory -Force $dest | Out-Null
        Copy-Item (Join-Path $d.FullName "*") $dest -Recurse -Force
        Write-Output "skill: $($d.Name)"
    }
}

# 3. SOUL.md
$soul = Join-Path $repo "config\hermes\SOUL.md"
if (Test-Path $soul) { Copy-Item $soul (Join-Path $hermesHome "SOUL.md") -Force; Write-Output "SOUL.md copiado" }

# 4. Secretos: fusiona CLAVE=valor no vacíos en el .env de Hermes
$secretos = Join-Path $repo "secretos\.env"
if (Test-Path $secretos) {
    $envHermes = Join-Path $hermesHome ".env"
    $lineas = if (Test-Path $envHermes) { @(Get-Content $envHermes -Encoding UTF8) } else { @() }
    foreach ($s in Get-Content $secretos -Encoding UTF8) {
        if ($s -notmatch "^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$") { continue }
        $k = $Matches[1]; $nueva = "$k=$($Matches[2])"
        $i = [array]::FindIndex([string[]]$lineas, [Predicate[string]]{ param($x) $x -match "^\s*$k\s*=" })
        if ($i -ge 0) { if ($lineas[$i] -ne $nueva) { $lineas[$i] = $nueva; Write-Output "secreto actualizado: $k" } }
        else { $lineas += $nueva; Write-Output "secreto añadido: $k" }
    }
    [IO.File]::WriteAllLines($envHermes, [string[]]$lineas, (New-Object Text.UTF8Encoding $false))
}
# 5. Consentimiento de los hooks propios (el gateway no pregunta)
$allow = Join-Path $hermesHome "shell-hooks-allowlist.json"
$al = if (Test-Path $allow) { Get-Content $allow -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{ approvals = @() } }
$hooks = @(
    @{ event = "pre_tool_call"; command = "E:/asistente-hermes/scripts/hook_tope_delegacion.py" },
    @{ event = "pre_llm_call";  command = "E:/asistente-hermes/scripts/hook_aviso_juego.py" }
)
$cambio = $false
foreach ($h in $hooks) {
    if (-not ($al.approvals | Where-Object { $_.event -eq $h.event -and $_.command -eq $h.command })) {
        $al.approvals = @($al.approvals) + [pscustomobject]$h
        $cambio = $true
        Write-Output "hook aprobado: $($h.event) $($h.command)"
    }
}
if ($cambio) { [IO.File]::WriteAllText($allow, ($al | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false)) }

# 6. Vigía de juegos al iniciar sesión (descarga los modelos de la GPU si hay juego)
$inicio = [Environment]::GetFolderPath("Startup")
Copy-Item (Join-Path $repo "scripts/vigia.vbs") (Join-Path $inicio "AsistenteVigia.vbs") -Force
Write-Output "vigía en Inicio"
# 7. secretos\ solo accesible para el usuario actual y SYSTEM (en E: heredaría "Usuarios autentificados")
$sec = Join-Path $repo "secretos"
if (Test-Path $sec) {
    icacls $sec /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" /Q | Out-Null
    icacls "$sec\*" /reset /T /Q | Out-Null  # el contenido hereda de la carpeta (no /T arriba: deja archivos sin permisos)
    Write-Output "secretos: permisos restringidos"
}
Write-Output "aplicar.ps1: listo"
