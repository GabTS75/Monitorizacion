# =============================================================================
#  procesos_monitor.py — Monitor de Procesos
#  Descripción : Monitoriza en tiempo real los procesos en ejecución:
#                top consumidores de CPU y RAM, estados, zombies y
#                un resumen general del sistema de procesos.
#  Requisitos  : pip install psutil
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué es un proceso?
#
#  Cada vez que abres un programa, el sistema operativo crea un "proceso":
#  una instancia en ejecución de ese programa con su propio espacio de memoria,
#  identificador único (PID) y estado.
#
#  Analogía: imagina un restaurante. El menú sería el programa (el archivo
#  en disco). Cada mesa con clientes siendo atendida sería un proceso:
#  el mismo menú "en ejecución" para distintos clientes al mismo tiempo.
#  El maitre (sistema operativo) gestiona todas las mesas y les asigna
#  camareros (núcleos de CPU) según la disponibilidad.
#
#  Estados posibles de un proceso:
#  ┌──────────────┬────────────────────────────────────────────────────┐
#  │ Estado       │ Significado                                        │
#  ├──────────────┼────────────────────────────────────────────────────┤
#  │ running  (R) │ Ejecutándose activamente en la CPU ahora mismo     │
#  │ sleeping (S) │ Esperando algo (un evento, I/O, un timer...)       │
#  │ disk-sleep(D)│ Esperando I/O de disco — no se puede interrumpir   │
#  │ stopped  (T) │ Pausado (ej: Ctrl+Z en terminal)                   │
#  │ zombie   (Z) │ Terminado pero su padre no ha "recogido" su estado │
#  │ idle     (I) │ Inactivo del kernel (Linux moderno)                │
#  └──────────────┴────────────────────────────────────────────────────┘
#
#  ¿Qué es un proceso zombie?
#  Cuando un proceso hijo termina, deja un pequeño registro en el sistema
#  esperando que su proceso padre lea su código de salida. Si el padre
#  nunca lo recoge, ese registro queda "vivo" sin hacer nada: un zombie.
#  Analogía: como un empleado que ya entregó su renuncia y vacío su mesa,
#  pero sigue apareciendo en la nómina porque RRHH no procesó el papeleo.
#
#  ¿Qué es el PID?
#  Process IDentifier — el número único que el SO asigna a cada proceso.
#  El proceso con PID 1 es siempre el primero en arrancar (init/systemd).
#  Es como el DNI de cada proceso.
# -----------------------------------------------------------------------------

import psutil       # Para acceder a la lista y datos de procesos
import time         # Para pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS  = 3     # Cada cuántos segundos se refresca la pantalla
TOP_N_PROCESOS      = 10    # Cuántos procesos mostrar en cada ranking
UMBRAL_CPU_PROC     = 50.0  # % de CPU de un proceso a partir del cual alertamos
UMBRAL_RAM_PROC_MB  = 500   # MB de RAM de un proceso a partir del cual alertamos
MOSTRAR_HILOS       = True  # True = muestra el número de hilos por proceso


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


# --- Función auxiliar: barra de progreso visual -------------------------------
def barra_progreso(porcentaje, longitud=12):
    """Genera una barra de progreso visual compacta."""
    # Nos aseguramos de que el porcentaje no supere 100
    # (un proceso puede reportar más del 100% en sistemas multinúcleo)
    porcentaje_clamped = min(porcentaje, 100)
    rellenos = int((porcentaje_clamped / 100) * longitud)
    barra    = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}]"


# --- Función auxiliar: colorear porcentaje de CPU ----------------------------
def color_cpu(porcentaje):
    """Colorea el uso de CPU de un proceso según su nivel."""
    if porcentaje < 20:
        return f"\033[92m{porcentaje:6.1f}%\033[0m"   # Verde
    elif porcentaje < UMBRAL_CPU_PROC:
        return f"\033[93m{porcentaje:6.1f}%\033[0m"   # Amarillo
    else:
        return f"\033[91m{porcentaje:6.1f}%\033[0m"   # Rojo


