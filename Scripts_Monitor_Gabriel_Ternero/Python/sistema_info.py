# =============================================================================
#  sistema_info.py — Información Estática del Sistema
#  Descripción : Muestra una "radiografía completa" del hardware y software
#                del sistema: CPU, RAM, discos, red, SO y más.
#                A diferencia del resto de scripts, este NO monitoriza
#                en tiempo real sino que toma una "foto" del sistema
#                en el momento de ejecutarse.
#  Requisitos  : pip install psutil
# =============================================================================

# -----------------------------------------------------------------------------
#  ¿Por qué un script de información estática?
#
#  Antes de monitorizar un sistema, necesitas saber QUÉ estás monitorizando.
#  Igual que un médico necesita conocer la ficha del paciente antes de
#  interpretar sus constantes vitales, un administrador de sistemas necesita
#  saber el hardware del equipo para entender las métricas que lee.
#
#  Información "estática" = datos que no cambian (o cambian muy poco):
#  ✅ Modelo de CPU, número de núcleos, frecuencia máxima
#  ✅ RAM total instalada
#  ✅ Sistema operativo y versión del kernel
#  ✅ Nombre del equipo (hostname)
#  ✅ Discos instalados y su capacidad total
#  ✅ Interfaces de red y sus direcciones MAC
#
#  Información "dinámica" = datos que cambian constantemente:
#  ❌ % de uso de CPU en este momento   → eso lo hacen los otros scripts
#  ❌ RAM libre ahora mismo
#  ❌ Temperatura actual
# -----------------------------------------------------------------------------

import psutil           # Hardware: CPU, RAM, discos, red
import platform         # Sistema operativo, arquitectura, versión del kernel
import os               # Información del sistema de archivos y hostname
import datetime         # Fecha y hora del informe y del arranque del sistema
import socket           # Hostname e información de red
import time             # Para calcular el uptime del sistema

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


# --- Función auxiliar: separador de sección ----------------------------------
def seccion(titulo, icono="📋", ancho=65):
    """
    Imprime una cabecera de sección con formato uniforme.
    Centraliza el estilo de todas las secciones del informe.
    """
    print(f"\n{'─' * ancho}")
    print(f" {icono}  {titulo.upper()}")
    print(f"{'─' * ancho}")


# --- Función auxiliar: línea de dato -----------------------------------------
def dato(etiqueta, valor, ancho_etiqueta=28):
    """
    Imprime una línea de dato con etiqueta y valor alineados.
    Ejemplo:  Sistema operativo       : Ubuntu 22.04 LTS
    """
    print(f"   {etiqueta:<{ancho_etiqueta}}: {valor}")


# =============================================================================
#  SECCIONES DEL INFORME
# =============================================================================

# --- Sección 1: Encabezado del informe ---------------------------------------
def mostrar_encabezado():
    """Muestra la cabecera principal del informe con fecha y hora."""
    ahora    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sistema  = platform.system()
    hostname = socket.gethostname()

    print("=" * 65)
    print("       🖥️   INFORME DE SISTEMA — Información Estática")
    print(f"       📅  Generado el : {ahora}")
    print(f"       🏠  Equipo      : {hostname}")
    print(f"       💻  Sistema     : {sistema}")
    print("=" * 65)


