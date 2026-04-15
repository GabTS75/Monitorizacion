# ==============================================================================
#  sistema_info.ps1 - Informacion Estatica del Sistema en PowerShell
#  Descripcion : Genera un informe completo del hardware y software del
#                sistema. A diferencia de los monitores, este script se
#                ejecuta UNA sola vez y muestra la informacion completa.
#  Requisitos  : PowerShell 5.1 o superior. Sin dependencias externas.
#                Algunos datos requieren ejecutar como Administrador.
#  Uso         : .\sistema_info.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  INFORMACION ESTATICA vs DINAMICA
#
#  Este script recoge datos que NO cambian (o cambian muy poco):
#    Modelo de CPU, numero de nucleos, frecuencia maxima
#    RAM total instalada, tipo de memoria
#    Sistema operativo y version
#    Discos instalados y capacidad total
#    Interfaces de red y direcciones MAC
#    Informacion de la BIOS/UEFI
#    Usuarios del sistema
#
#  Los datos que cambian constantemente (uso de CPU, RAM libre, velocidad
#  de red...) los cubren los scripts de monitorizacion individuales.
#
#  Analogia: este script es la ficha tecnica del equipo. Los monitores
#  son el cuadro de instrumentos mientras el equipo esta en marcha.
#  Necesitas ambos: la ficha para saber con que trabajas, y los
#  instrumentos para saber como esta funcionando ahora mismo.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Get-BytesLegibles {
    param([long]$Bytes)
    if     ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    elseif ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    elseif ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    else                    { return "$Bytes B"                     }
}

# --- Imprimir cabecera de seccion --------------------------------------------
# Centraliza el estilo visual de todas las secciones del informe.
# Todos los separadores usan solo caracteres ASCII para evitar problemas
# de codificacion en Windows en espanol.
#
function Write-Seccion {
    param([string]$Titulo)
    Write-Host ""
    Write-Host ("-" * 65) -ForegroundColor DarkGray
    Write-Host ("  $Titulo") -ForegroundColor Cyan
    Write-Host ("-" * 65) -ForegroundColor DarkGray
}

# --- Imprimir linea de dato alineada -----------------------------------------
# Muestra etiqueta y valor alineados en columnas para facilitar la lectura.
# Ejemplo:   Sistema operativo         :  Windows 11 Pro
#
function Write-Dato {
    param(
        [string]$Etiqueta,
        [string]$Valor,
        [string]$Color = "White"
    )
    Write-Host ("   {0,-28} :  " -f $Etiqueta) -NoNewline
    Write-Host $Valor -ForegroundColor $Color
}


# ==============================================================================
#  SECCIONES DEL INFORME
# ==============================================================================

# --- Seccion 1: Encabezado ---------------------------------------------------
function Write-Encabezado {
    $Ahora    = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Hostname = $env:COMPUTERNAME
    $SO       = (Get-CimInstance Win32_OperatingSystem).Caption

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  INFORME DE SISTEMA - Informacion Estatica" -ForegroundColor Cyan
    Write-Host ("  Generado el : $Ahora") -ForegroundColor Gray
    Write-Host ("  Equipo      : $Hostname") -ForegroundColor Gray
    Write-Host ("  Sistema     : $SO") -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan
}


