# ==============================================================================
#  bateria_monitor.ps1 - Monitor de Bateria en PowerShell
#  Descripcion : Monitoriza en tiempo real el estado de la bateria:
#                nivel de carga, estado de carga/descarga, tiempo estimado
#                y salud de la bateria (solo en equipos portatiles).
#  Requisitos  : PowerShell 5.1 o superior (incluido en Windows 10/11/Server).
#                Compatible con PowerShell 5.1, 6 y 7.
#                Solo util en portatiles. En sobremesa informa correctamente.
#  Uso         : .\bateria_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  FUENTES DE DATOS PARA LA BATERIA EN WINDOWS
#
#  Windows expone la informacion de la bateria a traves de varias vias:
#
#  Win32_Battery (CIM/WMI)
#      -> la fuente principal y mas compatible
#      -> disponible en todas las versiones de Windows
#      -> proporciona: nivel de carga, estado, tiempo estimado, salud
#
#  Propiedades clave de Win32_Battery:
#
#  EstimatedChargeRemaining  -> porcentaje de carga actual (0-100)
#
#  BatteryStatus             -> estado actual en forma de codigo numerico:
#                               1 = Descargando (en bateria)
#                               2 = Carga desconocida / CA conectada
#                               3 = Cargando completamente
#                               4 = Bajo (low)
#                               5 = Critico
#                               6 = Cargando
#                               7 = Cargando y alto
#                               8 = Cargando y bajo
#                               9 = Cargando y critico
#                              10 = Sin definir
#                              11 = Parcialmente cargado
#
#  EstimatedRunTime          -> minutos restantes estimados.
#                               Si vale 71582788 significa "desconocido"
#                               o "tiempo ilimitado" (cargando o lleno).
#
#  DesignCapacity            -> capacidad de diseno en mWh (cuando era nueva)
#  FullChargeCapacity        -> capacidad actual maxima en mWh (degradada)
#  La diferencia entre ambas nos da el % de salud de la bateria.
#
#  Analogia: es como comparar el deposito de un coche nuevo (diseno)
#  con el mismo deposito despues de anos de uso (capacidad actual).
#  Con el tiempo el deposito "encoge" y carga menos combustible.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos     = 5    # La bateria cambia lentamente, 5s es suficiente
$UmbralBateriaBaja     = 20   # % por debajo del cual avisamos de bateria baja
$UmbralBateriaCritica  = 10   # % por debajo del cual la situacion es critica
$UmbralBateriaAlta     = 95   # % por encima del cual sugerimos desenchufar
                               # Mantener al 100% enchufado degrada la bateria


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }

function Get-Barra {
    param([double]$Pct, [int]$Long = 30)
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}] {1:N1}%" -f (("#" * $Llenos) + ("-" * $Vacios)), $Pct
}


# --- Barra de bateria con color segun nivel ----------------------------------
# Cuatro niveles de color para la bateria:
# Verde  -> nivel normal (> 20%)
# Amarillo -> nivel bajo (10-20%)
# Rojo   -> nivel critico (< 10%)
# Cyan   -> bateria casi llena (> 95%), recomendamos desenchufar
#
function Write-BarraBateria {
    param([double]$Pct)
    $Barra = Get-Barra -Pct $Pct

    if     ($Pct -le $UmbralBateriaCritica) { $Color = "Red"    }
    elseif ($Pct -le $UmbralBateriaBaja)    { $Color = "Yellow" }
    elseif ($Pct -ge $UmbralBateriaAlta)    { $Color = "Cyan"   }
    else                                    { $Color = "Green"  }

    Write-Host ("   {0}" -f $Barra) -ForegroundColor $Color
}


# --- Traducir codigo de estado de la bateria ---------------------------------
# Win32_Battery devuelve el estado como un numero.
# Esta funcion lo convierte a texto legible con su color correspondiente.
#
function Get-TextoEstado {
    param([int]$Codigo)

    switch ($Codigo) {
        1  { return @{ Texto = "Descargando (en bateria)";      Color = "Yellow" } }
        2  { return @{ Texto = "Corriente alterna conectada";   Color = "Green"  } }
        3  { return @{ Texto = "Carga completa";                Color = "Cyan"   } }
        4  { return @{ Texto = "Bateria baja";                  Color = "Yellow" } }
        5  { return @{ Texto = "Bateria critica";               Color = "Red"    } }
        6  { return @{ Texto = "Cargando";                      Color = "Green"  } }
        7  { return @{ Texto = "Cargando - nivel alto";         Color = "Green"  } }
        8  { return @{ Texto = "Cargando - nivel bajo";         Color = "Yellow" } }
        9  { return @{ Texto = "Cargando - nivel critico";      Color = "Red"    } }
        11 { return @{ Texto = "Parcialmente cargada";          Color = "Yellow" } }
        default { return @{ Texto = "Estado desconocido ($Codigo)"; Color = "Gray" } }
    }
}