# --- Sección 2: Sistema operativo --------------------------------------------
def mostrar_so():
    """Muestra información detallada del sistema operativo."""
    seccion("Sistema Operativo", "🐧")

    # platform ofrece información del SO de forma multiplataforma
    dato("Sistema",             platform.system())
    dato("Nombre completo",     platform.platform())
    dato("Versión",             platform.version()[:60])   # Truncamos si es muy larga
    dato("Release",             platform.release())
    dato("Arquitectura",        platform.machine())
    dato("Procesador (arch)",   platform.processor() or "No disponible")

    # Versión de Python con la que se ejecuta este script
    # Útil para saber si el entorno es compatible con futuras mejoras
    dato("Python (este script)", platform.python_version())

    # Hostname: el nombre con el que este equipo se identifica en la red
    try:
        hostname   = socket.gethostname()
        ip_local   = socket.gethostbyname(hostname)
        dato("Hostname",         hostname)
        dato("IP local",         ip_local)
    except Exception:
        dato("Hostname",         "No disponible")

    # Tiempo de arranque del sistema (boot time)
    # psutil.boot_time() devuelve un timestamp UNIX del último arranque
    boot_timestamp = psutil.boot_time()
    boot_dt        = datetime.datetime.fromtimestamp(boot_timestamp)
    boot_str       = boot_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Calculamos cuánto tiempo lleva encendido el sistema
    segundos_activo = time.time() - boot_timestamp
    dias    = int(segundos_activo // 86400)
    horas   = int((segundos_activo % 86400) // 3600)
    minutos = int((segundos_activo % 3600)  // 60)

    dato("Último arranque",     boot_str)
    dato("Tiempo encendido",    f"{dias}d {horas}h {minutos}m")


# --- Sección 3: CPU ----------------------------------------------------------
def mostrar_cpu():
    """Muestra información estática del procesador."""
    seccion("Procesador (CPU)", "🧠")

    # Número de núcleos
    # logical=False → núcleos físicos del chip (los "reales")
    # logical=True  → núcleos lógicos (incluye Hyper-Threading)
    nucleos_fisicos = psutil.cpu_count(logical=False)
    nucleos_logicos = psutil.cpu_count(logical=True)
    dato("Núcleos físicos",     str(nucleos_fisicos))
    dato("Núcleos lógicos (HT)",str(nucleos_logicos))

    # Frecuencias
    freq = psutil.cpu_freq()
    if freq:
        dato("Frecuencia base",     f"{freq.min  / 1000:.2f} GHz")
        dato("Frecuencia máxima",   f"{freq.max  / 1000:.2f} GHz")
        dato("Frecuencia actual",   f"{freq.current / 1000:.2f} GHz")

    # Nombre del procesador según el sistema operativo
    # En Linux está en /proc/cpuinfo, en Windows en el registro
    nombre_cpu = platform.processor()

    # En Linux, platform.processor() a veces devuelve poco info.
    # Intentamos leer /proc/cpuinfo para obtener el nombre completo.
    if not nombre_cpu or nombre_cpu == 'x86_64':
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for linea in f:
                    if 'model name' in linea:
                        nombre_cpu = linea.split(':')[1].strip()
                        break
        except Exception:
            nombre_cpu = "No disponible"

    dato("Modelo",              nombre_cpu[:55] if nombre_cpu else "No disponible")

    # Instrucciones SIMD soportadas (AVX, SSE, etc.)
    # Solo disponible en Linux vía /proc/cpuinfo
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for linea in f:
                if linea.startswith('flags'):
                    flags = linea.split(':')[1].strip().split()
                    # Filtramos solo las extensiones más conocidas
                    conocidas = ['sse', 'sse2', 'sse3', 'ssse3', 'sse4_1',
                                 'sse4_2', 'avx', 'avx2', 'avx512f', 'aes',
                                 'vmx', 'svm']
                    presentes = [f.upper() for f in flags if f in conocidas]
                    if presentes:
                        dato("Extensiones CPU", ', '.join(presentes[:8]))
                    break
    except Exception:
        pass


# --- Sección 4: Memoria RAM --------------------------------------------------
def mostrar_ram():
    """Muestra información estática de la memoria del sistema."""
    seccion("Memoria RAM", "💾")

    ram  = psutil.virtual_memory()
    swap = psutil.swap_memory()

    dato("RAM total instalada",  bytes_a_legible(ram.total))
    dato("RAM disponible ahora", bytes_a_legible(ram.available))
    dato("RAM usada ahora",      f"{bytes_a_legible(ram.used)} ({ram.percent:.1f}%)")

    print()
    dato("Swap total",           bytes_a_legible(swap.total) if swap.total > 0 else "Sin swap")
    if swap.total > 0:
        dato("Swap usada ahora", f"{bytes_a_legible(swap.used)} ({swap.percent:.1f}%)")

    # Tipo de RAM (DDR4, DDR5...) — solo disponible via dmidecode en Linux con sudo
    # Lo intentamos pero no es crítico si no está disponible
    try:
        import subprocess
        resultado = subprocess.run(
            ['sudo', 'dmidecode', '-t', 'memory'],
            capture_output=True, text=True, timeout=3
        )
        if resultado.returncode == 0:
            for linea in resultado.stdout.split('\n'):
                if 'Type:' in linea and 'DDR' in linea:
                    tipo_ram = linea.split(':')[1].strip()
                    dato("Tipo de memoria",  tipo_ram)
                    break
                if 'Speed:' in linea and 'MT/s' in linea:
                    velocidad = linea.split(':')[1].strip()
                    dato("Velocidad",        velocidad)
                    break
    except Exception:
        pass   # dmidecode no disponible o sin sudo — no pasa nada


# --- Sección 5: Almacenamiento -----------------------------------------------
def mostrar_almacenamiento():
    """Muestra información de los discos y particiones del sistema."""
    seccion("Almacenamiento", "💽")

    particiones = psutil.disk_partitions(all=False)

    # Resumen por partición
    espacio_total_sistema = 0

    for part in particiones:
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue

        espacio_total_sistema += uso.total

        # Montamos la info de cada partición en un bloque visual
        print(f"\n   📀 {part.device}  →  {part.mountpoint}")
        print(f"      Sistema de archivos : {part.fstype or 'desconocido'}")
        print(f"      Opciones de montaje : {part.opts[:50]}")
        print(f"      Capacidad total     : {bytes_a_legible(uso.total)}")
        print(f"      Espacio usado       : {bytes_a_legible(uso.used)} "
              f"({uso.percent:.1f}%)")
        print(f"      Espacio libre       : {bytes_a_legible(uso.free)}")

    print(f"\n   📊 Espacio total sumado de todas las particiones: "
          f"{bytes_a_legible(espacio_total_sistema)}")


# --- Sección 6: Red ----------------------------------------------------------
def mostrar_red():
    """Muestra información estática de las interfaces de red."""
    seccion("Interfaces de Red", "🌐")

    # Direcciones por interfaz
    direcciones = psutil.net_if_addrs()

    # Estado (UP/DOWN, velocidad, MTU) por interfaz
    estados = psutil.net_if_stats()

    for interfaz, addrs in direcciones.items():

        # Omitimos loopback para no saturar la salida
        if interfaz.lower() in ('lo', 'loopback pseudo-interface 1'):
            continue

        estado_obj  = estados.get(interfaz)
        activa      = estado_obj.isup   if estado_obj else None
        velocidad   = estado_obj.speed  if estado_obj else None
        mtu         = estado_obj.mtu    if estado_obj else None

        estado_str = "\033[92mUP\033[0m" if activa else "\033[91mDOWN\033[0m"

        print(f"\n   🔌 {interfaz}  [{estado_str}]", end="")
        if velocidad:  print(f"  |  {velocidad} Mbps", end="")
        if mtu:        print(f"  |  MTU: {mtu}", end="")
        print()

        for addr in addrs:
            # AF_INET  = IPv4
            # AF_INET6 = IPv6
            # AF_LINK / AF_PACKET = dirección MAC (física)
            if addr.family == socket.AF_INET:
                print(f"      IPv4     : {addr.address}")
                if addr.netmask:
                    print(f"      Máscara  : {addr.netmask}")
                if addr.broadcast:
                    print(f"      Broadcast: {addr.broadcast}")

            elif addr.family == socket.AF_INET6:
                ipv6 = addr.address.split('%')[0]
                print(f"      IPv6     : {ipv6}")

            elif addr.family == psutil.AF_LINK:
                # La dirección MAC identifica físicamente la tarjeta de red
                # Es única en el mundo (teóricamente) y no cambia con el SO
                print(f"      MAC      : {addr.address}")


# --- Sección 7: Usuarios conectados ------------------------------------------
def mostrar_usuarios():
    """Muestra los usuarios actualmente conectados al sistema."""
    seccion("Usuarios Conectados", "👤")

    # users() devuelve una lista de usuarios con sesión activa
    # Cada entrada tiene: name, terminal, host, started, pid
    usuarios = psutil.users()

    if not usuarios:
        print("   No hay usuarios con sesión activa detectados.")
        return

    print(f"   {'Usuario':<20} {'Terminal':<12} {'Desde':<20} {'Host'}")
    print(f"   {'─'*20} {'─'*12} {'─'*20} {'─'*15}")

    for u in usuarios:
        # started es un timestamp UNIX — lo convertimos a fecha legible
        inicio = datetime.datetime.fromtimestamp(u.started).strftime("%Y-%m-%d %H:%M")
        host   = u.host if u.host else "local"
        term   = u.terminal if u.terminal else "N/A"
        print(f"   {u.name:<20} {term:<12} {inicio:<20} {host}")


# --- Sección 8: Resumen ejecutivo --------------------------------------------
def mostrar_resumen():
    """Muestra un resumen compacto con los datos más relevantes del sistema."""
    seccion("Resumen Ejecutivo", "📌")

    ram      = psutil.virtual_memory()
    cpu_n    = psutil.cpu_count(logical=True)
    cpu_f    = psutil.cpu_freq()
    boot_ts  = psutil.boot_time()
    dias_up  = int((time.time() - boot_ts) // 86400)
    sistema  = platform.system()
    hostname = socket.gethostname()

    # Espacio total en disco (suma de particiones no virtuales)
    total_disco = 0
    for p in psutil.disk_partitions(all=False):
        try:
            total_disco += psutil.disk_usage(p.mountpoint).total
        except Exception:
            pass

    # Nombre de CPU
    cpu_nombre = platform.processor() or "N/A"
    if not cpu_nombre or cpu_nombre == 'x86_64':
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for linea in f:
                    if 'model name' in linea:
                        cpu_nombre = linea.split(':')[1].strip()
                        break
        except Exception:
            pass

    print(f"""
   ┌─────────────────────────────────────────────────────┐
   │  🏠 Equipo   : {hostname:<37}│
   │  💻 SO       : {(sistema + ' ' + platform.release()):<37}│
   │  🧠 CPU      : {cpu_nombre[:37]:<37}│
   │  🔩 Núcleos  : {str(cpu_n) + ' lógicos':<37}│
   │  💾 RAM      : {bytes_a_legible(ram.total):<37}│
   │  💽 Disco    : {bytes_a_legible(total_disco) + ' (total)':<37}│
   │  ⏱️ Uptime   : {str(dias_up) + ' días desde el último arranque':<37}│
   └─────────────────────────────────────────────────────┘""")


# --- Función principal -------------------------------------------------------
def mostrar_sistema_info():
    """Ejecuta todas las secciones del informe en orden."""

    # Limpiamos la pantalla antes de mostrar el informe completo
    os.system('cls' if os.name == 'nt' else 'clear')

    mostrar_encabezado()
    mostrar_so()
    mostrar_cpu()
    mostrar_ram()
    mostrar_almacenamiento()
    mostrar_red()
    mostrar_usuarios()
    mostrar_resumen()

    # Pie del informe
    print("\n" + "=" * 65)
    print("   ✅ Informe completado. Este script NO monitoriza en tiempo real.")
    print("      Para monitorización continua usa los scripts específicos")
    print("      o el menú principal: python3 menu.py")
    print("=" * 65)
    print()


# --- Punto de entrada ---------------------------------------------------------
# sistema_info.py NO tiene bucle while True porque no es un monitor.
# Se ejecuta una vez, muestra el informe completo y termina.
# Es el único script de la colección que funciona así.

if __name__ == "__main__":
    mostrar_sistema_info()
