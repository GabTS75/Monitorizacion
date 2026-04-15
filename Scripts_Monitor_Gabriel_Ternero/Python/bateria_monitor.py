# =============================================================================
#  bateria_monitor.py — Monitor de Batería
#  Descripción : Monitoriza en tiempo real el estado de la batería:
#                nivel de carga, estado de carga/descarga, tiempo
#                estimado restante y salud general de la batería.
#  Requisitos  : pip install psutil
#
#  ℹ️  NOTA: Este script solo es útil en portátiles y dispositivos con batería.
#            En equipos de sobremesa (sin batería) se informará correctamente.
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Qué monitorizamos en la batería?
#
#  La batería de un portátil es mucho más que un simple "% de carga".
#  Tiene su propio sistema de gestión (BMS - Battery Management System)
#  que controla carga, descarga, temperatura y salud del acumulador.
#
#  Analogía: imagina una garrafa de agua. El porcentaje de carga sería
#  cuánta agua le queda. El tiempo restante sería cuánto tardará en
#  vaciarse al ritmo actual de consumo. Y la "salud" sería si la garrafa
#  ha perdido capacidad con el tiempo (las garrafas viejas se deforman
#  y ya no caben los mismos litros que cuando eran nuevas).
#
#  Datos principales que medimos:
#   Porcentaje        → nivel de carga actual (0-100%)
#   Estado            → cargando / descargando / carga completa
#   Tiempo restante   → estimación de cuánto dura la batería o cuánto tarda en cargarse
#   Enchufado         → si el adaptador de corriente está conectado
#
#  Lo que psutil NO puede darnos (requeriría herramientas del fabricante):
#  - Ciclos de carga acumulados
#  - Capacidad de diseño vs capacidad actual (degradación)
#  - Temperatura de la batería
#  - Voltaje actual
# -----------------------------------------------------------------------------

import psutil       # Para acceder al estado de la batería
import time         # Para pausas entre actualizaciones
import os           # Para interactuar con el sistema operativo
import datetime     # Para mostrar la fecha y hora actual
import platform     # Para detectar el sistema operativo

# --- Configuración general ----------------------------------------------------
INTERVALO_SEGUNDOS      = 5     # La batería cambia lentamente, 5s es suficiente
UMBRAL_BATERIA_BAJA     = 20    # % por debajo del cual avisamos de batería baja
UMBRAL_BATERIA_CRITICA  = 10    # % por debajo del cual la situación es crítica
UMBRAL_BATERIA_ALTA     = 95    # % por encima del cual sugerimos desenchufar
                                 # (mantener la batería al 100% constantemente
                                 #  enchufada acelera su degradación a largo plazo)


# --- Función auxiliar: limpiar pantalla ---------------------------------------
def limpiar_pantalla():
    """Limpia la terminal antes de cada actualización."""
    os.system('cls' if os.name == 'nt' else 'clear')


# --- Función auxiliar: barra de batería visual --------------------------------
# Para la batería usamos un diseño especial que se parece visualmente
# al icono de batería que todos conocemos de los teléfonos y portátiles.

def barra_bateria(porcentaje, longitud=30):
    """
    Genera una barra de carga visual con estilo de icono de batería.
    Ejemplo al 60%:  [██████████████████░░░░░░░░░░░░] 60.0%
    - porcentaje : nivel de carga actual (0-100)
    - longitud   : anchura interior de la barra
    """
    rellenos = int((porcentaje / 100) * longitud)
    barra    = '█' * rellenos + '░' * (longitud - rellenos)

    # Coloramos según el nivel de carga
    if porcentaje <= UMBRAL_BATERIA_CRITICA:
        color = "\033[91m"   # Rojo: crítico
    elif porcentaje <= UMBRAL_BATERIA_BAJA:
        color = "\033[93m"   # Amarillo: bajo
    elif porcentaje >= UMBRAL_BATERIA_ALTA:
        color = "\033[96m"   # Cian: muy cargada (casi llena)
    else:
        color = "\033[92m"   # Verde: nivel normal

    reset = "\033[0m"
    return f"{color}[{barra}] {porcentaje:.1f}%{reset}"


# --- Función auxiliar: formatear tiempo en segundos --------------------------
# psutil devuelve el tiempo restante de batería en segundos.
# Un usuario no piensa en segundos sino en horas y minutos.

