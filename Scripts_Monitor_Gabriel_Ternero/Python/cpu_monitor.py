# =============================================================================
#  cpu_monitor.py — Monitor de CPU
#  Descripción : Monitoriza en tiempo real el uso, frecuencia y carga del
#                procesador, mostrando los datos actualizados en pantalla.
#  Requisitos  : pip install psutil
# =============================================================================

# --- Importación de librerías -------------------------------------------------
# Las librerías son como "cajas de herramientas" ya hechas que alguien más
# programó y nosotros simplemente usamos. No hay que reinventar la rueda.

import psutil       # La librería estrella: nos da acceso a toda la info del hardware
import time         # Nos permite usar pausas (como un "espera X segundos")
import os           # Nos permite interactuar con el sistema operativo (ej: limpiar pantalla)
import datetime     # Para obtener la fecha y hora actual del sistema

# --- Configuración general ----------------------------------------------------
# Aquí centralizamos los parámetros que podemos querer cambiar fácilmente.
# Es una buena práctica definirlos al principio en lugar de tenerlos
# "escondidos" dentro del código.

INTERVALO_SEGUNDOS = 2      # Cada cuántos segundos se actualiza la pantalla
UMBRAL_ALERTA_CPU  = 85.0   # Si el uso supera este %, mostramos una advertencia
MOSTRAR_POR_NUCLEO = True   # True = muestra el uso de cada núcleo individualmente


# --- Función auxiliar: limpiar pantalla ---------------------------------------
# Una función es un bloque de código con nombre propio que podemos "llamar"
# cuando queramos, tantas veces como necesitemos, sin repetir el código.

def limpiar_pantalla():
    """Limpia la terminal para que cada actualización se vea limpia."""
    # 'cls' es el comando en Windows, 'clear' es el equivalente en Linux/Mac.
    # Con 'os.name' detectamos en qué sistema estamos ejecutando el script.
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: barra de progreso visual -------------------------------
# Esta función convierte un número (porcentaje) en una barra visual con
# caracteres, como las barras de carga que ves en muchos programas.
# Ejemplo: uso=75 → [███████████████░░░░░] 75.0%

def barra_progreso(porcentaje, longitud=20):
    """
    Genera una barra de progreso visual en texto.
    - porcentaje : valor entre 0 y 100
    - longitud   : número de caracteres que tendrá la barra
    """
    # Calculamos cuántos bloques rellenos corresponden al porcentaje dado.
    # Ejemplo: si porcentaje=50 y longitud=20 → rellenos = 10
    rellenos = int((porcentaje / 100) * longitud)

    # Construimos la barra: bloques rellenos + bloques vacíos
    barra = '█' * rellenos + '░' * (longitud - rellenos)

    # Devolvemos la barra dentro de corchetes con el porcentaje al lado
    return f"[{barra}] {porcentaje:5.1f}%"


# --- Función auxiliar: colorear texto según el nivel de uso ------------------
# Para hacer la lectura más intuitiva, usamos colores ANSI (códigos especiales
# que la terminal interpreta como colores). Verde = bien, amarillo = atención,
# rojo = problema.

def color_por_uso(porcentaje):
    """
    Devuelve el texto del porcentaje con color según el nivel de uso:
    - Verde   → uso bajo  (< 50%)
    - Amarillo → uso medio (50–85%)
    - Rojo    → uso alto  (> 85%)
    """
    # Códigos de escape ANSI: \033[ inicia el código, 'm' lo cierra,
    # \033[0m resetea el color al final para no "contaminar" el resto del texto.
    if porcentaje < 50:
        return f"\033[92m{barra_progreso(porcentaje)}\033[0m"   # Verde
    elif porcentaje < UMBRAL_ALERTA_CPU:
        return f"\033[93m{barra_progreso(porcentaje)}\033[0m"   # Amarillo
    else:
        return f"\033[91m{barra_progreso(porcentaje)}\033[0m"   # Rojo


