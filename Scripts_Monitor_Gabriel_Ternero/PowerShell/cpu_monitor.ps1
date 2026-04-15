# ==============================================================================
#  cpu_monitor.ps1 - Monitor de CPU en PowerShell
#  Descripcion : Monitoriza en tiempo real el uso, frecuencia y carga del
#                procesador en sistemas Windows (Home, Pro y Server).
#  Requisitos  : PowerShell 5.1 o superior (incluido en Windows 10/11/Server).
#                Sin dependencias externas. Todo viene integrado en Windows.
#  Uso         : .\cpu_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  POLITICA DE EJECUCION
#  Resuelve el error "no esta firmado digitalmente" en Windows 11 Home
#  y el error de politica restringida en cualquier version de Windows.
#  -Scope Process -> solo afecta a esta sesion. No modifica nada permanente.
#  -Force         -> no pide confirmacion.
# ------------------------------------------------------------------------------
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
#  Modifica estos valores para ajustar el comportamiento del monitor.
# ==============================================================================
$IntervaloSegundos = 2      # Segundos entre cada actualizacion de pantalla
$UmbralAlertaCPU   = 85     # % de CPU a partir del cual se muestra alerta
$MostrarPorNucleo  = $true  # $true = muestra uso de cada nucleo individual


# ==============================================================================
#  INICIALIZACION DE CONTADORES DE RENDIMIENTO
#
#  Usamos [System.Diagnostics.PerformanceCounter] en lugar de Get-Counter.
#
#  ¿Por que? Get-Counter con -MaxSamples 1 siempre devuelve 0.0% para la CPU.
#  Los contadores de rendimiento de Windows necesitan DOS lecturas separadas
#  en el tiempo para calcular un porcentaje: miden la diferencia entre
#  el estado inicial y el estado actual.
#
#  Con una sola lectura no hay diferencia posible, resultado: siempre 0.
#
#  La solucion es crear el contador, hacer una primera lectura (que
#  descartamos porque siempre es 0), esperar 1 segundo y a partir de
#  ahi cada lectura ya devuelve el valor real.
#
#  Analogia: es como medir la velocidad de un coche. No puedes saber
#  a cuanto va mirando solo su posicion actual. Necesitas ver donde
#  estaba hace 1 segundo y donde esta ahora, y calcular la diferencia.
#  Eso es exactamente lo que hace el contador internamente.
#
#  Los parametros de PerformanceCounter son:
#    1. Categoria : el grupo del contador  (ej: "Processor")
#    2. Contador  : la metrica especifica  (ej: "% Processor Time")
#    3. Instancia : "_Total" para la suma de todos los nucleos,
#                   o "0","1","2"... para nucleos individuales
# ==============================================================================

Write-Host ""
Write-Host "  Iniciando monitor de CPU..." -ForegroundColor Cyan
Write-Host "  Calibrando contadores (espera 2 segundos)..." -ForegroundColor Gray
Write-Host ""

# Contador: uso total de CPU (suma de todos los nucleos)
$CntTotal = [System.Diagnostics.PerformanceCounter]::new(
    "Processor", "% Processor Time", "_Total"
)

# Contador: tiempo ejecutando aplicaciones del usuario
$CntUsuario = [System.Diagnostics.PerformanceCounter]::new(
    "Processor", "% User Time", "_Total"
)

# Contador: tiempo ejecutando el kernel de Windows
$CntSistema = [System.Diagnostics.PerformanceCounter]::new(
    "Processor", "% Privileged Time", "_Total"
)

# Contador: tiempo que la CPU esta sin hacer nada (idle)
$CntInactivo = [System.Diagnostics.PerformanceCounter]::new(
    "Processor", "% Idle Time", "_Total"
)

# Contador: cola del procesador (cuantos hilos esperan para ejecutarse)
# Es el equivalente en Windows al "load average" de Linux
$CntCola = [System.Diagnostics.PerformanceCounter]::new(
    "System", "Processor Queue Length", ""
)

