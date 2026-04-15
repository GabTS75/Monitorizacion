# ==============================================================================
#  almacenamiento_monitor.ps1 - Monitor de Almacenamiento en PowerShell
#  Descripcion : Monitoriza en tiempo real el espacio en disco por unidad,
#                la velocidad de lectura/escritura y la actividad de I/O
#                de cada disco fisico del sistema.
#  Requisitos  : PowerShell 5.1 o superior (incluido en Windows 10/11/Server).
#                Sin dependencias externas.
#  Uso         : .\almacenamiento_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  QUE MONITORIZAMOS EN EL ALMACENAMIENTO
#
#  Al igual que en el script Python, el almacenamiento tiene tres niveles:
#
#  1. ESPACIO EN DISCO (por unidad/particion)
#     "Cuanto sitio me queda en cada unidad?"
#     Fuente: Win32_LogicalDisk via CIM
#     Ejemplo: C:\ tiene 500 GB total, 320 usados, 180 libres.
#
#  2. VELOCIDAD DE I/O (rendimiento en tiempo real)
#     "A que velocidad esta leyendo/escribiendo el disco ahora mismo?"
#     Fuente: PerformanceCounter "PhysicalDisk"
#     Ejemplo: el disco escribe a 120 MB/s porque estamos copiando archivos.
#
#  3. ACTIVIDAD DE I/O (estadisticas)
#     "Cuantas operaciones por segundo esta realizando el disco?"
#     Fuente: PerformanceCounter "PhysicalDisk"
#
#  Diferencia entre disco LOGICO y disco FISICO en Windows:
#  - Disco logico  -> una letra de unidad (C:\, D:\, E:\...)
#                     Lo que el usuario ve. Puede ser una particion.
#  - Disco fisico  -> el hardware real (SSD, HDD, NVMe...)
#                     Lo que tiene el contador de rendimiento.
#  Analogia: el disco fisico es el edificio completo. Los discos logicos
#  son los apartamentos dentro del edificio, cada uno con su letra.
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos   = 2      # Segundos entre actualizaciones
$UmbralAlertaDisco   = 85     # % de uso a partir del cual mostramos alerta
$UmbralCriticoDisco  = 95     # % critico: disco casi lleno, peligro real


# ==============================================================================
#  INICIALIZACION DE CONTADORES DE RENDIMIENTO
#
#  Para el almacenamiento usamos contadores de la categoria "PhysicalDisk".
#  El comodin "_Total" suma todos los discos fisicos.
#  Tambien creamos contadores individuales por disco fisico detectado.
#
#  Contadores que usamos:
#
#  "Disk Read Bytes/sec"   -> bytes leidos del disco por segundo
#  "Disk Write Bytes/sec"  -> bytes escritos en el disco por segundo
#  "Disk Reads/sec"        -> operaciones de lectura por segundo (IOPS)
#  "Disk Writes/sec"       -> operaciones de escritura por segundo (IOPS)
#  "% Disk Time"           -> % de tiempo que el disco esta ocupado
#                             Si se acerca al 100% el disco esta saturado
#  "Current Disk Queue Length" -> operaciones esperando (cola del disco)
#                                 Como la cola del procesador pero para discos
# ==============================================================================

Write-Host ""
Write-Host "  Iniciando monitor de almacenamiento..." -ForegroundColor Cyan
Write-Host "  Calibrando contadores (espera 2 segundos)..." -ForegroundColor Gray
Write-Host ""

# Contadores globales (suma de todos los discos)
$CntLecturaTotal  = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "Disk Read Bytes/sec", "_Total"
)
$CntEscrituraTotal = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "Disk Write Bytes/sec", "_Total"
)
$CntLecturasOps   = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "Disk Reads/sec", "_Total"
)
$CntEscriturasOps = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "Disk Writes/sec", "_Total"
)
$CntTiempoDisco   = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "% Disk Time", "_Total"
)
$CntColaDisco     = [System.Diagnostics.PerformanceCounter]::new(
    "PhysicalDisk", "Current Disk Queue Length", "_Total"
)

# Primera lectura de calibracion
$null = $CntLecturaTotal.NextValue()
$null = $CntEscrituraTotal.NextValue()
$null = $CntLecturasOps.NextValue()
$null = $CntEscriturasOps.NextValue()
$null = $CntTiempoDisco.NextValue()
$null = $CntColaDisco.NextValue()

Start-Sleep -Seconds 1

# Contadores individuales por disco fisico
# Get-CimInstance Win32_DiskDrive nos da la lista de discos fisicos
$DiscosFisicos = Get-CimInstance -ClassName Win32_DiskDrive
$CntsPorDisco  = @{}   # Hashtable: nombre del disco -> sus contadores

