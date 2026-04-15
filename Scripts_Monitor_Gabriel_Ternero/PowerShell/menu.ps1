# ==============================================================================
#  menu.ps1 - Panel de Control Principal en PowerShell
#  Descripcion : Menu interactivo que lanza cada script de monitorizacion
#                en su propia sesion de PowerShell, evitando colisiones
#                entre funciones con el mismo nombre.
#  Requisitos  : PowerShell 5.1 o superior. Todos los .ps1 en la misma carpeta.
#  Uso         : .\menu.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  POR QUE NO USAMOS DOT-SOURCING EN ESTE MENU
#
#  La version anterior usaba dot-sourcing (. .\script.ps1) para cargar
#  cada script. Esto causaba un problema grave: todos los scripts tienen
#  una funcion llamada exactamente "Start-Monitor". Al cargarlos todos,
#  cada uno sobreescribia la funcion del anterior, y al final solo
#  quedaba la ultima funcion cargada (temperatura_monitor.ps1).
#  Por eso todas las opciones lanzaban el monitor de temperatura.
#
#  La solucion es lanzar cada script en su PROPIA sesion de PowerShell:
#
#    powershell.exe -File ".\cpu_monitor.ps1"
#
#  Asi cada script corre de forma completamente aislada, con sus propias
#  funciones y variables, sin interferir con los demas ni con el menu.
#
#  Analogia: en lugar de meter a todos los empleados en la misma oficina
#  donde se pisarian unos a otros, cada uno trabaja en su propio despacho
#  y el menu es la recepcion que les da paso de uno en uno.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  RUTA BASE: carpeta donde esta este script
# ==============================================================================
$CarpetaBase = $PSScriptRoot
if (-not $CarpetaBase) {
    $CarpetaBase = (Get-Location).Path
}


# ==============================================================================
#  DEFINICION DE SCRIPTS DISPONIBLES
#  Cada entrada tiene el nombre del archivo y su tipo (monitor o informe).
#  El menu comprueba si el archivo existe y lo lanza cuando el usuario lo pide.
# ==============================================================================
$Scripts = @(
    @{ Numero = "1";  Titulo = "Monitor de CPU";              Archivo = "cpu_monitor.ps1";             Tipo = "monitor"; Descripcion = "Uso por nucleo, frecuencia, cola del procesador"        },
    @{ Numero = "2";  Titulo = "Monitor de Memoria RAM";      Archivo = "memoria_monitor.ps1";          Tipo = "monitor"; Descripcion = "RAM y pagina virtual: uso, disponible, paginacion"       },
    @{ Numero = "3";  Titulo = "Monitor de Almacenamiento";   Archivo = "almacenamiento_monitor.ps1";   Tipo = "monitor"; Descripcion = "Espacio por unidad, velocidad I/O, cola de disco"        },
    @{ Numero = "4";  Titulo = "Monitor de Temperaturas";     Archivo = "temperatura_monitor.ps1";      Tipo = "monitor"; Descripcion = "Sensores termicos via ACPI y LHM (equipo fisico)"        },
    @{ Numero = "5";  Titulo = "Monitor de GPU";              Archivo = "gpu_monitor.ps1";              Tipo = "monitor"; Descripcion = "Uso, VRAM y temperatura GPU (NVIDIA/AMD/LHM)"            },
    @{ Numero = "6";  Titulo = "Monitor de Red";              Archivo = "red_monitor.ps1";              Tipo = "monitor"; Descripcion = "Adaptadores, velocidad subida/bajada, conexiones TCP"    },
    @{ Numero = "7";  Titulo = "Monitor de Bateria";          Archivo = "bateria_monitor.ps1";          Tipo = "monitor"; Descripcion = "Nivel de carga, estado, autonomia (solo portatiles)"     },
    @{ Numero = "8";  Titulo = "Monitor de Ventiladores";     Archivo = "ventiladores_monitor.ps1";     Tipo = "monitor"; Descripcion = "RPM de ventiladores (requiere LHM con WMI activo)"       },
    @{ Numero = "9";  Titulo = "Monitor de Procesos";         Archivo = "procesos_monitor.ps1";         Tipo = "monitor"; Descripcion = "Top por CPU y RAM, hilos, handles, usuarios"             },
    @{ Numero = "10"; Titulo = "Informacion del Sistema";     Archivo = "sistema_info.ps1";             Tipo = "informe"; Descripcion = "Informe estatico: SO, CPU, RAM, discos, red, BIOS"       }
)


