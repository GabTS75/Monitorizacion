# =============================================================================
#  menu.py — Panel de Control Principal
#  Descripción : Menú interactivo que permite lanzar cualquiera de los
#                scripts de monitorización desde un único punto de entrada.
#                Actúa como "panel de control" de toda la colección.
#  Requisitos  : pip install psutil
#                Todos los scripts de la colección en la misma carpeta.
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Cómo funciona este script?
#
#  Hasta ahora cada script era autónomo: lo ejecutabas directamente y hacía
#  su trabajo. Este menú los une a todos usando un concepto fundamental
#  de Python: la IMPORTACIÓN DE MÓDULOS.
#
#  Recuerda la condición que pusimos al final de cada script:
#      if __name__ == "__main__":
#          iniciar_monitor()
#
#  Esa condición hace exactamente esto:
#  - Si ejecutas el script DIRECTAMENTE → arranca el monitor
#  - Si lo IMPORTAS desde otro script   → NO arranca solo
#
#  Así podemos importar cada monitor aquí y llamar a su función
#  iniciar_monitor() solo cuando el usuario lo pida desde el menú.
#
#  Analogía: imagina una caja de herramientas. Cada script es una
#  herramienta (destornillador, martillo, llave inglesa...). El menú
#  es la caja que las organiza y te deja elegir cuál usar sin tener
#  que buscarla entre todas. Las herramientas no "se activan solas"
#  por estar dentro de la caja: tú decides cuándo sacar cada una.
# -----------------------------------------------------------------------------

import os               # Para limpiar la pantalla y detectar el SO
import sys              # Para salir del programa limpiamente con sys.exit()
import time             # Para pequeñas pausas visuales
import platform         # Para mostrar info del sistema en el menú
import datetime         # Para mostrar la fecha y hora en el menú

# -----------------------------------------------------------------------------
#  IMPORTACIÓN DE LOS SCRIPTS DE MONITORIZACIÓN
#
#  Aquí importamos cada script como si fuera una librería.
#  Usamos bloques try/except individuales para que si falta uno de los
#  archivos, el menú siga funcionando con los que sí están disponibles.
#  No queremos que un solo archivo ausente rompa todo el menú.
# -----------------------------------------------------------------------------

# Diccionario que llevará la cuenta de qué módulos se cargaron correctamente
modulos_disponibles = {}

try:
    import cpu_monitor
    modulos_disponibles['cpu'] = True
except ImportError:
    modulos_disponibles['cpu'] = False

try:
    import memoria_monitor
    modulos_disponibles['memoria'] = True
except ImportError:
    modulos_disponibles['memoria'] = False

try:
    import almacenamiento_monitor
    modulos_disponibles['almacenamiento'] = True
except ImportError:
    modulos_disponibles['almacenamiento'] = False

try:
    import temperatura_monitor
    modulos_disponibles['temperatura'] = True
except ImportError:
    modulos_disponibles['temperatura'] = False

try:
    import gpu_monitor
    modulos_disponibles['gpu'] = True
except ImportError:
    modulos_disponibles['gpu'] = False

try:
    import red_monitor
    modulos_disponibles['red'] = True
except ImportError:
    modulos_disponibles['red'] = False

try:
    import bateria_monitor
    modulos_disponibles['bateria'] = True
except ImportError:
    modulos_disponibles['bateria'] = False

try:
    import ventiladores_monitor
    modulos_disponibles['ventiladores'] = True
except ImportError:
    modulos_disponibles['ventiladores'] = False

try:
    import procesos_monitor
    modulos_disponibles['procesos'] = True
except ImportError:
    modulos_disponibles['procesos'] = False

try:
    import sistema_info
    modulos_disponibles['sistema'] = True
except ImportError:
    modulos_disponibles['sistema'] = False


# =============================================================================
#  DEFINICIÓN DE OPCIONES DEL MENÚ
# =============================================================================
# Definimos las opciones como una lista de diccionarios.
# Cada opción tiene todos los datos necesarios para pintarla y ejecutarla.
# Esto es mucho mejor que tener un if/elif gigante más adelante:
# si queremos añadir una opción nueva, solo añadimos un elemento a esta lista.

