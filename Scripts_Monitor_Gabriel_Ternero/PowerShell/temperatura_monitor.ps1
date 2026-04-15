# ==============================================================================
#  temperatura_monitor.ps1 - Monitor de Temperaturas en PowerShell
#  Descripcion : Intenta leer las temperaturas del sistema usando todos los
#                metodos disponibles en Windows. Informa claramente de lo
#                que puede y no puede leer segun el hardware y el entorno.
#  Requisitos  : PowerShell 5.1 o superior. Sin dependencias externas.
#                Algunos datos requieren ejecutar como Administrador.
#  Uso         : .\temperatura_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  LA REALIDAD SOBRE LAS TEMPERATURAS EN WINDOWS
#
#  Esta es la situacion honesta que todo alumno debe conocer:
#
#  Windows NO tiene una API universal para leer temperaturas de hardware.
#  Cada fabricante (Intel, AMD, NVIDIA...) expone sus sensores de forma
#  diferente, y Microsoft no proporciona una interfaz estandar para todos.
#
#  Lo que SI existe en Windows via WMI:
#
#  MSAcpi_ThermalZoneTemperature (namespace root\wmi)
#      -> Lee las zonas termicas ACPI del sistema.
#      -> Disponible en la mayoria de equipos fisicos.
#      -> Devuelve temperatura en decikelvin (dividir entre 10 y restar 273.15
#         para obtener grados Celsius).
#      -> Limitacion: solo lee zonas ACPI genericas, no sensores especificos
#         de cada nucleo de CPU. Muchos fabricantes no implementan ACPI
#         correctamente y devuelve valores erroneos o 0.
#      -> En maquinas virtuales: siempre falla o devuelve datos invalidos.
#
#  Win32_TemperatureProbe (namespace root\cimv2)
#      -> Clase WMI para sondas de temperatura.
#      -> En la practica casi nunca devuelve datos reales.
#      -> La mayoria de fabricantes no implementan esta clase.
#
#  Lo que NO esta disponible sin software de terceros:
#      -> Temperatura por nucleo de CPU (Core 0, Core 1...)
#      -> Temperatura de GPU (requiere drivers especificos)
#      -> Temperatura de disco NVMe/SSD
#      -> Temperatura de placa base y VRMs
#
#  Para tener todos esos datos en Windows se necesita una de estas
#  herramientas que instalan sus propios drivers de bajo nivel:
#      -> HWiNFO64         (la mas completa)
#      -> Open Hardware Monitor / LibreHardwareMonitor
#      -> Core Temp        (especializada en CPU)
#      -> AIDA64
#
#  LibreHardwareMonitor tiene una opcion para exponer sus datos via WMI,
#  lo que permite leerlos desde PowerShell. Lo cubrimos en la Seccion 3.
#
#  Analogia: es como intentar leer el odometro de un coche a traves
#  de la radio. La radio no tiene acceso a ese dato. Necesitas conectar
#  un dispositivo especifico al puerto OBD del coche para leerlo.
#  Windows es la radio. HWiNFO es el dispositivo OBD.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos = 3     # Segundos entre actualizaciones

# Umbrales de temperatura en grados Celsius
$UmbralWarnCPU     = 75    # Temperatura de advertencia para CPU
$UmbralCritCPU     = 90    # Temperatura critica para CPU
$UmbralWarnDisco   = 50    # Temperatura de advertencia para disco
$UmbralCritDisco   = 60    # Temperatura critica para disco
$UmbralWarnGeneral = 65    # Para zonas termicas genericas
$UmbralCritGeneral = 80    # Para zonas termicas genericas


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }

function Get-Barra {
    param([double]$Pct, [int]$Long = 20)
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}]" -f (("#" * $Llenos) + ("-" * $Vacios))
}


# --- Mostrar temperatura con barra y color -----------------------------------
# La barra representa la temperatura en una escala de 0 a 120 grados.
# Colores: verde (normal), amarillo (advertencia), rojo (critico).
#
function Write-Temperatura {
    param(
        [string]$Etiqueta,
        [double]$TempC,
        [int]$UmbralWarn = 65,
        [int]$UmbralCrit = 80
    )

    # Convertimos la temperatura a porcentaje sobre 120 grados de referencia
    $Pct   = [math]::Min(($TempC / 120) * 100, 100)
    $Barra = Get-Barra -Pct $Pct -Long 20

    if     ($TempC -ge $UmbralCrit) { $Color = "Red"    }
    elseif ($TempC -ge $UmbralWarn) { $Color = "Yellow" }
    else                            { $Color = "Green"  }

    Write-Host ("   {0,-22}" -f $Etiqueta) -NoNewline
    Write-Host ("{0,6:N1} C  {1}" -f $TempC, $Barra) -ForegroundColor $Color
}