def segundos_a_tiempo(segundos):
    """
    Convierte segundos a formato legible horas/minutos.
    Ejemplos:
        3661 → "1h 01m"
        45   → "0h 45m"
        -1   → "Calculando..." (psutil devuelve -1 cuando no puede estimarlo)
    """
    # psutil devuelve psutil.POWER_TIME_UNKNOWN (-2) cuando el tiempo
    # no se puede calcular, y psutil.POWER_TIME_UNLIMITED cuando está
    # conectado y la batería ya está llena.
    if segundos == psutil.POWER_TIME_UNKNOWN:
        return "Calculando..."
    if segundos == psutil.POWER_TIME_UNLIMITED:
        return "Tiempo ilimitado (carga completa)"
    if segundos < 0:
        return "No disponible"

    horas   = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    return f"{horas}h {minutos:02d}m"


# --- Función auxiliar: icono de estado de la batería -------------------------
def icono_estado(enchufado, porcentaje):
    """
    Devuelve un icono y texto descriptivo según el estado de la batería.
    Combina si está enchufado con el nivel actual.
    """
    if enchufado:
        if porcentaje >= 100:
            return "🔋", "Carga completa"
        else:
            return "🔌", "Cargando"
    else:
        if porcentaje <= UMBRAL_BATERIA_CRITICA:
            return "🪫", "CRÍTICA — Conecta el cargador YA"
        elif porcentaje <= UMBRAL_BATERIA_BAJA:
            return "⚠️ ", "Batería baja — conecta pronto"
        else:
            return "🔋", "Descargando (en batería)"


# --- Función principal: obtener y mostrar estado de la batería ---------------

