# =============================================================================
#  ventiladores_monitor.py — Monitor de Ventiladores
#  Descripción : Monitoriza en tiempo real la velocidad de los ventiladores
#                del sistema (CPU, caja, GPU, fuente de alimentación...)
#                medida en RPM (Revoluciones Por Minuto).
#  Requisitos  : pip install psutil
#
#  ⚠️  COMPATIBILIDAD — Igual que con temperaturas:
#
#  Linux    → Funciona si lm-sensors está instalado y configurado.
#             Si no aparecen datos:
#                sudo apt install lm-sensors
#                sudo sensors-detect
#
#  macOS    → Funciona en equipos físicos Mac con sensores SMC.
#
#  Windows  → psutil NO soporta lectura de ventiladores en Windows.
#             El script lo detecta y sugiere alternativas.
#
#  VM       → Las máquinas virtuales no tienen acceso a ventiladores
#             físicos. Es el caso esperado en VirtualBox/VMware/WSL.
#
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué son las RPM y por qué importan?
#
#  RPM = Revoluciones Por Minuto. Es la medida de velocidad de giro de
#  un ventilador. A más RPM, más aire mueve, más refrigera... y más ruido.
#
#  Analogía: imagina el ventilador de techo de una habitación. Tiene
#  velocidades: 1 (suave), 2 (media), 3 (máxima). Los ventiladores de PC
#  funcionan igual pero con miles de velocidades posibles entre su mínimo
#  y su máximo, controladas automáticamente según la temperatura.
#
#  Rangos típicos de RPM según el tipo de ventilador:
#  ┌─────────────────────────┬──────────────┬──────────────┬──────────────┐
#  │ Tipo de ventilador      │ Parado/mín.  │ Normal       │ Máximo       │
#  ├─────────────────────────┼──────────────┼──────────────┼──────────────┤
#  │ Ventilador CPU (92mm)   │ 0 – 500 RPM  │ 800–1500 RPM │ 2000-3000RPM │
#  │ Ventilador caja (120mm) │ 0 – 400 RPM  │ 600–1000 RPM │ 1500-2000RPM │
#  │ Ventilador GPU          │ 0 RPM*       │ 800–1800 RPM │ 3000-4500RPM │
#  │ Ventilador fuente (PSU) │ 0 – 400 RPM  │ 600–1200 RPM │ 2000-2500RPM │
#  └─────────────────────────┴──────────────┴──────────────┴──────────────┘
#  * Las GPUs modernas tienen modo "0 RPM": los ventiladores están parados
#    cuando la temperatura es baja (< 50°C) y solo arrancan cuando se necesita.
#    Un ventilador de GPU a 0 RPM NO significa que esté roto.
#
#  ¿Cuándo preocuparse?
#  - Ventilador de CPU parado con temperatura alta → problema grave
#  - Ventilador acelerándose y desacelerándose constantemente → puede indicar
#    pasta térmica seca o mala circulación de aire
#  - RPM muy altas de forma sostenida con carga baja → sensor de temperatura
#    mal calibrado o problema de refrigeración
# -----------------------------------------------------------------------------

import psutil       # Para acceder a los sensores de ventiladores
import time         # Para pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual
import platform     # Para detectar el sistema operativo

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS   = 3      # Los ventiladores cambian con cierta inercia, 3s OK
RPM_MINIMA_ACTIVO    = 100    # Por debajo de este valor consideramos el ventilador
                               # como "parado" (algunos chips reportan ruido de 0-50 RPM)
RPM_UMBRAL_ALTO      = 2000   # RPM a partir de las cuales el ventilador está "alto"
RPM_UMBRAL_MUY_ALTO  = 3000   # RPM a partir de las cuales está al máximo/alerta
RPM_MAX_REFERENCIA   = 4000   # RPM que representa el "100%" en las barras visuales


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: barra de RPM visual ------------------------------------
# Para los ventiladores la barra representa RPM, no porcentaje.
# Usamos RPM_MAX_REFERENCIA como el "100%" de la barra.

def barra_rpm(rpm_actual, rpm_max=RPM_MAX_REFERENCIA, longitud=22):
    """
    Genera una barra visual proporcional a las RPM actuales.
    - rpm_actual : revoluciones por minuto actuales
    - rpm_max    : RPM que representa la barra completamente llena
    - longitud   : anchura de la barra en caracteres
    """
    # Calculamos qué proporción de la barra máxima corresponde a las RPM actuales
    # min(..., 100) evita que la barra se desborde si las RPM superan el máximo
    porcentaje = min((rpm_actual / rpm_max) * 100, 100)
    rellenos   = int((porcentaje / 100) * longitud)
    barra      = '█' * rellenos + '░' * (longitud - rellenos)
    return f"[{barra}]"


