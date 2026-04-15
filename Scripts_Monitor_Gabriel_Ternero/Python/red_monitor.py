# =============================================================================
#  red_monitor.py — Monitor de Red
#  Descripción : Monitoriza en tiempo real el tráfico de red por interfaz:
#                velocidad de subida/bajada, paquetes, errores y estado
#                de cada interfaz de red disponible en el sistema.
#  Requisitos  : pip install psutil
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué monitorizamos en la red?
#
#  Imagina que la tarjeta de red de tu ordenador es como el buzón de correos
#  de tu casa. Por él entran cartas (datos recibidos) y salen cartas
#  (datos enviados). Monitorizar la red es como tener un cartero que anota
#  cuántas cartas pasan, a qué velocidad llegan y si alguna se ha perdido
#  o llegado dañada.
#
#  Conceptos clave que vamos a medir:
#
#     Bytes recibidos (RX) → datos que llegan a tu equipo desde la red
#     Bytes enviados  (TX) → datos que tu equipo manda hacia la red
#
#     Paquetes → los datos no viajan de golpe, se dividen en trozos
#                llamados "paquetes". Como si una carta larga se dividiera
#                en varias páginas enviadas por separado.
#
#     Errores  → paquetes que llegaron corruptos o malformados
#     Drops    → paquetes descartados porque el sistema estaba demasiado ocupado
#
#     Interfaz → cada "tarjeta de red" es una interfaz. Un portátil puede
#                tener varias: eth0 (cable), wlan0 (WiFi), lo (loopback)...
#
#     Loopback (lo / Loopback Pseudo-Interface) → interfaz especial que el
#     sistema usa para comunicarse consigo mismo. El tráfico de 127.0.0.1
#     pasa por aquí. No es tráfico real de red, pero existe siempre.
# -----------------------------------------------------------------------------

import psutil       # Para acceder a las interfaces y estadísticas de red
import time         # Para pausas y para medir velocidades en tiempo real
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual
import socket       # Para obtener el hostname del equipo

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS      = 2        # Cada cuántos segundos se refresca la pantalla
UMBRAL_ALERTA_ERRORES   = 100      # Nº de errores a partir del cual mostramos alerta
UMBRAL_ALERTA_DROPS     = 50       # Nº de drops a partir del cual mostramos alerta
OCULTAR_LOOPBACK        = True     # True = oculta la interfaz loopback (lo/127.0.0.1)
                                   # Es tráfico interno del SO, raramente interesa
OCULTAR_INACTIVAS       = False    # True = oculta interfaces que están DOWN (apagadas)


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: convertir bytes a unidad legible ----------------------
def bytes_a_legible(bytes_valor):
    """Convierte bytes a KB, MB, GB o TB automáticamente."""
    unidades = [
        (1024 ** 4, "TB"),
        (1024 ** 3, "GB"),
        (1024 ** 2, "MB"),
        (1024 ** 1, "KB"),
    ]
    for divisor, nombre in unidades:
        if bytes_valor >= divisor:
            return f"{bytes_valor / divisor:.2f} {nombre}"
    return f"{bytes_valor} B"


# --- Función auxiliar: barra de actividad de red -----------------------------
# Para la red usamos una barra de actividad relativa, no absoluta.
# La referencia es 1 Gbps (125 MB/s), que es el límite de una conexión
# Gigabit Ethernet típica. Si el usuario tiene fibra de 10 Gbps puede
# ajustar el parámetro max_bytes_s.

def barra_actividad(bytes_por_segundo, max_bytes_s=125 * 1024 * 1024, longitud=15):
    """
    Genera una barra de actividad proporcional a la velocidad actual.
    - bytes_por_segundo : velocidad actual de transferencia
    - max_bytes_s       : velocidad máxima de referencia (por defecto: 1 Gbps)
    - longitud          : ancho de la barra en caracteres
    """
    # Calculamos qué porcentaje del máximo estamos usando
    porcentaje = min((bytes_por_segundo / max_bytes_s) * 100, 100)
    rellenos   = int((porcentaje / 100) * longitud)
    barra      = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}]"


# --- Función auxiliar: colorear velocidad según nivel ------------------------
def color_velocidad(velocidad_bytes_s):
    """
    Colorea la velocidad con verde/amarillo/rojo según el nivel de tráfico:
    - Verde    → tráfico bajo    (< 10 MB/s)
    - Amarillo → tráfico medio   (10 – 80 MB/s)
    - Rojo     → tráfico alto    (> 80 MB/s, cercano al límite de 1 Gbps)
    """
    vel_str = f"{bytes_a_legible(velocidad_bytes_s)}/s"
    if velocidad_bytes_s < 10 * 1024 * 1024:         # < 10 MB/s
        return f"\033[92m{vel_str:>12}\033[0m"       # Verde
    elif velocidad_bytes_s < 80 * 1024 * 1024:       # < 80 MB/s
        return f"\033[93m{vel_str:>12}\033[0m"       # Amarillo
    else:
        return f"\033[91m{vel_str:>12}\033[0m"       # Rojo


