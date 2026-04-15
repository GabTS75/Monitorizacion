# ==============================================================================
#  memoria_monitor.ps1 - Monitor de Memoria RAM en PowerShell
#  Descripcion : Monitoriza en tiempo real el uso de la memoria RAM y la
#                memoria virtual (pagina de Windows), mostrando los datos
#                actualizados en pantalla con alertas visuales.
#  Requisitos  : PowerShell 5.1 o superior (incluido en Windows 10/11/Server).
#                Sin dependencias externas.
#  Uso         : .\memoria_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  NOTA SOBRE LA MEMORIA EN WINDOWS vs LINUX
#
#  En Linux hablamos de RAM y Swap.
#  En Windows los conceptos equivalentes son:
#
#  RAM fisica     -> la memoria real instalada en el equipo (los modulos DDR)
#
#  Memoria virtual (pagina) -> archivo en el disco duro que Windows usa como
#                              extension de la RAM cuando esta se llena.
#                              Es el equivalente exacto al Swap de Linux.
#                              Por defecto Windows lo gestiona automaticamente
#                              y se llama "pagefile.sys" en la raiz de C:\
#
#  Memoria disponible       -> RAM libre + RAM en cache reutilizable.
#                              Es el dato mas util en la practica porque
#                              indica cuanta memoria puede usar una nueva
#                              aplicacion en este momento.
#
#  Memoria en uso           -> RAM ocupada por aplicaciones y el sistema.
#
#  Analogia: la RAM es la mesa de trabajo. El archivo de pagina es una
#  mesa auxiliar en el pasillo: mas lenta y lejana, pero sirve de apoyo
#  cuando la principal se llena.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos  = 2     # Segundos entre cada actualizacion de pantalla
$UmbralAlertaRAM    = 85    # % de RAM a partir del cual se muestra alerta
$UmbralAlertaPagina = 50    # % de pagina a partir del cual se muestra alerta
                             # La pagina se vigila antes que la RAM porque
                             # su uso elevado ya indica presion en el sistema


# ==============================================================================
#  INICIALIZACION DE CONTADORES DE RENDIMIENTO
#
#  Igual que en cpu_monitor.ps1, usamos PerformanceCounter en lugar de
#  Get-Counter para obtener valores reales en lugar de 0.0%.
#
#  Los contadores de memoria que usamos:
#
#  "Memory" \ "Available Bytes"
#      -> bytes de RAM disponibles en este momento (libre + cache)
#         Es el dato mas importante: cuanto puede usar una app nueva.
#
#  "Memory" \ "Pages/sec"
#      -> numero de paginas por segundo que Windows mueve entre RAM y disco.
#         Un valor alto y sostenido indica que el sistema esta bajo presion
#         de memoria: tiene que ir al disco constantemente a buscar datos.
#         Analogia: es como el numero de veces por segundo que el cocinero
#         tiene que ir al armario porque la encimera esta llena.
#
#  "Memory" \ "Page Faults/sec"
#      -> fallos de pagina por segundo. Ocurre cuando un proceso necesita
#         datos que no estan en RAM y hay que traerlos del disco o generarlos.
#         Algunos son normales, muchos indican falta de memoria.
#
#  "Paging File(_Total)" \ "% Usage"
#      -> porcentaje de uso del archivo de pagina (Swap de Windows).
#         Si sube mucho, el sistema esta usando el disco como RAM de emergencia.
# ==============================================================================

Write-Host ""
Write-Host "  Iniciando monitor de memoria..." -ForegroundColor Cyan
Write-Host "  Calibrando contadores (espera 2 segundos)..." -ForegroundColor Gray
Write-Host ""

$CntDisponible  = [System.Diagnostics.PerformanceCounter]::new(
    "Memory", "Available Bytes", ""
)
$CntPaginas     = [System.Diagnostics.PerformanceCounter]::new(
    "Memory", "Pages/sec", ""
)
$CntFallosPag   = [System.Diagnostics.PerformanceCounter]::new(
    "Memory", "Page Faults/sec", ""
)
$CntUsoPagina   = [System.Diagnostics.PerformanceCounter]::new(
    "Paging File", "% Usage", "_Total"
)

