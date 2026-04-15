# =============================================================================
#  temperatura_monitor.py — Monitor de Temperaturas
#  Descripción : Monitoriza en tiempo real las temperaturas de los sensores
#                del sistema: CPU, disco, placa base y otros componentes.
#  Requisitos  : pip install psutil
#
#  ⚠️  IMPORTANTE — Compatibilidad por plataforma:
#
#  🐧 Linux   → Funciona completamente. Requiere que los sensores del kernel
#               estén activos. Si no aparecen datos, ejecuta primero:
#                   sudo apt install lm-sensors
#                   sudo sensors-detect
#                   sudo modprobe coretemp   (para CPUs Intel)
#
#  🍎 macOS   → Funciona parcialmente. Algunos sensores pueden no estar
#               disponibles sin herramientas adicionales.
#
#  🪟 Windows → psutil NO soporta lectura de temperaturas en Windows.
#               En ese caso el script lo detecta y avisa al usuario
#               sugiriendo herramientas alternativas (HWiNFO, Core Temp...).
#
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Por qué monitorizar temperaturas?
#
#  Los componentes electrónicos generan calor al funcionar. Si ese calor no
#  se disipa correctamente, el sistema activa mecanismos de protección:
#
#  1. Throttling: reduce la velocidad del componente para generar menos calor.
#     Consecuencia: el equipo se vuelve lento sin razón aparente.
#
#  2. Apagado de emergencia: si la temperatura sigue subiendo, el sistema
#     se apaga bruscamente para evitar daños físicos permanentes.
#
#  Analogía: es como el termostato de un coche. Si el motor se calienta
#  demasiado, el coche "limita" la potencia o se apaga. Igual aquí.
#
#  Rangos orientativos de temperatura (varían según fabricante):
#  ┌─────────────────┬──────────────┬──────────────┬───────────────┐
#  │ Componente      │ Normal       │ Precaución   │ Peligro       │
#  ├─────────────────┼──────────────┼──────────────┼───────────────┤
#  │ CPU (idle)      │ 30 – 50 °C   │ 50 – 70 °C   │ > 90 °C       │
#  │ CPU (carga)     │ 50 – 70 °C   │ 70 – 85 °C   │ > 95 °C       │
#  │ GPU             │ 30 – 60 °C   │ 60 – 80 °C   │ > 90 °C       │
#  │ Disco duro HDD  │ 25 – 45 °C   │ 45 – 55 °C   │ > 60 °C       │
#  │ Disco SSD/NVMe  │ 25 – 50 °C   │ 50 – 65 °C   │ > 70 °C       │
#  │ Placa base      │ 20 – 40 °C   │ 40 – 60 °C   │ > 70 °C       │
#  └─────────────────┴──────────────┴──────────────┴───────────────┘
# -----------------------------------------------------------------------------

import psutil       # Para acceder a los sensores de temperatura
import time         # Para las pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual
import platform     # Para detectar en qué sistema operativo estamos

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS  = 3     # Las temperaturas cambian más lento que la CPU,
                             # con 3 segundos es suficiente para monitorizarlas

# Umbrales de temperatura en °C (ajustables según el hardware)
# Cada componente tiene sus propios umbrales porque no todos soportan
# las mismas temperaturas de forma segura.
UMBRALES = {
    # formato: 'nombre_sensor': (umbral_advertencia, umbral_critico)
    'cpu'        : (75, 90),
    'gpu'        : (75, 88),
    'disco'      : (50, 60),
    'placa_base' : (55, 70),
    'default'    : (70, 85),   # Para sensores no identificados explícitamente
}


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: barra de temperatura visual ---------------------------
# A diferencia de las barras de uso en % que van de 0 a 100,
# aquí la barra representa grados Celsius. Usamos 120 °C como máximo
# de referencia (ningún componente debería llegar tan alto).

def barra_temperatura(temp_actual, temp_max_referencia=120, longitud=20):
    """
    Genera una barra visual proporcional a la temperatura.
    - temp_actual          : temperatura actual en °C
    - temp_max_referencia  : temperatura que representaría la barra llena
    - longitud             : ancho total de la barra en caracteres
    """
    # Calculamos qué porcentaje de la barra_max representa la temp actual
    porcentaje = min((temp_actual / temp_max_referencia) * 100, 100)
    rellenos   = int((porcentaje / 100) * longitud)
    barra      = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}]"