# ==============================================================================
#  FUNCIONES DE INTERFAZ
# ==============================================================================

function Clear-Pantalla { Clear-Host }

# --- Comprobar si un script existe en la carpeta ----------------------------
function Test-ScriptDisponible {
    param([string]$Archivo)
    $Ruta = Join-Path $CarpetaBase $Archivo
    return (Test-Path $Ruta)
}

# --- Indicador visual de disponibilidad -------------------------------------
function Write-Indicador {
    param([string]$Archivo)
    if (Test-ScriptDisponible $Archivo) {
        Write-Host "[OK]" -ForegroundColor Green -NoNewline
    } else {
        Write-Host "[--]" -ForegroundColor Red -NoNewline
    }
}

# --- Banner del menu --------------------------------------------------------
function Write-Banner {
    $Ahora    = Get-Date -Format "yyyy-MM-dd  HH:mm:ss"
    $Hostname = $env:COMPUTERNAME

    $SO = ""
    try {
        $SO = (Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).Caption
    } catch { }

    $EstadoHW = ""
    try {
        $CntCPU = [System.Diagnostics.PerformanceCounter]::new(
            "Processor","% Processor Time","_Total")
        $null = $CntCPU.NextValue()
        Start-Sleep -Milliseconds 400
        $PctCPU = [math]::Round($CntCPU.NextValue(), 0)
        $CntCPU.Dispose()

        $SOWMI  = Get-CimInstance Win32_OperatingSystem
        $PctRAM = [math]::Round(
            (($SOWMI.TotalVisibleMemorySize - $SOWMI.FreePhysicalMemory) /
              $SOWMI.TotalVisibleMemorySize) * 100, 0)
        $EstadoHW = "CPU: $PctCPU%   RAM: $PctRAM%"
    } catch { }

    Write-Host ("+{0}+" -f ("=" * 63)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "".PadRight(63)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "   PANEL DE CONTROL - MONITOR DE HARDWARE".PadRight(63)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "".PadRight(63)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f ("   Fecha   : $Ahora").PadRight(63)) -ForegroundColor Gray
    Write-Host ("|{0}|" -f ("   Equipo  : $Hostname").PadRight(63)) -ForegroundColor Gray
    if ($SO)        { Write-Host ("|{0}|" -f ("   Sistema : $SO").PadRight(63)) -ForegroundColor Gray }
    if ($EstadoHW)  { Write-Host ("|{0}|" -f ("   Estado  : $EstadoHW").PadRight(63)) -ForegroundColor Gray }
    Write-Host ("|{0}|" -f "".PadRight(63)) -ForegroundColor Cyan
    Write-Host ("+{0}+" -f ("=" * 63)) -ForegroundColor Cyan
}

