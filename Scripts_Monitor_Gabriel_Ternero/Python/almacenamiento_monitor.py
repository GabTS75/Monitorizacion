# =============================================================================
#  almacenamiento_monitor.py — Monitor de Almacenamiento
#  Descripción : Monitoriza en tiempo real el espacio en disco por partición,
#                la velocidad de lectura/escritura y la actividad de I/O
#                (Input/Output) de cada dispositivo físico.
#  Requisitos  : pip install psutil
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué monitorizamos exactamente?
#
#  El almacenamiento tiene TRES niveles que hay que entender bien:
#
#  1️⃣  ESPACIO EN DISCO (particiones)
#      "¿Cuánto sitio me queda en cada unidad?"
#      Ejemplo: C:\ tiene 500 GB total, 320 usados, 180 libres.
#      Analogía: comprobar cuánto espacio libre hay en cada estante del armario.
#
#  2️⃣  VELOCIDAD DE I/O (rendimiento)
#      "¿A qué velocidad está leyendo/escribiendo el disco ahora mismo?"
#      Ejemplo: el disco está escribiendo a 120 MB/s porque estás copiando archivos.
#      Analogía: medir a qué velocidad el camión de reparto carga y descarga.
#
#  3️⃣  ACTIVIDAD DE I/O (estadísticas acumuladas)
#      "¿Cuántas operaciones ha hecho el disco desde que arrancó?"
#      Ejemplo: 1.245.302 lecturas y 823.104 escrituras desde el arranque.
#      Analogía: el cuentakilómetros total del disco.
# -----------------------------------------------------------------------------

import psutil       # Para acceder a particiones, espacio y estadísticas de disco
import time         # Para pausas y para calcular velocidades en tiempo real
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS      = 2     # Cada cuántos segundos se refresca la pantalla
UMBRAL_ALERTA_DISCO     = 85.0  # % de uso del disco a partir del cual alertamos
UMBRAL_CRITICO_DISCO    = 95.0  # % crítico: disco casi lleno, peligro real
MOSTRAR_PARTICIONES_ALL = False # False = omite particiones virtuales del SO
                                 # (como /proc, /sys, /dev en Linux)
                                 # True  = muestra absolutamente todas


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: convertir bytes a unidad legible ----------------------
# Reutilizamos la misma lógica que en memoria_monitor.py.
# En un proyecto real, esto estaría en un archivo "utils.py" compartido,
# pero aquí lo repetimos para que cada script sea completamente autónomo.

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


# --- Función auxiliar: barra de progreso visual -------------------------------
def barra_progreso(porcentaje, longitud=25):
    """Genera una barra de progreso visual con bloques Unicode."""
    rellenos = int((porcentaje / 100) * longitud)
    barra = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}] {porcentaje:5.1f}%"


# --- Función auxiliar: colorear según nivel de uso ----------------------------
# Para el disco usamos tres umbrales en lugar de dos, porque un disco al 95%
# es una emergencia real (el sistema puede dejar de funcionar si se llena).

def color_disco(porcentaje):
    """
    Colorea la barra de uso del disco según tres niveles:
    - Verde    → uso normal     (< 75%)
    - Amarillo → precaución     (75% – 85%)
    - Rojo     → alerta         (85% – 95%)
    - Rojo parpadeante → crítico (> 95%)
    """
    texto = barra_progreso(porcentaje)
    if porcentaje < 75:
        return f"\033[92m{texto}\033[0m"          # Verde
    elif porcentaje < UMBRAL_ALERTA_DISCO:
        return f"\033[93m{texto}\033[0m"          # Amarillo
    elif porcentaje < UMBRAL_CRITICO_DISCO:
        return f"\033[91m{texto}\033[0m"          # Rojo
    else:
        # \033[5m activa el "parpadeo" en terminales que lo soportan
        return f"\033[5m\033[91m{texto}\033[0m"   # Rojo parpadeante