OPCIONES = [
    {
        'numero'     : '1',
        'icono'      : '🧠',
        'titulo'     : 'Monitor de CPU',
        'descripcion': 'Uso por núcleo, frecuencia, carga media',
        'clave'      : 'cpu',
        'funcion'    : lambda: cpu_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',    # monitor = bucle continuo
    },
    {
        'numero'     : '2',
        'icono'      : '💾',
        'titulo'     : 'Monitor de Memoria RAM',
        'descripcion': 'RAM y Swap: uso, disponible, distribución',
        'clave'      : 'memoria',
        'funcion'    : lambda: memoria_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '3',
        'icono'      : '💽',
        'titulo'     : 'Monitor de Almacenamiento',
        'descripcion': 'Espacio por partición, velocidad I/O en tiempo real',
        'clave'      : 'almacenamiento',
        'funcion'    : lambda: almacenamiento_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '4',
        'icono'      : '🌡️ ',
        'titulo'     : 'Monitor de Temperaturas',
        'descripcion': 'Sensores térmicos: CPU, disco, placa base (Linux/Mac)',
        'clave'      : 'temperatura',
        'funcion'    : lambda: temperatura_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '5',
        'icono'      : '🎮',
        'titulo'     : 'Monitor de GPU',
        'descripcion': 'Uso, VRAM, temperatura GPU (NVIDIA/AMD)',
        'clave'      : 'gpu',
        'funcion'    : lambda: gpu_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '6',
        'icono'      : '🌐',
        'titulo'     : 'Monitor de Red',
        'descripcion': 'Interfaces, velocidad subida/bajada, conexiones',
        'clave'      : 'red',
        'funcion'    : lambda: red_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '7',
        'icono'      : '🔋',
        'titulo'     : 'Monitor de Batería',
        'descripcion': 'Nivel de carga, estado, autonomía estimada',
        'clave'      : 'bateria',
        'funcion'    : lambda: bateria_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '8',
        'icono'      : '💨',
        'titulo'     : 'Monitor de Ventiladores',
        'descripcion': 'RPM de todos los ventiladores detectados (Linux/Mac)',
        'clave'      : 'ventiladores',
        'funcion'    : lambda: ventiladores_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '9',
        'icono'      : '⚙️ ',
        'titulo'     : 'Monitor de Procesos',
        'descripcion': 'Top procesos por CPU y RAM, estados, zombies',
        'clave'      : 'procesos',
        'funcion'    : lambda: procesos_monitor.iniciar_monitor(),
        'tipo'       : 'monitor',
    },
    {
        'numero'     : '10',
        'icono'      : '📋',
        'titulo'     : 'Información del Sistema',
        'descripcion': 'Informe estático: SO, CPU, RAM, red, usuarios',
        'clave'      : 'sistema',
        'funcion'    : lambda: sistema_info.mostrar_sistema_info(),
        'tipo'       : 'informe',   # informe = se ejecuta una vez y vuelve
    },
]

# Opciones especiales que siempre están disponibles
OPCIONES_ESPECIALES = [
    {'numero': 'A', 'icono': '🔍', 'titulo': 'Estado de módulos',
     'descripcion': 'Ver qué scripts están disponibles'},
    {'numero': 'S', 'icono': '🚪', 'titulo': 'Salir',
     'descripcion': 'Cerrar el panel de control'},
]


# =============================================================================
#  FUNCIONES DE INTERFAZ DEL MENÚ
# =============================================================================

