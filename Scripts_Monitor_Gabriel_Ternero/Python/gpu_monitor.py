# =============================================================================
#  gpu_monitor.py — Monitor de GPU (Tarjeta Gráfica)
#  Descripción : Monitoriza en tiempo real el uso, memoria, temperatura
#                y rendimiento de la tarjeta gráfica del sistema.
#  Requisitos  : Ver sección de compatibilidad más abajo.
#
#  ⚠️  IMPORTANTE — Compatibilidad y herramientas necesarias:
#
#  A diferencia de CPU, RAM o red, psutil NO puede leer datos de la GPU.
#  Cada fabricante expone sus datos de forma diferente:
#
#  🟢 NVIDIA → nvidia-smi (incluido con los drivers oficiales de NVIDIA)
#              Disponible en Windows y Linux automáticamente si tienes
#              drivers NVIDIA instalados. Es la opción más completa.
#              Verificar: nvidia-smi --version
#
#  🔴 AMD    → No tiene herramienta universal en línea de comandos.
#              En Linux: rocm-smi (si tienes ROCm instalado)
#                        o lectura directa desde /sys/class/drm/
#              En Windows: no hay CLI oficial gratuita equivalente.
#
#  🔵 Intel  → Gráficas integradas Intel. Datos muy limitados.
#              En Linux: intel_gpu_top (paquete intel-gpu-tools)
#              En Windows: no hay CLI oficial.
#
#  🖥️  Sin GPU dedicada / MV → El script lo detecta y lo informa claramente.
#
#  Este script intenta detectar automáticamente qué GPU tienes y qué
#  herramienta está disponible, mostrando los datos que pueda obtener
#  y explicando qué falta si no puede mostrar algo.
#
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Por qué la GPU es tan especial?
#
#  La GPU (Graphics Processing Unit) es un procesador especializado,
#  diseñado para hacer muchos cálculos sencillos en paralelo.
#  Mientras la CPU es como un equipo de 8 expertos muy capaces,
#  la GPU es como un estadio con 10.000 trabajadores haciendo tareas simples.
#
#  Hoy en día la GPU no solo dibuja gráficos. También se usa para:
#  - Inteligencia Artificial y Machine Learning
#  - Minería de criptomonedas
#  - Renderizado de vídeo
#  - Simulaciones científicas
#
#  Por eso monitorizar la GPU es cada vez más importante, no solo para
#  jugadores sino para cualquier entorno técnico o profesional.
#
#  Datos clave que medimos:
#   Uso de GPU (%)        → qué porcentaje de los "núcleos" está trabajando
#   VRAM (memoria GPU)    → memoria propia de la tarjeta (como la RAM, pero de GPU)
#   Temperatura           → fundamental, las GPUs pueden superar los 90°C
#   Ventiladores (RPM)    → a más temperatura, más giran
#   Consumo (Watts)       → cuánta energía está usando la GPU
#   Procesos usando GPU   → qué aplicaciones están usando la tarjeta
# -----------------------------------------------------------------------------

import subprocess   # Para ejecutar comandos externos como nvidia-smi
import time         # Para pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual
import platform     # Para detectar el sistema operativo
import shutil       # Para comprobar si un comando existe en el sistema

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS  = 3     # Las GPUs cambian rápido, pero 3s es suficiente
UMBRAL_USO_GPU      = 90    # % de uso a partir del cual alertamos
UMBRAL_TEMP_GPU     = 80    # °C a partir del cual la temperatura es preocupante
UMBRAL_TEMP_CRITICA = 90    # °C a partir del cual es peligroso


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
def barra_progreso(porcentaje, longitud=20):
    """Genera una barra de progreso visual."""
    rellenos = int((porcentaje / 100) * longitud)
    barra    = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}] {porcentaje:5.1f}%"


# --- Función auxiliar: colorear barra según nivel ----------------------------
def color_por_nivel(porcentaje, umbral_warn=70, umbral_crit=90):
    """Devuelve la barra coloreada según el nivel de uso."""
    texto = barra_progreso(porcentaje)
    if porcentaje < umbral_warn:
        return f"\033[92m{texto}\033[0m"    # Verde
    elif porcentaje < umbral_crit:
        return f"\033[93m{texto}\033[0m"    # Amarillo
    else:
        return f"\033[91m{texto}\033[0m"    # Rojo


