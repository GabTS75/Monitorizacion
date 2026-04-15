# ==============================================================================
#  ventiladores_monitor.ps1 - Monitor de Ventiladores en PowerShell
#  Descripcion : Lee las RPM de los ventiladores del sistema usando todos
#                los metodos disponibles en Windows. Incluye diagnostico
#                detallado para guiar la configuracion de LHM.
#  Requisitos  : PowerShell 5.1 o superior. Sin dependencias externas.
#                Para RPM reales: LibreHardwareMonitor con WMI activado.
#  Uso         : .\ventiladores_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  POR QUE LHM NECESITA CONFIGURACION ADICIONAL
#
#  LibreHardwareMonitor tiene DOS modos de funcionamiento:
#
#  Modo normal (por defecto)
#      -> Muestra datos en su propia ventana grafica.
#      -> NO comparte nada con el sistema WMI de Windows.
#      -> PowerShell no puede leer ningun dato aunque LHM este abierto.
#
#  Modo con Remote Web Server activado
#      -> Ademas de mostrar su ventana, registra el namespace
#         root\LibreHardwareMonitor en el sistema WMI de Windows.
#      -> PowerShell puede leer todos los sensores desde ese namespace.
#      -> Se activa en: Options -> Remote Web Server -> Run
#
#  Adicionalmente, LHM debe ejecutarse como Administrador para poder
#  acceder a los drivers de bajo nivel que leen los chips sensores.
#  Sin privilegios de admin puede mostrar algunos datos en su interfaz
#  pero no registra el namespace WMI correctamente.
#
#  Resumen de pasos necesarios:
#  1. Cerrar LHM si esta abierto sin privilegios.
#  2. Volver a abrir LHM con "Ejecutar como administrador".
#  3. En LHM: Options -> Remote Web Server -> marcar "Run".
#  4. Ejecutar este script: ya detectara todos los sensores.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos  = 3
$RPMMinimaActivo    = 100
$RPMUmbralAlto      = 2000
$RPMUmbralMuyAlto   = 3000
$RPMMaxReferencia   = 4000


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }

function Get-BarraRPM {
    param([double]$RPM, [int]$Long = 22)
    $Pct    = [math]::Min(($RPM / $RPMMaxReferencia) * 100, 100)
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}]" -f (("#" * $Llenos) + ("-" * $Vacios))
}

function Get-ColorRPM {
    param([double]$RPM)
    if     ($RPM -lt $RPMMinimaActivo)  { return "DarkGray" }
    elseif ($RPM -lt $RPMUmbralAlto)    { return "Green"    }
    elseif ($RPM -lt $RPMUmbralMuyAlto) { return "Yellow"   }
    else                                { return "Red"      }
}

function Get-EstadoVentilador {
    param([double]$RPM)
    if     ($RPM -lt $RPMMinimaActivo)  { return "Parado"   }
    elseif ($RPM -lt $RPMUmbralAlto)    { return "Normal"   }
    elseif ($RPM -lt $RPMUmbralMuyAlto) { return "Alto"     }
    else                                { return "Muy alto" }
}

function Write-VentiladorFila {
    param([string]$Nombre, [double]$RPM)
    $Barra  = Get-BarraRPM -RPM $RPM
    $Color  = Get-ColorRPM -RPM $RPM
    $Estado = Get-EstadoVentilador -RPM $RPM
    $NCorto = if ($Nombre.Length -gt 28) { $Nombre.Substring(0,25)+"..." } else { $Nombre }
    Write-Host ("   {0,-28}" -f $NCorto) -NoNewline
    Write-Host ("{0,7:N0} RPM  {1}  {2}" -f $RPM, $Barra, $Estado) -ForegroundColor $Color
}