# Primera lectura de calibracion: siempre devuelve 0, la descartamos
$null = $CntDisponible.NextValue()
$null = $CntPaginas.NextValue()
$null = $CntFallosPag.NextValue()
$null = $CntUsoPagina.NextValue()

Start-Sleep -Seconds 1

# Segunda espera: ahora los contadores tienen datos reales
Start-Sleep -Seconds 1

Write-Host "  Listo. Arrancando..." -ForegroundColor Green
Start-Sleep -Seconds 1


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }


# --- Convertir bytes a unidad legible -----------------------------------------
# La memoria se mide internamente en bytes pero nosotros pensamos en GB.
# Esta funcion hace la conversion automaticamente eligiendo la unidad
# mas adecuada segun el tamano del valor.
# Ejemplo: 8589934592 bytes -> "8.00 GB"
#
function Get-BytesLegibles {
    param([long]$Bytes)

    if     ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    elseif ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    elseif ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    else                    { return "$Bytes B"                     }
}
# Nota: en PowerShell 1KB, 1MB, 1GB y 1TB son constantes integradas.
# 1KB = 1024, 1MB = 1048576, 1GB = 1073741824. No hay que calcularlos.


# --- Barra de progreso con caracteres ASCII ----------------------------------
function Get-Barra {
    param(
        [double]$Pct,
        [int]$Long = 25
    )
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }

    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    $Barra  = ("#" * $Llenos) + ("-" * $Vacios)
    return "[{0}] {1:N1}%" -f $Barra, $Pct
}


# --- Escribir barra con color -------------------------------------------------
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

    Write-Host ("   {0,-14}" -f $Etiqueta) -NoNewline
    Write-Host $Barra -ForegroundColor $Color
}


# --- Escribir linea de detalle alineada ---------------------------------------
# Muestra una etiqueta y su valor alineados en columnas.
# Ejemplo:   Total instalada  :    16.00 GB
#
function Write-Detalle {
    param(
        [string]$Etiqueta,
        [string]$Valor
    )
    Write-Host ("   {0,-20} : {1,12}" -f $Etiqueta, $Valor)
}


# --- Diagnostico de salud de la memoria ---------------------------------------
# Evalua el estado general y devuelve un texto con color.
# Tres niveles: bien (verde), vigilancia (amarillo), presion (rojo).
#
function Write-Diagnostico {
    param(
        [double]$PctRAM,
        [double]$PctPagina,
        [double]$PaginasSeg
    )

    $Critico  = ($PctRAM -ge $UmbralAlertaRAM) -or ($PctPagina -ge $UmbralAlertaPagina)
    $Vigilar  = ($PctRAM -ge 60) -or ($PctPagina -ge 30) -or ($PaginasSeg -gt 100)

    if ($Critico) {
        Write-Host "   ESTADO: MEMORIA BAJO ALTA PRESION" -ForegroundColor Red
        Write-Host "   El sistema esta usando disco como RAM de emergencia." -ForegroundColor Red
        Write-Host "   Cierra aplicaciones o considera ampliar la RAM." -ForegroundColor Yellow
    } elseif ($Vigilar) {
        Write-Host "   ESTADO: Memoria bajo vigilancia" -ForegroundColor Yellow
        Write-Host "   El uso es elevado. Monitoriza la tendencia." -ForegroundColor Yellow
    } else {
        Write-Host "   ESTADO: Memoria en buen estado" -ForegroundColor Green
    }
}