# --- Función auxiliar: colorear temperatura ----------------------------------
def color_temperatura(temp):
    """Devuelve la temperatura coloreada según umbrales de GPU."""
    barra = barra_progreso(min((temp / 110) * 100, 100))  # referencia 110°C
    if temp < UMBRAL_TEMP_GPU:
        return f"\033[92m{temp:.1f} °C  {barra}\033[0m"
    elif temp < UMBRAL_TEMP_CRITICA:
        return f"\033[93m{temp:.1f} °C  {barra}\033[0m"
    else:
        return f"\033[91m{temp:.1f} °C  {barra}\033[0m"


# =============================================================================
#  BLOQUE NVIDIA — Lectura via nvidia-smi
# =============================================================================
# nvidia-smi es la herramienta oficial de NVIDIA para consultar y controlar
# GPUs. Viene incluida con los drivers de NVIDIA y funciona tanto en
# Windows como en Linux. La llamamos como si fuera un comando de terminal
# y parseamos su salida.

def nvidia_disponible():
    """
    Comprueba si nvidia-smi está instalado y accesible en el sistema.
    shutil.which() busca el comando en el PATH del sistema, igual que
    cuando escribes un comando en la terminal. Devuelve la ruta si existe
    o None si no se encuentra.
    """
    return shutil.which("nvidia-smi") is not None


def obtener_datos_nvidia():
    """
    Ejecuta nvidia-smi con formato CSV para obtener datos de todas las GPUs.
    Devuelve una lista de diccionarios, uno por GPU detectada.

    nvidia-smi --query-gpu permite especificar exactamente qué datos queremos.
    --format=csv,noheader,nounits devuelve los valores sin cabecera ni unidades,
    lo que hace el parseo muy sencillo.
    """

    # Lista de campos que queremos consultar a nvidia-smi
    # Cada campo tiene un nombre oficial que nvidia-smi reconoce.
    campos = [
        "index",                    # Índice de la GPU (0, 1, 2...)
        "name",                     # Nombre del modelo (ej: NVIDIA GeForce RTX 3080)
        "driver_version",           # Versión del driver instalado
        "temperature.gpu",          # Temperatura del núcleo en °C
        "fan.speed",                # Velocidad del ventilador en %
        "utilization.gpu",          # Uso del núcleo gráfico en %
        "utilization.memory",       # Uso de la VRAM en %
        "memory.total",             # VRAM total en MiB
        "memory.used",              # VRAM usada en MiB
        "memory.free",              # VRAM libre en MiB
        "power.draw",               # Consumo actual en Watts
        "power.limit",              # Límite de potencia configurado en Watts
        "clocks.current.graphics",  # Frecuencia actual del núcleo gráfico en MHz
        "clocks.current.memory",    # Frecuencia actual de la VRAM en MHz
        "pcie.link.width.current",  # Ancho del bus PCIe actual (x4, x8, x16)
    ]

    # Construimos el comando completo como lista de argumentos
    # Es más seguro que pasarlo como string (evita problemas con espacios)
    comando = [
        "nvidia-smi",
        f"--query-gpu={','.join(campos)}",
        "--format=csv,noheader,nounits"
    ]

    try:
        # subprocess.run() ejecuta el comando y captura su salida
        # capture_output=True → captura stdout y stderr
        # text=True           → devuelve strings en lugar de bytes
        # timeout=5           → si tarda más de 5 segundos, lanza TimeoutExpired
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Si nvidia-smi devuelve un código de error, retornamos lista vacía
        if resultado.returncode != 0:
            return []

        gpus = []

        # Cada línea de la salida corresponde a una GPU
        for linea in resultado.stdout.strip().split('\n'):
            if not linea.strip():
                continue

            # Separamos los valores por coma y los limpiamos de espacios
            valores = [v.strip() for v in linea.split(',')]

            # Si no tenemos todos los campos esperados, saltamos esta línea
            if len(valores) < len(campos):
                continue

            # Construimos un diccionario campo → valor para acceder por nombre
            datos = dict(zip(campos, valores))

            # Convertimos los valores numéricos a float donde corresponde.
            # Usamos una función auxiliar que devuelve None si el valor
            # es "[N/A]" (nvidia-smi usa esto cuando un dato no está disponible)
            def to_float(clave):
                val = datos.get(clave, "N/A").replace('[N/A]', '').strip()
                try:
                    return float(val)
                except ValueError:
                    return None

            def to_int(clave):
                val = datos.get(clave, "N/A").replace('[N/A]', '').strip()
                try:
                    return int(float(val))
                except ValueError:
                    return None

            # Construimos el diccionario final con tipos correctos
            gpus.append({
                'indice'       : to_int('index'),
                'nombre'       : datos.get('name', 'GPU desconocida'),
                'driver'       : datos.get('driver_version', 'N/A'),
                'temperatura'  : to_float('temperature.gpu'),
                'ventilador'   : to_float('fan.speed'),
                'uso_gpu'      : to_float('utilization.gpu'),
                'uso_vram'     : to_float('utilization.memory'),
                'vram_total'   : to_int('memory.total'),      # en MiB
                'vram_usada'   : to_int('memory.used'),       # en MiB
                'vram_libre'   : to_int('memory.free'),       # en MiB
                'consumo_w'    : to_float('power.draw'),
                'limite_w'     : to_float('power.limit'),
                'freq_nucleo'  : to_int('clocks.current.graphics'),  # MHz
                'freq_vram'    : to_int('clocks.current.memory'),    # MHz
                'pcie_ancho'   : to_int('pcie.link.width.current'),
            })

        return gpus

    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def obtener_procesos_nvidia():
    """
    Obtiene la lista de procesos que están usando la GPU NVIDIA.
    nvidia-smi pmon (process monitor) da esta información.
    """
    try:
        resultado = subprocess.run(
            ["nvidia-smi", "pmon", "-c", "1", "-s", "um"],
            capture_output=True, text=True, timeout=5
        )
        if resultado.returncode != 0:
            return []

        procesos = []
        for linea in resultado.stdout.strip().split('\n'):
            # Las líneas que empiezan con # son cabeceras, las saltamos
            if linea.startswith('#') or not linea.strip():
                continue
            partes = linea.split()
            if len(partes) >= 5:
                procesos.append({
                    'gpu'    : partes[0],
                    'pid'    : partes[1],
                    'tipo'   : partes[2],   # C=Compute, G=Graphics, C+G=ambos
                    'mem_mb' : partes[3],
                    'nombre' : partes[4] if len(partes) > 4 else 'N/A',
                })
        return procesos

    except Exception:
        return []