foreach ($Disco in $DiscosFisicos) {
    # El indice del disco en los contadores de rendimiento es un numero:
    # "0 C:", "1 D:", etc. Extraemos el indice del DeviceID del disco.
    # DeviceID tiene formato "\\.\PHYSICALDRIVE0", "\\.\PHYSICALDRIVE1"...
    $Indice = $Disco.DeviceID -replace '[^0-9]', ''

    # Buscamos la instancia del contador que corresponde a este disco
    # Los contadores de PhysicalDisk usan el formato "0 C: D:" donde
    # el numero es el indice y las letras son las particiones del disco
    try {
        $Instancias = (New-Object System.Diagnostics.PerformanceCounterCategory(
            "PhysicalDisk")).GetInstanceNames()
        $Instancia  = $Instancias | Where-Object { $_ -match "^$Indice " -and $_ -ne "_Total" }

        if ($Instancia) {
            $CntsPorDisco[$Disco.Model] = @{
                Lectura   = [System.Diagnostics.PerformanceCounter]::new(
                    "PhysicalDisk", "Disk Read Bytes/sec", $Instancia)
                Escritura = [System.Diagnostics.PerformanceCounter]::new(
                    "PhysicalDisk", "Disk Write Bytes/sec", $Instancia)
                Tiempo    = [System.Diagnostics.PerformanceCounter]::new(
                    "PhysicalDisk", "% Disk Time", $Instancia)
            }
            # Primera lectura de calibracion para este disco
            $null = $CntsPorDisco[$Disco.Model].Lectura.NextValue()
            $null = $CntsPorDisco[$Disco.Model].Escritura.NextValue()
            $null = $CntsPorDisco[$Disco.Model].Tiempo.NextValue()
        }
    }
    catch { }   # Si no podemos crear el contador para este disco, lo saltamos
}

Start-Sleep -Seconds 1
Write-Host "  Listo. Arrancando..." -ForegroundColor Green
Start-Sleep -Seconds 1


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
    param([double]$Pct, [int]$Long = 22)
    if ($Pct -lt 0)   { $Pct = 0 }
    if ($Pct -gt 100) { $Pct = 100 }
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}] {1:N1}%" -f (("#" * $Llenos) + ("-" * $Vacios)), $Pct
}


# --- Barra de disco con tres niveles de color --------------------------------
# El disco tiene un nivel extra: critico (casi lleno = peligro real).
# Un disco completamente lleno puede hacer que Windows deje de funcionar.
#
function Write-UsoDisco {
    param(
        [string]$Etiqueta,
        [double]$Pct
    )
    $Barra = Get-Barra -Pct $Pct

    if      ($Pct -lt 75)                { $Color = "Green"  }
    elseif  ($Pct -lt $UmbralAlertaDisco){ $Color = "Yellow" }
    elseif  ($Pct -lt $UmbralCriticoDisco){$Color = "Red"    }
    else                                 { $Color = "Magenta"}  # Critico

    Write-Host ("   {0,-6}" -f $Etiqueta) -NoNewline
    Write-Host $Barra -ForegroundColor $Color
}