# --- Función auxiliar: medir velocidad de red en tiempo real -----------------
# Igual que con el disco, necesitamos DOS lecturas separadas por tiempo
# para calcular la velocidad actual. La red no tiene un "velocímetro"
# instantáneo: hay que observar cuántos bytes pasaron en un intervalo.

def obtener_velocidades_red(intervalo=1):
    """
    Mide la velocidad actual de cada interfaz de red.
    Hace dos lecturas separadas por 'intervalo' segundos y calcula la diferencia.

    Devuelve un diccionario:
    { 'eth0': {'rx': bytes/s, 'tx': bytes/s, 'pkt_rx': pkt/s, 'pkt_tx': pkt/s} }
    """
    # Primera lectura: contadores acumulados por interfaz
    # pernic=True → devuelve datos separados por cada interfaz de red
    antes = psutil.net_io_counters(pernic=True)
    time.sleep(intervalo)
    despues = psutil.net_io_counters(pernic=True)

    velocidades = {}

    for interfaz in antes:
        if interfaz not in despues:
            continue   # La interfaz desapareció entre mediciones (USB WiFi desconectado)

        # Calculamos la diferencia de bytes y paquetes en el intervalo
        rx_bytes = despues[interfaz].bytes_recv   - antes[interfaz].bytes_recv
        tx_bytes = despues[interfaz].bytes_sent   - antes[interfaz].bytes_sent
        rx_pkts  = despues[interfaz].packets_recv - antes[interfaz].packets_recv
        tx_pkts  = despues[interfaz].packets_sent - antes[interfaz].packets_sent

        velocidades[interfaz] = {
            'rx'     : rx_bytes / intervalo,   # bytes/segundo recibidos
            'tx'     : tx_bytes / intervalo,   # bytes/segundo enviados
            'pkt_rx' : rx_pkts  / intervalo,   # paquetes/segundo recibidos
            'pkt_tx' : tx_pkts  / intervalo,   # paquetes/segundo enviados
        }

    return velocidades


# --- Función auxiliar: obtener direcciones IP de una interfaz ----------------
def obtener_ips(nombre_interfaz):
    """
    Devuelve las direcciones IP (IPv4 e IPv6) asignadas a una interfaz.
    net_if_addrs() devuelve todas las direcciones de todas las interfaces.
    Filtramos las de la interfaz que nos interesa.
    """
    ips = []

    try:
        direcciones = psutil.net_if_addrs()
        if nombre_interfaz not in direcciones:
            return ["Sin dirección IP"]

        for addr in direcciones[nombre_interfaz]:
            # AF_INET  = familia de direcciones IPv4 (ej: 192.168.1.10)
            # AF_INET6 = familia de direcciones IPv6 (ej: fe80::1)
            if addr.family == socket.AF_INET:
                mascara = f"/{addr.netmask}" if addr.netmask else ""
                ips.append(f"IPv4: {addr.address}{mascara}")
            elif addr.family == socket.AF_INET6:
                # Las IPs IPv6 pueden ser muy largas; las truncamos si es necesario
                ipv6 = addr.address.split('%')[0]   # Quitamos el sufijo de zona (%eth0)
                ips.append(f"IPv6: {ipv6}")

    except Exception:
        pass

    return ips if ips else ["Sin dirección IP"]


# --- Función auxiliar: estado de las interfaces ------------------------------
def obtener_estado_interfaces():
    """
    Devuelve el estado (UP/DOWN) y la velocidad de enlace de cada interfaz.
    net_if_stats() proporciona: isup, duplex, speed, mtu.
    - isup  → True si la interfaz está activa (UP), False si está caída (DOWN)
    - speed → velocidad de enlace en Mbps (0 si no se puede determinar)
    - mtu   → Maximum Transmission Unit: tamaño máximo de paquete en bytes
    """
    try:
        return psutil.net_if_stats()
    except Exception:
        return {}


# --- Función principal: obtener y mostrar datos de red -----------------------