# --- Función auxiliar: colorear RPM según nivel -------------------------------
def color_rpm(rpm):
    """
    Devuelve las RPM formateadas con color según el nivel de actividad:
    - Gris   → ventilador parado (< RPM_MINIMA_ACTIVO)
    - Verde  → velocidad baja o normal
    - Amarillo → velocidad alta
    - Rojo   → velocidad muy alta (máximo o alerta)
    """
    rpm_str = f"{rpm:>6.0f} RPM"

    if rpm < RPM_MINIMA_ACTIVO:
        return f"\033[2m{rpm_str}\033[0m"           # Gris tenue: parado
    elif rpm < RPM_UMBRAL_ALTO:
        return f"\033[92m{rpm_str}\033[0m"           # Verde: normal
    elif rpm < RPM_UMBRAL_MUY_ALTO:
        return f"\033[93m{rpm_str}\033[0m"           # Amarillo: alto
    else:
        return f"\033[91m{rpm_str}\033[0m"           # Rojo: muy alto


# --- Función auxiliar: interpretar estado del ventilador ----------------------
def estado_ventilador(rpm, rpm_criticas=None):
    """
    Devuelve un texto descriptivo del estado del ventilador
    basándose en sus RPM actuales y, si existen, sus RPM críticas
    definidas por el fabricante.
    - rpm          : velocidad actual
    - rpm_criticas : umbral crítico del fabricante (puede ser None)
    """
    if rpm < RPM_MINIMA_ACTIVO:
        return "⚫ Parado"
    elif rpm_criticas and rpm >= rpm_criticas:
        return "🔴 Crítico"
    elif rpm >= RPM_UMBRAL_MUY_ALTO:
        return "🔴 Muy alto"
    elif rpm >= RPM_UMBRAL_ALTO:
        return "🟡 Alto"
    else:
        return "🟢 Normal"


# --- Función auxiliar: identificar tipo de ventilador por nombre --------------
def identificar_ventilador(nombre):
    """
    Intenta deducir el tipo de ventilador a partir de su nombre técnico.
    Los nombres varían mucho según el fabricante del chip sensor.
    Devuelve un icono y una descripción legible.
    """
    nombre_lower = nombre.lower()

    if any(p in nombre_lower for p in ['cpu', 'processor', 'proc']):
        return '🧠', 'Ventilador CPU'
    elif any(p in nombre_lower for p in ['gpu', 'vga', 'graphic']):
        return '🎮', 'Ventilador GPU'
    elif any(p in nombre_lower for p in ['sys', 'system', 'case', 'chassis', 'chasis']):
        return '🖥️ ', 'Ventilador de caja'
    elif any(p in nombre_lower for p in ['psu', 'power', 'fuente']):
        return '⚡', 'Ventilador fuente'
    elif any(p in nombre_lower for p in ['pump', 'bomba', 'liquid', 'water', 'aio']):
        return '💧', 'Bomba refrigeración líquida'
    elif any(p in nombre_lower for p in ['fan1', 'fan2', 'fan3', 'fan4', 'fan5']):
        # Nombres genéricos como "fan1", "fan2"...
        numero = ''.join(filter(str.isdigit, nombre))
        return '💨', f'Ventilador #{numero}' if numero else 'Ventilador'
    else:
        return '💨', f'Ventilador ({nombre})'


# --- Función principal: obtener y mostrar datos de ventiladores ---------------