def mostrar_bateria():
    """Recopila y muestra en pantalla todos los datos de la batería."""

    ahora   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sistema = platform.system()

    limpiar_pantalla()

    # Cabecera
    print("=" * 62)
    print("       🔋  MONITOR DE BATERÍA — Tiempo Real")
    print(f"       📅 {ahora}  |  Sistema: {sistema}")
    print("=" * 62)

    # =========================================================================
    #  Verificamos si psutil puede leer datos de batería
    # =========================================================================
    # sensors_battery() devuelve un objeto con los datos de la batería,
    # o None si el sistema no tiene batería o no puede leerla.
    # En un PC de sobremesa siempre devolverá None.

    bateria = psutil.sensors_battery()

    # -------------------------------------------------------------------------
    #  Sin batería detectada
    # -------------------------------------------------------------------------
    if bateria is None:
        print()
        print("  ℹ️  No se detectó ninguna batería en este sistema.")
        print()

        if sistema == "Windows":
            print("  Posibles motivos:")
            print("  • Equipo de sobremesa (tower/desktop) sin batería.")
            print("  • Portátil con batería no reconocida por el driver.")
            print()
            print("  💡 Si es un portátil y no aparece nada, comprueba")
            print("     que los drivers de ACPI están instalados correctamente")
            print("     en el Administrador de Dispositivos.")
        elif sistema == "Linux":
            print("  Posibles motivos:")
            print("  • Equipo de sobremesa sin batería.")
            print("  • Máquina virtual (VMs no tienen batería real).")
            print("  • El módulo ACPI del kernel no está cargado.")
            print()
            print("  💡 Comprueba con:")
            print("     ls /sys/class/power_supply/")
            print("     upower -i $(upower -e | grep BAT)")
        else:
            print("  • Puede ser un equipo de sobremesa.")
            print("  • O una máquina virtual sin batería virtual configurada.")

        print()
        print("=" * 62)
        print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
        print("=" * 62)
        return

    # =========================================================================
    #  Tenemos datos de batería — los mostramos
    # =========================================================================
    #
    # El objeto 'bateria' tiene estos atributos:
    #   percent    → porcentaje de carga actual (float, 0.0 a 100.0)
    #   secsleft   → segundos restantes estimados (int, o constantes especiales)
    #   power_plugged → True si el adaptador de corriente está enchufado

    porcentaje = bateria.percent
    enchufado  = bateria.power_plugged
    segundos   = bateria.secsleft

    # Obtenemos icono y texto de estado
    icono, estado_texto = icono_estado(enchufado, porcentaje)

    # -------------------------------------------------------------------------
    #  SECCIÓN 1: Estado principal
    # -------------------------------------------------------------------------
    print(f"\n{icono}  ESTADO ACTUAL\n")
    print(f"   Nivel de carga  : {barra_bateria(porcentaje)}")
    print(f"   Estado          : {estado_texto}")
    print(f"   Adaptador       : {'✅ Conectado' if enchufado else '❌ Desconectado'}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 2: Tiempo estimado
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n⏱️  TIEMPO ESTIMADO\n")

    tiempo_str = segundos_a_tiempo(segundos)

    if enchufado:
        if porcentaje >= 100:
            print(f"   Tiempo para carga completa : Ya está al 100% ✅")
        else:
            print(f"   Tiempo hasta carga completa: {tiempo_str}")
            print(f"   (Estimación aproximada — varía según el consumo del equipo)")
    else:
        print(f"   Autonomía restante estimada: {tiempo_str}")

        # Si la batería está baja, añadimos urgencia al mensaje
        if porcentaje <= UMBRAL_BATERIA_CRITICA:
            print(f"\n   🚨 \033[91mBATERÍA CRÍTICA — El equipo se apagará pronto\033[0m")
            print(f"      Conecta el cargador inmediatamente.")
        elif porcentaje <= UMBRAL_BATERIA_BAJA:
            print(f"\n   ⚠️  \033[93mBatería baja — conecta el cargador pronto\033[0m")

    # -------------------------------------------------------------------------
    #  SECCIÓN 3: Consejos de salud de la batería
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n🩺 SALUD Y CONSEJOS\n")

    # Evaluamos la situación actual y damos consejos contextuales.
    # Los consejos solo aparecen cuando son relevantes, no siempre.
    consejos = []

    if enchufado and porcentaje >= UMBRAL_BATERIA_ALTA:
        # Batería muy cargada y enchufada: puede acelerar la degradación
        consejos.append((
            "💡",
            "\033[96m",
            f"Batería al {porcentaje:.0f}% con cargador conectado.",
            "Mantener la batería constantemente al 100% acelera su",
            "degradación. Si puedes, desenchufar entre el 20% y el 80%",
            "prolonga significativamente su vida útil."
        ))

    if not enchufado and porcentaje > 80:
        # Batería alta sin enchufar: situación ideal
        consejos.append((
            "✅", "\033[92m",
            "Nivel de batería óptimo para uso en movilidad.",
            "", "", ""
        ))

    if not enchufado and porcentaje <= UMBRAL_BATERIA_BAJA and porcentaje > UMBRAL_BATERIA_CRITICA:
        consejos.append((
            "⚠️ ", "\033[93m",
            "Batería baja. Conecta el cargador cuando puedas.",
            "Las descargas profundas repetidas reducen la vida útil.", "", ""
        ))

    if not consejos:
        # Estado normal: nada especial que destacar
        if enchufado:
            print(f"   ✅ \033[92mBatería cargándose normalmente.\033[0m")
        else:
            print(f"   ✅ \033[92mBatería en uso normal. Nivel adecuado.\033[0m")
    else:
        for consejo in consejos:
            icono_c, color, *lineas = consejo
            print(f"   {icono_c} {color}{lineas[0]}\033[0m")
            for linea in lineas[1:]:
                if linea:
                    print(f"      {linea}")

    # -------------------------------------------------------------------------
    #  SECCIÓN 4: Información adicional del sistema de energía (Linux)
    # -------------------------------------------------------------------------
    # En Linux podemos obtener información más detallada de la batería
    # leyendo directamente desde /sys/class/power_supply/
    # Esto nos da datos como la capacidad real vs la de diseño.

    if sistema == "Linux":
        ruta_base = "/sys/class/power_supply"
        try:
            dispositivos = os.listdir(ruta_base)
            baterias_sys = [d for d in dispositivos if d.startswith("BAT")]

            if baterias_sys:
                print(f"\n{'─' * 62}")
                print(f"\n📋 INFORMACIÓN DETALLADA (desde /sys — solo Linux)\n")

                for bat in baterias_sys:
                    ruta_bat = os.path.join(ruta_base, bat)
                    print(f"   🔋 Dispositivo: {bat}")

                    # Función auxiliar local para leer un archivo de /sys
                    # Los archivos de /sys contienen un único valor en texto
                    def leer_sys(nombre_archivo):
                        """Lee un valor de /sys/class/power_supply/BATx/archivo"""
                        try:
                            ruta = os.path.join(ruta_bat, nombre_archivo)
                            with open(ruta, 'r') as f:
                                return f.read().strip()
                        except Exception:
                            return None

                    # Capacidad de diseño vs capacidad real actual
                    # energy_full_design → capacidad cuando la batería era nueva
                    # energy_full        → capacidad máxima actual (degradada)
                    # La diferencia nos da el % de degradación acumulada
                    disenyo  = leer_sys("energy_full_design")
                    actual   = leer_sys("energy_full")
                    estado_s = leer_sys("status")
                    ciclos   = leer_sys("cycle_count")
                    fabricante = leer_sys("manufacturer")
                    modelo   = leer_sys("model_name")
                    tecnologia = leer_sys("technology")

                    if fabricante : print(f"   Fabricante   : {fabricante}")
                    if modelo     : print(f"   Modelo       : {modelo}")
                    if tecnologia : print(f"   Tecnología   : {tecnologia}")
                    if estado_s   : print(f"   Estado (sys) : {estado_s}")
                    if ciclos     : print(f"   Ciclos carga : {ciclos}")

                    # Calculamos la salud de la batería si tenemos ambos valores
                    if disenyo and actual:
                        try:
                            # Los valores en /sys vienen en microvatios-hora (µWh)
                            cap_disenyo = int(disenyo)
                            cap_actual  = int(actual)

                            if cap_disenyo > 0:
                                salud = (cap_actual / cap_disenyo) * 100

                                # Coloreamos según la salud
                                if salud >= 80:
                                    color_salud = "\033[92m"   # Verde: batería sana
                                elif salud >= 60:
                                    color_salud = "\033[93m"   # Amarillo: degradada
                                else:
                                    color_salud = "\033[91m"   # Rojo: muy degradada

                                print(f"\n   🩺 Salud de la batería:")
                                print(f"      Capacidad de diseño : "
                                      f"{cap_disenyo / 1_000_000:.2f} Wh")
                                print(f"      Capacidad actual    : "
                                      f"{cap_actual  / 1_000_000:.2f} Wh")
                                print(f"      Salud estimada      : "
                                      f"{color_salud}{salud:.1f}%\033[0m")

                                if salud < 60:
                                    print(f"\n      \033[91m⚠️  La batería ha perdido más del 40% de su")
                                    print(f"         capacidad original. Considera reemplazarla.\033[0m")
                                elif salud < 80:
                                    print(f"\n      \033[93m💡 La batería muestra cierta degradación.")
                                    print(f"         Es normal en baterías con más de 2-3 años.\033[0m")
                        except ValueError:
                            pass
                    print()

        except FileNotFoundError:
            pass   # /sys no existe en este sistema (no es Linux o es una VM)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    #  SECCIÓN 5: Diagrama visual del nivel de carga
    # -------------------------------------------------------------------------
    print(f"\n{'─' * 62}")
    print(f"\n📊 DIAGRAMA DE CARGA\n")

    # Pintamos un "icono" de batería grande en ASCII
    # para que sea visualmente impactante y fácil de leer de un vistazo
    nivel = int(porcentaje / 10)   # Escala de 0 a 10 bloques

    bloques_llenos  = '█' * nivel
    bloques_vacios  = '░' * (10 - nivel)

    if porcentaje <= UMBRAL_BATERIA_CRITICA:
        color_diag = "\033[91m"
    elif porcentaje <= UMBRAL_BATERIA_BAJA:
        color_diag = "\033[93m"
    else:
        color_diag = "\033[92m"

    # Dibujamos la batería como un rectángulo ASCII
    print(f"   ┌──────────────────────────┐ ┐")
    print(f"   │ {color_diag}{bloques_llenos:<10}{bloques_vacios:>10}\033[0m │ │")
    print(f"   │ {color_diag}{porcentaje:^26.1f}%\033[0m │ │  ← Polo positivo")
    print(f"   └──────────────────────────┘ ┘")

    simbolo_enchufe = "🔌 Cargando" if enchufado else "🔋 En batería"
    print(f"\n   {simbolo_enchufe}  —  {estado_texto}")

    # Pie del monitor
    print("\n" + "=" * 62)
    print(f"   🔄 Actualizando cada {INTERVALO_SEGUNDOS}s  |  Ctrl+C para salir")
    print("=" * 62)


# --- Bucle principal de monitorización ----------------------------------------
def iniciar_monitor():
    """Inicia el bucle de monitorización continua de batería."""
    print("Iniciando monitor de batería... (Ctrl+C para detener)")
    time.sleep(1)

    while True:
        try:
            mostrar_bateria()
            time.sleep(INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor detenido por el usuario. ¡Hasta luego!")
            break


# --- Punto de entrada ---------------------------------------------------------
if __name__ == "__main__":
    iniciar_monitor()