# --- Función auxiliar: color y símbolo según temperatura ---------------------
# Recibe la temperatura y los umbrales específicos del componente
# y devuelve la temperatura formateada con el color adecuado.

def formato_temperatura(temp, umbral_warn, umbral_crit):
    """
    Devuelve la temperatura formateada con color y símbolo:
    - 🟢 Verde   → temperatura normal
    - 🟡 Amarillo → temperatura elevada (precaución)
    - 🔴 Rojo    → temperatura crítica (peligro)
    """
    barra = barra_temperatura(temp)

    if temp < umbral_warn:
        # Verde: todo bien
        simbolo = "🟢"
        color   = "\033[92m"
    elif temp < umbral_crit:
        # Amarillo: hay que vigilarlo
        simbolo = "🟡"
        color   = "\033[93m"
    else:
        # Rojo: temperatura peligrosa
        simbolo = "🔴"
        color   = "\033[91m"

    reset = "\033[0m"
    return f"{simbolo} {color}{temp:5.1f} °C  {barra}{reset}"


# --- Función auxiliar: identificar tipo de sensor ----------------------------
# psutil devuelve los sensores con nombres técnicos que varían según el
# fabricante y el sistema operativo. Esta función intenta "traducirlos"
# a categorías comprensibles para asignar los umbrales correctos.

def identificar_sensor(nombre_sensor):
    """
    Intenta clasificar un sensor en una categoría conocida basándose
    en palabras clave en su nombre.
    Devuelve la clave de UMBRALES correspondiente.
    """
    # Convertimos a minúsculas para comparar sin importar mayúsculas
    nombre = nombre_sensor.lower()

    # CPU: nombres típicos en distintos sistemas
    if any(p in nombre for p in ['cpu', 'core', 'package', 'coretemp', 'k10temp',
                                  'zenpower', 'acpitz', 'processor']):
        return 'cpu'

    # GPU: nombres típicos de NVIDIA, AMD e Intel
    if any(p in nombre for p in ['gpu', 'nvidia', 'radeon', 'amdgpu',
                                  'nouveau', 'drm']):
        return 'gpu'

    # Disco: HDDs y SSDs/NVMe
    if any(p in nombre for p in ['disk', 'drive', 'nvme', 'ssd', 'hdd',
                                  'storage', 'ata']):
        return 'disco'

    # Placa base: chipset, VRMs, sensores de placa
    if any(p in nombre for p in ['board', 'motherboard', 'chipset', 'vrm',
                                  'nct', 'it8', 'sch', 'w83']):
        return 'placa_base'

    # Si no reconocemos el sensor, usamos umbrales por defecto
    return 'default'


# --- Función principal: obtener y mostrar temperaturas -----------------------