# =============================================================================
#  BLOQUE AMD — Lectura via /sys/class/drm/ (Linux)
# =============================================================================
# En Linux, el kernel expone información de las GPUs AMD a través del
# sistema de archivos virtual /sys. Es menos elegante que nvidia-smi pero
# funciona sin instalar nada adicional si tienes drivers AMDGPU cargados.

def obtener_datos_amd_linux():
    """
    Intenta leer datos básicos de GPUs AMD en Linux desde /sys/class/drm/.
    Devuelve una lista de diccionarios con los datos disponibles.
    """
    import glob   # Para buscar patrones de archivos (como ls con comodines)

    gpus = []

    # /sys/class/drm/cardX/ contiene información de cada GPU
    # Buscamos todas las carpetas que coincidan con el patrón card0, card1...
    tarjetas = glob.glob('/sys/class/drm/card[0-9]')

    for tarjeta in sorted(tarjetas):
        datos = {'nombre': os.path.basename(tarjeta)}

        # --- Temperatura -----------------------------------------------------
        # En GPUs AMD con driver amdgpu, la temperatura está en:
        # /sys/class/drm/cardX/device/hwmon/hwmonY/temp1_input
        # El valor viene en milicélsius (dividimos entre 1000)
        ruta_hwmon = os.path.join(tarjeta, 'device', 'hwmon')
        try:
            hwmons = os.listdir(ruta_hwmon)
            if hwmons:
                ruta_temp = os.path.join(ruta_hwmon, hwmons[0], 'temp1_input')
                with open(ruta_temp, 'r') as f:
                    datos['temperatura'] = int(f.read().strip()) / 1000
        except Exception:
            datos['temperatura'] = None

        # --- Uso de GPU (%) --------------------------------------------------
        # Disponible en: /sys/class/drm/cardX/device/gpu_busy_percent
        ruta_uso = os.path.join(tarjeta, 'device', 'gpu_busy_percent')
        try:
            with open(ruta_uso, 'r') as f:
                datos['uso_gpu'] = float(f.read().strip())
        except Exception:
            datos['uso_gpu'] = None

        # --- Memoria VRAM ----------------------------------------------------
        # mem_info_vram_total y mem_info_vram_used (en bytes)
        for campo, archivo in [('vram_total', 'mem_info_vram_total'),
                                ('vram_usada', 'mem_info_vram_used')]:
            ruta = os.path.join(tarjeta, 'device', archivo)
            try:
                with open(ruta, 'r') as f:
                    datos[campo] = int(f.read().strip())   # bytes
            except Exception:
                datos[campo] = None

        # Solo añadimos la tarjeta si obtuvimos al menos algún dato útil
        if any(v is not None for k, v in datos.items() if k != 'nombre'):
            gpus.append(datos)

    return gpus


# =============================================================================
#  FUNCIÓN PRINCIPAL: mostrar datos de GPU
# =============================================================================