# --- Función principal: obtener y mostrar datos de CPU -----------------------
# Esta es la función más importante del script. Recopila toda la información
# de la CPU y la presenta de forma organizada en pantalla.

def mostrar_cpu():
    """Recopila y muestra en pantalla todos los datos relevantes de la CPU."""

    # --- 1. Fecha y hora actual -----------------------------------------------
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 2. Uso global de CPU (%) ---------------------------------------------
    # interval=1 significa que psutil "observa" la CPU durante 1 segundo antes
    # de devolver el resultado. Sin este parámetro, daría 0.0% siempre.
    uso_total = psutil.cpu_percent(interval=1)

    # --- 3. Uso por núcleo (%) ------------------------------------------------
    # percpu=True devuelve una lista con el % de uso de cada núcleo por separado.
    # Ejemplo en un procesador de 4 núcleos: [12.5, 45.0, 8.3, 67.1]
    uso_por_nucleo = psutil.cpu_percent(percpu=True)

    # --- 4. Información sobre los núcleos ------------------------------------
    # logical=False → núcleos físicos reales del chip
    # logical=True  → núcleos lógicos (incluye Hyper-Threading si existe)
    nucleos_fisicos = psutil.cpu_count(logical=False)
    nucleos_logicos = psutil.cpu_count(logical=True)

    # --- 5. Frecuencia de la CPU ----------------------------------------------
    # Devuelve un objeto con: current (actual), min (mínima), max (máxima)
    # Los valores vienen en MHz, nosotros los convertimos a GHz dividiendo /1000
    frecuencia = psutil.cpu_freq()

    # --- 6. Carga media del sistema (load average) ----------------------------
    # Este dato indica el "trabajo pendiente" que tiene el sistema.
    # Se mide en 3 intervalos: último 1 min, últimos 5 min, últimos 15 min.
    # Solo está disponible en Linux/Mac (en Windows devuelve error, lo capturamos)
    try:
        carga_1, carga_5, carga_15 = os.getloadavg()
    except AttributeError:
        # En Windows, os.getloadavg() no existe, así que asignamos None
        carga_1 = carga_5 = carga_15 = None

    # --- 7. Tiempos de CPU (en segundos acumulados) ---------------------------
    # La CPU no siempre está haciendo "tu trabajo". Parte del tiempo lo dedica
    # al sistema operativo, a esperar el disco, etc. cpu_times() nos desglosa
    # en qué ha invertido su tiempo desde que arrancó el equipo.
    tiempos = psutil.cpu_times()

    # --- 8. Estadísticas de CPU ----------------------------------------------
    # Interrupciones: señales de hardware que "interrumpen" a la CPU (teclado,
    # red, disco...). Cambios de contexto: cuántas veces cambió entre procesos.
    stats = psutil.cpu_stats()

    # =========================================================================
    #  A partir de aquí: construimos la pantalla con todos los datos obtenidos
    # =========================================================================

    limpiar_pantalla()

    # Cabecera del monitor
    print("=" * 60)
    print("       🖥️  MONITOR DE CPU — Tiempo Real")
    print(f"       📅 {ahora}")
    print("=" * 60)

    # --- Uso global -----------------------------------------------------------
    print(f"\n📊 USO GLOBAL DE CPU")
    print(f"   {color_por_uso(uso_total)}")

    # Si el uso supera el umbral, mostramos una advertencia visible
    if uso_total >= UMBRAL_ALERTA_CPU:
        print(f"\n   ⚠️  \033[91mALERTA: CPU al {uso_total}% — uso muy elevado\033[0m")

    # --- Núcleos y frecuencia -------------------------------------------------
    print(f"\n🔩 NÚCLEOS")
    print(f"   Físicos  : {nucleos_fisicos}")
    print(f"   Lógicos  : {nucleos_logicos}")

    # Mostramos la frecuencia solo si psutil pudo obtenerla
    # (en algunas VMs o contenedores puede no estar disponible)
    if frecuencia:
        print(f"\n⚡ FRECUENCIA")
        print(f"   Actual   : {frecuencia.current / 1000:.2f} GHz")
        print(f"   Máxima   : {frecuencia.max    / 1000:.2f} GHz")
        print(f"   Mínima   : {frecuencia.min    / 1000:.2f} GHz")

    # --- Uso por núcleo -------------------------------------------------------
    if MOSTRAR_POR_NUCLEO:
        print(f"\n🧩 USO POR NÚCLEO")
        for i, uso in enumerate(uso_por_nucleo):
            # Formateamos el número de núcleo con cero a la izquierda: 00, 01, 02...
            print(f"   Núcleo {i:02d} : {color_por_uso(uso)}")

    # --- Carga media ----------------------------------------------------------
    print(f"\n📈 CARGA MEDIA DEL SISTEMA")
    if carga_1 is not None:
        print(f"   Último  1 min  : {carga_1:.2f}")
        print(f"   Últimos 5 min  : {carga_5:.2f}")
        print(f"   Últimos 15 min : {carga_15:.2f}")
        # La carga media es "preocupante" cuando supera el número de núcleos lógicos.
        # Si tienes 4 núcleos y la carga es 6.0, hay más trabajo del que puede manejar.
        if carga_1 > nucleos_logicos:
            print(f"   ⚠️  \033[93mCarga superior al número de núcleos ({nucleos_logicos})\033[0m")
    else:
        print("   (No disponible en Windows)")

    # --- Tiempos de CPU -------------------------------------------------------
    print(f"\n⏱️  TIEMPOS DE CPU (segundos acumulados desde arranque)")
    print(f"   Usuario (procesos del usuario) : {tiempos.user:>12.2f} s")
    print(f"   Sistema (kernel del SO)        : {tiempos.system:>12.2f} s")
    print(f"   Inactivo (idle)                : {tiempos.idle:>12.2f} s")
    # iowait solo existe en Linux (tiempo esperando operaciones de disco/red)
    if hasattr(tiempos, 'iowait'):
        print(f"   Espera I/O (disco/red)         : {tiempos.iowait:>12.2f} s")

    # --- Estadísticas ---------------------------------------------------------
    print(f"\n📡 ESTADÍSTICAS")
    print(f"   Interrupciones hardware  : {stats.interrupts:>12,}")
    print(f"   Interrupciones software  : {stats.soft_interrupts:>12,}")
    print(f"   Cambios de contexto      : {stats.ctx_switches:>12,}")

    # Pie del monitor con instrucciones para el usuario
    print("\n" + "=" * 60)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 60)