# Primera lectura de todos los contadores: siempre devuelve 0, la descartamos.
# Es el "disparo de salida" que pone en marcha el mecanismo de medicion.
$null = $CntTotal.NextValue()
$null = $CntUsuario.NextValue()
$null = $CntSistema.NextValue()
$null = $CntInactivo.NextValue()
$null = $CntCola.NextValue()

# Esperamos para que los contadores tengan un intervalo de medicion real
Start-Sleep -Seconds 1

# Contadores individuales por nucleo
# Primero averiguamos cuantos nucleos logicos tiene el sistema
$InfoCPU        = Get-CimInstance -ClassName Win32_Processor
if ($InfoCPU -is [array]) { $InfoCPU = $InfoCPU[0] }
$TotalNucleosL  = $InfoCPU.NumberOfLogicalProcessors

$CntNucleos = @()   # Array vacio donde iremos guardando un contador por nucleo
for ($i = 0; $i -lt $TotalNucleosL; $i++) {
    $C = [System.Diagnostics.PerformanceCounter]::new(
        "Processor", "% Processor Time", "$i"
    )
    $null = $C.NextValue()   # Primera lectura de calibracion
    $CntNucleos += $C
}

# Segunda espera: ahora si todos los contadores tienen datos reales
Start-Sleep -Seconds 1
Write-Host "  Listo. Arrancando..." -ForegroundColor Green
Start-Sleep -Seconds 1


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

# --- Limpiar pantalla ---------------------------------------------------------
function Clear-Pantalla {
    Clear-Host
}


# --- Barra de progreso visual -------------------------------------------------
# Usamos # para los bloques rellenos y - para los vacios.
# Solo caracteres ASCII (codigos 32-126) para evitar problemas de codificacion
# en Windows en espanol con el juego de caracteres Windows-1252.
# Ejemplo: [##########----------] 50.0%
#
function Get-Barra {
    param(
        [double]$Pct,           # Porcentaje (0-100)
        [int]$Long = 20         # Anchura de la barra en caracteres
    )
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }

    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    $Barra  = ("#" * $Llenos) + ("-" * $Vacios)

    # {0} -> primer parametro (la barra)
    # {1:N1} -> segundo parametro, numero con 1 decimal
    # -f es el operador de formato, equivalente a los f-strings de Python
    return "[{0}] {1:N1}%" -f $Barra, $Pct
}


# --- Escribir barra con color segun nivel de uso ------------------------------
# Combina etiqueta + barra + color en una sola llamada.
# -NoNewline evita el salto de linea entre la etiqueta y la barra,
# igual que end="" en Python.
#
function Write-Uso {
    param(
        [string]$Etiqueta,
        [double]$Pct,
        [int]$Umbral = 85
    )
    $Barra = Get-Barra -Pct $Pct

    if      ($Pct -lt 50)     { $Color = "Green"  }
    elseif  ($Pct -lt $Umbral){ $Color = "Yellow" }
    else                      { $Color = "Red"    }

    # {0,-15} -> alinea la etiqueta a la izquierda en 15 caracteres
    Write-Host ("   {0,-15}" -f $Etiqueta) -NoNewline
    Write-Host $Barra -ForegroundColor $Color
}


# --- Obtener frecuencia del procesador ----------------------------------------
# CurrentClockSpeed es la frecuencia actual que reporta el hardware.
# MaxClockSpeed es la frecuencia maxima de fabrica.
# Ambas vienen en MHz desde WMI, las convertimos a GHz dividiendo entre 1000.
#
function Get-Frecuencia {
    $CPU = Get-CimInstance -ClassName Win32_Processor
    if ($CPU -is [array]) { $CPU = $CPU[0] }
    return @{
        Actual = $CPU.CurrentClockSpeed   # MHz
        Maxima = $CPU.MaxClockSpeed       # MHz
    }
}