# ==============================================================================
#  DIAGNOSTICO DE LIBREHARDWAREMONITOR
#  Distingue tres situaciones muy diferentes:
#  A) LHM no esta instalado o no se esta ejecutando
#  B) LHM esta ejecutandose pero sin el WMI activado
#  C) LHM esta ejecutandose con WMI activado y hay datos disponibles
# ==============================================================================
function Get-DiagnosticoLHM {
    <#
    Devuelve un hashtable con:
        Estado  : "no_proceso" | "sin_wmi" | "wmi_vacio" | "ok"
        Mensaje : descripcion del estado encontrado
        Proceso : objeto del proceso si LHM esta en ejecucion
    #>

    # Paso 1: comprobar si el proceso de LHM esta en ejecucion
    # Get-Process busca por nombre de ejecutable (sin extension)
    $ProcLHM = Get-Process -Name "LibreHardwareMonitor" -ErrorAction SilentlyContinue

    if (-not $ProcLHM) {
        return @{
            Estado  = "no_proceso"
            Mensaje = "LibreHardwareMonitor no esta en ejecucion."
            Proceso = $null
        }
    }

    # Paso 2: LHM esta corriendo. Comprobamos si el namespace WMI existe.
    # Para ello intentamos listar las clases del namespace.
    # Si el namespace no existe Get-CimInstance lanzara un error especifico.
    try {
        $null = Get-CimInstance -Namespace "root\LibreHardwareMonitor" `
                                -ClassName "__Namespace" `
                                -ErrorAction Stop
    }
    catch [Microsoft.Management.Infrastructure.CimException] {
        # El namespace no existe: LHM corre pero sin WMI activado
        return @{
            Estado  = "sin_wmi"
            Mensaje = "LHM esta en ejecucion pero el servidor WMI NO esta activado."
            Proceso = $ProcLHM
        }
    }
    catch {
        return @{
            Estado  = "sin_wmi"
            Mensaje = "LHM esta en ejecucion pero no se puede acceder a su WMI."
            Proceso = $ProcLHM
        }
    }

    # Paso 3: el namespace existe. Comprobamos si hay sensores de tipo Fan.
    try {
        $Sensores = Get-CimInstance -Namespace "root\LibreHardwareMonitor" `
                                    -ClassName "Sensor" `
                                    -ErrorAction Stop |
                    Where-Object { $_.SensorType -eq "Fan" }

        if (-not $Sensores -or @($Sensores).Count -eq 0) {
            return @{
                Estado  = "wmi_vacio"
                Mensaje = "WMI activo pero sin sensores de ventilador disponibles."
                Proceso = $ProcLHM
            }
        }

        return @{
            Estado   = "ok"
            Mensaje  = "LHM activo y con datos disponibles."
            Proceso  = $ProcLHM
            Sensores = $Sensores
        }
    }
    catch {
        return @{
            Estado  = "wmi_vacio"
            Mensaje = "WMI activo pero no se pudieron leer los sensores."
            Proceso = $ProcLHM
        }
    }
}


# ==============================================================================
#  METODOS DE LECTURA DE VENTILADORES
# ==============================================================================

function Get-VentiladoresLHM {
    try {
        $Sensores = Get-CimInstance -Namespace "root\LibreHardwareMonitor" `
                                    -ClassName "Sensor" -ErrorAction Stop |
                    Where-Object { $_.SensorType -eq "Fan" }
        $Resultados = @()
        foreach ($S in $Sensores) {
            if ($S.Value -ne $null -and $S.Value -ge 0) {
                $Resultados += [PSCustomObject] @{
                    Nombre = "{0} / {1}" -f $S.Parent, $S.Name
                    RPM    = [math]::Round($S.Value, 0)
                    Fuente = "LibreHardwareMonitor"
                }
            }
        }
        return $Resultados
    }
    catch { return @() }
}

function Get-VentiladoresOHM {
    try {
        $Sensores = Get-CimInstance -Namespace "root\OpenHardwareMonitor" `
                                    -ClassName "Sensor" -ErrorAction Stop |
                    Where-Object { $_.SensorType -eq "Fan" }
        $Resultados = @()
        foreach ($S in $Sensores) {
            if ($S.Value -ne $null -and $S.Value -ge 0) {
                $Resultados += [PSCustomObject] @{
                    Nombre = "{0} / {1}" -f $S.Parent, $S.Name
                    RPM    = [math]::Round($S.Value, 0)
                    Fuente = "OpenHardwareMonitor"
                }
            }
        }
        return $Resultados
    }
    catch { return @() }
}