# --- Función auxiliar: colorear uso de RAM -----------------------------------
def color_ram(bytes_valor):
    """Colorea el uso de RAM de un proceso según su nivel."""
    mb = bytes_valor / (1024 * 1024)
    texto = f"{bytes_a_legible(bytes_valor):>10}"
    if mb < 100:
        return f"\033[92m{texto}\033[0m"    # Verde:   < 100 MB
    elif mb < UMBRAL_RAM_PROC_MB:
        return f"\033[93m{texto}\033[0m"    # Amarillo: 100–500 MB
    else:
        return f"\033[91m{texto}\033[0m"    # Rojo:    > 500 MB


# --- Función auxiliar: truncar nombre de proceso largo ----------------------
def truncar(texto, longitud):
    """Trunca un texto si supera la longitud máxima, añadiendo '...'"""
    if len(texto) > longitud:
        return texto[:longitud - 3] + "..."
    return texto


# --- Función principal: recopilar datos de todos los procesos ----------------

def recopilar_procesos():
    """
    Obtiene la lista de todos los procesos en ejecución con sus datos.
    Devuelve una lista de diccionarios, uno por proceso.

    Usamos psutil.process_iter() que es más eficiente que llamar a
    psutil.pids() y luego crear un Process() para cada uno.
    process_iter() itera sobre los procesos ya existentes de forma segura.

    El parámetro 'attrs' especifica qué atributos queremos leer.
    Solo pedimos lo que necesitamos: así es más rápido y consume menos.
    """
    procesos = []

    # Lista de atributos que queremos leer de cada proceso
    atributos = [
        'pid',            # Identificador único del proceso
        'name',           # Nombre del ejecutable (ej: python3, chrome, sshd)
        'username',       # Usuario propietario del proceso
        'status',         # Estado: running, sleeping, zombie, etc.
        'cpu_percent',    # % de CPU usado (requiere llamada previa para calibrar)
        'memory_info',    # Objeto con rss, vms y otros datos de memoria
        'memory_percent', # % de RAM total del sistema que usa este proceso
        'num_threads',    # Número de hilos (threads) del proceso
        'create_time',    # Timestamp UNIX de cuándo se creó el proceso
        'ppid',           # PID del proceso padre (Parent PID)
    ]

    for proceso in psutil.process_iter(atributos):
        try:
            # info es un diccionario con los atributos pedidos
            info = proceso.info

            # Ignoramos procesos con PID 0 (proceso idle del kernel)
            if info['pid'] == 0:
                continue

            # Calculamos la memoria RSS en bytes
            # RSS (Resident Set Size) = memoria física real que ocupa el proceso
            # Es el dato más representativo del consumo real de RAM.
            # VMS (Virtual Memory Size) incluye memoria mapeada pero no usada,
            # lo que lo hace mucho mayor y menos representativo.
            mem_bytes = info['memory_info'].rss if info['memory_info'] else 0

            # Calculamos el tiempo de vida del proceso
            # create_time es un timestamp UNIX (segundos desde 1970-01-01)
            # Restamos del tiempo actual para obtener cuánto lleva en marcha
            try:
                tiempo_activo = time.time() - info['create_time']
                horas   = int(tiempo_activo // 3600)
                minutos = int((tiempo_activo % 3600) // 60)
                uptime  = f"{horas:02d}h {minutos:02d}m"
            except Exception:
                uptime = "N/A"

            procesos.append({
                'pid'       : info['pid'],
                'nombre'    : info['name'] or 'N/A',
                'usuario'   : info['username'] or 'N/A',
                'estado'    : info['status'] or 'N/A',
                'cpu'       : info['cpu_percent'] or 0.0,
                'ram_bytes' : mem_bytes,
                'ram_pct'   : info['memory_percent'] or 0.0,
                'hilos'     : info['num_threads'] or 0,
                'uptime'    : uptime,
                'ppid'      : info['ppid'],
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Estos errores son completamente normales en la monitorización:
            # - NoSuchProcess : el proceso terminó mientras lo leíamos
            # - AccessDenied  : no tenemos permiso para leer ese proceso
            # - ZombieProcess : proceso zombie, sin datos accesibles
            # Los ignoramos silenciosamente y continuamos con el siguiente.
            continue

    return procesos


# --- Función principal: obtener y mostrar datos de procesos ------------------

def mostrar_procesos():
    """Recopila y muestra en pantalla todos los datos de procesos."""

    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Recopilamos todos los procesos
    todos = recopilar_procesos()

    # --- Contadores por estado -----------------------------------------------
    # Agrupamos los procesos por su estado para el resumen global
    conteo_estados = {}
    for p in todos:
        estado = p['estado']
        conteo_estados[estado] = conteo_estados.get(estado, 0) + 1

    # Identificamos los zombies (son los más importantes de detectar)
    zombies = [p for p in todos if p['estado'] == 'zombie']

    # --- Rankings ------------------------------------------------------------
    # Ordenamos la lista completa por CPU (de mayor a menor) y tomamos los top N
    top_cpu = sorted(todos, key=lambda p: p['cpu'],       reverse=True)[:TOP_N_PROCESOS]
    top_ram = sorted(todos, key=lambda p: p['ram_bytes'], reverse=True)[:TOP_N_PROCESOS]

    # =========================================================================
    #  Construcción de la pantalla
    # =========================================================================

    limpiar_pantalla()

    # Cabecera
    print("=" * 70)
    print("       ⚙️   MONITOR DE PROCESOS — Tiempo Real")
    print(f"       📅 {ahora}")
    print("=" * 70)

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Resumen global del sistema de procesos
    # -------------------------------------------------------------------------
    print(f"\n📊 RESUMEN GLOBAL\n")

    total = len(todos)
    print(f"   Total de procesos : {total}")

    # Mostramos el conteo de cada estado de forma compacta
    for estado, cantidad in sorted(conteo_estados.items(), key=lambda x: x[1], reverse=True):
        # Iconos y colores según el estado
        iconos = {
            'running'   : ('▶️ ', '\033[92m'),
            'sleeping'  : ('💤', '\033[94m'),
            'disk-sleep': ('💿', '\033[93m'),
            'stopped'   : ('⏸️ ', '\033[93m'),
            'zombie'    : ('🧟', '\033[91m'),
            'idle'      : ('⏳', '\033[2m'),
        }
        icono, color = iconos.get(estado, ('⚪', ''))
        reset = '\033[0m' if color else ''
        print(f"   {icono}  {color}{estado:<14}{reset} : {cantidad:>5}")

    # Alerta especial si hay zombies
    if zombies:
        print(f"\n   ⚠️  \033[91mATENCIÓN: {len(zombies)} proceso(s) zombie detectado(s)\033[0m")
        print(f"      Los zombies no consumen CPU ni RAM, pero indican que")
        print(f"      algún proceso padre no está gestionando bien sus hijos.")
        for z in zombies[:3]:   # Mostramos hasta 3 zombies como máximo
            print(f"      → PID {z['pid']} ({z['nombre']}) — padre: PID {z['ppid']}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Top N procesos por uso de CPU
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print(f"\n🧠 TOP {TOP_N_PROCESOS} PROCESOS POR USO DE CPU\n")

    # Cabecera de la tabla
    col_hilo = "Hilos" if MOSTRAR_HILOS else ""
    print(f"   {'PID':>7}  {'CPU':>8}  {'Barra CPU':^14}  "
          f"{'RAM':>10}  {'Estado':<12}  {'Hilos':>5}  Proceso")
    print(f"   {'─'*7}  {'─'*8}  {'─'*14}  "
          f"{'─'*10}  {'─'*12}  {'─'*5}  {'─'*25}")

    for p in top_cpu:
        # Solo mostramos procesos con al menos algo de actividad
        # para no llenar la pantalla de procesos dormidos al 0%
        barra = barra_progreso(p['cpu'])
        hilo_str = f"{p['hilos']:>5}" if MOSTRAR_HILOS else ""
        nombre   = truncar(p['nombre'], 25)

        print(f"   {p['pid']:>7}  "
              f"{color_cpu(p['cpu'])}  "
              f"{barra:^14}  "
              f"{color_ram(p['ram_bytes'])}  "
              f"{p['estado']:<12}  "
              f"{hilo_str}  "
              f"{nombre}")

        # Alerta inline si un proceso está consumiendo demasiada CPU
        if p['cpu'] >= UMBRAL_CPU_PROC:
            print(f"   {'':>7}  \033[91m⚠️  Proceso con uso de CPU muy elevado\033[0m")

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Top N procesos por uso de RAM
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print(f"\n💾 TOP {TOP_N_PROCESOS} PROCESOS POR USO DE RAM\n")

    print(f"   {'PID':>7}  {'RAM':>10}  {'RAM%':>6}  {'Barra RAM':^14}  "
          f"{'Estado':<12}  {'Tiempo':>8}  Proceso")
    print(f"   {'─'*7}  {'─'*10}  {'─'*6}  {'─'*14}  "
          f"{'─'*12}  {'─'*8}  {'─'*25}")

    for p in top_ram:
        barra   = barra_progreso(p['ram_pct'])
        nombre  = truncar(p['nombre'], 25)

        print(f"   {p['pid']:>7}  "
              f"{color_ram(p['ram_bytes'])}  "
              f"{p['ram_pct']:>5.1f}%  "
              f"{barra:^14}  "
              f"{p['estado']:<12}  "
              f"{p['uptime']:>8}  "
              f"{nombre}")

        if p['ram_bytes'] / (1024*1024) >= UMBRAL_RAM_PROC_MB:
            print(f"   {'':>7}  \033[93m⚠️  Proceso con uso de RAM elevado\033[0m")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Estadísticas de CPU globales del sistema (contexto)
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print(f"\n📈 CONTEXTO DEL SISTEMA\n")

    # Estos datos complementan los de procesos individuales con una visión
    # del sistema completo, útil para entender si el equipo está saturado.
    try:
        cpu_global  = psutil.cpu_percent(interval=0)
        ram_global  = psutil.virtual_memory()
        stats_cpu   = psutil.cpu_stats()

        print(f"   CPU global del sistema    : {cpu_global:>6.1f}%")
        print(f"   RAM usada del sistema     : {ram_global.percent:>6.1f}%  "
              f"({bytes_a_legible(ram_global.used)} / {bytes_a_legible(ram_global.total)})")
        print(f"   Cambios de contexto/total : {stats_cpu.ctx_switches:>12,}")
        print(f"   Total procesos activos    : {total:>6}")

        # El load average es la "cola de espera" de la CPU
        # Si es mayor que el número de núcleos, hay más trabajo del que se puede hacer
        try:
            carga = os.getloadavg()
            nucleos = psutil.cpu_count(logical=True)
            print(f"\n   Carga media (1/5/15 min)  : "
                  f"{carga[0]:.2f} / {carga[1]:.2f} / {carga[2]:.2f}")
            if carga[0] > nucleos:
                print(f"   ⚠️  \033[93mCarga superior a los {nucleos} núcleos disponibles\033[0m")
        except AttributeError:
            pass   # getloadavg no está disponible en Windows

    except Exception:
        pass

    # -------------------------------------------------------------------------
    #  SECCIÓN 5: Procesos con usuario propietario (agrupado)
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print(f"\n👤 PROCESOS POR USUARIO\n")

    # Agrupamos el número de procesos por usuario
    # Útil para detectar si un usuario está consumiendo muchos recursos
    usuarios = {}
    for p in todos:
        usuario = p['usuario'] if p['usuario'] else 'desconocido'
        # En Windows los usuarios tienen formato DOMINIO\usuario, simplificamos
        usuario_corto = usuario.split('\\')[-1] if '\\' in usuario else usuario
        usuarios[usuario_corto] = usuarios.get(usuario_corto, 0) + 1

    # Ordenamos por número de procesos (de más a menos)
    for usuario, cantidad in sorted(usuarios.items(), key=lambda x: x[1], reverse=True):
        barra = '█' * min(cantidad // 2, 30)   # Barra proporcional (escala: 2 proc = 1 bloque)
        print(f"   {usuario:<20} : {cantidad:>5} procesos  {barra}")

    # Pie del monitor
    print("\n" + "=" * 70)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 70)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de procesos."""
    print("Iniciando monitor de procesos... (Ctrl+C para detener)")

    # Nota importante: psutil necesita una primera llamada a cpu_percent()
    # con interval=None para "calibrar" el contador antes de usarlo.
    # Si no hacemos esto, la primera lectura de CPU de cada proceso dará 0.0%.
    # Llamamos a process_iter una vez de forma silenciosa para inicializar.
    print("ℹ️  Calibrando contadores de CPU (1 segundo)...")
    for p in psutil.process_iter(['cpu_percent']):
        try:
            p.cpu_percent()
        except Exception:
            pass
    time.sleep(1)   # Esperamos 1 segundo para que los contadores tengan datos

    while True:
        try:
            mostrar_procesos()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