# --- Convertir minutos a formato legible -------------------------------------
# EstimatedRunTime viene en minutos. Lo convertimos a horas y minutos.
# El valor especial 71582788 significa "tiempo desconocido o ilimitado".
#
function Get-TiempoLegible {
    param([long]$Minutos)

    # Valor especial de WMI: significa "no disponible" o "tiempo ilimitado"
    if ($Minutos -ge 71582788 -or $Minutos -lt 0) {
        return "Calculando o no disponible"
    }

    $Horas = [int]($Minutos / 60)
    $Mins  = [int]($Minutos % 60)
    return "{0}h {1:D2}m" -f $Horas, $Mins
}


# --- Calcular salud de la bateria -------------------------------------------
# La salud se calcula comparando la capacidad actual maxima con la
# capacidad de diseno original (cuando la bateria era nueva).
# Salud = (CapacidadActual / CapacidadDiseno) * 100
# No todos los fabricantes reportan estos datos via WMI.
#
function Get-SaludBateria {
    param(
        [long]$CapacidadDiseno,
        [long]$CapacidadActual
    )

    # Si alguno de los valores es 0 o no valido, no podemos calcular la salud
    if ($CapacidadDiseno -le 0 -or $CapacidadActual -le 0) {
        return -1   # -1 indica "no disponible"
    }

    return [math]::Round(($CapacidadActual / $CapacidadDiseno) * 100, 1)
}