# --- Pantalla principal del menu --------------------------------------------
function Show-Menu {
    Clear-Pantalla
    Write-Banner
    Write-Host ""
    Write-Host "  Escribe el numero y pulsa Enter:" -ForegroundColor White
    Write-Host ""

    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray
    Write-Host ("  |{0}|" -f "          MONITORES EN TIEMPO REAL".PadRight(61)) -ForegroundColor White
    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray

    foreach ($S in $Scripts) {
        if ($S.Tipo -eq "monitor") {
            Write-Host ("  | [{0,2}] " -f $S.Numero) -NoNewline
            Write-Indicador $S.Archivo
            Write-Host ("  {0,-34}|" -f $S.Titulo) -ForegroundColor White
            Write-Host ("  |        {0,-53}|" -f $S.Descripcion) -ForegroundColor DarkGray
            Write-Host ("  |{0}|" -f "".PadRight(61)) -ForegroundColor DarkGray
        }
    }

    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray
    Write-Host ("  |{0}|" -f "          INFORMES ESTATICOS".PadRight(61)) -ForegroundColor White
    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray

    foreach ($S in $Scripts) {
        if ($S.Tipo -eq "informe") {
            Write-Host ("  | [{0,2}] " -f $S.Numero) -NoNewline
            Write-Indicador $S.Archivo
            Write-Host ("  {0,-34}|" -f $S.Titulo) -ForegroundColor White
            Write-Host ("  |        {0,-53}|" -f $S.Descripcion) -ForegroundColor DarkGray
            Write-Host ("  |{0}|" -f "".PadRight(61)) -ForegroundColor DarkGray
        }
    }

    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray
    Write-Host ("  |  [ A]  Estado de modulos - ver que scripts estan disponibles  |") -ForegroundColor Gray
    Write-Host ("  |  [ S]  Salir del panel de control                             |") -ForegroundColor Gray
    Write-Host ("  +{0}+" -f ("-" * 61)) -ForegroundColor DarkGray
    Write-Host ""
}