# --- Seccion 2: Sistema operativo --------------------------------------------
function Write-SistemaOperativo {
    Write-Seccion "SISTEMA OPERATIVO"

    $SO      = Get-CimInstance -ClassName Win32_OperatingSystem
    $CS      = Get-CimInstance -ClassName Win32_ComputerSystem

    # Uptime: tiempo que lleva encendido el sistema
    $Uptime  = (Get-Date) - $SO.LastBootUpTime
    $BootStr = $SO.LastBootUpTime.ToString("yyyy-MM-dd HH:mm:ss")

    Write-Dato "Sistema operativo"    $SO.Caption
    Write-Dato "Version"              $SO.Version
    Write-Dato "Build"                $SO.BuildNumber
    Write-Dato "Arquitectura"         $SO.OSArchitecture
    Write-Dato "Tipo instalacion"     $SO.InstallDate.ToString("yyyy-MM-dd")
    Write-Dato "Ultimo arranque"      $BootStr
    Write-Dato "Tiempo encendido"     ("{0}d {1}h {2}m" -f $Uptime.Days, $Uptime.Hours, $Uptime.Minutes)
    Write-Dato "Nombre del equipo"    $env:COMPUTERNAME
    Write-Dato "Dominio / Grupo"      $(if($CS.PartOfDomain){"Dominio: $($CS.Domain)"}else{"Grupo trabajo: $($CS.Workgroup)"})
    Write-Dato "Tipo de sistema"      $CS.SystemType
    Write-Dato "Fabricante equipo"    $CS.Manufacturer
    Write-Dato "Modelo equipo"        $CS.Model

    # Version de PowerShell
    Write-Dato "Version PowerShell"   ("$($PSVersionTable.PSVersion)  (este script)")
}