# --- Barra de actividad de I/O -----------------------------------------------
# Para la velocidad usamos una barra relativa a 500 MB/s como referencia
# de "disco muy activo". Un SSD NVMe moderno puede superar eso, pero es
# una buena referencia para la mayoria de los equipos.
#
function Write-BarraActividad {
    param([double]$BytesPorSeg)
    $RefMax  = 500MB   # 500 MB/s como referencia del 100% de la barra
    $Pct     = [math]::Min(($BytesPorSeg / $RefMax) * 100, 100)
    $Llenos  = [int](($Pct / 100) * 15)
    $Vacios  = 15 - $Llenos
    $Barra   = "[" + ("#" * $Llenos) + ("-" * $Vacios) + "]"

    if      ($Pct -lt 30) { $Color = "Green"  }
    elseif  ($Pct -lt 70) { $Color = "Yellow" }
    else                  { $Color = "Red"    }

    Write-Host $Barra -ForegroundColor $Color -NoNewline
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-Almacenamiento {

    $Ahora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # --- Leer contadores de rendimiento globales ------------------------------
    $LecturaBps   = [math]::Round($CntLecturaTotal.NextValue(),  0)
    $EscrituraBps = [math]::Round($CntEscrituraTotal.NextValue(),0)
    $LecturasOps  = [math]::Round($CntLecturasOps.NextValue(),   1)
    $EscriturasOps= [math]::Round($CntEscriturasOps.NextValue(), 1)
    $TiempoDisco  = [math]::Round($CntTiempoDisco.NextValue(),   1)
    $ColaDisco    = [int]$CntColaDisco.NextValue()

    # Velocidades por disco individual
    $VelPorDisco = @{}
    foreach ($Modelo in $CntsPorDisco.Keys) {
        $VelPorDisco[$Modelo] = @{
            Lectura   = [math]::Round($CntsPorDisco[$Modelo].Lectura.NextValue(),   0)
            Escritura = [math]::Round($CntsPorDisco[$Modelo].Escritura.NextValue(), 0)
            Tiempo    = [math]::Round($CntsPorDisco[$Modelo].Tiempo.NextValue(),    1)
        }
    }

    # --- Leer espacio en disco por unidad logica (C:\, D:\...) ---------------
    # Win32_LogicalDisk nos da todas las unidades con sus letras y espacio.
    # DriveType = 3 significa disco fijo local (excluye CD-ROM, red, etc.)
    $UnidadesLogicas = Get-CimInstance -ClassName Win32_LogicalDisk |
                       Where-Object { $_.DriveType -eq 3 }

    # --- Leer informacion de discos fisicos -----------------------------------
    $DiscosFisicos = Get-CimInstance -ClassName Win32_DiskDrive

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  MONITOR DE ALMACENAMIENTO - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora" -ForegroundColor Gray
    Write-Host ("=" * 65) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  SECCION 1: Espacio por unidad logica
    # --------------------------------------------------------------------------
    Write-Host "`nESPACIO POR UNIDAD" -ForegroundColor White
    Write-Host ("   {0,-6} {1,10} {2,10} {3,10}   Uso" -f `
                "Unidad","Total","Usado","Libre")
    Write-Host ("   {0,-6} {1,10} {2,10} {3,10}   {4}" -f `
                "------","----------","----------","----------",("-"*30))

    $AlertasEspacio = @()   # Guardamos alertas para mostrarlas al final

    foreach ($Unidad in $UnidadesLogicas) {
        $Total  = $Unidad.Size
        $Libre  = $Unidad.FreeSpace
        $Usado  = $Total - $Libre
        $PctUso = [math]::Round(($Usado / $Total) * 100, 1)

        # Mostramos la fila de datos de esta unidad
        Write-Host ("   {0,-6} {1,10} {2,10} {3,10}   " -f `
            $Unidad.DeviceID,
            (Get-BytesLegibles $Total),
            (Get-BytesLegibles $Usado),
            (Get-BytesLegibles $Libre)) -NoNewline

        # La barra y el color van aparte para poder colorearlos
        Write-UsoDisco -Etiqueta "" -Pct $PctUso

        # Registramos alertas
        if ($PctUso -ge $UmbralCriticoDisco) {
            $AlertasEspacio += "  CRITICO: $($Unidad.DeviceID) al $PctUso% - DISCO CASI LLENO"
        } elseif ($PctUso -ge $UmbralAlertaDisco) {
            $AlertasEspacio += "  ALERTA:  $($Unidad.DeviceID) al $PctUso% - espacio bajo"
        }
    }

    # Mostramos las alertas si las hay
    if ($AlertasEspacio.Count -gt 0) {
        Write-Host ""
        foreach ($Alerta in $AlertasEspacio) {
            if ($Alerta -match "CRITICO") {
                Write-Host $Alerta -ForegroundColor Magenta
            } else {
                Write-Host $Alerta -ForegroundColor Red
            }
        }
    }

    # --------------------------------------------------------------------------
    #  SECCION 2: Velocidad de I/O en tiempo real (global)
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
    Write-Host "`nVELOCIDAD DE I/O EN TIEMPO REAL (todos los discos)" `
               -ForegroundColor White

    Write-Host "   Lectura  : " -NoNewline
    Write-BarraActividad -BytesPorSeg $LecturaBps
    Write-Host ("  {0,12}/s  ({1:N0} ops/s)" -f `
                (Get-BytesLegibles $LecturaBps), $LecturasOps)

    Write-Host "   Escritura: " -NoNewline
    Write-BarraActividad -BytesPorSeg $EscrituraBps
    Write-Host ("  {0,12}/s  ({1:N0} ops/s)" -f `
                (Get-BytesLegibles $EscrituraBps), $EscriturasOps)

    # Ocupacion del disco: % del tiempo que el disco esta haciendo algo
    Write-Host "`n   Disco ocupado : " -NoNewline
    $ColorOcup = if ($TiempoDisco -lt 50) {"Green"} elseif ($TiempoDisco -lt 85) {"Yellow"} else {"Red"}
    Write-Host ("{0:N1}%" -f $TiempoDisco) -ForegroundColor $ColorOcup -NoNewline

    # Cola del disco: operaciones esperando para ser procesadas
    # Si la cola supera 2 de forma sostenida, el disco es un cuello de botella
    Write-Host ("   |   Cola: {0}" -f $ColaDisco) -NoNewline
    if ($ColaDisco -gt 2) {
        Write-Host "  (cuello de botella)" -ForegroundColor Red
    } elseif ($ColaDisco -gt 0) {
        Write-Host "  (actividad normal)" -ForegroundColor Yellow
    } else {
        Write-Host "  (disco libre)" -ForegroundColor Green
    }

    # --------------------------------------------------------------------------
    #  SECCION 3: Velocidad por disco fisico individual
    # --------------------------------------------------------------------------
    if ($VelPorDisco.Count -gt 0) {
        Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
        Write-Host "`nVELOCIDAD POR DISCO FISICO" -ForegroundColor White

        foreach ($Modelo in $VelPorDisco.Keys) {
            $Vel = $VelPorDisco[$Modelo]

            # Truncamos el nombre del modelo si es muy largo
            $NombreCorto = if ($Modelo.Length -gt 35) { $Modelo.Substring(0,32) + "..." } else { $Modelo }

            Write-Host ("   {0}" -f $NombreCorto) -ForegroundColor Gray

            Write-Host "      Lect : " -NoNewline
            Write-BarraActividad -BytesPorSeg $Vel.Lectura
            Write-Host ("  {0,10}/s" -f (Get-BytesLegibles $Vel.Lectura))

            Write-Host "      Escr : " -NoNewline
            Write-BarraActividad -BytesPorSeg $Vel.Escritura
            Write-Host ("  {0,10}/s" -f (Get-BytesLegibles $Vel.Escritura))

            Write-Host ("      Ocup : {0:N1}%" -f $Vel.Tiempo) -NoNewline
            if ($Vel.Tiempo -gt 85) {
                Write-Host "  SATURADO" -ForegroundColor Red
            } elseif ($Vel.Tiempo -gt 50) {
                Write-Host "  Activo" -ForegroundColor Yellow
            } else {
                Write-Host "  Normal" -ForegroundColor Green
            }
        }
    }

    # --------------------------------------------------------------------------
    #  SECCION 4: Informacion de discos fisicos
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 65)" -ForegroundColor DarkGray
    Write-Host "`nDISCOS FISICOS DETECTADOS" -ForegroundColor White

    foreach ($Disco in $DiscosFisicos) {
        $TamanoGB = [math]::Round($Disco.Size / 1GB, 1)
        $NombreCorto = if ($Disco.Model.Length -gt 40) {
            $Disco.Model.Substring(0,37) + "..."
        } else { $Disco.Model }

        Write-Host ("   Modelo    : {0}" -f $NombreCorto)
        Write-Host ("   Tamano    : {0} GB" -f $TamanoGB)
        Write-Host ("   Interfaz  : {0}" -f $Disco.InterfaceType)
        Write-Host ("   Particion : {0}" -f $Disco.Partitions)

        # MediaType indica si es HDD, SSD u otro
        # No todos los discos reportan este dato correctamente
        if ($Disco.MediaType -and $Disco.MediaType -ne "Unspecified") {
            Write-Host ("   Tipo      : {0}" -f $Disco.MediaType)
        }
        Write-Host ""
    }

    # Pie
    Write-Host ("=" * 65) -ForegroundColor Cyan
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
            Show-Almacenamiento
            Start-Sleep -Seconds $IntervaloSegundos
        }
    }
    finally {
        # Liberamos todos los contadores
        $CntLecturaTotal.Dispose()
        $CntEscrituraTotal.Dispose()
        $CntLecturasOps.Dispose()
        $CntEscriturasOps.Dispose()
        $CntTiempoDisco.Dispose()
        $CntColaDisco.Dispose()
        foreach ($Modelo in $CntsPorDisco.Keys) {
            $CntsPorDisco[$Modelo].Lectura.Dispose()
            $CntsPorDisco[$Modelo].Escritura.Dispose()
            $CntsPorDisco[$Modelo].Tiempo.Dispose()
        }
        Write-Host "`n`n  Monitor detenido. Hasta luego!" -ForegroundColor Green
    }
}


# ==============================================================================
#  PUNTO DE ENTRADA
# ==============================================================================
if ($MyInvocation.InvocationName -ne '.') {
    Start-Monitor
}