def mostrar_red():
    """Recopila y muestra en pantalla todos los datos de red."""

    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Obtenemos el nombre del equipo en la red
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "desconocido"

    # Medimos velocidades (1 segundo de medición incluido aquí)
    velocidades  = obtener_velocidades_red(intervalo=1)
    stats_if     = obtener_estado_interfaces()

    # Contadores acumulados totales de cada interfaz (desde el arranque)
    try:
        contadores = psutil.net_io_counters(pernic=True)
    except Exception:
        contadores = {}

    limpiar_pantalla()

    # Cabecera
    print("=" * 68)
    print("       🌐  MONITOR DE RED — Tiempo Real")
    print(f"       📅 {ahora}  |  Host: {hostname}")
    print("=" * 68)

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Estado y velocidad por interfaz
    # -------------------------------------------------------------------------
    print(f"\n📡 INTERFACES DE RED\n")

    alertas_red = []   # Para el diagnóstico final

    for interfaz, vel in velocidades.items():

        # --- Filtros de visualización ----------------------------------------

        # Omitir loopback si está configurado
        if OCULTAR_LOOPBACK and interfaz.lower() in ('lo', 'loopback pseudo-interface 1'):
            continue

        # Obtener estado de la interfaz
        estado_obj = stats_if.get(interfaz)
        esta_activa = estado_obj.isup if estado_obj else True

        # Omitir interfaces inactivas si está configurado
        if OCULTAR_INACTIVAS and not esta_activa:
            continue

        # --- Cabecera de la interfaz -----------------------------------------
        estado_str  = "\033[92mUP  ✅\033[0m" if esta_activa else "\033[91mDOWN ❌\033[0m"
        velocidad_enlace = ""
        mtu_str     = ""

        if estado_obj:
            if estado_obj.speed > 0:
                # La velocidad de enlace es la capacidad máxima del adaptador
                # (ej: 1000 Mbps = Gigabit). No confundir con la velocidad actual.
                velocidad_enlace = f"  |  Enlace: {estado_obj.speed} Mbps"
            if estado_obj.mtu > 0:
                mtu_str = f"  |  MTU: {estado_obj.mtu} B"

        print(f"  🔌 \033[1m{interfaz}\033[0m   Estado: {estado_str}{velocidad_enlace}{mtu_str}")

        # --- Direcciones IP --------------------------------------------------
        ips = obtener_ips(interfaz)
        for ip in ips:
            print(f"     {ip}")

        # --- Velocidad actual (tiempo real) ----------------------------------
        print(f"\n     ⚡ VELOCIDAD ACTUAL")
        print(f"     📥 Bajada  : {color_velocidad(vel['rx'])}  "
              f"{barra_actividad(vel['rx'])}"
              f"  {vel['pkt_rx']:6.0f} pkt/s")
        print(f"     📤 Subida  : {color_velocidad(vel['tx'])}  "
              f"{barra_actividad(vel['tx'])}"
              f"  {vel['pkt_tx']:6.0f} pkt/s")

        # --- Estadísticas acumuladas desde el arranque -----------------------
        if interfaz in contadores:
            cnt = contadores[interfaz]
            print(f"\n     📊 ACUMULADO (desde el arranque)")
            print(f"     {'Recibido':<12}: {bytes_a_legible(cnt.bytes_recv):>10}"
                  f"  ({cnt.packets_recv:>10,} paquetes)")
            print(f"     {'Enviado':<12}: {bytes_a_legible(cnt.bytes_sent):>10}"
                  f"  ({cnt.packets_sent:>10,} paquetes)")

            # --- Errores y drops ---------------------------------------------
            # Los errores son paquetes corruptos. Los drops son paquetes que
            # el sistema recibió pero tuvo que tirar porque estaba saturado.
            # Ambos deberían ser 0 o muy cercanos a 0 en una red sana.
            errores_rx = cnt.errin
            errores_tx = cnt.errout
            drops_rx   = cnt.dropin
            drops_tx   = cnt.dropout

            # Solo mostramos errores/drops si existen, para no saturar la pantalla
            if errores_rx > 0 or errores_tx > 0 or drops_rx > 0 or drops_tx > 0:
                print(f"\n     ⚠️  INCIDENCIAS")

                if errores_rx > 0 or errores_tx > 0:
                    err_color = "\033[91m" if (errores_rx + errores_tx) > UMBRAL_ALERTA_ERRORES else "\033[93m"
                    print(f"     {err_color}Errores RX: {errores_rx:>8,}  |  Errores TX: {errores_tx:>8,}\033[0m")

                if drops_rx > 0 or drops_tx > 0:
                    drp_color = "\033[91m" if (drops_rx + drops_tx) > UMBRAL_ALERTA_DROPS else "\033[93m"
                    print(f"     {drp_color}Drops   RX: {drops_rx:>8,}  |  Drops   TX: {drops_tx:>8,}\033[0m")

                # Guardamos la alerta para el diagnóstico final
                if (errores_rx + errores_tx) > UMBRAL_ALERTA_ERRORES:
                    alertas_red.append((interfaz, "errores elevados", errores_rx + errores_tx))
                if (drops_rx + drops_tx) > UMBRAL_ALERTA_DROPS:
                    alertas_red.append((interfaz, "drops elevados", drops_rx + drops_tx))

        print(f"\n  {'─' * 64}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Resumen global de tráfico (todas las interfaces sumadas)
    # -------------------------------------------------------------------------
    try:
        io_total = psutil.net_io_counters()   # Sin pernic=True → totales globales
        print(f"\n🌍 TRÁFICO TOTAL DEL SISTEMA (todas las interfaces)")
        print(f"   Total recibido : {bytes_a_legible(io_total.bytes_recv):>12}"
              f"  ({io_total.packets_recv:>12,} paquetes)")
        print(f"   Total enviado  : {bytes_a_legible(io_total.bytes_sent):>12}"
              f"  ({io_total.packets_sent:>12,} paquetes)")
    except Exception:
        pass

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Conexiones activas (resumen por estado)
    # -------------------------------------------------------------------------
    # net_connections() devuelve todas las conexiones TCP/UDP activas.
    # En lugar de listarlas todas (pueden ser cientos), hacemos un resumen
    # agrupado por estado de conexión TCP.
    print(f"\n{'─' * 68}")
    print(f"\n🔗 CONEXIONES DE RED — RESUMEN POR ESTADO\n")

    try:
        # El parámetro 'inet' filtra solo conexiones IPv4 e IPv6 (excluye Unix sockets)
        conexiones = psutil.net_connections(kind='inet')

        # Agrupamos las conexiones por su estado (ESTABLISHED, LISTEN, TIME_WAIT...)
        # Usamos un diccionario donde la clave es el estado y el valor es el contador
        estados = {}
        for conn in conexiones:
            # conn.status puede ser 'ESTABLISHED', 'LISTEN', 'TIME_WAIT',
            # 'CLOSE_WAIT', 'NONE' (para UDP), etc.
            estado = conn.status if conn.status else "UDP/NONE"
            estados[estado] = estados.get(estado, 0) + 1

        if estados:
            # Ordenamos por cantidad (de más a menos) para ver lo más relevante primero
            for estado, cantidad in sorted(estados.items(), key=lambda x: x[1], reverse=True):
                # Coloreamos los estados más relevantes
                if estado == "ESTABLISHED":
                    estado_str = f"\033[92m{estado:<20}\033[0m"   # Verde: conexiones activas
                elif estado == "LISTEN":
                    estado_str = f"\033[94m{estado:<20}\033[0m"   # Azul: puertos escuchando
                elif estado in ("TIME_WAIT", "CLOSE_WAIT"):
                    estado_str = f"\033[93m{estado:<20}\033[0m"   # Amarillo: cerrándose
                else:
                    estado_str = f"{estado:<20}"
                print(f"   {estado_str} : {cantidad:>5} conexiones")

            print(f"\n   Total          : {len(conexiones):>5} conexiones")
        else:
            print("   No se detectaron conexiones activas.")

    except psutil.AccessDenied:
        # En Linux/Mac, listar conexiones de otros usuarios requiere root/sudo
        print("   ℹ️  Se necesitan permisos de administrador para ver todas las conexiones.")
        print("      Ejecuta el script con: sudo python3 red_monitor.py")
    except Exception as e:
        print(f"   ℹ️  No se pudieron obtener las conexiones: {e}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Diagnóstico de red
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 68}")
    print(f"\n🩺 DIAGNÓSTICO DE RED\n")

    if alertas_red:
        for interfaz, tipo, valor in alertas_red:
            print(f"  \033[91m⚠️  {interfaz}: {tipo} ({valor:,})\033[0m")
            if "errores" in tipo:
                print(f"     Posible causa: cable dañado, driver desactualizado")
                print(f"     o interferencias en la red inalámbrica.")
            elif "drops" in tipo:
                print(f"     Posible causa: interfaz saturada o buffer insuficiente.")
    else:
        print("  \033[92m✅ Red funcionando correctamente.\033[0m")
        print("     Sin errores ni paquetes descartados reseñables.")

    # Pie del monitor
    print("\n" + "=" * 68)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 68)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de red."""
    print("Iniciando monitor de red... (Ctrl+C para detener)")
    print(f"ℹ️  Cada ciclo incluye 1s de medición de velocidad + {INTERVALO_SEGUNDOS}s de pausa.")
    time.sleep(2)

    while True:
        try:
            mostrar_red()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