# --- Función auxiliar: velocidad de I/O en tiempo real -----------------------
# Esta función es especial: para saber la VELOCIDAD actual (MB/s), necesitamos
# hacer DOS mediciones separadas por un intervalo de tiempo y calcular
# la diferencia. Es como medir velocidad en un coche: no puedes saber a qué
# vas mirando solo la posición actual, necesitas dos posiciones y el tiempo.

def obtener_velocidad_io(intervalo=1):
    """
    Calcula la velocidad de lectura/escritura actual de cada disco.
    Estrategia: leer contadores → esperar 'intervalo' segundos → leer de nuevo
                → calcular la diferencia → dividir por el tiempo.

    Devuelve un diccionario: { 'sda': {'lectura': X, 'escritura': Y}, ... }
    donde X e Y son bytes por segundo.
    """
    # Primera lectura de los contadores acumulados de I/O por dispositivo.
    # disk_io_counters(perdisk=True) devuelve un dict con cada disco como clave.
    # Ejemplo: {'sda': sdiskio(...), 'sdb': sdiskio(...)}
    antes = psutil.disk_io_counters(perdisk=True)

    # Esperamos el intervalo especificado
    time.sleep(intervalo)

    # Segunda lectura: ahora los contadores habrán aumentado si hubo actividad
    despues = psutil.disk_io_counters(perdisk=True)

    # Calculamos la velocidad para cada disco
    velocidades = {}

    for disco in antes:
        # Solo procesamos discos que siguen presentes en la segunda lectura
        # (por si se desconectó un USB entre mediciones)
        if disco in despues:
            # Bytes leídos en el intervalo = lectura_final - lectura_inicial
            bytes_leidos   = despues[disco].read_bytes  - antes[disco].read_bytes
            bytes_escritos = despues[disco].write_bytes - antes[disco].write_bytes

            # Velocidad = bytes transferidos / segundos transcurridos
            velocidades[disco] = {
                'lectura'   : bytes_leidos   / intervalo,   # bytes/segundo
                'escritura' : bytes_escritos / intervalo,   # bytes/segundo
            }

    return velocidades


# --- Función principal: obtener y mostrar datos de almacenamiento -------------

