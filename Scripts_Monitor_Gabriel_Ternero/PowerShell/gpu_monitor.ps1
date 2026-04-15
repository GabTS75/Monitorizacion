# ==============================================================================
#  gpu_monitor.ps1 - Monitor de GPU en PowerShell
#  Descripcion : Monitoriza en tiempo real el uso, memoria y temperatura
#                de la tarjeta grafica del sistema.
#  Requisitos  : PowerShell 5.1 o superior.
#                NVIDIA: drivers oficiales con nvidia-smi instalado.
#                AMD/Intel: LibreHardwareMonitor con WMI activo.
#  Uso         : .\gpu_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  FUENTES DE DATOS PARA LA GPU EN WINDOWS
#
#  Al igual que en Python, psutil no puede leer la GPU. En PowerShell
#  tampoco hay una API universal. Usamos tres enfoques:
#
#  1. nvidia-smi (NVIDIA)
#     Herramienta oficial de NVIDIA incluida con los drivers.
#     Disponible en Windows y Linux si tienes GPU NVIDIA.
#     Devuelve todos los datos: uso, VRAM, temperatura, consumo...
#
#  2. LibreHardwareMonitor via WMI (AMD / Intel / cualquier GPU)
#     Si LHM esta en ejecucion con Remote Web Server activo,
#     expone sensores de GPU en root\LibreHardwareMonitor.
#     Funciona con NVIDIA, AMD e Intel integradas.
#
#  3. Win32_VideoController via CIM (informacion estatica)
#     Solo da datos estaticos: nombre, VRAM total, driver, resolucion.
#     No tiene uso en tiempo real ni temperatura.
#     Util como fallback para mostrar al menos la GPU detectada.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos  = 3
$UmbralUsoGPU       = 90     # % de uso a partir del cual alertamos
$UmbralTempWarn     = 75     # Temperatura de advertencia en Celsius
$UmbralTempCrit     = 90     # Temperatura critica en Celsius


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }

function Get-BytesLegibles {
    param([long]$Bytes)
    if     ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    elseif ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    elseif ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    else                    { return "$Bytes B"                     }
}

function Get-Barra {
    param([double]$Pct, [int]$Long = 20)
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}] {1:N1}%" -f (("#" * $Llenos) + ("-" * $Vacios)), $Pct
}

function Get-ColorNivel {
    param([double]$Pct, [int]$UmbralWarn = 70, [int]$UmbralCrit = 90)
    if     ($Pct -ge $UmbralCrit) { return "Red"    }
    elseif ($Pct -ge $UmbralWarn) { return "Yellow" }
    else                          { return "Green"  }
}

function Get-ColorTemp {
    param([double]$Temp)
    if     ($Temp -ge $UmbralTempCrit) { return "Red"    }
    elseif ($Temp -ge $UmbralTempWarn) { return "Yellow" }
    else                               { return "Green"  }
}


# ==============================================================================
#  METODO 1: NVIDIA via nvidia-smi
# ==============================================================================

function Test-NvidiaSmi {
    # Comprobamos si nvidia-smi existe en el PATH del sistema
    # Get-Command devuelve $null si el comando no existe
    $Cmd = Get-Command "nvidia-smi" -ErrorAction SilentlyContinue
    return ($null -ne $Cmd)
}

