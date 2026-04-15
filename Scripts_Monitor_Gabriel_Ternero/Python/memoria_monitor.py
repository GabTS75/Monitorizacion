# =============================================================================
#  memoria_monitor.py — Monitor de Memoria RAM y Swap
#  Descripción : Monitoriza en tiempo real el uso de la memoria RAM y la
#                memoria de intercambio (Swap), mostrando los datos
#                actualizados en pantalla con alertas visuales.
#  Requisitos  : pip install psutil
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué es la RAM?
#  Imagina que tu ordenador es una cocina. El disco duro sería el armario donde
#  guardas todos los ingredientes (datos). La RAM sería la encimera de trabajo:
#  el espacio donde colocas solo lo que necesitas en este momento para cocinar.
#  Cuanto más grande la encimera, más cosas puedes preparar a la vez sin
#  tener que ir al armario constantemente.
#
#  ¿Qué es el Swap?
#  Siguiendo la analogía: cuando la encimera (RAM) se llena, empiezas a usar
#  una mesa auxiliar más lenta y lejana (el disco duro) para dejar cosas
#  temporalmente. Eso es el Swap: RAM "de emergencia" en el disco.
#  Es mucho más lento que la RAM real, así que un Swap muy usado es señal
#  de que el equipo necesita más memoria.
# -----------------------------------------------------------------------------

import psutil       # Librería para acceder a la información del hardware
import time         # Para las pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS    = 2     # Cada cuántos segundos se refresca la pantalla
UMBRAL_ALERTA_RAM     = 85.0  # % de RAM a partir del cual mostramos alerta
UMBRAL_ALERTA_SWAP    = 50.0  # % de Swap a partir del cual mostramos alerta
                               # (el Swap empieza a ser preocupante antes que la RAM)


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización para una lectura limpia."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: convertir bytes a unidad legible ----------------------
# La memoria se mide internamente en bytes, pero nosotros preferimos verla
# en MB o GB. Esta función hace esa conversión automáticamente.
# Ejemplo: 8.589.934.592 bytes → "8.00 GB"

def bytes_a_legible(bytes_valor):
    """
    Convierte una cantidad de bytes a la unidad más legible:
    KB, MB, GB o TB según el tamaño.
    - bytes_valor : número entero de bytes a convertir
    """
    # Definimos los divisores para cada unidad.
    # 1 KB = 1024 bytes, 1 MB = 1024 KB, etc.
    # Usamos una lista de tuplas (divisor, nombre de la unidad).
    unidades = [
        (1024 ** 4, "TB"),   # Terabytes  — para valores enormes
        (1024 ** 3, "GB"),   # Gigabytes  — lo más común en RAM moderna
        (1024 ** 2, "MB"),   # Megabytes  — para valores pequeños
        (1024 ** 1, "KB"),   # Kilobytes  — para valores muy pequeños
    ]

    # Recorremos la lista de mayor a menor.
    # En cuanto el valor sea mayor o igual al divisor, usamos esa unidad.
    for divisor, nombre in unidades:
        if bytes_valor >= divisor:
            return f"{bytes_valor / divisor:.2f} {nombre}"

    # Si el valor es menor que 1 KB, lo mostramos directamente en bytes
    return f"{bytes_valor} B"


# --- Función auxiliar: barra de progreso visual -------------------------------
# La misma idea que en cpu_monitor.py: convertimos un % en una barra de texto.
# La reutilizamos aquí para ser consistentes visualmente entre scripts.

def barra_progreso(porcentaje, longitud=25):
    """
    Genera una barra de progreso visual.
    - porcentaje : valor entre 0 y 100
    - longitud   : ancho total de la barra en caracteres
    """
    rellenos = int((porcentaje / 100) * longitud)
    barra = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}] {porcentaje:5.1f}%"


# --- Función auxiliar: colorear según nivel de uso ----------------------------
def color_por_uso(porcentaje, umbral_alerta):
    """
    Devuelve la barra de progreso con color ANSI según el nivel de uso.
    A diferencia de cpu_monitor, aquí recibimos el umbral como parámetro
    porque RAM y Swap tienen umbrales diferentes.
    - Verde    → uso bajo   (< 50%)
    - Amarillo → uso medio  (50% – umbral_alerta)
    - Rojo     → uso alto   (> umbral_alerta)
    """
    texto = barra_progreso(porcentaje)
    if porcentaje < 50:
        return f"\033[92m{texto}\033[0m"             # Verde
    elif porcentaje < umbral_alerta:
        return f"\033[93m{texto}\033[0m"             # Amarillo
    else:
        return f"\033[91m{texto}\033[0m"             # Rojo