# ==============================================================================
#  FUNCION PRINCIPAL: leer datos y construir la pantalla
# ==============================================================================
function Show-CPU {

    # --- Leer todos los contadores en este ciclo ------------------------------
    # Cada llamada a NextValue() devuelve el uso desde la ultima lectura.
    # Como los contadores estan activos desde el inicio, el intervalo
    # de medicion es el tiempo real transcurrido entre ciclos.
    $UsoCPU   = [math]::Round($CntTotal.NextValue(),    1)
    $PctUsr   = [math]::Round($CntUsuario.NextValue(),  1)
    $PctSys   = [math]::Round($CntSistema.NextValue(),  1)
    $PctIdle  = [math]::Round($CntInactivo.NextValue(), 1)
    $Cola     = [int]$CntCola.NextValue()

    # Uso de cada nucleo
    $UsosNucleo = @()
    foreach ($C in $CntNucleos) {
        $UsosNucleo += [math]::Round($C.NextValue(), 1)
    }

    # --- Leer datos estaticos del sistema -------------------------------------
    # Estos datos no cambian con el tiempo, no necesitan PerformanceCounter
    $CPU            = Get-CimInstance -ClassName Win32_Processor
    if ($CPU -is [array]) { $CPU = $CPU[0] }

    $NucleosFis     = $CPU.NumberOfCores
    $NucleosLog     = $CPU.NumberOfLogicalProcessors
    $Frecuencia     = Get-Frecuencia

    $SO             = Get-CimInstance -ClassName Win32_OperatingSystem
    $Uptime         = (Get-Date) - $SO.LastBootUpTime
    $Ahora          = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    #  Solo caracteres ASCII en separadores y textos para evitar
    #  problemas de codificacion en Windows en espanol.
    # ==========================================================================
    Clear-Pantalla

    # Cabecera
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host "  MONITOR DE CPU - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 62) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  SECCION 1: Uso global
    # --------------------------------------------------------------------------
    Write-Host "`nUSO GLOBAL DE CPU" -ForegroundColor White
    Write-Uso -Etiqueta "Total CPU" -Pct $UsoCPU -Umbral $UmbralAlertaCPU

    if ($UsoCPU -ge $UmbralAlertaCPU) {
        Write-Host "`n   ALERTA: CPU al $UsoCPU% - uso muy elevado" `
                   -ForegroundColor Red
    }

    # --------------------------------------------------------------------------
    #  SECCION 2: Informacion del procesador
    # --------------------------------------------------------------------------
    Write-Host "`nPROCESADOR" -ForegroundColor White
    Write-Host ("   Modelo   : {0}" -f $CPU.Name.Trim())
    Write-Host ("   Fisicos  : {0} nucleos" -f $NucleosFis)
    Write-Host ("   Logicos  : {0} nucleos" -f $NucleosLog)

    # --------------------------------------------------------------------------
    #  SECCION 3: Frecuencia
    # --------------------------------------------------------------------------
    Write-Host "`nFRECUENCIA" -ForegroundColor White
    Write-Host ("   Actual   : {0:N2} GHz" -f ($Frecuencia.Actual / 1000))
    Write-Host ("   Maxima   : {0:N2} GHz" -f ($Frecuencia.Maxima / 1000))

    # --------------------------------------------------------------------------
    #  SECCION 4: Uso por nucleo
    # --------------------------------------------------------------------------
    if ($MostrarPorNucleo -and $UsosNucleo.Count -gt 0) {
        Write-Host "`nUSO POR NUCLEO" -ForegroundColor White
        for ($i = 0; $i -lt $UsosNucleo.Count; $i++) {
            Write-Uso -Etiqueta ("Nucleo {0:D2}" -f $i) -Pct $UsosNucleo[$i]
        }
    }

    # --------------------------------------------------------------------------
    #  SECCION 5: Cola del procesador
    #  Cola = 0             -> CPU sin presion, todo fluye
    #  Cola <= nucleos      -> carga manejable
    #  Cola >  nucleos      -> hay mas trabajo del que la CPU puede atender
    # --------------------------------------------------------------------------
    Write-Host "`nCOLA DEL PROCESADOR" -ForegroundColor White
    Write-Host ("   Hilos en espera : {0}" -f $Cola) -NoNewline

    if     ($Cola -eq 0)                               { Write-Host "  (sin presion)"  -ForegroundColor Green  }
    elseif ($Cola -gt 0 -and $Cola -le $NucleosLog)    { Write-Host "  (carga normal)" -ForegroundColor Yellow }
    elseif ($Cola -gt $NucleosLog)                     { Write-Host "  SOBRECARGA"      -ForegroundColor Red   }
    else                                               { Write-Host "  (no disponible)"                        }

    # --------------------------------------------------------------------------
    #  SECCION 6: Desglose de tiempo de CPU
    #  Usuario    -> tiempo ejecutando aplicaciones del usuario
    #  Sistema    -> tiempo ejecutando el kernel de Windows
    #  Inactivo   -> tiempo que la CPU no tiene nada que hacer
    # --------------------------------------------------------------------------
    Write-Host "`nDESGLOSE DE TIEMPO DE CPU" -ForegroundColor White
    Write-Host ("   Usuario  (aplicaciones)  : {0,6:N1}%" -f $PctUsr)
    Write-Host ("   Sistema  (kernel Windows): {0,6:N1}%" -f $PctSys)
    Write-Host ("   Inactivo (idle)          : {0,6:N1}%" -f $PctIdle)

    # --------------------------------------------------------------------------
    #  SECCION 7: Informacion del sistema
    # --------------------------------------------------------------------------
    Write-Host "`nSISTEMA" -ForegroundColor White
    Write-Host ("   Version  : {0}" -f $SO.Caption)
    Write-Host ("   Encendido: {0}d {1}h {2}m" -f `
                $Uptime.Days, $Uptime.Hours, $Uptime.Minutes)

    # Pie
    Write-Host ("`n" + "=" * 62) -ForegroundColor Cyan
    Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f `
                $IntervaloSegundos) -ForegroundColor Gray
    Write-Host ("=" * 62) -ForegroundColor Cyan
}


# ==============================================================================
#  BUCLE PRINCIPAL
#  try/finally garantiza que la limpieza de recursos y el mensaje de
#  despedida se ejecuten SIEMPRE, tanto si el usuario pulsa Ctrl+C
#  como si ocurre cualquier otro error inesperado.
# ==============================================================================
function Start-Monitor {
    try {
        while ($true) {
            Show-CPU
            Start-Sleep -Seconds $IntervaloSegundos
        }
    }
    finally {
        # Liberamos todos los objetos .NET de los contadores.
        # Dispose() libera los recursos del sistema que tiene reservados
        # el contador. Es buena practica hacerlo siempre con objetos .NET.
        $CntTotal.Dispose()
        $CntUsuario.Dispose()
        $CntSistema.Dispose()
        $CntInactivo.Dispose()
        $CntCola.Dispose()
        foreach ($C in $CntNucleos) { $C.Dispose() }

        Write-Host "`n`n  Monitor detenido. Hasta luego!" -ForegroundColor Green
    }
}


# ==============================================================================
#  PUNTO DE ENTRADA
#  $MyInvocation.InvocationName contiene '.' cuando el script se carga
#  con dot-sourcing desde menu.ps1 (. .\cpu_monitor.ps1).
#  En ese caso solo cargamos las funciones sin ejecutar el monitor.
#  Si se ejecuta directamente, el valor es la ruta del script y arrancamos.
#  Es el equivalente de if __name__ == "__main__" de Python.
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Start-Monitor
}