def mostrar_almacenamiento():
    """Recopila y muestra en pantalla todos los datos de almacenamiento."""

    # --- 1. Fecha y hora actual -----------------------------------------------
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 2. Lista de particiones montadas -------------------------------------
    # disk_partitions() devuelve una lista de particiones del sistema.
    # Cada elemento tiene: device, mountpoint, fstype, opts
    #   device     → el dispositivo físico  (ej: /dev/sda1, C:\)
    #   mountpoint → dónde está montado     (ej: /, /home, C:\)
    #   fstype     → sistema de archivos    (ej: ext4, ntfs, vfat)
    #   opts       → opciones de montaje    (ej: rw, ro, noexec...)
    #
    # all=False filtra las particiones virtuales del sistema operativo
    # (como /proc, /sys, tmpfs en Linux) que no son discos reales.
    particiones = psutil.disk_partitions(all=MOSTRAR_PARTICIONES_ALL)

    # --- 3. Velocidades de I/O en tiempo real ---------------------------------
    # Llamamos a nuestra función que hace las dos mediciones.
    # Nota: esta llamada "bloquea" el script durante 1 segundo mientras mide.
    # Ese segundo de pausa está incluido dentro del INTERVALO_SEGUNDOS total.
    try:
        velocidades = obtener_velocidad_io(intervalo=1)
    except Exception:
        # En algunos entornos (contenedores, VMs sin privilegios) no se pueden
        # leer los contadores de I/O. En ese caso simplemente los omitimos.
        velocidades = {}

    # --- 4. Estadísticas globales de I/O --------------------------------------
    # disk_io_counters() sin parámetros devuelve los totales acumulados
    # del SISTEMA COMPLETO (suma de todos los discos).
    try:
        io_global = psutil.disk_io_counters()
    except Exception:
        io_global = None

    # =========================================================================
    #  Construcción de la pantalla
    # =========================================================================

    limpiar_pantalla()

    # Cabecera
    print("=" * 65)
    print("       💽  MONITOR DE ALMACENAMIENTO — Tiempo Real")
    print(f"       📅 {ahora}")
    print("=" * 65)

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Espacio por partición
    # -------------------------------------------------------------------------
    print(f"\n📂 ESPACIO EN DISCO POR PARTICIÓN")
    print(f"   {'Unidad':<18} {'FS':<7} {'Total':>9} {'Usado':>9} {'Libre':>9}  Uso")
    print(f"   {'─'*18} {'─'*6} {'─'*9} {'─'*9} {'─'*9}  {'─'*33}")

    # Contador de alertas para el diagnóstico final
    alertas_disco = []

    for particion in particiones:
        try:
            # disk_usage() puede lanzar PermissionError en algunos puntos de
            # montaje del sistema (ej: /proc/tty en Linux). Lo capturamos.
            uso = psutil.disk_usage(particion.mountpoint)

        except PermissionError:
            # Si no tenemos permiso para leer una partición, la saltamos
            print(f"   {particion.mountpoint:<18} — Sin permiso de lectura")
            continue

        except OSError:
            # Puede ocurrir con unidades de red no disponibles o discos extraíbles
            print(f"   {particion.mountpoint:<18} — No disponible")
            continue

        # Abreviamos el punto de montaje si es muy largo para que quepa en pantalla
        mountpoint = particion.mountpoint
        if len(mountpoint) > 17:
            mountpoint = mountpoint[:14] + "..."

        # Abreviamos el tipo de sistema de archivos si es muy largo
        fstype = particion.fstype[:6] if particion.fstype else "?"

        # Construimos la línea de datos de esta partición
        print(f"   {mountpoint:<18} {fstype:<7} "
              f"{bytes_a_legible(uso.total):>9} "
              f"{bytes_a_legible(uso.used):>9} "
              f"{bytes_a_legible(uso.free):>9}  "
              f"{color_disco(uso.percent)}")

        # Registramos alertas para el diagnóstico al final
        if uso.percent >= UMBRAL_CRITICO_DISCO:
            alertas_disco.append((mountpoint, uso.percent, "CRÍTICO"))
        elif uso.percent >= UMBRAL_ALERTA_DISCO:
            alertas_disco.append((mountpoint, uso.percent, "ALERTA"))

    # Mostramos las alertas agrupadas bajo la tabla
    if alertas_disco:
        print()
        for mountpoint, pct, nivel in alertas_disco:
            if nivel == "CRÍTICO":
                print(f"   🚨 \033[5m\033[91m{nivel}: {mountpoint} al {pct:.1f}% — ¡disco casi lleno!\033[0m")
            else:
                print(f"   ⚠️  \033[91m{nivel}: {mountpoint} al {pct:.1f}% — espacio bajo\033[0m")

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Velocidad de I/O en tiempo real (por dispositivo)
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 65}")
    print(f"\n⚡ VELOCIDAD DE I/O EN TIEMPO REAL (último segundo)")

    if not velocidades:
        print("   ℹ️  No se pueden leer los contadores de I/O en este entorno.")
    else:
        print(f"   {'Dispositivo':<12} {'Lectura':>14} {'Escritura':>14}  Actividad")
        print(f"   {'─'*12} {'─'*14} {'─'*14}  {'─'*20}")

        for disco, vel in velocidades.items():
            lect_str   = f"{bytes_a_legible(vel['lectura'])}/s"
            escrit_str = f"{bytes_a_legible(vel['escritura'])}/s"

            # Indicador visual de actividad: cuántos bloques según MB/s
            # Normalizamos sobre 500 MB/s como referencia de "disco muy activo"
            actividad_total = vel['lectura'] + vel['escritura']
            pct_actividad   = min((actividad_total / (500 * 1024 * 1024)) * 100, 100)
            barrita = '█' * int(pct_actividad / 10) + '░' * (10 - int(pct_actividad / 10))

            print(f"   {disco:<12} {lect_str:>14} {escrit_str:>14}  [{barrita}]")

            # Advertencia si la velocidad de escritura es muy alta sostenida
            if vel['escritura'] > 200 * 1024 * 1024:   # > 200 MB/s escritura
                print(f"   {'':12} 💡 Escritura intensa en {disco}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Estadísticas acumuladas de I/O (desde el arranque)
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 65}")
    print(f"\n📊 ESTADÍSTICAS ACUMULADAS DE I/O (desde el arranque)")

    if io_global is None:
        print("   ℹ️  No disponible en este entorno.")
    else:
        # Estas estadísticas son totales ACUMULADOS desde que arrancó el sistema.
        # Son útiles para entender el "historial de trabajo" del disco.

        print(f"   Lecturas realizadas  : {io_global.read_count:>15,} operaciones")
        print(f"   Escrituras realizadas: {io_global.write_count:>15,} operaciones")
        print(f"   Datos leídos         : {bytes_a_legible(io_global.read_bytes):>15}")
        print(f"   Datos escritos       : {bytes_a_legible(io_global.write_bytes):>15}")

        # Tiempo que el disco ha estado ocupado en operaciones de I/O.
        # Se mide en milisegundos. Lo convertimos a segundos para más claridad.
        # Un valor muy alto indica que el disco ha estado muy ocupado.
        print(f"   Tiempo en lectura    : {io_global.read_time  / 1000:>15.1f} s")
        print(f"   Tiempo en escritura  : {io_global.write_time / 1000:>15.1f} s")

        # En Linux están disponibles también: busy_time (tiempo total ocupado)
        # y merged_read/merged_write (operaciones fusionadas para eficiencia)
        if hasattr(io_global, 'busy_time'):
            print(f"   Tiempo disco ocupado : {io_global.busy_time / 1000:>15.1f} s")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Información de dispositivos físicos
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 65}")
    print(f"\n🔌 DISPOSITIVOS DETECTADOS")

    # Mostramos un resumen de cada dispositivo con su sistema de archivos
    # y las opciones de montaje (si está en modo solo lectura, etc.)
    dispositivos_vistos = set()   # Para no mostrar el mismo dispositivo dos veces

    for particion in particiones:
        # Normalizamos el nombre del dispositivo para agrupar particiones del mismo disco
        # Ejemplo: /dev/sda1 y /dev/sda2 pertenecen al mismo disco /dev/sda
        dispositivo = particion.device

        if dispositivo not in dispositivos_vistos:
            dispositivos_vistos.add(dispositivo)

            # Truncamos si el nombre es muy largo
            dev_str = dispositivo if len(dispositivo) <= 30 else dispositivo[:27] + "..."

            # Indicamos si está montado en solo lectura (ro) o lectura-escritura (rw)
            modo = "solo lectura" if "ro" in particion.opts else "lectura/escritura"

            print(f"   📀 {dev_str}")
            print(f"      Tipo    : {particion.fstype if particion.fstype else 'desconocido'}")
            print(f"      Montado : {particion.mountpoint}")
            print(f"      Modo    : {modo}")
            print()

    # Pie del monitor
    print("=" * 65)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 65)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de almacenamiento."""
    print("Iniciando monitor de almacenamiento... (Ctrl+C para detener)")

    # Aviso importante: la medición de velocidad de I/O tarda 1 segundo extra
    # porque necesita dos lecturas separadas. El intervalo real entre
    # actualizaciones será INTERVALO_SEGUNDOS + 1 segundo de medición.
    print(f"ℹ️  Nota: cada ciclo incluye 1s de medición de I/O + {INTERVALO_SEGUNDOS}s de pausa.")
    time.sleep(2)

    while True:
        try:
            mostrar_almacenamiento()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