def mostrar_ventiladores():
    """Recopila y muestra en pantalla todos los datos de ventiladores."""

    ahora   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sistema = platform.system()

    # =========================================================================
    #  Verificación de compatibilidad con Windows
    # =========================================================================
    # Al igual que con temperaturas, psutil no soporta ventiladores en Windows.
    # sensors_fans() simplemente no existe en Windows.

    if sistema == "Windows":
        limpiar_pantalla()
        print("=" * 62)
        print("       💨  MONITOR DE VENTILADORES")
        print(f"       📅 {ahora}")
        print("=" * 62)
        print()
        print("  ⚠️  \033[93mLectura de ventiladores no disponible en Windows\033[0m")
        print()
        print("  psutil no tiene acceso a los sensores de ventiladores")
        print("  en Windows por las mismas razones que con las temperaturas.")
        print()
        print("  💡 Alternativas gratuitas para Windows:")
        print()
        print("     🔧 HWiNFO64")
        print("        Muestra RPM de todos los ventiladores detectados.")
        print("        → https://www.hwinfo.com")
        print()
        print("     🔧 SpeedFan (clásico, compatible con hardware antiguo)")
        print("        Permite ver y controlar velocidades de ventiladores.")
        print("        → https://www.almico.com/speedfan.php")
        print()
        print("     🔧 Fan Control (moderno, interfaz muy limpia)")
        print("        → https://github.com/Rem0o/FanControl.Releases")
        print()
        print("     🔧 MSI Afterburner (solo GPU)")
        print("        Muestra y controla el ventilador de la GPU.")
        print("        → https://www.msi.com/Landing/afterburner")
        print()
        print("=" * 62)
        print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
        print("=" * 62)
        return

    # =========================================================================
    #  Lectura de sensores de ventiladores (Linux / macOS)
    # =========================================================================
    # sensors_fans() funciona exactamente igual que sensors_temperatures():
    # devuelve un diccionario donde la clave es el nombre del chip sensor
    # y el valor es una lista de lecturas de ventiladores de ese chip.
    # Cada lectura tiene: label (nombre), current (RPM actuales), high y critical
    # (RPM máximas definidas por el fabricante, si existen).

    try:
        ventiladores = psutil.sensors_fans()
    except AttributeError:
        # psutil instalado pero sin soporte de sensores en este sistema
        ventiladores = None

    limpiar_pantalla()

    # Cabecera
    print("=" * 62)
    print("       💨  MONITOR DE VENTILADORES — Tiempo Real")
    print(f"       📅 {ahora}  |  Sistema: {sistema}")
    print("=" * 62)

    # -------------------------------------------------------------------------
    #  Sin sensores de ventiladores disponibles
    # -------------------------------------------------------------------------
    if not ventiladores:
        print()
        print("  ℹ️  No se detectaron sensores de ventiladores.")
        print()
        print("  Posibles causas:\n")
        print("  🖥️  Máquina virtual (VirtualBox, VMware, WSL...)")
        print("     Las VMs no tienen acceso a los ventiladores físicos.")
        print("     Es el caso más habitual — no indica ningún error.\n")
        print("  🔧 lm-sensors no está instalado o configurado.")
        print("     Prueba:")
        print("       sudo apt install lm-sensors")
        print("       sudo sensors-detect")
        print("       sudo modprobe coretemp\n")
        print("  💻 Hardware sin chip sensor compatible.")
        print("     Algunos portátiles de gama baja o placas antiguas")
        print("     no tienen chip de monitorización accesible.\n")
        print("  💡 Verifica con el comando 'sensors' en la terminal.")
        print("     Si aparecen datos ahí, reinicia el script.")
        print()
        print("=" * 62)
        print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
        print("=" * 62)
        return

    # =========================================================================
    #  Tenemos datos — procesamos y mostramos
    # =========================================================================

    # Recopilamos todos los ventiladores en una lista plana para el resumen
    # Cada elemento: (chip, label, rpm_actual, rpm_high, rpm_critical)
    todos_los_fans = []

    for nombre_chip, lecturas in ventiladores.items():
        for lectura in lecturas:
            todos_los_fans.append({
                'chip'    : nombre_chip,
                'label'   : lectura.label if lectura.label else 'Fan',
                'rpm'     : lectura.current,
                'high'    : lectura.high     if hasattr(lectura, 'high')     else None,
                'critical': lectura.critical if hasattr(lectura, 'critical') else None,
            })

    # Contadores para el resumen
    activos  = sum(1 for f in todos_los_fans if f['rpm'] >= RPM_MINIMA_ACTIVO)
    parados  = sum(1 for f in todos_los_fans if f['rpm'] <  RPM_MINIMA_ACTIVO)
    alertas  = []

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Ventiladores agrupados por chip sensor
    # -------------------------------------------------------------------------
    print(f"\n💨 VENTILADORES DETECTADOS\n")
    print(f"   Total: {len(todos_los_fans)}  |  "
          f"\033[92mActivos: {activos}\033[0m  |  "
          f"\033[2mParados: {parados}\033[0m\n")

    for nombre_chip, lecturas in ventiladores.items():

        print(f"  📡 \033[1m{nombre_chip.upper()}\033[0m")

        for lectura in lecturas:
            rpm      = lectura.current
            label    = lectura.label if lectura.label else "Fan"
            high     = getattr(lectura, 'high',     None)
            critical = getattr(lectura, 'critical', None)

            # Identificamos el tipo de ventilador por su nombre
            icono, descripcion = identificar_ventilador(label)

            # Estado textual del ventilador
            estado = estado_ventilador(rpm, critical)

            # Línea principal con RPM y barra visual
            print(f"     {icono}  {descripcion:<30} {color_rpm(rpm)}")
            print(f"        Barra   : {barra_rpm(rpm)} {estado}")

            # Si el fabricante definió límites, los mostramos como referencia
            refs = []
            if high     and high     > 0: refs.append(f"alto.fab: {high:.0f} RPM")
            if critical and critical > 0: refs.append(f"crítico.fab: {critical:.0f} RPM")
            if refs:
                print(f"        Límites : \033[2m{' | '.join(refs)}\033[0m")

            # Guardamos alertas si las RPM superan los límites del fabricante
            if critical and rpm >= critical:
                alertas.append((label, rpm, "CRÍTICA"))
            elif high and rpm >= high:
                alertas.append((label, rpm, "ELEVADA"))
            elif rpm >= RPM_UMBRAL_MUY_ALTO:
                alertas.append((label, rpm, "MUY ALTA"))

            # Nota especial para ventilador a 0 RPM
            if rpm < RPM_MINIMA_ACTIVO:
                # Intentamos distinguir si es normal (GPU en modo silencio)
                # o potencialmente preocupante
                if any(p in label.lower() for p in ['gpu', 'vga']):
                    print(f"        \033[2mℹ️  Las GPUs modernas paran sus ventiladores")
                    print(f"           en reposo (modo 0 RPM). Es normal.\033[0m")
                else:
                    print(f"        \033[93m⚠️  Ventilador parado — verifica que funcione\033[0m")

            print()   # Línea en blanco entre ventiladores

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Alertas activas
    # -------------------------------------------------------------------------
    if alertas:
        print(f"{'─' * 62}")
        print(f"\n🚨 ALERTAS ACTIVAS\n")
        for label, rpm, nivel in alertas:
            if nivel == "CRÍTICA":
                print(f"  \033[91m🔴 RPM CRÍTICAS : {label} → {rpm:.0f} RPM\033[0m")
                print(f"     Revisa la refrigeración del equipo inmediatamente.")
            elif nivel == "MUY ALTA":
                print(f"  \033[91m🔴 RPM MUY ALTAS: {label} → {rpm:.0f} RPM\033[0m")
                print(f"     El sistema está trabajando al límite de refrigeración.")
            else:
                print(f"  \033[93m🟡 RPM elevadas : {label} → {rpm:.0f} RPM\033[0m")
                print(f"     Vigila si la tendencia sigue subiendo.")
        print()

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Gráfico de barras comparativo
    # -------------------------------------------------------------------------
    print(f"{'─' * 62}")
    print(f"\n📊 COMPARATIVA DE VELOCIDADES\n")

    if todos_los_fans:
        # Ordenamos de mayor a menor RPM para una lectura más visual
        fans_ordenados = sorted(todos_los_fans, key=lambda f: f['rpm'], reverse=True)
        rpm_max_real   = max(f['rpm'] for f in fans_ordenados) if fans_ordenados else 1

        for fan in fans_ordenados:
            # Usamos el máximo real del sistema como referencia de la barra
            # para que el ventilador más rápido ocupe la barra completa
            ref = max(rpm_max_real, RPM_MAX_REFERENCIA)
            barra = barra_rpm(fan['rpm'], rpm_max=ref, longitud=25)
            icono, _ = identificar_ventilador(fan['label'])
            nombre_corto = fan['label'][:20] if len(fan['label']) > 20 else fan['label']
            print(f"   {icono} {nombre_corto:<20} {barra} {color_rpm(fan['rpm'])}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Diagnóstico global de ventilación
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n🩺 DIAGNÓSTICO DE VENTILACIÓN\n")

    if alertas:
        criticas = sum(1 for a in alertas if a[2] in ("CRÍTICA", "MUY ALTA"))
        if criticas:
            print("  \033[91m🚨 SISTEMA CON VENTILADORES AL LÍMITE:\033[0m")
            print("     • Comprueba que no hay polvo obstruyendo los ventiladores.")
            print("     • Verifica que todos los ventiladores giran correctamente.")
            print("     • Comprueba la circulación de aire dentro de la caja.")
            print("     • Considera añadir pasta térmica si no se ha hecho recientemente.")
        else:
            print("  \033[93m⚠️  Algunas velocidades están elevadas.")
            print("     Monitoriza la tendencia en los próximos minutos.\033[0m")
    elif parados > 0 and activos == 0:
        print("  \033[91m⚠️  Todos los ventiladores reportan 0 RPM.")
        print("     Si el equipo no está en reposo y la temperatura sube,")
        print("     puede haber un problema con los sensores o los ventiladores.\033[0m")
    else:
        print("  \033[92m✅ Sistema de ventilación en estado normal.\033[0m")
        if parados > 0:
            print(f"     ({parados} ventilador(es) en reposo — puede ser normal)")
        print("     Velocidades dentro de rangos esperados.")

    # Pie del monitor
    print("\n" + "=" * 62)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 62)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de ventiladores."""
    print("Iniciando monitor de ventiladores... (Ctrl+C para detener)")
    time.sleep(1)

    while True:
        try:
            mostrar_ventiladores()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
