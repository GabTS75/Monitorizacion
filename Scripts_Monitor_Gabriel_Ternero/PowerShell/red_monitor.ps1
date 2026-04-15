# ==============================================================================
#  red_monitor.ps1 - Monitor de Red en PowerShell
#  Descripcion : Monitoriza en tiempo real el trafico de red por interfaz:
#                velocidad de subida/bajada, paquetes, errores y estado
#                de cada adaptador de red disponible en el sistema.
#  Requisitos  : PowerShell 5.1 o superior (incluido en Windows 10/11/Server).
#                Sin dependencias externas.
#  Uso         : .\red_monitor.ps1
# ==============================================================================

# ------------------------------------------------------------------------------
#  CONCEPTOS CLAVE DE RED EN WINDOWS
#
#  En Windows los adaptadores de red se gestionan de forma diferente a Linux.
#  No hay nombres como eth0 o wlan0. En su lugar cada adaptador tiene un
#  nombre descriptivo como "Ethernet", "Wi-Fi", "Ethernet 2", etc.
#
#  Fuentes de datos que usamos en este script:
#
#  PerformanceCounter "Network Interface"
#      -> velocidad de envio/recepcion en tiempo real (bytes/seg)
#      -> paquetes por segundo
#      -> errores y descartes
#      Nota: los nombres de instancia en este contador usan el nombre
#      del adaptador con algunos caracteres sustituidos (los parentesis
#      se convierten en corchetes, etc.)
#
#  Win32_NetworkAdapterConfiguration (CIM)
#      -> direcciones IP (IPv4 e IPv6)
#      -> direccion MAC
#      -> mascara de subred
#      -> puerta de enlace
#
#  Win32_NetworkAdapter (CIM)
#      -> nombre del adaptador
#      -> estado (conectado/desconectado)
#      -> velocidad de enlace (bps)
#      -> tipo de adaptador
#
#  Get-NetTCPConnection (cmdlet nativo de PowerShell)
#      -> conexiones TCP activas con sus estados
#      -> equivalente a netstat en la terminal
# ------------------------------------------------------------------------------

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force


# ==============================================================================
#  CONFIGURACION
# ==============================================================================
$IntervaloSegundos    = 2       # Segundos entre actualizaciones
$UmbralAlertaErrores  = 100     # Numero de errores a partir del cual alertamos
$OcultarLoopback      = $true   # Ocultar adaptador de loopback (127.0.0.1)
$OcultarDesconectados = $false  # Mostrar tambien adaptadores sin cable/wifi


# ==============================================================================
#  INICIALIZACION DE CONTADORES DE RENDIMIENTO
#
#  La categoria "Network Interface" tiene una instancia por cada adaptador.
#  Primero obtenemos la lista de instancias disponibles y luego creamos
#  un contador de velocidad para cada adaptador activo.
#
#  Contadores por adaptador:
#  "Bytes Received/sec"     -> bytes recibidos por segundo (bajada)
#  "Bytes Sent/sec"         -> bytes enviados por segundo (subida)
#  "Packets Received/sec"   -> paquetes recibidos por segundo
#  "Packets Sent/sec"       -> paquetes enviados por segundo
#  "Packets Received Errors"-> paquetes recibidos con error (acumulado)
#  "Packets Outbound Errors"-> paquetes enviados con error (acumulado)
#  "Packets Received Discarded" -> paquetes descartados en recepcion
# ==============================================================================