def mostrar_gpu():
    """Detecta la GPU disponible y muestra sus datos en pantalla."""

    ahora   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sistema = platform.system()

    limpiar_pantalla()

    # Cabecera
    print("=" * 65)
    print("       🎮  MONITOR DE GPU — Tiempo Real")
    print(f"       📅 {ahora}  |  Sistema: {sistema}")
    print("=" * 65)

    # =========================================================================
    #  CASO 1: GPU NVIDIA con nvidia-smi disponible (Windows o Linux)
    # =========================================================================
    if nvidia_disponible():

        gpus = obtener_datos_nvidia()

        if not gpus:
            print("\n  ⚠️  nvidia-smi está instalado pero no devolvió datos.")
            print("     Puede que la GPU no esté activa o haya un problema con el driver.")
        else:
            print(f"\n  ✅ \033[92mNVIDIA nvidia-smi detectado\033[0m  —  "
                  f"{len(gpus)} GPU(s) encontrada(s)\n")

            for gpu in gpus:
                # --- Cabecera de cada GPU ------------------------------------
                print(f"  {'─' * 61}")
                print(f"  🎮 GPU #{gpu['indice']}  —  \033[1m{gpu['nombre']}\033[0m")
                print(f"     Driver: {gpu['driver']}")
                if gpu.get('pcie_ancho'):
                    print(f"     PCIe  : x{gpu['pcie_ancho']}")
                print()

                # --- Uso del núcleo gráfico ----------------------------------
                if gpu['uso_gpu'] is not None:
                    print(f"  📊 USO DEL NÚCLEO GRÁFICO")
                    print(f"     {color_por_nivel(gpu['uso_gpu'], 70, UMBRAL_USO_GPU)}")
                    if gpu['uso_gpu'] >= UMBRAL_USO_GPU:
                        print(f"     ⚠️  \033[91mGPU al {gpu['uso_gpu']:.0f}% — carga muy elevada\033[0m")

                # --- Memoria VRAM --------------------------------------------
                if gpu['uso_vram'] is not None:
                    print(f"\n  🧠 MEMORIA VRAM")
                    print(f"     {color_por_nivel(gpu['uso_vram'], 70, 90)}")

                if gpu['vram_total'] is not None:
                    # La VRAM viene en MiB desde nvidia-smi, convertimos a bytes
                    total_b = gpu['vram_total'] * 1024 * 1024
                    usada_b = gpu['vram_usada'] * 1024 * 1024
                    libre_b = gpu['vram_libre'] * 1024 * 1024
                    print(f"     Total : {bytes_a_legible(total_b):>10}")
                    print(f"     Usada : {bytes_a_legible(usada_b):>10}")
                    print(f"     Libre : {bytes_a_legible(libre_b):>10}")

                # --- Temperatura ---------------------------------------------
                if gpu['temperatura'] is not None:
                    print(f"\n  🌡️  TEMPERATURA")
                    print(f"     {color_temperatura(gpu['temperatura'])}")
                    if gpu['temperatura'] >= UMBRAL_TEMP_CRITICA:
                        print(f"     🚨 \033[91mTEMPERATURA CRÍTICA — revisa la refrigeración\033[0m")
                    elif gpu['temperatura'] >= UMBRAL_TEMP_GPU:
                        print(f"     ⚠️  \033[93mTemperatura elevada — vigila la tendencia\033[0m")

                # --- Ventilador ----------------------------------------------
                if gpu['ventilador'] is not None:
                    print(f"\n  💨 VENTILADOR")
                    print(f"     {color_por_nivel(gpu['ventilador'], 60, 90)}")

                # --- Consumo energético --------------------------------------
                if gpu['consumo_w'] is not None:
                    print(f"\n  ⚡ CONSUMO ENERGÉTICO")
                    print(f"     Actual : {gpu['consumo_w']:>7.1f} W")
                    if gpu['limite_w'] is not None:
                        pct_consumo = (gpu['consumo_w'] / gpu['limite_w']) * 100
                        print(f"     Límite : {gpu['limite_w']:>7.1f} W")
                        print(f"     Uso    : {color_por_nivel(pct_consumo, 80, 95)}")

                # --- Frecuencias ---------------------------------------------
                if gpu['freq_nucleo'] is not None:
                    print(f"\n  🔢 FRECUENCIAS")
                    print(f"     Núcleo gráfico : {gpu['freq_nucleo']:>6} MHz")
                    if gpu['freq_vram'] is not None:
                        print(f"     Memoria VRAM   : {gpu['freq_vram']:>6} MHz")

                print()

            # --- Procesos usando la GPU ------------------------------------
            print(f"  {'─' * 61}")
            print(f"\n  🔍 PROCESOS USANDO LA GPU\n")
            procesos = obtener_procesos_nvidia()

            if not procesos:
                print("     Ningún proceso usando la GPU actualmente.")
            else:
                print(f"     {'GPU':<5} {'PID':<8} {'Tipo':<6} {'VRAM(MB)':<10} Proceso")
                print(f"     {'─'*5} {'─'*8} {'─'*6} {'─'*10} {'─'*20}")
                for p in procesos:
                    tipo_str = {'C': 'Cómputo', 'G': 'Gráfico', 'C+G': 'Ambos'}.get(p['tipo'], p['tipo'])
                    print(f"     {p['gpu']:<5} {p['pid']:<8} {tipo_str:<8} {p['mem_mb']:<10} {p['nombre']}")

    # =========================================================================
    #  CASO 2: Linux con posible GPU AMD (sin nvidia-smi)
    # =========================================================================
    elif sistema == "Linux":

        print(f"\n  ℹ️  nvidia-smi no encontrado. Intentando lectura AMD via /sys...\n")
        gpus_amd = obtener_datos_amd_linux()

        if gpus_amd:
            print(f"  🔴 GPU(s) AMD detectada(s): {len(gpus_amd)}\n")

            for gpu in gpus_amd:
                print(f"  {'─' * 61}")
                print(f"  🎮 {gpu['nombre']}\n")

                if gpu.get('uso_gpu') is not None:
                    print(f"  📊 USO DE GPU")
                    print(f"     {color_por_nivel(gpu['uso_gpu'], 70, UMBRAL_USO_GPU)}\n")

                if gpu.get('temperatura') is not None:
                    print(f"  🌡️  TEMPERATURA")
                    print(f"     {color_temperatura(gpu['temperatura'])}\n")

                if gpu.get('vram_total') is not None:
                    pct_vram = (gpu['vram_usada'] / gpu['vram_total']) * 100 if gpu['vram_total'] > 0 else 0
                    print(f"  🧠 MEMORIA VRAM")
                    print(f"     {color_por_nivel(pct_vram, 70, 90)}")
                    print(f"     Total : {bytes_a_legible(gpu['vram_total'])}")
                    print(f"     Usada : {bytes_a_legible(gpu['vram_usada'])}\n")

        else:
            # No hay nvidia-smi ni datos AMD en /sys — informamos claramente
            print("  ℹ️  No se detectó ninguna GPU con datos disponibles.\n")
            print("  Posibles situaciones:\n")
            print("  🖥️  Máquina virtual (VirtualBox, VMware, WSL...)")
            print("     Las VMs no exponen la GPU física del host.")
            print("     La GPU virtual del hipervisor no tiene sensores reales.\n")
            print("  🔴 GPU AMD sin datos en /sys/class/drm/")
            print("     Puede que el driver amdgpu no esté cargado.")
            print("     Prueba: sudo modprobe amdgpu\n")
            print("  🔵 GPU Intel integrada")
            print("     Instala: sudo apt install intel-gpu-tools")
            print("     Luego usa: sudo intel_gpu_top\n")
            print("  🟢 GPU NVIDIA sin drivers oficiales")
            print("     Instala los drivers NVIDIA y nvidia-smi estará disponible.")

    # =========================================================================
    #  CASO 3: Windows sin nvidia-smi
    # =========================================================================
    else:
        print("\n  ℹ️  No se encontró nvidia-smi en este sistema Windows.\n")
        print("  Si tienes una GPU NVIDIA:")
        print("  → Instala o reinstala los drivers oficiales desde:")
        print("    https://www.nvidia.com/drivers\n")
        print("  Si tienes una GPU AMD o Intel en Windows:")
        print("  → psutil y nvidia-smi no cubren estas GPUs.")
        print("  → Alternativas recomendadas:\n")
        print("     🔧 GPU-Z         → https://www.techpowerup.com/gpuz")
        print("        Muestra todos los datos de cualquier GPU.")
        print()
        print("     🔧 HWiNFO64      → https://www.hwinfo.com")
        print("        Cubre GPU, CPU, placa y todos los sensores.")
        print()
        print("     🔧 MSI Afterburner → https://www.msi.com/Landing/afterburner")
        print("        Ideal para NVIDIA y AMD, con overlay en juegos.")

    # Pie del monitor
    print("\n" + "=" * 65)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 65)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de la GPU."""
    print("Iniciando monitor de GPU... (Ctrl+C para detener)")
    time.sleep(1)

    while True:
        try:
            mostrar_gpu()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