def mostrar_temperaturas():
    """Recopila y muestra en pantalla todos los datos de temperatura."""

    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # =========================================================================
    #  Verificación de compatibilidad con el sistema operativo
    # =========================================================================

    sistema = platform.system()

    # En Windows, psutil.sensors_temperatures() no está disponible.
    # Lo detectamos ANTES de intentar usarlo para dar un mensaje claro.
    if sistema == "Windows":
        limpiar_pantalla()
        print("=" * 65)
        print("       🌡️  MONITOR DE TEMPERATURAS")
        print(f"       📅 {ahora}")
        print("=" * 65)
        print()
        print("  ⚠️  \033[93mLectura de temperaturas no disponible en Windows\033[0m")
        print()
        print("  psutil no tiene acceso a los sensores de temperatura")
        print("  en sistemas Windows por limitaciones del sistema operativo.")
        print()
        print("  💡 Alternativas gratuitas para Windows:")
        print()
        print("     🔧 HWiNFO64   → https://www.hwinfo.com")
        print("        La más completa. Muestra todos los sensores.")
        print()
        print("     🔧 Core Temp  → https://www.alcpu.com/CoreTemp")
        print("        Especializada en temperaturas de CPU por núcleo.")
        print()
        print("     🔧 Open Hardware Monitor")
        print("        → https://openhardwaremonitor.org")
        print("        Open source, similar a HWiNFO.")
        print()
        print("     🔧 MSI Afterburner (si tienes GPU NVIDIA/AMD)")
        print("        → https://www.msi.com/Landing/afterburner")
        print()
        print("=" * 65)
        print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
        print("=" * 65)
        return   # Salimos de la función, no hay nada más que mostrar en Windows

    # =========================================================================
    #  Lectura de sensores (Linux / macOS)
    # =========================================================================

    # sensors_temperatures() devuelve un diccionario donde:
    #   - La clave es el nombre del "chip" o módulo sensor (ej: 'coretemp')
    #   - El valor es una lista de lecturas de ese chip
    # Cada lectura tiene: label, current, high, critical
    #   label    → nombre del sensor individual (ej: 'Core 0', 'Package id 0')
    #   current  → temperatura actual en °C
    #   high     → temperatura "alta" definida por el fabricante en °C (si existe)
    #   critical → temperatura crítica definida por el fabricante en °C (si existe)

    try:
        sensores = psutil.sensors_temperatures()
    except AttributeError:
        # Por si acaso el sistema tiene psutil pero sin soporte de sensores
        sensores = None

    limpiar_pantalla()

    # Cabecera
    print("=" * 65)
    print("       🌡️  MONITOR DE TEMPERATURAS — Tiempo Real")
    print(f"       📅 {ahora}  |  Sistema: {sistema}")
    print("=" * 65)

    # -------------------------------------------------------------------------
    #  Sin sensores disponibles
    # -------------------------------------------------------------------------
    if not sensores:
        print()
        print("  ℹ️  No se detectaron sensores de temperatura.")
        print()
        print("  Posibles causas:")
        print("  • Los módulos del kernel no están cargados.")
        print("    Prueba: sudo modprobe coretemp  (Intel)")
        print("            sudo modprobe k10temp   (AMD)")
        print()
        print("  • lm-sensors no está instalado o configurado.")
        print("    Prueba: sudo apt install lm-sensors")
        print("            sudo sensors-detect")
        print()
        print("  • Estás en una máquina virtual sin acceso a sensores físicos.")
        print("    (Normal en VMs: VMware, VirtualBox, WSL...)")
        print()
        print("=" * 65)
        print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
        print("=" * 65)
        return

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Sensores organizados por chip/módulo
    # -------------------------------------------------------------------------
    print(f"\n🌡️  SENSORES DETECTADOS\n")

    # Listas para el resumen final
    todas_las_temps  = []   # Guardamos (nombre, temp, tipo) para el diagnóstico
    alertas          = []   # Guardamos las temperaturas en niveles de alerta

    # Iteramos sobre cada "chip" sensor y sus lecturas
    for nombre_chip, lecturas in sensores.items():

        # Identificamos el tipo de componente para usar los umbrales correctos
        tipo      = identificar_sensor(nombre_chip)
        warn, crit = UMBRALES[tipo]

        # Cabecera del chip con un icono según su tipo
        iconos = {
            'cpu'       : '🧠',
            'gpu'       : '🎮',
            'disco'     : '💽',
            'placa_base': '🖥️',
            'default'   : '📡',
        }
        icono = iconos.get(tipo, '📡')

        print(f"  {icono}  \033[1m{nombre_chip.upper()}\033[0m")

        # Iteramos sobre cada sensor individual dentro del chip
        for lectura in lecturas:

            # Algunas lecturas pueden tener temperatura 0.0 o negativa,
            # lo que indica que el sensor no está disponible o es inválido.
            # Las filtramos para no mostrar datos sin sentido.
            if lectura.current <= 0:
                continue

            # Formateamos la temperatura con color y barra
            temp_str = formato_temperatura(lectura.current, warn, crit)

            # Mostramos la etiqueta del sensor y su temperatura actual
            # La etiqueta puede ser "Core 0", "Package id 0", "temp1", etc.
            etiqueta = lectura.label if lectura.label else "Sensor"
            print(f"     {etiqueta:<20} {temp_str}", end="")

            # Si el fabricante definió un límite "high" o "critical",
            # lo mostramos como referencia adicional
            refs = []
            if lectura.high     and lectura.high     > 0:
                refs.append(f"máx.fab: {lectura.high:.0f}°C")
            if lectura.critical and lectura.critical > 0:
                refs.append(f"crit.fab: {lectura.critical:.0f}°C")
            if refs:
                print(f"  \033[2m({', '.join(refs)})\033[0m", end="")
            print()   # Salto de línea al final de cada sensor

            # Guardamos para el resumen
            todas_las_temps.append((f"{nombre_chip}/{etiqueta}", lectura.current, tipo))

            # Registramos alertas
            if lectura.current >= crit:
                alertas.append((nombre_chip, etiqueta, lectura.current, "CRÍTICA"))
            elif lectura.current >= warn:
                alertas.append((nombre_chip, etiqueta, lectura.current, "ELEVADA"))

        print()   # Línea en blanco entre chips para separar visualmente

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Alertas activas
    # -------------------------------------------------------------------------
    if alertas:
        print(f"{'─' * 65}")
        print(f"\n🚨 ALERTAS ACTIVAS\n")
        for chip, sensor, temp, nivel in alertas:
            if nivel == "CRÍTICA":
                print(f"  \033[5m\033[91m🔴 TEMPERATURA CRÍTICA: {chip} / {sensor} → {temp:.1f} °C\033[0m")
                print(f"     Comprueba la refrigeración del equipo inmediatamente.")
            else:
                print(f"  \033[93m🟡 Temperatura elevada : {chip} / {sensor} → {temp:.1f} °C\033[0m")
                print(f"     Vigila si sigue subiendo.")
        print()

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Resumen — temperaturas más altas del sistema
    # -------------------------------------------------------------------------
    if todas_las_temps:
        print(f"{'─' * 65}")
        print(f"\n📊 RESUMEN — TOP 5 TEMPERATURAS MÁS ALTAS\n")

        # Ordenamos de mayor a menor temperatura y tomamos las 5 primeras
        top5 = sorted(todas_las_temps, key=lambda x: x[1], reverse=True)[:5]

        for i, (nombre, temp, tipo) in enumerate(top5, 1):
            warn, crit = UMBRALES[tipo]
            print(f"  {i}. {nombre:<35} {formato_temperatura(temp, warn, crit)}")

        # Temperatura media de todo el sistema
        if todas_las_temps:
            media = sum(t[1] for t in todas_las_temps) / len(todas_las_temps)
            print(f"\n  📈 Temperatura media del sistema : {media:.1f} °C")
            print(f"  🌡️  Sensores activos              : {len(todas_las_temps)}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Diagnóstico general de refrigeración
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 65}")
    print(f"\n🩺 DIAGNÓSTICO DE REFRIGERACIÓN\n")

    criticas  = sum(1 for a in alertas if a[3] == "CRÍTICA")
    elevadas  = sum(1 for a in alertas if a[3] == "ELEVADA")

    if criticas > 0:
        print("  \033[91m🚨 SISTEMA EN RIESGO TÉRMICO — Actúa de inmediato:\033[0m")
        print("     • Comprueba que los ventiladores funcionan correctamente.")
        print("     • Verifica que no haya polvo obstruyendo la refrigeración.")
        print("     • Comprueba que la pasta térmica no está seca.")
        print("     • Cierra aplicaciones que consuman muchos recursos.")
    elif elevadas > 0:
        print("  \033[93m⚠️  TEMPERATURA ELEVADA — Recomendaciones:\033[0m")
        print("     • Aumenta la ventilación del equipo o la sala.")
        print("     • Comprueba si el perfil de ventiladores está activo.")
        print("     • Vigila si la tendencia es ascendente.")
    else:
        print("  \033[92m✅ Sistema térmico en buen estado.\033[0m")
        print("     Todas las temperaturas dentro de rangos normales.")

    # Pie del monitor
    print("\n" + "=" * 65)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 65)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de temperaturas."""
    print("Iniciando monitor de temperaturas... (Ctrl+C para detener)")
    time.sleep(1)

    while True:
        try:
            mostrar_temperaturas()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