# --- Convertir decikelvin a Celsius ------------------------------------------
# WMI devuelve las temperaturas ACPI en decikelvin (decimas de kelvin).
# Formula: Celsius = (DeciKelvin / 10) - 273.15
# Ejemplo: 3232 decikelvin -> (3232/10) - 273.15 = 49.85 Celsius
#
function Convert-DecikelvinACelsius {
    param([long]$DeciKelvin)
    return [math]::Round(($DeciKelvin / 10) - 273.15, 1)
}


# --- Validar si una temperatura es razonable ---------------------------------
# WMI a veces devuelve valores invalidos: 0, negativos o exageradamente
# altos. Esta funcion filtra los que no tienen sentido fisico.
# Un componente informatico real estara entre 0 y 120 grados Celsius.
#
function Test-TemperaturaValida {
    param([double]$TempC)
    return ($TempC -gt 0 -and $TempC -lt 120)
}


# ==============================================================================
#  METODO 1: Zonas termicas ACPI via WMI (root\wmi)
#  Es el metodo mas compatible. Funciona en muchos equipos fisicos.
#  No funciona en maquinas virtuales.
# ==============================================================================
function Get-TemperaturaACPI {
    try {
        # Importante: este namespace es root\wmi, distinto del habitual root\cimv2
        # Si no se especifica el namespace correcto no encontrara la clase
        $Zonas = Get-CimInstance -Namespace "root\wmi" `
                                 -ClassName "MSAcpi_ThermalZoneTemperature" `
                                 -ErrorAction Stop

        $Resultados = @()
        foreach ($Zona in $Zonas) {
            $TempC = Convert-DecikelvinACelsius -DeciKelvin $Zona.CurrentTemperature

            if (Test-TemperaturaValida -TempC $TempC) {
                # InstanceName suele tener formato como "ACPI\ThermalZone\..."
                # Limpiamos el nombre para que sea mas legible
                $Nombre = $Zona.InstanceName -replace 'ACPI\\ThermalZone\\', '' `
                                             -replace '_\d+$', ''
                if (-not $Nombre) { $Nombre = "Zona ACPI" }

                $Resultados += [PSCustomObject] @{
                    Nombre = $Nombre
                    TempC  = $TempC
                    Fuente = "ACPI"
                }
            }
        }
        return $Resultados
    }
    catch {
        return @()   # Devolvemos array vacio si falla
    }
}


# ==============================================================================
#  METODO 2: Win32_TemperatureProbe (root\cimv2)
#  Clase estandar de WMI para sondas de temperatura.
#  En la practica rara vez devuelve datos reales, pero lo intentamos.
# ==============================================================================
function Get-TemperaturaProbe {
    try {
        $Sondas = Get-CimInstance -ClassName "Win32_TemperatureProbe" `
                                  -ErrorAction Stop

        $Resultados = @()
        foreach ($Sonda in $Sondas) {
            # CurrentReading viene en decimas de grado Celsius
            if ($Sonda.CurrentReading -and $Sonda.CurrentReading -gt 0) {
                $TempC = $Sonda.CurrentReading / 10.0

                if (Test-TemperaturaValida -TempC $TempC) {
                    $Nombre = if ($Sonda.Name) { $Sonda.Name } else { "Sonda WMI" }
                    $Resultados += [PSCustomObject] @{
                        Nombre = $Nombre
                        TempC  = $TempC
                        Fuente = "WMI Probe"
                    }
                }
            }
        }
        return $Resultados
    }
    catch {
        return @()
    }
}


# ==============================================================================
#  METODO 3: LibreHardwareMonitor via WMI (root\LibreHardwareMonitor)
#  LibreHardwareMonitor es una aplicacion gratuita y de codigo abierto
#  que puede exponer sus datos via WMI cuando se ejecuta con la opcion
#  "Remote Web Server" activada o simplemente ejecutandose en segundo plano.
#  Si esta instalado y corriendo, podemos leer todos sus sensores desde PS.
# ==============================================================================
function Get-TemperaturaLHM {
    try {
        # Intentamos conectar al namespace de LibreHardwareMonitor
        $Sensores = Get-CimInstance -Namespace "root\LibreHardwareMonitor" `
                                    -ClassName "Sensor" `
                                    -ErrorAction Stop |
                    Where-Object { $_.SensorType -eq "Temperature" }

        $Resultados = @()
        foreach ($Sensor in $Sensores) {
            if ($Sensor.Value -and (Test-TemperaturaValida -TempC $Sensor.Value)) {
                $Resultados += [PSCustomObject] @{
                    Nombre = "{0} / {1}" -f $Sensor.Parent, $Sensor.Name
                    TempC  = [math]::Round($Sensor.Value, 1)
                    Fuente = "LibreHardwareMonitor"
                }
            }
        }
        return $Resultados
    }
    catch {
        return @()
    }
}


# ==============================================================================
#  METODO 4: OpenHardwareMonitor via WMI (root\OpenHardwareMonitor)
#  La version original de OpenHardwareMonitor, anterior a LibreHardwareMonitor.
#  Algunos usuarios aun lo tienen instalado.
# ==============================================================================
function Get-TemperaturaOHM {
    try {
        $Sensores = Get-CimInstance -Namespace "root\OpenHardwareMonitor" `
                                    -ClassName "Sensor" `
                                    -ErrorAction Stop |
                    Where-Object { $_.SensorType -eq "Temperature" }

        $Resultados = @()
        foreach ($Sensor in $Sensores) {
            if ($Sensor.Value -and (Test-TemperaturaValida -TempC $Sensor.Value)) {
                $Resultados += [PSCustomObject] @{
                    Nombre = "{0} / {1}" -f $Sensor.Parent, $Sensor.Name
                    TempC  = [math]::Round($Sensor.Value, 1)
                    Fuente = "OpenHardwareMonitor"
                }
            }
        }
        return $Resultados
    }
    catch {
        return @()
    }
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-Temperaturas {

    $Ahora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # Intentamos todos los metodos en orden de preferencia
    # Si un metodo falla o no devuelve datos, pasamos al siguiente
    $ResultadosACPI = Get-TemperaturaACPI
    $ResultadosProbe= Get-TemperaturaProbe
    $ResultadosLHM  = Get-TemperaturaLHM
    $ResultadosOHM  = Get-TemperaturaOHM

    # Combinamos todos los resultados en una sola lista
    $TodosResultados = @()
    $TodosResultados += $ResultadosLHM    # LHM primero: es el mas preciso
    $TodosResultados += $ResultadosOHM    # OHM segundo
    $TodosResultados += $ResultadosACPI   # ACPI tercero: datos genericos
    $TodosResultados += $ResultadosProbe  # WMI Probe ultimo: rara vez funciona

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  MONITOR DE TEMPERATURAS - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  Estado de cada metodo de lectura
    # --------------------------------------------------------------------------
    Write-Host "`nFUENTES DE DATOS DISPONIBLES" -ForegroundColor White
    Write-Host ""

    # LHM
    if ($ResultadosLHM.Count -gt 0) {
        Write-Host "   [OK] LibreHardwareMonitor : {0} sensores detectados" `
                   -f $ResultadosLHM.Count -ForegroundColor Green
    } else {
        Write-Host "   [--] LibreHardwareMonitor : no detectado" `
                   -ForegroundColor DarkGray
    }

    # OHM
    if ($ResultadosOHM.Count -gt 0) {
        Write-Host "   [OK] OpenHardwareMonitor  : {0} sensores detectados" `
                   -f $ResultadosOHM.Count -ForegroundColor Green
    } else {
        Write-Host "   [--] OpenHardwareMonitor  : no detectado" `
                   -ForegroundColor DarkGray
    }

    # ACPI
    if ($ResultadosACPI.Count -gt 0) {
        Write-Host "   [OK] Zonas ACPI (WMI)     : {0} zonas detectadas" `
                   -f $ResultadosACPI.Count -ForegroundColor Green
    } else {
        Write-Host "   [--] Zonas ACPI (WMI)     : no disponible en este sistema" `
                   -ForegroundColor DarkGray
    }

    # WMI Probe
    if ($ResultadosProbe.Count -gt 0) {
        Write-Host "   [OK] Win32_TemperatureProbe: {0} sondas detectadas" `
                   -f $ResultadosProbe.Count -ForegroundColor Green
    } else {
        Write-Host "   [--] Win32_TemperatureProbe: no implementado en este HW" `
                   -ForegroundColor DarkGray
    }

    # --------------------------------------------------------------------------
    #  Mostramos los datos si tenemos algun resultado
    # --------------------------------------------------------------------------
    if ($TodosResultados.Count -gt 0) {

        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nTEMPERATURAS DETECTADAS" -ForegroundColor White
        Write-Host ""

        $Alertas = @()

        foreach ($R in $TodosResultados) {

            # Elegimos los umbrales segun el tipo de sensor por nombre
            $Warn = $UmbralWarnGeneral
            $Crit = $UmbralCritGeneral

            $NombreLower = $R.Nombre.ToLower()
            if ($NombreLower -match "cpu|core|processor|package") {
                $Warn = $UmbralWarnCPU
                $Crit = $UmbralCritCPU
            } elseif ($NombreLower -match "disk|drive|nvme|ssd|hdd|storage") {
                $Warn = $UmbralWarnDisco
                $Crit = $UmbralCritDisco
            }

            # Etiqueta con la fuente entre parentesis
            $Etiqueta = "{0} ({1})" -f $R.Nombre, $R.Fuente
            if ($Etiqueta.Length -gt 35) {
                $Etiqueta = $Etiqueta.Substring(0, 32) + "..."
            }

            Write-Temperatura -Etiqueta $Etiqueta `
                              -TempC $R.TempC `
                              -UmbralWarn $Warn `
                              -UmbralCrit $Crit

            # Registramos alertas
            if ($R.TempC -ge $Crit) {
                $Alertas += "  CRITICA: {0} -> {1:N1} C" -f $R.Nombre, $R.TempC
            } elseif ($R.TempC -ge $Warn) {
                $Alertas += "  ELEVADA: {0} -> {1:N1} C" -f $R.Nombre, $R.TempC
            }
        }

        # Alertas activas
        if ($Alertas.Count -gt 0) {
            Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
            Write-Host "`nALERTAS ACTIVAS" -ForegroundColor Red
            foreach ($A in $Alertas) {
                if ($A -match "CRITICA") {
                    Write-Host $A -ForegroundColor Red
                } else {
                    Write-Host $A -ForegroundColor Yellow
                }
            }
        }

        # Resumen: temperatura mas alta
        $MasAlta = $TodosResultados | Sort-Object TempC -Descending |
                   Select-Object -First 1
        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nRESUMEN" -ForegroundColor White
        Write-Host ("   Sensores activos   : {0}" -f $TodosResultados.Count)
        Write-Host ("   Temperatura maxima : {0:N1} C  ({1})" -f `
                    $MasAlta.TempC, $MasAlta.Nombre)
        $Media = ($TodosResultados | Measure-Object -Property TempC -Average).Average
        Write-Host ("   Temperatura media  : {0:N1} C" -f $Media)

    } else {

        # --------------------------------------------------------------------------
        #  Sin datos disponibles: explicamos la situacion y ofrecemos alternativas
        # --------------------------------------------------------------------------
        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  No se pudieron obtener datos de temperatura." `
                   -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Causas mas probables:" -ForegroundColor White
        Write-Host ""
        Write-Host "  1. Maquina virtual (VirtualBox, VMware, Hyper-V...)" `
                   -ForegroundColor Gray
        Write-Host "     Las VMs no tienen acceso a los sensores del host." `
                   -ForegroundColor Gray
        Write-Host "     Es el caso mas habitual. No indica ningun error." `
                   -ForegroundColor Gray
        Write-Host ""
        Write-Host "  2. Hardware sin sensores ACPI accesibles." `
                   -ForegroundColor Gray
        Write-Host "     Algunos equipos no implementan el estandar ACPI" `
                   -ForegroundColor Gray
        Write-Host "     correctamente para exponer temperaturas via WMI." `
                   -ForegroundColor Gray
        Write-Host ""
        Write-Host "  3. Falta de permisos (ejecutar como Administrador)." `
                   -ForegroundColor Gray
        Write-Host "     Algunos espacios de nombres WMI requieren admin." `
                   -ForegroundColor Gray

        Write-Host ""
        Write-Host "$("-" * 65)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  SOLUCION RECOMENDADA:" -ForegroundColor White
        Write-Host ""
        Write-Host "  Instala LibreHardwareMonitor (gratuito, codigo abierto):" `
                   -ForegroundColor Cyan
        Write-Host "  https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
        Write-Host ""
        Write-Host "  Pasos:" -ForegroundColor White
        Write-Host "    1. Descarga y ejecuta LibreHardwareMonitor como Admin."
        Write-Host "    2. En el menu: Options -> Run On Windows Startup (opcional)"
        Write-Host "    3. Deja LibreHardwareMonitor abierto en segundo plano."
        Write-Host "    4. Vuelve a ejecutar este script: detectara sus sensores."
        Write-Host ""
        Write-Host "  Otras alternativas:" -ForegroundColor White
        Write-Host "    HWiNFO64          https://www.hwinfo.com"
        Write-Host "    Core Temp         https://www.alcpu.com/CoreTemp"
        Write-Host "    AIDA64            https://www.aida64.com"
    }

    # Pie
    Write-Host ("`n" + "=" * 65) -ForegroundColor Cyan
    Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f `
                $IntervaloSegundos) -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan
}


# ==============================================================================
#  BUCLE PRINCIPAL
# ==============================================================================
function Start-Monitor {
    try {
        while ($true) {
            Show-Temperaturas
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