# --- Seccion 3: Procesador ---------------------------------------------------
function Write-Procesador {
    Write-Seccion "PROCESADOR (CPU)"

    $CPUs = Get-CimInstance -ClassName Win32_Processor

    # En servidores puede haber varios procesadores fisicos
    $NumCPU = 0
    foreach ($CPU in $CPUs) {
        $NumCPU++
        if (@($CPUs).Count -gt 1) {
            Write-Host ("   --- Procesador fisico #{0} ---" -f $NumCPU) `
                       -ForegroundColor Gray
        }

        Write-Dato "Modelo"               $CPU.Name.Trim()
        Write-Dato "Fabricante"           $CPU.Manufacturer
        Write-Dato "Arquitectura"         $(switch($CPU.Architecture){
                                            0{"x86"} 1{"MIPS"} 2{"Alpha"}
                                            3{"PowerPC"} 5{"ARM"} 6{"ia64"}
                                            9{"x64"} default{"Desconocida"}})
        Write-Dato "Nucleos fisicos"      $CPU.NumberOfCores.ToString()
        Write-Dato "Nucleos logicos"      $CPU.NumberOfLogicalProcessors.ToString()
        Write-Dato "Frecuencia maxima"    ("{0:N2} GHz" -f ($CPU.MaxClockSpeed / 1000))
        Write-Dato "Frecuencia actual"    ("{0:N2} GHz" -f ($CPU.CurrentClockSpeed / 1000))
        Write-Dato "Nivel de socket"      $CPU.SocketDesignation
        Write-Dato "Nivel L2 cache"       $(if($CPU.L2CacheSize){"{0} KB" -f $CPU.L2CacheSize}else{"N/A"})
        Write-Dato "Nivel L3 cache"       $(if($CPU.L3CacheSize){"{0} KB" -f $CPU.L3CacheSize}else{"N/A"})
        Write-Dato "Virtualizacion"       $(if($CPU.VirtualizationFirmwareEnabled){"Habilitada"}else{"Deshabilitada o no disponible"})
    }
}


# --- Seccion 4: Memoria RAM --------------------------------------------------
function Write-MemoriaRAM {
    Write-Seccion "MEMORIA RAM"

    $SO  = Get-CimInstance -ClassName Win32_OperatingSystem
    $CS  = Get-CimInstance -ClassName Win32_ComputerSystem

    $RAMTotal     = $CS.TotalPhysicalMemory
    $RAMDisponible= $SO.FreePhysicalMemory * 1KB
    $RAMUsada     = $RAMTotal - $RAMDisponible

    Write-Dato "RAM total instalada"  (Get-BytesLegibles $RAMTotal)
    Write-Dato "RAM usada ahora"      (Get-BytesLegibles $RAMUsada)
    Write-Dato "RAM disponible ahora" (Get-BytesLegibles $RAMDisponible)

    # Modulos fisicos de memoria
    # Win32_PhysicalMemory da informacion de cada modulo RAM instalado
    $Modulos = Get-CimInstance -ClassName Win32_PhysicalMemory `
                               -ErrorAction SilentlyContinue

    if ($Modulos) {
        Write-Host ""
        Write-Host "   MODULOS DE MEMORIA INSTALADOS:" -ForegroundColor Gray

        $NumSlot = 0
        foreach ($Mod in $Modulos) {
            $NumSlot++
            $CapStr   = Get-BytesLegibles $Mod.Capacity
            $TipoStr  = switch ($Mod.MemoryType) {
                20 {"DDR"} 21 {"DDR2"} 24 {"DDR3"} 26 {"DDR4"} 34 {"DDR5"}
                default {
                    # SMBIOSMemoryType es mas fiable en sistemas modernos
                    switch ($Mod.SMBIOSMemoryType) {
                        26 {"DDR4"} 34 {"DDR5"} 24 {"DDR3"}
                        default {"Tipo $($Mod.SMBIOSMemoryType)"}
                    }
                }
            }
            $VelStr   = if ($Mod.Speed) { "$($Mod.Speed) MHz" } else { "N/A" }
            $FabStr   = if ($Mod.Manufacturer) { $Mod.Manufacturer.Trim() } else { "N/A" }
            $SlotStr  = if ($Mod.DeviceLocator) { $Mod.DeviceLocator } else { "Slot $NumSlot" }

            Write-Host ("   Slot {0,-12}  {1,-8}  {2,-6}  {3,-10}  {4}" -f `
                        $SlotStr, $CapStr, $TipoStr, $VelStr, $FabStr)
        }
    }

    # Archivo de pagina (Swap de Windows)
    Write-Host ""
    $Pagina = Get-CimInstance -ClassName Win32_PageFileUsage -ErrorAction SilentlyContinue
    if ($Pagina) {
        $TotalPag = 0
        foreach ($P in $Pagina) { $TotalPag += $P.AllocatedBaseSize }
        Write-Dato "Archivo de pagina"    ("{0} MB  (en {1})" -f $TotalPag, (($Pagina | ForEach-Object {$_.Name}) -join ", "))
    } else {
        Write-Dato "Archivo de pagina"    "No configurado"
    }
}


# --- Seccion 5: Almacenamiento -----------------------------------------------
function Write-Almacenamiento {
    Write-Seccion "ALMACENAMIENTO"

    # Discos fisicos
    $DiscosFisicos = Get-CimInstance -ClassName Win32_DiskDrive
    Write-Host "   DISCOS FISICOS:" -ForegroundColor Gray
    Write-Host ""

    foreach ($Disco in $DiscosFisicos) {
        $TamStr   = Get-BytesLegibles $Disco.Size
        $ModeloStr= if ($Disco.Model.Length -gt 40) {
            $Disco.Model.Substring(0,37)+"..."
        } else { $Disco.Model }

        Write-Dato "  Modelo"             $ModeloStr
        Write-Dato "  Tamano"             $TamStr
        Write-Dato "  Interfaz"           $Disco.InterfaceType
        Write-Dato "  Particiones"        $Disco.Partitions.ToString()
        Write-Dato "  N. de serie"        $(if($Disco.SerialNumber){$Disco.SerialNumber.Trim()}else{"N/A"})
        if ($Disco.FirmwareRevision) {
            Write-Dato "  Firmware"        $Disco.FirmwareRevision.Trim()
        }
        Write-Host ""
    }

    # Unidades logicas (letras de unidad)
    $Unidades = Get-CimInstance -ClassName Win32_LogicalDisk |
                Where-Object { $_.DriveType -eq 3 }

    Write-Host "   UNIDADES LOGICAS:" -ForegroundColor Gray
    Write-Host ""
    Write-Host ("   {0,-6}  {1,-10}  {2,12}  {3,12}  {4,12}  {5}" -f `
                "Unidad","Tipo FS","Total","Usado","Libre","Uso%") -ForegroundColor Gray
    Write-Host ("   {0,-6}  {1,-10}  {2,12}  {3,12}  {4,12}  {5}" -f `
                "------","----------","------------","------------","------------","----") `
               -ForegroundColor DarkGray

    foreach ($U in $Unidades) {
        $Total  = $U.Size
        $Libre  = $U.FreeSpace
        $Usado  = $Total - $Libre
        $PctUso = if ($Total -gt 0) { [math]::Round(($Usado/$Total)*100,1) } else { 0 }

        $Color = if ($PctUso -ge 95) { "Magenta" } `
                 elseif ($PctUso -ge 85) { "Red" } `
                 elseif ($PctUso -ge 75) { "Yellow" } `
                 else { "Green" }

        Write-Host ("   {0,-6}  {1,-10}  {2,12}  {3,12}  {4,12}  " -f `
            $U.DeviceID,
            $U.FileSystem,
            (Get-BytesLegibles $Total),
            (Get-BytesLegibles $Usado),
            (Get-BytesLegibles $Libre)) -NoNewline
        Write-Host ("{0,4:N1}%" -f $PctUso) -ForegroundColor $Color
    }
}


# --- Seccion 6: Tarjeta grafica ----------------------------------------------
function Write-GPU {
    Write-Seccion "TARJETA GRAFICA (GPU)"

    $GPUs = Get-CimInstance -ClassName Win32_VideoController
    $Num  = 0

    foreach ($GPU in $GPUs) {
        $Num++
        if (@($GPUs).Count -gt 1) {
            Write-Host ("   --- GPU #{0} ---" -f $Num) -ForegroundColor Gray
        }

        Write-Dato "Nombre"               $GPU.Name
        Write-Dato "Fabricante"           $(if($GPU.AdapterCompatibility){$GPU.AdapterCompatibility}else{"N/A"})
        Write-Dato "Memoria dedicada"     $(if($GPU.AdapterRAM -and $GPU.AdapterRAM -gt 0){ Get-BytesLegibles $GPU.AdapterRAM }else{"N/A (usar GPU-Z para dato real)"})
        Write-Dato "Resolucion actual"    ("{0} x {1}" -f $GPU.CurrentHorizontalResolution, $GPU.CurrentVerticalResolution)
        Write-Dato "Bits de color"        $(if($GPU.CurrentBitsPerPixel){"$($GPU.CurrentBitsPerPixel) bits"}else{"N/A"})
        Write-Dato "Tasa refresco"        $(if($GPU.CurrentRefreshRate){"$($GPU.CurrentRefreshRate) Hz"}else{"N/A"})
        Write-Dato "Version driver"       $(if($GPU.DriverVersion){$GPU.DriverVersion}else{"N/A"})
        Write-Dato "Fecha driver"         $(if($GPU.DriverDate){$GPU.DriverDate.ToString("yyyy-MM-dd")}else{"N/A"})
        Write-Dato "Estado"               $GPU.Status
        Write-Host ""
    }
}


# --- Seccion 7: Red ----------------------------------------------------------
function Write-Red {
    Write-Seccion "INTERFACES DE RED"

    # Adaptadores con IP habilitada
    $Configs = Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration |
               Where-Object { $_.IPEnabled -eq $true }

    foreach ($Config in $Configs) {
        Write-Host ("   [{0}]" -f $Config.Description) -ForegroundColor White

        # IPv4
        $IPv4 = $Config.IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' }
        if ($IPv4) {
            Write-Dato "  IPv4"              ($IPv4 -join ", ")
            $Mascara = $Config.IPSubnet | Where-Object { $_ -match '^\d' } |
                       Select-Object -First 1
            if ($Mascara) { Write-Dato "  Mascara"         $Mascara }
        }

        # IPv6
        $IPv6 = $Config.IPAddress | Where-Object { $_ -match ':' }
        if ($IPv6) {
            $IPv6Limpia = ($IPv6 | ForEach-Object { ($_ -split '%')[0] }) -join ", "
            Write-Dato "  IPv6"              $IPv6Limpia
        }

        # MAC y otros datos
        if ($Config.MACAddress)       { Write-Dato "  MAC"               $Config.MACAddress }
        $GW = $Config.DefaultIPGateway -join ", "
        if ($GW)                      { Write-Dato "  Puerta de enlace"  $GW }
        $DNS = $Config.DNSServerSearchOrder -join ", "
        if ($DNS)                     { Write-Dato "  DNS"               $DNS }
        Write-Dato "  DHCP"               $(if($Config.DHCPEnabled){"Si"}else{"No (IP estatica)"})

        Write-Host ""
    }
}


# --- Seccion 8: BIOS/UEFI ---------------------------------------------------
function Write-BIOS {
    Write-Seccion "BIOS / UEFI"

    $BIOS  = Get-CimInstance -ClassName Win32_BIOS
    $Board = Get-CimInstance -ClassName Win32_BaseBoard

    Write-Dato "Fabricante BIOS"      $BIOS.Manufacturer
    Write-Dato "Version BIOS"         $BIOS.SMBIOSBIOSVersion
    Write-Dato "Fecha BIOS"           $(try{$BIOS.ReleaseDate.ToString("yyyy-MM-dd")}catch{"N/A"})
    Write-Dato "Tipo firmware"        $(if($BIOS.BIOSVersion -match "UEFI" -or
                                          $BIOS.SMBIOSBIOSVersion -match "UEFI")
                                          {"UEFI"}else{"BIOS (o no determinado)"})

    Write-Host ""
    Write-Dato "Fabricante placa"     $(if($Board.Manufacturer){$Board.Manufacturer}else{"N/A"})
    Write-Dato "Modelo placa"         $(if($Board.Product){$Board.Product}else{"N/A"})
    Write-Dato "Version placa"        $(if($Board.Version){$Board.Version}else{"N/A"})
    Write-Dato "N. serie placa"       $(if($Board.SerialNumber){$Board.SerialNumber.Trim()}else{"N/A"})
}


# --- Seccion 9: Usuarios del sistema ----------------------------------------
function Write-Usuarios {
    Write-Seccion "USUARIOS DEL SISTEMA"

    # Usuarios locales del equipo
    try {
        $Usuarios = Get-LocalUser -ErrorAction Stop
        Write-Host "   CUENTAS LOCALES:" -ForegroundColor Gray
        Write-Host ""
        Write-Host ("   {0,-22}  {1,-10}  {2,-8}  {3}" -f `
                    "Nombre","Estado","Admin","Ultimo acceso") -ForegroundColor Gray
        Write-Host ("   {0,-22}  {1,-10}  {2,-8}  {3}" -f `
                    "----------------------","----------","--------","-------------------") `
                   -ForegroundColor DarkGray

        # Obtenemos los miembros del grupo Administradores para marcarlos
        try {
            $Admins = Get-LocalGroupMember -Group "Administrators" `
                                           -ErrorAction Stop |
                      ForEach-Object { $_.Name -replace ".*\\", "" }
        } catch {
            $Admins = @()
        }

        foreach ($U in $Usuarios) {
            $Estado  = if ($U.Enabled) { "Activa" } else { "Desactivada" }
            $EsAdmin = if ($Admins -contains $U.Name) { "Si" } else { "No" }
            $UltAcc  = if ($U.LastLogon) {
                $U.LastLogon.ToString("yyyy-MM-dd HH:mm")
            } else { "Nunca / N/A" }

            $Color = if (-not $U.Enabled) { "DarkGray" } `
                     elseif ($EsAdmin -eq "Si") { "Yellow" } `
                     else { "White" }

            Write-Host ("   {0,-22}  {1,-10}  {2,-8}  {3}" -f `
                        $U.Name, $Estado, $EsAdmin, $UltAcc) -ForegroundColor $Color
        }
    }
    catch {
        Write-Host "   Get-LocalUser no disponible en esta edicion de Windows." `
                   -ForegroundColor Gray
        Write-Host "   Usa 'net user' en CMD para ver los usuarios locales." `
                   -ForegroundColor Gray
    }

    # Sesiones activas ahora mismo
    Write-Host ""
    Write-Host "   SESIONES ACTIVAS AHORA:" -ForegroundColor Gray
    Write-Host ""
    try {
        $Sesiones = Get-CimInstance -ClassName Win32_LogonSession |
                    Where-Object { $_.LogonType -eq 2 -or $_.LogonType -eq 10 }

        if (@($Sesiones).Count -gt 0) {
            foreach ($Ses in $Sesiones) {
                $TipoStr = switch ($Ses.LogonType) {
                    2  { "Interactiva (local)" }
                    10 { "Remota (RDP/Terminal)" }
                    default { "Tipo $($Ses.LogonType)" }
                }
                $Inicio = $Ses.StartTime.ToString("yyyy-MM-dd HH:mm:ss")
                Write-Host ("   Sesion iniciada : {0}  ({1})" -f $Inicio, $TipoStr)
            }
        } else {
            Write-Host "   No se detectaron sesiones interactivas activas."
        }
    }
    catch {
        Write-Host "   No se pudieron obtener las sesiones activas." -ForegroundColor Gray
    }
}


# --- Seccion 10: Resumen ejecutivo ------------------------------------------
function Write-Resumen {
    Write-Seccion "RESUMEN EJECUTIVO"

    $CPU  = Get-CimInstance -ClassName Win32_Processor
    if ($CPU -is [array]) { $CPU = $CPU[0] }
    $CS   = Get-CimInstance -ClassName Win32_ComputerSystem
    $SO   = Get-CimInstance -ClassName Win32_OperatingSystem
    $BIOS = Get-CimInstance -ClassName Win32_BIOS

    # Espacio total en disco
    $TotalDisco = 0
    Get-CimInstance -ClassName Win32_LogicalDisk |
        Where-Object { $_.DriveType -eq 3 } |
        ForEach-Object { $TotalDisco += $_.Size }

    $Uptime = (Get-Date) - $SO.LastBootUpTime

    Write-Host ""
    Write-Host ("   +{0}+" -f ("-" * 55))
    Write-Host ("   |  {0,-53}|" -f "RESUMEN DEL SISTEMA")
    Write-Host ("   +{0}+" -f ("-" * 55))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Equipo",    $env:COMPUTERNAME)
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Fabricante", ($CS.Manufacturer -replace "  "," "))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Modelo",    ($CS.Model -replace "  "," "))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "SO",        ($SO.Caption -replace "Microsoft ",""))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "CPU",       ($CPU.Name.Trim() -replace "\(R\)|\(TM\)",""))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Nucleos",   ("{0} fisicos / {1} logicos" -f $CPU.NumberOfCores, $CPU.NumberOfLogicalProcessors))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "RAM",       (Get-BytesLegibles $CS.TotalPhysicalMemory))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Disco total",(Get-BytesLegibles $TotalDisco))
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "BIOS",      $BIOS.SMBIOSBIOSVersion)
    Write-Host ("   |  {0,-18} : {1,-32}|" -f "Uptime",    ("{0}d {1}h {2}m" -f $Uptime.Days,$Uptime.Hours,$Uptime.Minutes))
    Write-Host ("   +{0}+" -f ("-" * 55))
    Write-Host ""
}


# ==============================================================================
#  FUNCION PRINCIPAL: ejecuta todas las secciones en orden
# ==============================================================================
function Show-SistemaInfo {

    Clear-Host

    Write-Encabezado
    Write-SistemaOperativo
    Write-Procesador
    Write-MemoriaRAM
    Write-Almacenamiento
    Write-GPU
    Write-Red
    Write-BIOS
    Write-Usuarios
    Write-Resumen

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  Informe completado." -ForegroundColor Green
    Write-Host "  Este script NO monitoriza en tiempo real." -ForegroundColor Gray
    Write-Host "  Para monitorizacion continua usa menu.ps1" -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host ""
}


# ==============================================================================
#  PUNTO DE ENTRADA
#  sistema_info.ps1 NO tiene bucle while porque no es un monitor.
#  Se ejecuta UNA sola vez, muestra el informe completo y termina.
#  Es el unico script de la coleccion que funciona de esta forma.
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Show-SistemaInfo
}

Read-Host -Prompt "Presiona Enter para salir..."