function Get-DatosNVIDIA {
    <#
    Ejecuta nvidia-smi con formato CSV y parsea la salida.
    Devuelve una lista de hashtables, una por GPU detectada.
    #>
    $Campos = @(
        "index",
        "name",
        "driver_version",
        "temperature.gpu",
        "fan.speed",
        "utilization.gpu",
        "utilization.memory",
        "memory.total",
        "memory.used",
        "memory.free",
        "power.draw",
        "power.limit",
        "clocks.current.graphics",
        "clocks.current.memory"
    )

    $Consulta = $Campos -join ","

    try {
        # Ejecutamos nvidia-smi y capturamos su salida
        # /C ejecuta el comando y cierra la ventana
        $Salida = & nvidia-smi "--query-gpu=$Consulta" "--format=csv,noheader,nounits" `
                               2>$null

        if (-not $Salida) { return @() }

        $GPUs = @()

        foreach ($Linea in $Salida) {
            $Valores = $Linea -split ',' | ForEach-Object { $_.Trim() }
            if ($Valores.Count -lt $Campos.Count) { continue }

            # Funcion auxiliar para convertir a numero o devolver $null
            $ToFloat = {
                param($Val)
                $Val = $Val -replace '\[N/A\]','' -replace 'N/A',''
                $Val = $Val.Trim()
                if ($Val -eq "") { return $null }
                try { return [double]$Val } catch { return $null }
            }

            $GPUs += @{
                Indice     = $Valores[0]
                Nombre     = $Valores[1]
                Driver     = $Valores[2]
                Temp       = & $ToFloat $Valores[3]
                VentPct    = & $ToFloat $Valores[4]
                UsoGPU     = & $ToFloat $Valores[5]
                UsoVRAM    = & $ToFloat $Valores[6]
                VRAMTotalMB= & $ToFloat $Valores[7]
                VRAMUsadaMB= & $ToFloat $Valores[8]
                VRAMLibreMB= & $ToFloat $Valores[9]
                ConsumoW   = & $ToFloat $Valores[10]
                LimiteW    = & $ToFloat $Valores[11]
                FreqCore   = & $ToFloat $Valores[12]
                FreqVRAM   = & $ToFloat $Valores[13]
            }
        }
        return $GPUs
    }
    catch {
        return @()
    }
}


# ==============================================================================
#  METODO 2: LibreHardwareMonitor via WMI
# ==============================================================================

function Get-DatosLHM_GPU {
    try {
        $Sensores = Get-CimInstance -Namespace "root\LibreHardwareMonitor" `
                                    -ClassName "Sensor" -ErrorAction Stop

        # Agrupamos los sensores por hardware (cada GPU es un hardware distinto)
        $GPUs = @{}

        foreach ($S in $Sensores) {
            # Filtramos solo sensores de GPU
            if ($S.Parent -notmatch "gpu|nvidia|amd|radeon|geforce|intel.*graphics" `
                -and $S.SensorType -notin @("Load","Temperature","Fan","Power","Clock","SmallData")) {
                continue
            }

            # Solo procesamos sensores de estos tipos relevantes para GPU
            if ($S.SensorType -notin @("Load","Temperature","Fan","Power","Clock","SmallData")) {
                continue
            }

            if (-not $GPUs.ContainsKey($S.Parent)) {
                $GPUs[$S.Parent] = @{
                    Nombre     = $S.Parent
                    Sensores   = @()
                }
            }
            $GPUs[$S.Parent].Sensores += $S
        }

        return $GPUs
    }
    catch {
        return @{}
    }
}


# ==============================================================================
#  METODO 3: Win32_VideoController (informacion estatica)
# ==============================================================================

function Get-GPUEstatica {
    $GPUs = Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue
    return $GPUs
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-GPU {

    $Ahora   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $TieneNV = Test-NvidiaSmi
    $GPUsNV  = if ($TieneNV) { Get-DatosNVIDIA } else { @() }
    $GPUsLHM = Get-DatosLHM_GPU
    $GPUsWMI = Get-GPUEstatica

    Clear-Pantalla

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  MONITOR DE GPU - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  CASO 1: NVIDIA con nvidia-smi disponible
    # --------------------------------------------------------------------------
    if ($TieneNV -and $GPUsNV.Count -gt 0) {

        Write-Host "`n  [OK] NVIDIA nvidia-smi detectado - $($GPUsNV.Count) GPU(s)" `
                   -ForegroundColor Green

        foreach ($GPU in $GPUsNV) {
            Write-Host "`n  $("-" * 63)" -ForegroundColor DarkGray
            Write-Host ("  GPU #{0}  -  {1}" -f $GPU.Indice, $GPU.Nombre) `
                       -ForegroundColor White
            Write-Host ("  Driver: {0}" -f $GPU.Driver) -ForegroundColor Gray
            Write-Host ""

            # Uso del nucleo grafico
            if ($null -ne $GPU.UsoGPU) {
                $Color = Get-ColorNivel -Pct $GPU.UsoGPU -UmbralWarn 70 -UmbralCrit $UmbralUsoGPU
                Write-Host "  USO DEL NUCLEO GRAFICO" -ForegroundColor White
                Write-Host ("     {0}" -f (Get-Barra -Pct $GPU.UsoGPU)) -ForegroundColor $Color
                if ($GPU.UsoGPU -ge $UmbralUsoGPU) {
                    Write-Host ("     ALERTA: GPU al {0:N0}% - carga muy elevada" -f $GPU.UsoGPU) `
                               -ForegroundColor Red
                }
                Write-Host ""
            }

            # Memoria VRAM
            if ($null -ne $GPU.UsoVRAM) {
                $Color = Get-ColorNivel -Pct $GPU.UsoVRAM -UmbralWarn 70 -UmbralCrit 90
                Write-Host "  MEMORIA VRAM" -ForegroundColor White
                Write-Host ("     {0}" -f (Get-Barra -Pct $GPU.UsoVRAM)) -ForegroundColor $Color
                if ($null -ne $GPU.VRAMTotalMB) {
                    $TotalB = $GPU.VRAMTotalMB * 1MB
                    $UsadaB = $GPU.VRAMUsadaMB * 1MB
                    $LibreB = $GPU.VRAMLibreMB * 1MB
                    Write-Host ("     Total : {0,10}" -f (Get-BytesLegibles $TotalB))
                    Write-Host ("     Usada : {0,10}" -f (Get-BytesLegibles $UsadaB))
                    Write-Host ("     Libre : {0,10}" -f (Get-BytesLegibles $LibreB))
                }
                Write-Host ""
            }

            # Temperatura
            if ($null -ne $GPU.Temp) {
                $Color = Get-ColorTemp -Temp $GPU.Temp
                $BarraT= Get-Barra -Pct ([math]::Min(($GPU.Temp / 110) * 100, 100))
                Write-Host "  TEMPERATURA" -ForegroundColor White
                Write-Host ("     {0:N1} C   {1}" -f $GPU.Temp, $BarraT) -ForegroundColor $Color
                if ($GPU.Temp -ge $UmbralTempCrit) {
                    Write-Host "     TEMPERATURA CRITICA - revisa la refrigeracion" `
                               -ForegroundColor Red
                }
                Write-Host ""
            }

            # Ventilador
            if ($null -ne $GPU.VentPct) {
                $Color = Get-ColorNivel -Pct $GPU.VentPct -UmbralWarn 60 -UmbralCrit 90
                Write-Host "  VENTILADOR" -ForegroundColor White
                Write-Host ("     {0}" -f (Get-Barra -Pct $GPU.VentPct)) -ForegroundColor $Color
                Write-Host ""
            }

            # Consumo energetico
            if ($null -ne $GPU.ConsumoW -and $null -ne $GPU.LimiteW) {
                $PctConsumo = if ($GPU.LimiteW -gt 0) {
                    ($GPU.ConsumoW / $GPU.LimiteW) * 100
                } else { 0 }
                $Color = Get-ColorNivel -Pct $PctConsumo -UmbralWarn 80 -UmbralCrit 95
                Write-Host "  CONSUMO ENERGETICO" -ForegroundColor White
                Write-Host ("     Actual : {0:N1} W" -f $GPU.ConsumoW)
                Write-Host ("     Limite : {0:N1} W" -f $GPU.LimiteW)
                Write-Host ("     {0}" -f (Get-Barra -Pct $PctConsumo)) -ForegroundColor $Color
                Write-Host ""
            }

            # Frecuencias
            if ($null -ne $GPU.FreqCore) {
                Write-Host "  FRECUENCIAS" -ForegroundColor White
                Write-Host ("     Nucleo grafico : {0:N0} MHz" -f $GPU.FreqCore)
                if ($null -ne $GPU.FreqVRAM) {
                    Write-Host ("     Memoria VRAM   : {0:N0} MHz" -f $GPU.FreqVRAM)
                }
                Write-Host ""
            }
        }

    # --------------------------------------------------------------------------
    #  CASO 2: LibreHardwareMonitor con sensores de GPU
    # --------------------------------------------------------------------------
    } elseif ($GPUsLHM.Count -gt 0) {

        Write-Host "`n  [OK] LibreHardwareMonitor detectado" -ForegroundColor Green
        Write-Host ""

        foreach ($NombreGPU in $GPUsLHM.Keys) {
            $GPU = $GPUsLHM[$NombreGPU]

            Write-Host ("  $("-" * 63)") -ForegroundColor DarkGray
            Write-Host ("  {0}" -f $NombreGPU) -ForegroundColor White
            Write-Host ""

            foreach ($S in $GPU.Sensores) {
                switch ($S.SensorType) {
                    "Load" {
                        if ($S.Value -ne $null) {
                            $Color = Get-ColorNivel -Pct $S.Value
                            Write-Host ("  {0,-25} {1}" -f $S.Name, (Get-Barra -Pct $S.Value)) `
                                       -ForegroundColor $Color
                        }
                    }
                    "Temperature" {
                        if ($S.Value -ne $null) {
                            $Color = Get-ColorTemp -Temp $S.Value
                            $Barra = Get-Barra -Pct ([math]::Min(($S.Value/110)*100,100))
                            Write-Host ("  {0,-25} {1:N1} C  {2}" -f $S.Name, $S.Value, $Barra) `
                                       -ForegroundColor $Color
                        }
                    }
                    "Fan" {
                        if ($S.Value -ne $null) {
                            Write-Host ("  {0,-25} {1:N0} RPM" -f $S.Name, $S.Value)
                        }
                    }
                    "Power" {
                        if ($S.Value -ne $null) {
                            Write-Host ("  {0,-25} {1:N1} W" -f $S.Name, $S.Value)
                        }
                    }
                    "Clock" {
                        if ($S.Value -ne $null) {
                            Write-Host ("  {0,-25} {1:N0} MHz" -f $S.Name, $S.Value) `
                                       -ForegroundColor Gray
                        }
                    }
                    "SmallData" {
                        if ($S.Value -ne $null) {
                            Write-Host ("  {0,-25} {1:N1} MB" -f $S.Name, $S.Value) `
                                       -ForegroundColor Gray
                        }
                    }
                }
            }
            Write-Host ""
        }

    # --------------------------------------------------------------------------
    #  CASO 3: Solo informacion estatica via WMI
    # --------------------------------------------------------------------------
    } else {

        Write-Host ""
        Write-Host "  [--] nvidia-smi no encontrado" -ForegroundColor DarkGray
        Write-Host "  [--] LibreHardwareMonitor no detectado" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  Solo se puede mostrar informacion estatica:" -ForegroundColor Yellow
        Write-Host ""

        if ($GPUsWMI) {
            foreach ($GPU in $GPUsWMI) {
                Write-Host ("  Nombre   : {0}" -f $GPU.Name) -ForegroundColor White
                if ($GPU.AdapterRAM -and $GPU.AdapterRAM -gt 0) {
                    Write-Host ("  VRAM     : {0}" -f (Get-BytesLegibles $GPU.AdapterRAM))
                }
                Write-Host ("  Driver   : {0}" -f $GPU.DriverVersion)
                Write-Host ("  Resolucion: {0} x {1}" -f `
                    $GPU.CurrentHorizontalResolution, $GPU.CurrentVerticalResolution)
                Write-Host ""
            }
        }

        Write-Host "$("-" * 65)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  Para monitorizar en tiempo real:" -ForegroundColor White
        Write-Host ""
        Write-Host "  GPU NVIDIA:" -ForegroundColor Cyan
        Write-Host "    Instala los drivers oficiales desde:"
        Write-Host "    https://www.nvidia.com/drivers"
        Write-Host ""
        Write-Host "  GPU AMD o Intel:" -ForegroundColor Cyan
        Write-Host "    Instala LibreHardwareMonitor con WMI activo:"
        Write-Host "    https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
        Write-Host "    Options -> Remote Web Server -> Run"
        Write-Host ""
        Write-Host "  Alternativas con interfaz grafica:" -ForegroundColor White
        Write-Host "    GPU-Z      https://www.techpowerup.com/gpuz"
        Write-Host "    HWiNFO64   https://www.hwinfo.com"
        Write-Host "    MSI Afterburner (NVIDIA/AMD)"
    }

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f $IntervaloSegundos) `
               -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan
}


# ==============================================================================
#  BUCLE PRINCIPAL
# ==============================================================================
function Start-Monitor {
    Write-Host "  Iniciando monitor de GPU..." -ForegroundColor Cyan
    Start-Sleep -Seconds 1

    try {
        while ($true) {
            Show-GPU
            Start-Sleep -Seconds $IntervaloSegundos
        }
    }
    finally {
        Write-Host "`n`n  Monitor detenido. Hasta luego!" -ForegroundColor Green
    }
}


# ==============================================================================
#  PUNTO DE ENTRADA
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Start-Monitor
}