# --- Función auxiliar: línea de detalle de memoria ---------------------------
# Esta pequeña función nos evita repetir el mismo formato en varios sitios.
# Principio de programación: DRY = "Don't Repeat Yourself" (No te repitas).

def linea_detalle(etiqueta, valor_bytes, ancho=10):
    """
    Devuelve una línea formateada con etiqueta y valor convertido.
    - etiqueta   : texto descriptivo (ej: "Total")
    - valor_bytes: cantidad en bytes a convertir
    - ancho      : ancho mínimo del campo de la etiqueta (para alinear columnas)
    """
    # El símbolo < en el formato significa "alinear a la izquierda"
    # El número indica el ancho mínimo del campo.
    return f"   {etiqueta:<12} : {bytes_a_legible(valor_bytes):>12}"


# --- Función principal: obtener y mostrar datos de memoria -------------------

def mostrar_memoria():
    """Recopila y muestra en pantalla todos los datos de RAM y Swap."""

    # --- 1. Fecha y hora actual -----------------------------------------------
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 2. Datos de la memoria RAM -------------------------------------------
    # virtual_memory() devuelve un objeto con múltiples atributos.
    # Es como abrir un "informe completo" de la RAM en un solo comando.
    ram = psutil.virtual_memory()

    # Atributos más importantes del objeto ram:
    #   ram.total      → total de RAM instalada en el sistema (en bytes)
    #   ram.available  → memoria disponible REAL para nuevos procesos (en bytes)
    #                   OJO: no es lo mismo que "libre". La memoria "libre" no
    #                   incluye la caché, pero la "disponible" sí la considera
    #                   reutilizable. "available" es el dato más útil en la práctica.
    #   ram.used       → memoria actualmente en uso por procesos (en bytes)
    #   ram.free       → memoria completamente libre, sin ningún uso (en bytes)
    #   ram.percent    → porcentaje de uso (0.0 a 100.0)
    #   ram.cached     → memoria usada como caché del sistema (solo Linux/Mac)
    #   ram.buffers    → memoria usada como buffers del kernel (solo Linux)
    #   ram.shared     → memoria compartida entre procesos (solo Linux/Mac)

    # --- 3. Datos de la memoria Swap ------------------------------------------
    # swap_memory() devuelve la información del espacio de intercambio.
    # En Windows se llama "archivo de paginación". En Linux, "partición swap".
    swap = psutil.swap_memory()

    # Atributos del objeto swap:
    #   swap.total     → tamaño total del espacio swap configurado
    #   swap.used      → cuánto swap está siendo utilizado ahora mismo
    #   swap.free      → cuánto swap queda libre
    #   swap.percent   → porcentaje de uso del swap
    #   swap.sin       → datos leídos DESDE el disco hacia RAM (swap in)  — en bytes
    #   swap.sout      → datos escritos DESDE la RAM hacia el disco (swap out) — en bytes
    #   Nota: sin/sout son acumulados desde el arranque del sistema.

    # =========================================================================
    #  Construcción de la pantalla
    # =========================================================================

    limpiar_pantalla()

    # Cabecera
    print("=" * 62)
    print("       💾  MONITOR DE MEMORIA — Tiempo Real")
    print(f"       📅 {ahora}")
    print("=" * 62)

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Memoria RAM
    # -------------------------------------------------------------------------
    print(f"\n📊 USO DE MEMORIA RAM")
    print(f"   {color_por_uso(ram.percent, UMBRAL_ALERTA_RAM)}")

    # Alerta si superamos el umbral
    if ram.percent >= UMBRAL_ALERTA_RAM:
        print(f"\n   ⚠️  \033[91mALERTA: RAM al {ram.percent}% — riesgo de lentitud o cuelgues\033[0m")

    # Desglose detallado de la RAM
    # Mostramos los valores más relevantes alineados en columnas
    print(f"\n📋 DESGLOSE DE RAM")
    print(linea_detalle("Total",      ram.total))
    print(linea_detalle("Usada",      ram.used))
    print(linea_detalle("Disponible", ram.available))

    # ── Nota importante sobre "disponible" vs "libre" ──────────────────────
    # "Libre"      (ram.free)      → RAM vacía, sin ningún uso
    # "Disponible" (ram.available) → RAM libre + caché recuperable
    # El sistema operativo es inteligente: cuando no tienes nada en caché,
    # la reutiliza automáticamente. Por eso "disponible" es el dato real.
    # ────────────────────────────────────────────────────────────────────────
    print(linea_detalle("Libre",      ram.free))

    # Caché y buffers solo existen en Linux/Mac
    # hasattr() comprueba si el objeto tiene ese atributo antes de usarlo,
    # evitando errores en Windows donde no existen.
    if hasattr(ram, 'cached'):
        print(linea_detalle("Caché",  ram.cached))
    if hasattr(ram, 'buffers'):
        print(linea_detalle("Buffers", ram.buffers))
    if hasattr(ram, 'shared'):
        print(linea_detalle("Compartida", ram.shared))

    # ── Mini resumen visual de la distribución de RAM ──────────────────────
    # Calculamos el % de cada componente sobre el total para pintarlo
    print(f"\n🗂️  DISTRIBUCIÓN VISUAL DE LA RAM")

    pct_usada     = (ram.used      / ram.total) * 100
    pct_libre     = (ram.free      / ram.total) * 100
    pct_disponible= (ram.available / ram.total) * 100

    print(f"   Usada      : {barra_progreso(pct_usada,     20)}")
    print(f"   Libre      : {barra_progreso(pct_libre,     20)}")
    print(f"   Disponible : {barra_progreso(pct_disponible,20)}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Memoria Swap
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n💿 USO DE MEMORIA SWAP")

    # Es posible que el sistema no tenga Swap configurado (swap.total == 0).
    # En ese caso no tiene sentido mostrar porcentajes ni barras.
    if swap.total == 0:
        print("   ℹ️  No hay memoria Swap configurada en este sistema.")
        print("      (Es normal en algunos sistemas o máquinas virtuales)")
    else:
        print(f"   {color_por_uso(swap.percent, UMBRAL_ALERTA_SWAP)}")

        # Alerta de Swap
        if swap.percent >= UMBRAL_ALERTA_SWAP:
            print(f"\n   ⚠️  \033[93mATENCIÓN: Swap al {swap.percent}% — la RAM está bajo presión\033[0m")
            print(    "      El sistema está usando el disco como memoria extra.")
            print(    "      Esto es significativamente más lento que la RAM real.")

        # Desglose del Swap
        print(f"\n📋 DESGLOSE DE SWAP")
        print(linea_detalle("Total", swap.total))
        print(linea_detalle("Usada", swap.used))
        print(linea_detalle("Libre", swap.free))

        # Actividad de Swap: cuántos datos se han movido entre RAM y disco
        # Un valor alto de sout (swap out) significa que el sistema ha tenido
        # que "desalojar" datos de la RAM hacia el disco para hacer sitio.
        print(f"\n🔄 ACTIVIDAD DE SWAP (desde el arranque)")
        print(f"   Entrada (disco → RAM) : {bytes_a_legible(swap.sin):>12}")
        print(f"   Salida  (RAM → disco) : {bytes_a_legible(swap.sout):>12}")

        # Si swap.sout es muy alto, añadimos un consejo contextual
        if swap.sout > (1024 ** 3):   # Más de 1 GB de swap out
            print(f"   💡 \033[93mSe han movido más de 1 GB al disco. Considera ampliar la RAM.\033[0m")

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Resumen global de salud de la memoria
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n🩺 DIAGNÓSTICO RÁPIDO")

    # Evaluamos el estado general con una lógica simple de semáforo
    if ram.percent < 50 and (swap.total == 0 or swap.percent < 20):
        estado = "\033[92m✅ Memoria en buen estado\033[0m"
    elif ram.percent < UMBRAL_ALERTA_RAM and (swap.total == 0 or swap.percent < UMBRAL_ALERTA_SWAP):
        estado = "\033[93m⚠️  Memoria bajo vigilancia\033[0m"
    else:
        estado = "\033[91m🚨 Memoria bajo alta presión\033[0m"

    print(f"   {estado}")

    # Pie del monitor
    print("\n" + "=" * 62)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 62)


# --- Bucle principal de monitorización ----------------------------------------
# Igual que en cpu_monitor.py: un bucle while True que llama a mostrar_memoria()
# cada INTERVALO_SEGUNDOS, hasta que el usuario pulsa Ctrl+C.

def iniciar_monitor():
    """Inicia el bucle de monitorización continua de memoria."""
    print("Iniciando monitor de memoria... (Ctrl+C para detener)")
    time.sleep(1)

    while True:
        try:
            mostrar_memoria()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
# Solo arranca si ejecutamos este archivo directamente.
# Si lo importa el menú principal, no se lanzará automáticamente.

if __name__ == "__main__":
    iniciar_monitor()