# --- Bucle principal de monitorización ---------------------------------------
# Todo lo de arriba son "preparativos". Aquí es donde el script realmente
# "vive": entra en un bucle infinito que llama a mostrar_cpu() una y otra vez,
# con una pausa entre cada llamada.

def iniciar_monitor():
    """Inicia el bucle de monitorización continua."""
    print("Iniciando monitor de CPU... (Ctrl+C para detener)")
    time.sleep(1)  # Pequeña pausa antes de empezar, para que el mensaje se lea

    # 'while True' crea un bucle que nunca termina por sí solo.
    # Es como decirle al script: "repite esto para siempre".
    while True:
        try:
            mostrar_cpu()           # Llamamos a la función que muestra los datos
            time.sleep(INTERVALO_SEGUNDOS)  # Esperamos antes de la siguiente actualización

        except KeyboardInterrupt:
            # Cuando el usuario pulsa Ctrl+C, Python lanza una excepción llamada
            # KeyboardInterrupt. La "capturamos" aquí para cerrar limpiamente
            # en lugar de mostrar un error feo en pantalla.
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break  # 'break' rompe el bucle while y termina el script


# --- Punto de entrada del script ---------------------------------------------
# Esta parte es muy importante en Python. La condición:
#   if __name__ == "__main__":
# significa: "ejecuta esto SOLO si el script se lanzó directamente".
# Si en el futuro importamos este archivo desde otro script (como el menú),
# esta parte NO se ejecutará automáticamente. Así controlamos cuándo arranca.

if __name__ == "__main__":
    iniciar_monitor()