Write-Host ""
Write-Host "  Iniciando monitor de red..." -ForegroundColor Cyan
Write-Host "  Detectando adaptadores y calibrando (espera 2 segundos)..." `
           -ForegroundColor Gray
Write-Host ""

# Obtenemos la lista de instancias del contador "Network Interface"
# Cada instancia es un adaptador de red disponible en el sistema
try {
    $CategoriaNIC = New-Object System.Diagnostics.PerformanceCounterCategory("Network Interface")
    $InstanciasNIC = $CategoriaNIC.GetInstanceNames()
} catch {
    $InstanciasNIC = @()
}

# Creamos contadores para cada adaptador detectado
# Usamos un hashtable: nombre del adaptador -> sus contadores
$CntsPorAdaptador = @{}

foreach ($Instancia in $InstanciasNIC) {
    # Filtramos el loopback si esta configurado
    # En Windows el loopback se llama "MS TCP Loopback interface" o similar
    if ($OcultarLoopback -and $Instancia -match "Loopback|loopback") { continue }

    try {
        $CntsPorAdaptador[$Instancia] = @{
            BytesRx   = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Bytes Received/sec", $Instancia)
            BytesTx   = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Bytes Sent/sec", $Instancia)
            PktRx     = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Packets Received/sec", $Instancia)
            PktTx     = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Packets Sent/sec", $Instancia)
            ErrRx     = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Packets Received Errors", $Instancia)
            ErrTx     = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Packets Outbound Errors", $Instancia)
            Descartes = [System.Diagnostics.PerformanceCounter]::new(
                "Network Interface", "Packets Received Discarded", $Instancia)
        }
        # Primera lectura de calibracion para todos los contadores
        foreach ($Cnt in $CntsPorAdaptador[$Instancia].Values) {
            $null = $Cnt.NextValue()
        }
    } catch { }
}

Start-Sleep -Seconds 1
Start-Sleep -Seconds 1

Write-Host "  Listo. Arrancando..." -ForegroundColor Green
Start-Sleep -Seconds 1


# ==============================================================================
#  FUNCIONES AUXILIARES
# ==============================================================================

function Clear-Pantalla { Clear-Host }

function Get-BytesLegibles {
    param([double]$Bytes)
    if     ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    elseif ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    elseif ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    else                    { return "{0:N0} B"  -f $Bytes          }
}


# --- Barra de actividad de red -----------------------------------------------
# Referencia: 125 MB/s = 1 Gbps (velocidad tipica de una red Gigabit)
# Si tienes fibra de 10 Gbps puedes aumentar la referencia a 1250MB
#
function Get-BarraRed {
    param([double]$BytesPorSeg, [int]$Long = 18)
    $RefMax = 125MB   # 125 MB/s = 1 Gbps de referencia
    $Pct    = [math]::Min(($BytesPorSeg / $RefMax) * 100, 100)
    $Llenos = [int](($Pct / 100) * $Long)
    $Vacios = $Long - $Llenos
    return "[{0}]" -f (("#" * $Llenos) + ("-" * $Vacios))
}


# --- Color segun velocidad de red --------------------------------------------
function Get-ColorVelocidad {
    param([double]$BytesPorSeg)
    if     ($BytesPorSeg -lt 10MB)  { return "Green"  }   # < 10 MB/s
    elseif ($BytesPorSeg -lt 80MB)  { return "Yellow" }   # 10-80 MB/s
    else                            { return "Red"    }   # > 80 MB/s
}


# --- Obtener informacion de IP de los adaptadores ----------------------------
# Win32_NetworkAdapterConfiguration con IPEnabled=$true nos da solo los
# adaptadores que tienen una IP asignada (descartar adaptadores virtuales
# sin configuracion de red activa).
#
function Get-InfoAdaptadores {
    $Configs = Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration |
               Where-Object { $_.IPEnabled -eq $true }

    $InfoMap = @{}   # Hashtable: descripcion del adaptador -> sus datos IP

    foreach ($Config in $Configs) {
        $IPv4 = ($Config.IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' }) -join ", "
        $IPv6 = ($Config.IPAddress | Where-Object { $_ -match ':' }) -join ", "

        $InfoMap[$Config.Description] = @{
            IPv4       = if ($IPv4) { $IPv4 } else { "Sin IP" }
            IPv6       = if ($IPv6) { ($IPv6 -split '%')[0] } else { "" }
            MAC        = $Config.MACAddress
            Mascara    = ($Config.IPSubnet | Where-Object { $_ -match '^\d' } | Select-Object -First 1)
            Gateway    = ($Config.DefaultIPGateway -join ", ")
            DHCP       = $Config.DHCPEnabled
        }
    }
    return $InfoMap
}


# --- Obtener estado de los adaptadores fisicos --------------------------------
# Win32_NetworkAdapter nos da el estado de conexion y la velocidad de enlace.
# NetConnectionStatus = 2 significa conectado.
#
function Get-EstadoAdaptadores {
    $Adaptadores = Get-CimInstance -ClassName Win32_NetworkAdapter |
                   Where-Object { $_.PhysicalAdapter -eq $true }

    $EstadoMap = @{}
    foreach ($Adapt in $Adaptadores) {
        $Conectado = $Adapt.NetConnectionStatus -eq 2
        $VelMbps   = if ($Adapt.Speed) {
            [math]::Round($Adapt.Speed / 1MB, 0)
        } else { 0 }

        $EstadoMap[$Adapt.Name] = @{
            Conectado = $Conectado
            VelMbps   = $VelMbps
            Tipo      = $Adapt.AdapterType
        }
    }
    return $EstadoMap
}


# --- Resumen de conexiones TCP por estado ------------------------------------
# Get-NetTCPConnection es un cmdlet nativo de PowerShell que lista todas
# las conexiones TCP activas. Equivale a ejecutar "netstat -an" en cmd.
# Lo agrupamos por estado para no saturar la pantalla con cientos de lineas.
#
function Get-ResumenConexiones {
    try {
        $Conexiones = Get-NetTCPConnection -ErrorAction Stop

        # Group-Object agrupa los elementos por una propiedad.
        # Es como el groupby de Python o un GROUP BY de SQL.
        $Grupos = $Conexiones | Group-Object -Property State |
                  Sort-Object -Property Count -Descending

        return $Grupos
    } catch {
        return $null
    }
}


# ==============================================================================
#  FUNCION PRINCIPAL
# ==============================================================================
function Show-Red {

    $Ahora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # Leer velocidades de todos los adaptadores
    $Velocidades = @{}
    foreach ($Nombre in $CntsPorAdaptador.Keys) {
        $Cnt = $CntsPorAdaptador[$Nombre]
        $Velocidades[$Nombre] = @{
            BytesRx   = [math]::Round($Cnt.BytesRx.NextValue(),   0)
            BytesTx   = [math]::Round($Cnt.BytesTx.NextValue(),   0)
            PktRx     = [math]::Round($Cnt.PktRx.NextValue(),     1)
            PktTx     = [math]::Round($Cnt.PktTx.NextValue(),     1)
            ErrRx     = [int]$Cnt.ErrRx.NextValue()
            ErrTx     = [int]$Cnt.ErrTx.NextValue()
            Descartes = [int]$Cnt.Descartes.NextValue()
        }
    }

    # Datos estaticos (IPs, estado, conexiones)
    $InfoIP    = Get-InfoAdaptadores
    $Estado    = Get-EstadoAdaptadores
    $Hostname  = $env:COMPUTERNAME   # Variable de entorno: nombre del equipo
    $Conexiones= Get-ResumenConexiones

    # ==========================================================================
    #  CONSTRUCCION DE LA PANTALLA
    # ==========================================================================
    Clear-Pantalla

    Write-Host ("=" * 68) -ForegroundColor Cyan
    Write-Host "  MONITOR DE RED - Tiempo Real" -ForegroundColor Cyan
    Write-Host "  $Ahora  |  Equipo: $Hostname" -ForegroundColor Gray
    Write-Host ("=" * 68) -ForegroundColor Cyan

    # --------------------------------------------------------------------------
    #  SECCION 1: Velocidad y datos por adaptador
    # --------------------------------------------------------------------------
    Write-Host "`nADAPTADORES DE RED" -ForegroundColor White

    $AlertasRed = @()

    foreach ($Nombre in $Velocidades.Keys) {
        $Vel = $Velocidades[$Nombre]

        # Omitimos adaptadores sin actividad si estan desconectados
        # Un adaptador completamente a 0 en todo probablemente no esta en uso
        $TotalActividad = $Vel.BytesRx + $Vel.BytesTx + $Vel.ErrRx + $Vel.ErrTx
        if ($OcultarDesconectados -and $TotalActividad -eq 0) { continue }

        # Nombre del adaptador truncado si es muy largo
        $NombreCorto = if ($Nombre.Length -gt 45) {
            $Nombre.Substring(0, 42) + "..."
        } else { $Nombre }

        Write-Host "`n  [$NombreCorto]" -ForegroundColor White

        # Intentamos encontrar la IP de este adaptador buscando en InfoIP
        # Los nombres en los contadores y en WMI no siempre coinciden exactamente
        # asi que hacemos una busqueda parcial por similitud
        $IPInfo = $null
        foreach ($Clave in $InfoIP.Keys) {
            # Comparamos las primeras palabras del nombre para encontrar coincidencias
            $PalabrasCnt = ($Nombre -split ' ')[0..1] -join ' '
            $PalabrasWMI = ($Clave -split ' ')[0..1] -join ' '
            if ($Clave -like "*$PalabrasCnt*" -or $Nombre -like "*$PalabrasWMI*") {
                $IPInfo = $InfoIP[$Clave]
                break
            }
        }

        # Mostramos la IP si la encontramos
        if ($IPInfo) {
            Write-Host ("     IPv4     : {0}" -f $IPInfo.IPv4) -ForegroundColor Gray
            if ($IPInfo.IPv6) {
                Write-Host ("     IPv6     : {0}" -f ($IPInfo.IPv6.Substring(0, [math]::Min(50, $IPInfo.IPv6.Length)))) -ForegroundColor Gray
            }
            if ($IPInfo.MAC) {
                Write-Host ("     MAC      : {0}" -f $IPInfo.MAC) -ForegroundColor Gray
            }
            $GwStr = if ($IPInfo.Gateway) { $IPInfo.Gateway } else { "N/A" }
            Write-Host ("     Gateway  : {0}  |  DHCP: {1}" -f $GwStr, $(if($IPInfo.DHCP){"Si"}else{"No"})) -ForegroundColor Gray
        }

        # Velocidades de bajada y subida
        Write-Host ""
        $BarraRx  = Get-BarraRed -BytesPorSeg $Vel.BytesRx
        $ColorRx  = Get-ColorVelocidad -BytesPorSeg $Vel.BytesRx
        $BarraTx  = Get-BarraRed -BytesPorSeg $Vel.BytesTx
        $ColorTx  = Get-ColorVelocidad -BytesPorSeg $Vel.BytesTx

        Write-Host "     Bajada : " -NoNewline
        Write-Host $BarraRx -ForegroundColor $ColorRx -NoNewline
        Write-Host ("  {0,12}/s   {1:N0} pkt/s" -f (Get-BytesLegibles $Vel.BytesRx), $Vel.PktRx)

        Write-Host "     Subida : " -NoNewline
        Write-Host $BarraTx -ForegroundColor $ColorTx -NoNewline
        Write-Host ("  {0,12}/s   {1:N0} pkt/s" -f (Get-BytesLegibles $Vel.BytesTx), $Vel.PktTx)

        # Errores y descartes (solo si existen)
        # En una red sana estos valores deben ser 0 o muy cercanos a 0
        if ($Vel.ErrRx -gt 0 -or $Vel.ErrTx -gt 0 -or $Vel.Descartes -gt 0) {
            Write-Host ("     Errores: RX={0}  TX={1}  Descartes={2}" -f `
                $Vel.ErrRx, $Vel.ErrTx, $Vel.Descartes) -ForegroundColor Yellow

            if (($Vel.ErrRx + $Vel.ErrTx) -gt $UmbralAlertaErrores) {
                $AlertasRed += "  ALERTA: $NombreCorto - errores elevados ($(($Vel.ErrRx + $Vel.ErrTx)))"
            }
        }
    }

    # --------------------------------------------------------------------------
    #  SECCION 2: Trafico total acumulado desde el arranque
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 68)" -ForegroundColor DarkGray
    Write-Host "`nTRAFICO ACUMULADO DESDE EL ARRANQUE" -ForegroundColor White

    # Win32_PerfRawData_Tcpip_NetworkInterface nos da los bytes totales
    # acumulados desde que arranco el sistema, no la velocidad actual.
    try {
        $DatosAcum = Get-CimInstance -ClassName Win32_PerfRawData_Tcpip_NetworkInterface
        $TotalRx = 0
        $TotalTx = 0
        foreach ($D in $DatosAcum) {
            if ($OcultarLoopback -and $D.Name -match "Loopback") { continue }
            $TotalRx += $D.BytesReceivedPerSec
            $TotalTx += $D.BytesSentPerSec
        }
        Write-Host ("   Total recibido : {0}" -f (Get-BytesLegibles $TotalRx))
        Write-Host ("   Total enviado  : {0}" -f (Get-BytesLegibles $TotalTx))
    } catch {
        Write-Host "   No disponible en este sistema." -ForegroundColor Gray
    }

    # --------------------------------------------------------------------------
    #  SECCION 3: Resumen de conexiones TCP por estado
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 68)" -ForegroundColor DarkGray
    Write-Host "`nCONEXIONES TCP - RESUMEN POR ESTADO" -ForegroundColor White

    if ($Conexiones) {
        $Total = ($Conexiones | Measure-Object -Property Count -Sum).Sum
        foreach ($Grupo in $Conexiones) {
            # Coloreamos los estados mas relevantes
            # ESTABLISHED = conexion activa y comunicandose
            # LISTEN      = puerto abierto esperando conexiones
            # TIME_WAIT   = conexion cerrандose (espera normal de TCP)
            $Color = switch ($Grupo.Name) {
                "Established" { "Green"  }
                "Listen"      { "Cyan"   }
                "TimeWait"    { "Yellow" }
                "CloseWait"   { "Yellow" }
                "SynSent"     { "Gray"   }
                "SynReceived" { "Gray"   }
                default       { "White"  }
            }
            Write-Host ("   {0,-20} : {1,5} conexiones" -f `
                $Grupo.Name, $Grupo.Count) -ForegroundColor $Color
        }
        Write-Host ("   {0,-20} : {1,5} conexiones" -f "TOTAL", $Total)
    } else {
        Write-Host "   No se pudieron obtener las conexiones TCP." -ForegroundColor Gray
        Write-Host "   Prueba a ejecutar el script como Administrador." -ForegroundColor Gray
    }

    # --------------------------------------------------------------------------
    #  SECCION 4: Alertas
    # --------------------------------------------------------------------------
    if ($AlertasRed.Count -gt 0) {
        Write-Host "`n$("-" * 68)" -ForegroundColor DarkGray
        Write-Host "`nALERTAS DE RED" -ForegroundColor Red
        foreach ($Alerta in $AlertasRed) {
            Write-Host $Alerta -ForegroundColor Red
            Write-Host "   Posible causa: cable danado, driver desactualizado" `
                       -ForegroundColor Yellow
            Write-Host "   o interferencias en la red inalambrica." `
                       -ForegroundColor Yellow
        }
    }

    # --------------------------------------------------------------------------
    #  SECCION 5: Diagnostico
    # --------------------------------------------------------------------------
    Write-Host "`n$("-" * 68)" -ForegroundColor DarkGray
    Write-Host "`nDIAGNOSTICO" -ForegroundColor White

    if ($AlertasRed.Count -gt 0) {
        Write-Host "   ATENCION: hay errores de red que requieren revision." `
                   -ForegroundColor Red
    } elseif ($CntsPorAdaptador.Count -eq 0) {
        Write-Host "   No se detectaron adaptadores de red monitorizables." `
                   -ForegroundColor Yellow
        Write-Host "   Comprueba que hay adaptadores activos en el sistema." `
                   -ForegroundColor Yellow
    } else {
        Write-Host "   Red funcionando correctamente." -ForegroundColor Green
        Write-Host "   Sin errores ni paquetes descartados reseniables." `
                   -ForegroundColor Green
    }

    # Pie
    Write-Host ("`n" + "=" * 68) -ForegroundColor Cyan
    Write-Host ("  Actualizando cada {0}s  |  Ctrl+C para salir" -f `
                $IntervaloSegundos) -ForegroundColor Gray
    Write-Host ("=" * 68) -ForegroundColor Cyan
}


# ==============================================================================
#  BUCLE PRINCIPAL
# ==============================================================================
function Start-Monitor {
    try {
        while ($true) {
            Show-Red
            Start-Sleep -Seconds $IntervaloSegundos
        }
    }
    finally {
        # Liberamos todos los contadores de todos los adaptadores
        foreach ($Nombre in $CntsPorAdaptador.Keys) {
            foreach ($Cnt in $CntsPorAdaptador[$Nombre].Values) {
                try { $Cnt.Dispose() } catch { }
            }
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