# ==============================================================================
#  FUNCION PRINCIPAL: leer datos y construir la pantalla
# ==============================================================================
function Show-Memoria {

    $Ahora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # --- Leer contadores de rendimiento ---------------------------------------
    # Bytes disponibles de RAM en este momento
    $BytesDisponibles = [long]$CntDisponible.NextValue()

    # Paginas movidas entre RAM y disco por segundo
    # Un valor alto y sostenido indica falta de memoria
    $PaginasPorSeg = [math]::Round($CntPaginas.NextValue(), 1)

    # Fallos de pagina por segundo
    $FallosPorSeg  = [math]::Round($CntFallosPag.NextValue(), 1)

    # Porcentaje de uso del archivo de pagina (Swap de Windows)
    $PctPagina     = [math]::Round($CntUsoPagina.NextValue(), 1)

    # --- Leer datos de RAM desde Win32_OperatingSystem ------------------------
    # Esta clase de WMI nos da el total y los valores actuales de memoria.
    # TotalVisibleMemorySize -> RAM total instalada (en KB)
    # FreePhysicalMemory     -> RAM libre en este momento (en KB)
    # TotalVirtualMemorySize -> RAM + archivo de pagina combinados (en KB)
    # FreeVirtualMemory      -> virtual disponible en este momento (en KB)
    $SO = Get-CimInstance -ClassName Win32_OperatingSystem

    # Convertimos de KB a bytes multiplicando por 1KB (= 1024)
    $RAMTotal      = $SO.TotalVisibleMemorySize * 1KB
    $RAMLibre      = $SO.FreePhysicalMemory     * 1KB

    # RAM usada = total - libre
    $RAMUsada      = $RAMTotal - $RAMLibre

    # Porcentaje de uso de RAM
    $PctRAM        = [math]::Round(($RAMUsada / $RAMTotal) * 100, 1)

    # Memoria disponible (del contador, mas precisa que FreePhysicalMemory)
    # porque incluye la cache del sistema que puede ser reutilizada
    $PctDisponible = [math]::Round(($BytesDisponibles / $RAMTotal) * 100, 1)

    # --- Datos del archivo de pagina desde Win32_PageFileUsage ---------------
    # Esta clase nos da el tamano y uso actual del archivo de pagina.
    # AllocatedBaseSize -> tamano del archivo de pagina en MB
    # CurrentUsage      -> uso actual en MB
    $Pagina = Get-CimInstance -ClassName Win32_PageFileUsage
    $PaginaTotalMB = 0
    $PaginaUsadaMB = 0
    if ($Pagina) {
        # Puede haber varios archivos de pagina en distintas unidades.
        # Sumamos todos para tener el total del sistema.
        foreach ($P in $Pagina) {
            $PaginaTotalMB += $P.AllocatedBaseSize
            $PaginaUsadaMB += $P.CurrentUsage
        }
    }
    $PaginaTotalBytes = $PaginaTotalMB * 1MB
    $PaginaUsadaBytes = $PaginaUsadaMB * 1MB

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host "  MONITOR DE MEMORIA - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 62) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  SECCION 1: Uso de RAM
    # --------------------------------------------------------------------------
    Write-Host "`nUSO DE MEMORIA RAM" -ForegroundColor White
    Write-Uso -Etiqueta "RAM en uso" -Pct $PctRAM -Umbral $UmbralAlertaRAM

    if ($PctRAM -ge $UmbralAlertaRAM) {
        Write-Host "`n   ALERTA: RAM al $PctRAM% - riesgo de lentitud" `
                   -ForegroundColor Red
    }

    # --------------------------------------------------------------------------
    #  SECCION 2: Desglose de RAM
    # --------------------------------------------------------------------------
    Write-Host "`nDESGLOSE DE RAM" -ForegroundColor White
    Write-Detalle -Etiqueta "Total instalada"  -Valor (Get-BytesLegibles $RAMTotal)
    Write-Detalle -Etiqueta "En uso"           -Valor (Get-BytesLegibles $RAMUsada)
    Write-Detalle -Etiqueta "Disponible"       -Valor (Get-BytesLegibles $BytesDisponibles)
    Write-Detalle -Etiqueta "Libre"            -Valor (Get-BytesLegibles $RAMLibre)

    # Mostramos tambien la distribucion visual de los componentes
    Write-Host "`nDISTRIBUCION VISUAL" -ForegroundColor White
    Write-Uso -Etiqueta "En uso"      -Pct $PctRAM        -Umbral $UmbralAlertaRAM
    Write-Uso -Etiqueta "Disponible"  -Pct $PctDisponible -Umbral 100

    # --------------------------------------------------------------------------
    #  SECCION 3: Archivo de pagina (Swap de Windows)
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 62)" -ForegroundColor DarkGray
    Write-Host "`nARCHIVO DE PAGINA (equivalente al Swap de Linux)" -ForegroundColor White

    if ($PaginaTotalMB -eq 0) {
        Write-Host "   No hay archivo de pagina configurado." -ForegroundColor Gray
        Write-Host "   (Inusual en Windows - puede ser una VM sin pagefile)" -ForegroundColor Gray
    } else {
        Write-Uso -Etiqueta "Pagina en uso" -Pct $PctPagina -Umbral $UmbralAlertaPagina

        if ($PctPagina -ge $UmbralAlertaPagina) {
            Write-Host "`n   ATENCION: Archivo de pagina al $PctPagina%" `
                       -ForegroundColor Red
            Write-Host "   Windows esta usando el disco como RAM de emergencia." `
                       -ForegroundColor Yellow
            Write-Host "   Esto es mucho mas lento que la RAM fisica." `
                       -ForegroundColor Yellow
        }

        Write-Host ""
        Write-Detalle -Etiqueta "Tamano total"  -Valor (Get-BytesLegibles $PaginaTotalBytes)
        Write-Detalle -Etiqueta "En uso"        -Valor (Get-BytesLegibles $PaginaUsadaBytes)
        Write-Detalle -Etiqueta "Libre"         -Valor (Get-BytesLegibles ($PaginaTotalBytes - $PaginaUsadaBytes))
    }

    # --------------------------------------------------------------------------
    #  SECCION 4: Actividad de paginacion en tiempo real
    #  Estos contadores miden cuanta actividad hay entre la RAM y el disco.
    #  Valores bajos son normales. Valores altos y sostenidos indican
    #  que el sistema esta constantemente moviendo datos al disco porque
    #  no tiene suficiente RAM.
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 62)" -ForegroundColor DarkGray
    Write-Host "`nACTIVIDAD DE PAGINACION (tiempo real)" -ForegroundColor White

    Write-Host ("   Paginas por segundo    : {0,8:N1}" -f $PaginasPorSeg) -NoNewline
    if ($PaginasPorSeg -gt 100) {
        Write-Host "  ALTO - presion de memoria" -ForegroundColor Red
    } elseif ($PaginasPorSeg -gt 20) {
        Write-Host "  Moderado" -ForegroundColor Yellow
    } else {
        Write-Host "  Normal" -ForegroundColor Green
    }

    Write-Host ("   Fallos de pagina/seg   : {0,8:N1}" -f $FallosPorSeg) -NoNewline
    if ($FallosPorSeg -gt 1000) {
        Write-Host "  ALTO" -ForegroundColor Red
    } elseif ($FallosPorSeg -gt 200) {
        Write-Host "  Moderado" -ForegroundColor Yellow
    } else {
        Write-Host "  Normal" -ForegroundColor Green
    }

    # --------------------------------------------------------------------------
    #  SECCION 5: Diagnostico global
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 62)" -ForegroundColor DarkGray
    Write-Host "`nDIAGNOSTICO" -ForegroundColor White
    Write-Diagnostico -PctRAM $PctRAM -PctPagina $PctPagina -PaginasSeg $PaginasPorSeg

    # Pie
    Write-Host ("`n" + "=" * 62) -ForegroundColor Cyan
    Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f `
                $IntervaloSegundos) -ForegroundColor Gray
    Write-Host ("=" * 62) -ForegroundColor Cyan
}


# ==============================================================================
#  BUCLE PRINCIPAL
# ==============================================================================
function Start-Monitor {
    try {
        while ($true) {
            Show-Memoria
            Start-Sleep -Seconds $IntervaloSegundos
        }
    }
    finally {
        $CntDisponible.Dispose()
        $CntPaginas.Dispose()
        $CntFallosPag.Dispose()
        $CntUsoPagina.Dispose()
        Write-Host "`n`n  Monitor detenido. Hasta luego!" -ForegroundColor Green
    }
}


# ==============================================================================
#  PUNTO DE ENTRADA
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Start-Monitor
}