# --- Pantalla de estado de modulos ------------------------------------------
function Show-EstadoModulos {
    Clear-Pantalla
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host "  ESTADO DE MODULOS" -ForegroundColor Cyan
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Archivos necesarios en la carpeta: $CarpetaBase"
    Write-Host ""

    $Cargados  = 0
    $Faltantes = 0

    foreach ($S in $Scripts) {
        $Ruta = Join-Path $CarpetaBase $S.Archivo
        if (Test-Path $Ruta) {
            Write-Host ("   [OK]  {0}" -f $S.Archivo) -ForegroundColor Green
            $Cargados++
        } else {
            Write-Host ("   [--]  {0}  <- No encontrado" -f $S.Archivo) -ForegroundColor Red
            $Faltantes++
        }
    }

    Write-Host ""
    Write-Host ("  Disponibles: {0}/{1}" -f $Cargados, $Scripts.Count)

    if ($Faltantes -gt 0) {
        Write-Host ("  Faltan: {0} archivo(s)" -f $Faltantes) -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Asegurate de que todos los .ps1 estan en la misma carpeta." -ForegroundColor Yellow
    } else {
        Write-Host "  Todos los modulos estan disponibles." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host "  Pulsa Enter para volver..." -ForegroundColor Gray
    Read-Host | Out-Null
}

# --- Pantalla de transicion -------------------------------------------------
function Show-Transicion {
    param($Script)
    Clear-Pantalla
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host ("  Lanzando: {0}" -f $Script.Titulo) -ForegroundColor Cyan
    Write-Host ("=" * 62) -ForegroundColor Cyan
    Write-Host ""
    if ($Script.Tipo -eq "monitor") {
        Write-Host "  Monitor en TIEMPO REAL." -ForegroundColor White
        Write-Host "  Se abrira en esta misma ventana." -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Para volver al menu: pulsa  Ctrl + C" -ForegroundColor Yellow
    } else {
        Write-Host "  Informe ESTATICO." -ForegroundColor White
        Write-Host "  Se ejecutara una vez. Podras leerlo antes de volver." -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "  Iniciando en 2 segundos..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

# --- Pantalla de despedida --------------------------------------------------
function Show-Despedida {
    Clear-Pantalla
    Write-Host ("+{0}+" -f ("=" * 45)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "".PadRight(45)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "   Hasta luego!".PadRight(45)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "".PadRight(45)) -ForegroundColor Cyan
    Write-Host ("|{0}|" -f "   Gracias por usar el Monitor de Hardware.".PadRight(45)) -ForegroundColor Gray
    Write-Host ("|{0}|" -f "".PadRight(45)) -ForegroundColor Cyan
    Write-Host ("+{0}+" -f ("=" * 45)) -ForegroundColor Cyan
    Write-Host ""
}


# ==============================================================================
#  LOGICA DE EJECUCION
#  Cada script se lanza con powershell.exe -File en lugar de dot-sourcing.
#  Esto garantiza que cada monitor corre en su propia sesion aislada,
#  con sus propias funciones, sin colisionar con las de los demas scripts.
# ==============================================================================
function Invoke-Script {
    param($ScriptObj)

    $Ruta = Join-Path $CarpetaBase $ScriptObj.Archivo

    # Verificamos que el archivo existe
    if (-not (Test-Path $Ruta)) {
        Write-Host ""
        Write-Host ("  El archivo '{0}' no esta disponible." -f $ScriptObj.Archivo) `
                   -ForegroundColor Red
        Write-Host "  Comprueba que esta en la misma carpeta que menu.ps1" `
                   -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        return
    }

    Show-Transicion -Script $ScriptObj

    try {
        # Lanzamos el script en la misma ventana de PowerShell pero en
        # un proceso hijo. -ExecutionPolicy Bypass garantiza que se ejecuta
        # sin problemas de politica de ejecucion.
        # -NoProfile evita cargar el perfil del usuario (mas rapido).
        # -File indica la ruta del script a ejecutar.
        $Proceso = Start-Process -FilePath "powershell.exe" `
                                 -ArgumentList "-NoProfile", `
                                               "-ExecutionPolicy", "Bypass", `
                                               "-File", "`"$Ruta`"" `
                                 -Wait `
                                 -NoNewWindow `
                                 -PassThru

        # -Wait hace que el menu espere a que el monitor termine (Ctrl+C)
        # -NoNewWindow mantiene todo en la misma ventana de consola
        # -PassThru devuelve el objeto proceso para comprobar el codigo de salida

    } catch {
        Write-Host ""
        Write-Host "  Error al lanzar el script:" -ForegroundColor Red
        Write-Host ("  {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }

    # Tras volver del script, gestionamos el retorno segun el tipo
    Write-Host ""
    if ($ScriptObj.Tipo -eq "informe") {
        Write-Host "  Pulsa Enter si has terminado de leer..." -ForegroundColor Gray
        Read-Host | Out-Null
    } else {
        Write-Host "  Volviendo al menu principal..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}


# ==============================================================================
#  BUCLE PRINCIPAL DEL MENU
# ==============================================================================
function Start-Menu {
    $Continuar = $true

    while ($Continuar) {
        Show-Menu
        $Eleccion = Read-Host "  Tu eleccion"

        if ([string]::IsNullOrWhiteSpace($Eleccion)) { continue }

        $Eleccion = $Eleccion.Trim()

        # Opciones especiales
        if ($Eleccion.ToUpper() -eq "A") {
            Show-EstadoModulos
            continue
        }

        if ($Eleccion.ToUpper() -eq "S") {
            $Continuar = $false
            continue
        }

        # Buscamos el script que corresponde al numero elegido
        $ScriptElegido = $null
        foreach ($S in $Scripts) {
            if ($S.Numero -eq $Eleccion) {
                $ScriptElegido = $S
                break
            }
        }

        if ($ScriptElegido) {
            Invoke-Script -ScriptObj $ScriptElegido
        } else {
            Write-Host ""
            Write-Host "  Opcion no reconocida. Escribe un numero del 1 al 10," `
                       -ForegroundColor Yellow
            Write-Host "  'A' para ver modulos disponibles o 'S' para salir." `
                       -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }

    Show-Despedida
}


# ==============================================================================
#  PUNTO DE ENTRADA
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Start-Menu
}