# --- Determinar si la bateria esta enchufada ---------------------------------
# Deducimos si esta enchufada a partir del codigo de BatteryStatus.
# Los codigos 2, 3, 6, 7, 8 y 9 indican que hay corriente alterna.
#
function Get-EstaEnchufada {
    param([int]$Codigo)
    return ($Codigo -eq 2 -or $Codigo -eq 3 -or
            $Codigo -eq 6 -or $Codigo -eq 7 -or
            $Codigo -eq 8 -or $Codigo -eq 9)
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-Bateria {

    $Ahora   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Sistema = (Get-CimInstance Win32_OperatingSystem).Caption

    # --- Leer datos de la bateria via WMI ------------------------------------
    # Usamos ErrorAction SilentlyContinue para que no muestre error
    # si no hay bateria en el sistema (equipos de sobremesa)
    $Baterias = Get-CimInstance -ClassName Win32_Battery `
                                -ErrorAction SilentlyContinue

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host "  MONITOR DE BATERIA - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 62) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  Sin bateria detectada
    # --------------------------------------------------------------------------
    if (-not $Baterias) {
        Write-Host ""
        Write-Host "  No se detecto ninguna bateria en este sistema." `
                   -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Posibles motivos:" -ForegroundColor White
        Write-Host "    - Equipo de sobremesa (desktop) sin bateria."
        Write-Host "    - Maquina virtual (las VMs no tienen bateria real)."
        Write-Host "    - Portatil con driver ACPI no instalado correctamente."
        Write-Host ""
        Write-Host "  Si es un portatil, comprueba en el Administrador de" -ForegroundColor Gray
        Write-Host "  dispositivos que 'Bateria' aparece sin errores." -ForegroundColor Gray
        Write-Host ""
        Write-Host ("=" * 62) -ForegroundColor Cyan
        Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f `
                    $IntervaloSegundos) -ForegroundColor Gray
        Write-Host ("=" * 62) -ForegroundColor Cyan
        return
    }

    # --------------------------------------------------------------------------
    #  Procesamos cada bateria detectada
    #  (la mayoria de portatiles tiene una, pero puede haber mas)
    # --------------------------------------------------------------------------
    foreach ($Bat in $Baterias) {

        $Porcentaje  = $Bat.EstimatedChargeRemaining
        $CodigoEstado= $Bat.BatteryStatus
        $MinutosRest = $Bat.EstimatedRunTime
        $CapDiseno   = $Bat.DesignCapacity
        $CapActual   = $Bat.FullChargeCapacity
        $NombreBat   = $Bat.Name
        $Fabricante  = $Bat.DeviceID

        # Obtenemos texto y color del estado
        $InfoEstado  = Get-TextoEstado   -Codigo $CodigoEstado
        $Enchufada   = Get-EstaEnchufada -Codigo $CodigoEstado
        $Salud       = Get-SaludBateria  -CapacidadDiseno $CapDiseno `
                                         -CapacidadActual $CapActual

        # ----------------------------------------------------------------------
        #  SECCION 1: Estado principal
        # ----------------------------------------------------------------------
        Write-Host ""
        Write-Host "BATERIA DETECTADA" -ForegroundColor White
        if ($NombreBat) {
            Write-Host ("   Nombre     : {0}" -f $NombreBat)
        }

        Write-Host ""
        Write-Host "NIVEL DE CARGA" -ForegroundColor White
        Write-BarraBateria -Pct $Porcentaje

        Write-Host ""
        Write-Host "ESTADO ACTUAL" -ForegroundColor White
        Write-Host ("   Estado     : {0}" -f $InfoEstado.Texto) `
                   -ForegroundColor $InfoEstado.Color

        if ($Enchufada) {
            Write-Host "   Adaptador  : Conectado" -ForegroundColor Green
        } else {
            Write-Host "   Adaptador  : Desconectado (funcionando con bateria)" `
                       -ForegroundColor Yellow
        }

        # Alertas de nivel de carga
        if ($Porcentaje -le $UmbralBateriaCritica -and -not $Enchufada) {
            Write-Host ""
            Write-Host "   BATERIA CRITICA - Conecta el cargador inmediatamente" `
                       -ForegroundColor Red
            Write-Host "   El sistema podria apagarse sin previo aviso." `
                       -ForegroundColor Red
        } elseif ($Porcentaje -le $UmbralBateriaBaja -and -not $Enchufada) {
            Write-Host ""
            Write-Host "   Bateria baja - conecta el cargador pronto." `
                       -ForegroundColor Yellow
        }

        # ----------------------------------------------------------------------
        #  SECCION 2: Tiempo estimado
        # ----------------------------------------------------------------------
        Write-Host ""
        Write-Host "$("-" * 62)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "TIEMPO ESTIMADO" -ForegroundColor White

        if ($Enchufada) {
            if ($Porcentaje -ge 100) {
                Write-Host "   Carga completa al 100%" -ForegroundColor Cyan
            } else {
                Write-Host "   Cargando... (tiempo hasta carga completa no" `
                           -ForegroundColor Green
                Write-Host "   disponible directamente via WMI en Windows)" `
                           -ForegroundColor Gray
            }
        } else {
            $TiempoStr = Get-TiempoLegible -Minutos $MinutosRest
            Write-Host ("   Autonomia restante estimada : {0}" -f $TiempoStr)

            # Advertencia adicional si el tiempo es muy corto
            if ($MinutosRest -lt 71582788 -and $MinutosRest -gt 0 `
                -and $MinutosRest -lt 30) {
                Write-Host "   Menos de 30 minutos de bateria restantes." `
                           -ForegroundColor Red
            }
        }

        # ----------------------------------------------------------------------
        #  SECCION 3: Salud de la bateria
        # ----------------------------------------------------------------------
        Write-Host ""
        Write-Host "$("-" * 62)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "SALUD DE LA BATERIA" -ForegroundColor White

        if ($Salud -ge 0) {
            # Tenemos datos de capacidad para calcular la salud
            Write-Host ("   Capacidad de diseno  : {0} mWh" -f $CapDiseno)
            Write-Host ("   Capacidad actual max : {0} mWh" -f $CapActual)
            Write-Host ("   Salud estimada       : {0}%" -f $Salud) -NoNewline

            if ($Salud -ge 80) {
                Write-Host "  (bateria en buen estado)" -ForegroundColor Green
            } elseif ($Salud -ge 60) {
                Write-Host "  (degradacion moderada, normal con el uso)" `
                           -ForegroundColor Yellow
            } else {
                Write-Host "  (degradacion elevada, considera reemplazarla)" `
                           -ForegroundColor Red
            }

            # Barra visual de salud
            $BarraSalud = Get-Barra -Pct $Salud -Long 25
            $ColorSalud = if ($Salud -ge 80) { "Green" } `
                          elseif ($Salud -ge 60) { "Yellow" } `
                          else { "Red" }
            Write-Host ("   {0}" -f $BarraSalud) -ForegroundColor $ColorSalud

        } else {
            # El fabricante no reporta capacidades via WMI
            Write-Host "   Datos de capacidad no disponibles via WMI." `
                       -ForegroundColor Gray
            Write-Host ""
            Write-Host "   Para ver la salud real de la bateria en Windows:" `
                       -ForegroundColor White
            Write-Host "   Abre PowerShell como Administrador y ejecuta:"
            Write-Host ""
            Write-Host "     powercfg /batteryreport" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "   Genera un informe HTML completo con ciclos de carga," `
                       -ForegroundColor Gray
            Write-Host "   capacidad de diseno vs actual y mucho mas." `
                       -ForegroundColor Gray
        }

        # ----------------------------------------------------------------------
        #  SECCION 4: Consejos contextuales
        # ----------------------------------------------------------------------
        Write-Host ""
        Write-Host "$("-" * 62)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "CONSEJOS" -ForegroundColor White

        if ($Enchufada -and $Porcentaje -ge $UmbralBateriaAlta) {
            Write-Host "   Bateria al $Porcentaje% con cargador conectado." `
                       -ForegroundColor Cyan
            Write-Host "   Mantener la bateria constantemente al 100% enchufada" `
                       -ForegroundColor Yellow
            Write-Host "   acelera su degradacion. Si puedes, desenchufa entre" `
                       -ForegroundColor Yellow
            Write-Host "   el 20% y el 80% para prolongar su vida util." `
                       -ForegroundColor Yellow

        } elseif (-not $Enchufada -and $Porcentaje -gt 40 `
                  -and $Porcentaje -lt $UmbralBateriaAlta) {
            Write-Host "   Nivel de bateria optimo para uso en movilidad." `
                       -ForegroundColor Green

        } elseif ($Enchufada -and $Porcentaje -lt $UmbralBateriaAlta) {
            Write-Host "   Bateria cargandose normalmente." -ForegroundColor Green

        } elseif (-not $Enchufada -and $Porcentaje -le $UmbralBateriaBaja `
                  -and $Porcentaje -gt $UmbralBateriaCritica) {
            Write-Host "   Las descargas profundas repetidas reducen la vida" `
                       -ForegroundColor Yellow
            Write-Host "   util de la bateria. Conecta el cargador pronto." `
                       -ForegroundColor Yellow
        } else {
            Write-Host "   Bateria en uso normal." -ForegroundColor Green
        }

        # ----------------------------------------------------------------------
        #  SECCION 5: Diagrama visual ASCII de la bateria
        # ----------------------------------------------------------------------
        Write-Host ""
        Write-Host "$("-" * 62)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "DIAGRAMA DE CARGA" -ForegroundColor White
        Write-Host ""

        # Representamos la bateria como un rectangulo ASCII
        # El nivel de carga se visualiza con bloques #
        $NivelBloques = [int]($Porcentaje / 10)   # Escala de 0 a 10 bloques
        $BloquesCarga = "#" * $NivelBloques
        $BloquesVacio = "-" * (10 - $NivelBloques)

        $ColorDiag = if ($Porcentaje -le $UmbralBateriaCritica) { "Red" } `
                     elseif ($Porcentaje -le $UmbralBateriaBaja) { "Yellow" } `
                     else { "Green" }

        Write-Host "   +----------------------------+ +"
        Write-Host "   |" -NoNewline
        Write-Host (" {0,-10}{1,10} " -f $BloquesCarga, $BloquesVacio) `
                   -ForegroundColor $ColorDiag -NoNewline
        Write-Host "| |"
        Write-Host "   |" -NoNewline
        Write-Host ("{0,26:N1}%" -f $Porcentaje) `
                   -ForegroundColor $ColorDiag -NoNewline
        Write-Host "  | |  <- Polo positivo"
        Write-Host "   +----------------------------+ +"
        Write-Host ""

        if ($Enchufada) {
            Write-Host "   [Cargador conectado]  -  $($InfoEstado.Texto)" `
                       -ForegroundColor Green
        } else {
            Write-Host "   [En bateria]  -  $($InfoEstado.Texto)" `
                       -ForegroundColor Yellow
        }
    }

    # --------------------------------------------------------------------------
    #  NOTA SOBRE powercfg
    #  Recordamos al usuario la herramienta nativa de Windows para informes
    #  detallados de bateria, especialmente util para ver la degradacion.
    # --------------------------------------------------------------------------
    Write-Host ""
    Write-Host "$("-" * 62)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "HERRAMIENTA ADICIONAL DE WINDOWS" -ForegroundColor White
    Write-Host "   Para un informe completo de la bateria ejecuta como Admin:" `
               -ForegroundColor Gray
    Write-Host "     powercfg /batteryreport" -ForegroundColor Cyan
    Write-Host "   Genera battery-report.html con historial de ciclos y salud." `
               -ForegroundColor Gray

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
            Show-Bateria
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