def limpiar_pantalla():
    """Limpia la terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def indicador_disponible(clave):
    """
    Devuelve un indicador visual de si el módulo está disponible.
    ✅ = el archivo .py está presente e importado correctamente
    ❌ = el archivo .py no se encontró en la carpeta
    """
    if modulos_disponibles.get(clave, False):
        return "\033[92m✅\033[0m"
    else:
        return "\033[91m❌\033[0m"


def mostrar_banner():
    """
    Muestra el banner principal del menú con información del sistema.
    Un banner es la "portada" del programa: la primera cosa que ves.
    """
    ahora    = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    sistema  = platform.system()
    hostname = ""
    try:
        import socket
        hostname = socket.gethostname()
    except Exception:
        hostname = "N/A"

    # Intentamos leer el uso actual de CPU y RAM para el banner
    # Si falla (psutil no instalado), simplemente no lo mostramos
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.3)
        ram_pct = psutil.virtual_memory().percent
        estado_hw = f"CPU: {cpu_pct:.0f}%  |  RAM: {ram_pct:.0f}%"
    except Exception:
        estado_hw = ""

    print("╔" + "═" * 63 + "╗")
    print("║" + " " * 63 + "║")
    print("║" + "   🖥️   PANEL DE CONTROL — MONITOR DE HARDWARE".ljust(63) + "║")
    print("║" + " " * 63 + "║")
    print("║" + f"   📅  {ahora}".ljust(62) + "║")
    print("║" + f"   🏠  Equipo : {hostname}  |  {sistema}".ljust(62) + "║")
    if estado_hw:
        print("║" + f"   📊  Estado : {estado_hw}".ljust(62) + "║")
    print("║" + " " * 63 + "║")
    print("╚" + "═" * 63 + "╝")


def mostrar_menu():
    """
    Construye y muestra el menú completo con todas las opciones.
    Las opciones no disponibles se muestran atenuadas para que el
    usuario sepa que faltan archivos, no que el menú está roto.
    """
    limpiar_pantalla()
    mostrar_banner()

    print()
    print("  Elige una opción escribiendo su número y pulsando Enter:")
    print()

    # --- Opciones de monitorización ------------------------------------------
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │               📡  MONITORES EN TIEMPO REAL                  │")
    print("  ├─────────────────────────────────────────────────────────────┤")

    for opcion in OPCIONES:
        if opcion['tipo'] == 'monitor':
            disponible = indicador_disponible(opcion['clave'])

            # Si el módulo no está disponible, atenuamos el texto
            if modulos_disponibles.get(opcion['clave'], False):
                titulo_str = f"\033[1m{opcion['titulo']}\033[0m"
                desc_str   = f"\033[2m{opcion['descripcion']}\033[0m"
            else:
                titulo_str = f"\033[2m{opcion['titulo']}\033[0m"
                desc_str   = f"\033[2m{opcion['descripcion']}\033[0m"

            print(f"  │  [{opcion['numero']:>2}] {opcion['icono']}  "
                  f"{titulo_str:<30} {disponible}  │")
            print(f"  │       \033[2m{opcion['descripcion']:<52}\033[0m  │")
            print("  │                                                             │")

    # --- Opción de informe ---------------------------------------------------
    print("  ├─────────────────────────────────────────────────────────────┤")
    print("  │                  📋  INFORMES ESTÁTICOS                     │")
    print("  ├─────────────────────────────────────────────────────────────┤")

    for opcion in OPCIONES:
        if opcion['tipo'] == 'informe':
            disponible = indicador_disponible(opcion['clave'])
            if modulos_disponibles.get(opcion['clave'], False):
                titulo_str = f"\033[1m{opcion['titulo']}\033[0m"
            else:
                titulo_str = f"\033[2m{opcion['titulo']}\033[0m"

            print(f"  │  [{opcion['numero']:>2}] {opcion['icono']}  "
                  f"{titulo_str:<30} {disponible}  │")
            print(f"  │       \033[2m{opcion['descripcion']:<52}\033[0m  │")
            print("  │                                                             │")

    # --- Opciones especiales -------------------------------------------------
    print("  ├─────────────────────────────────────────────────────────────┤")
    for esp in OPCIONES_ESPECIALES:
        print(f"  │  [ {esp['numero']}] {esp['icono']}  "
              f"\033[1m{esp['titulo']:<30}\033[0m         │")
        print(f"  │       \033[2m{esp['descripcion']:<52}\033[0m  │")

    print("  └─────────────────────────────────────────────────────────────┘")
    print()


def mostrar_estado_modulos():
    """
    Muestra una pantalla detallada con el estado de cada módulo.
    Útil para diagnosticar por qué alguna opción no está disponible.
    """
    limpiar_pantalla()
    print("=" * 62)
    print("  🔍  ESTADO DE MÓDULOS")
    print("=" * 62)
    print()
    print("  Este menú necesita los siguientes archivos en la misma")
    print("  carpeta que menu.py:\n")

    archivos = {
        'cpu'           : 'cpu_monitor.py',
        'memoria'       : 'memoria_monitor.py',
        'almacenamiento': 'almacenamiento_monitor.py',
        'temperatura'   : 'temperatura_monitor.py',
        'gpu'           : 'gpu_monitor.py',
        'red'           : 'red_monitor.py',
        'bateria'       : 'bateria_monitor.py',
        'ventiladores'  : 'ventiladores_monitor.py',
        'procesos'      : 'procesos_monitor.py',
        'sistema'       : 'sistema_info.py',
    }

    total     = len(archivos)
    cargados  = sum(1 for v in modulos_disponibles.values() if v)
    faltantes = total - cargados

    for clave, archivo in archivos.items():
        estado = modulos_disponibles.get(clave, False)
        if estado:
            print(f"   \033[92m✅  {archivo}\033[0m")
        else:
            print(f"   \033[91m❌  {archivo}  ← No encontrado\033[0m")

    print()
    print(f"  Cargados : {cargados}/{total}")

    if faltantes > 0:
        print(f"\n  ⚠️  Faltan {faltantes} archivo(s).")
        print("  Asegúrate de que todos los .py estén en la misma carpeta.")
        print("  Estructura esperada:")
        print()
        print("   📁 monitoreo/")
        for archivo in archivos.values():
            print(f"      ├── {archivo}")
        print("      └── menu.py  ← (este archivo)")
    else:
        print("\n  \033[92m✅ Todos los módulos están disponibles.\033[0m")

    print()
    print("=" * 62)
    input("  Pulsa Enter para volver al menú...")


def pantalla_lanzando(opcion):
    """
    Muestra una pantalla de transición antes de lanzar un monitor.
    Da un momento al usuario para prepararse y saber qué va a ver.
    """
    limpiar_pantalla()
    print("=" * 62)
    print(f"  {opcion['icono']}  Lanzando: {opcion['titulo']}")
    print("=" * 62)
    print()

    if opcion['tipo'] == 'monitor':
        print("  ℹ️  Este es un monitor en TIEMPO REAL.")
        print("     La pantalla se actualizará automáticamente.")
        print()
        print("  🛑  Para volver al menú: pulsa  Ctrl + C")
    else:
        print("  ℹ️  Este es un informe ESTÁTICO.")
        print("     Se ejecutará una vez y volverás al menú.")

    print()
    print("  Iniciando en 2 segundos...")
    time.sleep(2)


def ejecutar_opcion(numero):
    """
    Localiza la opción elegida por el usuario y la ejecuta.
    Gestiona los casos de módulo no disponible y errores inesperados.
    - numero : string con el número/letra que escribió el usuario
    """
    # Buscamos la opción en la lista de opciones normales
    opcion_elegida = None
    for opcion in OPCIONES:
        if opcion['numero'] == numero:
            opcion_elegida = opcion
            break

    # Si no la encontramos en las normales, comprobamos las especiales
    if not opcion_elegida:
        if numero.upper() == 'A':
            mostrar_estado_modulos()
            return True   # True = seguir mostrando el menú
        elif numero.upper() == 'S':
            return False  # False = salir del menú
        else:
            # Número no reconocido — avisamos y volvemos al menú
            print()
            print("  ⚠️  Opción no reconocida. Escribe un número del 1 al 10,")
            print("     'A' para ver el estado de módulos, o 'S' para salir.")
            time.sleep(2)
            return True

    # Verificamos que el módulo está disponible antes de intentar lanzarlo
    if not modulos_disponibles.get(opcion_elegida['clave'], False):
        print()
        print(f"  ❌ El módulo '{opcion_elegida['titulo']}' no está disponible.")
        print(f"     Asegúrate de que el archivo correspondiente")
        print(f"     está en la misma carpeta que menu.py.")
        print()
        print("  Pulsa 'A' en el menú para ver qué archivos faltan.")
        time.sleep(3)
        return True

    # Todo bien — mostramos la transición y lanzamos el monitor
    pantalla_lanzando(opcion_elegida)

    try:
        # Aquí ocurre la magia: llamamos a la función del módulo importado
        # La función ya sabe si es un monitor (while True) o un informe (una vez)
        opcion_elegida['funcion']()

    except KeyboardInterrupt:
        # El usuario pulsó Ctrl+C para salir del monitor
        # Lo capturamos aquí como segunda red de seguridad
        pass

    except Exception as e:
        # Si algo falla dentro del monitor, lo mostramos de forma amigable
        # en lugar de un traceback de Python que puede asustar a los estudiantes
        print(f"\n\n  ⚠️  El monitor se cerró con un error inesperado:")
        print(f"     {type(e).__name__}: {e}")
        print()
        print("  Esto puede ocurrir si falta alguna dependencia o")
        print("  el hardware no es accesible en este entorno.")

    # Después de que la opción termine (o sea interrumpida),
    # el comportamiento de retorno depende del tipo de opción:
    #
    # - Monitor  : termina porque el usuario pulsó Ctrl+C, así que
    #              un pequeño sleep es suficiente antes de volver.
    #
    # - Informe  : termina solo al acabar de imprimir. Sin pausa,
    #              el menú volvería antes de que el usuario pueda
    #              leer el informe. Usamos input() para que el
    #              usuario decida cuándo está listo para continuar.
    print()
    if opcion_elegida['tipo'] == 'informe':
        input("  📖  Pulsa Enter cuando hayas terminado de leer...")
    else:
        print("  ↩️  Volviendo al menú principal...")
        time.sleep(1.5)
    return True   # Volvemos al menú

def despedida():
    """Muestra un mensaje de cierre al salir del programa."""
    limpiar_pantalla()
    print("╔" + "═" * 45 + "╗")
    print("║" + " " * 45 + "║")
    print("║" + " 👋  ¡Hasta luego!".center(44) + "║")
    print("║" + " " * 45 + "║")
    print("║" + "   Gracias por usar el Monitor de Hardware.".ljust(45) + "║")
    print("║" + " " * 45 + "║")
    print("╚" + "═" * 45 + "╝")
    print()


# =============================================================================
#  BUCLE PRINCIPAL DEL MENÚ
# =============================================================================
# El menú también tiene un bucle, pero es diferente al while True de los
# monitores. Aquí el bucle espera la entrada del usuario, ejecuta lo
# que pida, y vuelve a mostrar el menú. Se detiene cuando el usuario
# elige salir (opción S) o pulsa Ctrl+C en el propio menú.

def iniciar_menu():
    """Inicia el bucle principal del panel de control."""

    continuar = True   # Variable que controla si seguimos mostrando el menú

    while continuar:
        try:
            # Mostramos el menú y pedimos una opción
            mostrar_menu()
            eleccion = input("  Tu elección → ").strip()

            # Si el usuario pulsa Enter sin escribir nada, volvemos a mostrar
            if not eleccion:
                continue

            # Ejecutamos la opción y guardamos si debemos continuar
            continuar = ejecutar_opcion(eleccion)

        except KeyboardInterrupt:
            # Ctrl+C en el propio menú (no dentro de un monitor)
            # Lo tratamos como "quiero salir"
            print()
            continuar = False

    # Cuando salimos del bucle, mostramos la despedida
    despedida()


# --- Verificación de dependencias antes de arrancar --------------------------
def verificar_psutil():
    """
    Comprueba que psutil está instalado antes de arrancar el menú.
    Si no lo está, da instrucciones claras en lugar de un ImportError.
    psutil es la única dependencia externa de toda la colección.
    """
    try:
        import psutil
        return True
    except ImportError:
        print()
        print("  ❌ psutil no está instalado.")
        print()
        print("  psutil es la librería que permite leer el hardware.")
        print("  Sin ella, ninguno de los monitores puede funcionar.")
        print()
        print("  Instálala con:")
        print()
        print("     pip install psutil")
        print()
        print("  O si usas Python 3 específicamente:")
        print()
        print("     pip3 install psutil")
        print()
        return False


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    # Antes de mostrar el menú, verificamos que psutil está disponible
    if verificar_psutil():
        iniciar_menu()
    else:
        sys.exit(1)   # Salimos con código de error 1 (convención: 0=OK, >0=error)