function Get-VentiladoresWMI {
    try {
        $Fans = Get-CimInstance -ClassName "Win32_Fan" -ErrorAction Stop
        $Resultados = @()
        foreach ($Fan in $Fans) {
            $Nombre = if ($Fan.Name) { $Fan.Name } else { "Ventilador WMI" }
            $RPM    = if ($Fan.DesiredSpeed -and $Fan.DesiredSpeed -gt 0) {
                $Fan.DesiredSpeed
            } else { 0 }
            $Resultados += [PSCustomObject] @{
                Nombre = $Nombre
                RPM    = $RPM
                Fuente = "Win32_Fan"
            }
        }
        return $Resultados
    }
    catch { return @() }
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-Ventiladores {

    $Ahora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # Diagnostico completo de LHM antes de intentar leer datos
    $DiagLHM        = Get-DiagnosticoLHM
    $ResultadosLHM  = Get-VentiladoresLHM
    $ResultadosOHM  = Get-VentiladoresOHM
    $ResultadosWMI  = Get-VentiladoresWMI

    $ConRPM = @()
    $ConRPM += $ResultadosLHM
    $ConRPM += $ResultadosOHM

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  MONITOR DE VENTILADORES - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  SECCION 1: Estado de LibreHardwareMonitor con diagnostico detallado
    # --------------------------------------------------------------------------
    Write-Host "`nESTADO DE LIBREHARDWAREMONITOR" -ForegroundColor White
    Write-Host ""

    switch ($DiagLHM.Estado) {

        "no_proceso" {
            Write-Host "   [--] LHM no esta en ejecucion." -ForegroundColor Red
            Write-Host ""
            Write-Host "   Para obtener RPM reales sigue estos pasos:" `
                       -ForegroundColor Yellow
            Write-Host ""
            Write-Host "   1. Descarga LibreHardwareMonitor:" -ForegroundColor White
            Write-Host "      https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
            Write-Host "      (descarga el .zip de la seccion Releases)"
            Write-Host ""
            Write-Host "   2. Extrae el zip y abre con BOTON DERECHO ->" `
                       -ForegroundColor White
            Write-Host "      'Ejecutar como administrador'" -ForegroundColor Cyan
            Write-Host "      (imprescindible para acceder a los chips sensores)"
            Write-Host ""
            Write-Host "   3. En LHM ve a: Options -> Remote Web Server" `
                       -ForegroundColor White
            Write-Host "      y marca la casilla 'Run'" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "   4. Deja LHM abierto y vuelve a ejecutar este script." `
                       -ForegroundColor White
        }

        "sin_wmi" {
            # Este es el caso exacto que describes: LHM corre pero sin WMI
            $EsAdmin = $DiagLHM.Proceso.SI -ne $null
            Write-Host "   [!!] LHM esta en ejecucion pero el servidor WMI" `
                       -ForegroundColor Yellow
            Write-Host "        NO esta activado." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "   Este es el motivo por el que el script no ve los datos" `
                       -ForegroundColor White
            Write-Host "   aunque LHM muestre los sensores en su ventana." `
                       -ForegroundColor White
            Write-Host ""
            Write-Host "   SOLUCION (2 pasos):" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "   Paso 1: Cierra LHM y vuelve a abrirlo con" `
                       -ForegroundColor White
            Write-Host "           boton derecho -> 'Ejecutar como administrador'" `
                       -ForegroundColor Cyan
            Write-Host "           (si ya lo ejecutas como admin, omite este paso)"
            Write-Host ""
            Write-Host "   Paso 2: En LHM abierto ve a:" -ForegroundColor White
            Write-Host "           Options  ->  Remote Web Server" -ForegroundColor Cyan
            Write-Host "           y marca la casilla 'Run'" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "   Tras activarlo vuelve a ejecutar este script." `
                       -ForegroundColor White
            Write-Host "   No hace falta reiniciar ni cerrar nada mas." `
                       -ForegroundColor Gray
        }

        "wmi_vacio" {
            Write-Host "   [~] LHM activo con WMI habilitado pero sin sensores" `
                       -ForegroundColor Yellow
            Write-Host "       de ventilador disponibles en este hardware." `
                       -ForegroundColor Yellow
            Write-Host ""
            Write-Host "   Es posible que tu hardware no tenga sensores de RPM" `
                       -ForegroundColor Gray
            Write-Host "   accesibles o que LHM no tenga soporte para el chip" `
                       -ForegroundColor Gray
            Write-Host "   sensor de tu placa base." -ForegroundColor Gray
            Write-Host ""
            Write-Host "   Comprueba en la ventana de LHM si aparece alguna" `
                       -ForegroundColor White
            Write-Host "   seccion llamada 'Fans' o 'Fan' con valores." `
                       -ForegroundColor White
            Write-Host "   Si no aparece, el hardware no expone esos sensores." `
                       -ForegroundColor Gray
        }

        "ok" {
            Write-Host ("   [OK] LHM activo con WMI habilitado - {0} sensores" `
                        -f @($DiagLHM.Sensores).Count) -ForegroundColor Green
        }
    }

    # Estado de OHM
    if ($ResultadosOHM.Count -gt 0) {
        Write-Host ""
        Write-Host ("   [OK] OpenHardwareMonitor : {0} ventiladores detectados" `
                    -f $ResultadosOHM.Count) -ForegroundColor Green
    }

    # Estado de WMI nativo
    if ($ResultadosWMI.Count -gt 0) {
        Write-Host ""
        Write-Host ("   [OK] Win32_Fan (WMI)     : {0} dispositivos (sin RPM exactas)" `
                    -f $ResultadosWMI.Count) -ForegroundColor Yellow
    }

    # --------------------------------------------------------------------------
    #  SECCION 2: Datos de ventiladores si los hay
    # --------------------------------------------------------------------------
    if ($ConRPM.Count -gt 0) {

        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nVENTILADORES - RPM EN TIEMPO REAL" -ForegroundColor White
        Write-Host ""
        Write-Host ("   {0,-28} {1,10}   {2,-22}  Estado" -f `
                    "Ventilador","Velocidad","Barra") -ForegroundColor Gray
        Write-Host ("   {0}" -f ("-" * 62)) -ForegroundColor DarkGray

        $Activos = 0
        $Parados = 0
        $Alertas = @()

        foreach ($V in $ConRPM) {
            Write-VentiladorFila -Nombre $V.Nombre -RPM $V.RPM
            if ($V.RPM -ge $RPMMinimaActivo) { $Activos++ } else { $Parados++ }
            if ($V.RPM -ge $RPMUmbralMuyAlto) {
                $Alertas += "  RPM muy alta: {0} -> {1:N0} RPM" -f $V.Nombre, $V.RPM
            }
        }

        Write-Host ""
        Write-Host ("   Total: {0}  |  " -f $ConRPM.Count) -NoNewline
        Write-Host ("Activos: {0}  " -f $Activos) -ForegroundColor Green -NoNewline
        Write-Host ("|  Parados: {0}" -f $Parados) -ForegroundColor DarkGray

        # Nota sobre modo 0 RPM de GPUs modernas
        $GPUParada = $ConRPM | Where-Object {
            $_.RPM -lt $RPMMinimaActivo -and $_.Nombre -match "gpu|vga|graphic"
        }
        if ($GPUParada) {
            Write-Host ""
            Write-Host "   Nota: ventilador GPU a 0 RPM es normal en reposo." `
                       -ForegroundColor Gray
            Write-Host "   Las GPUs modernas los paran cuando la temp es baja." `
                       -ForegroundColor Gray
        }

        # Alertas
        if ($Alertas.Count -gt 0) {
            Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
            Write-Host "`nALERTAS" -ForegroundColor Red
            foreach ($A in $Alertas) { Write-Host $A -ForegroundColor Red }
        }

        # Grafico comparativo
        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nCOMPARATIVA" -ForegroundColor White
        Write-Host ""

        $RPMMaxReal = ($ConRPM | Measure-Object -Property RPM -Maximum).Maximum
        $RefComp    = [math]::Max($RPMMaxReal, $RPMMaxReferencia)

        $ConRPM | Sort-Object RPM -Descending | ForEach-Object {
            $Pct    = [math]::Min(($_.RPM / $RefComp) * 100, 100)
            $Llenos = [int](($Pct / 100) * 28)
            $Barra  = "[" + ("#" * $Llenos) + ("-" * (28 - $Llenos)) + "]"
            $Color  = Get-ColorRPM -RPM $_.RPM
            $NCorto = if ($_.Nombre.Length -gt 22) {
                $_.Nombre.Substring(0,19)+"..." } else { $_.Nombre }
            Write-Host ("   {0,-22} {1}  {2:N0} RPM" -f $NCorto, $Barra, $_.RPM) `
                       -ForegroundColor $Color
        }

        # Diagnostico final
        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nDIAGNOSTICO" -ForegroundColor White
        Write-Host ""
        if ($Alertas.Count -gt 0) {
            Write-Host "   ATENCION: velocidades elevadas. Revisa la refrigeracion." `
                       -ForegroundColor Red
        } elseif ($Activos -eq 0) {
            Write-Host "   Todos los ventiladores en reposo (0 RPM)." -ForegroundColor Yellow
            Write-Host "   Si la temperatura es alta podria haber un problema." `
                       -ForegroundColor Yellow
        } else {
            Write-Host "   Sistema de ventilacion en estado normal." -ForegroundColor Green
            if ($Parados -gt 0) {
                Write-Host ("   ({0} en reposo - puede ser normal)" -f $Parados) `
                           -ForegroundColor Gray
            }
        }
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
            Show-Ventiladores
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
