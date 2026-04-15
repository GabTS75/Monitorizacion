# Monitorización (completo) | Gabriel Ternero

## 🖥️ Guía completa de monitorización del hardware de un PC

Lista **completa y exhaustiva** de todo lo que se debería cubrir en una **guía completa de monitorización del hardware de un ordenador:**

## 🧠 1. CPU (Procesador)

- Uso total (%) y por núcleo
- Frecuencia actual (MHz/GHz) por núcleo
- Número de núcleos físicos y lógicos (threads)
- Carga media del sistema (load average: 1, 5, 15 min)
- Tiempo en cada estado: user, system, idle, iowait, irq, softirq, steal
- Cambios de contexto por segundo
- Interrupciones por segundo

---

## 🧩 2. Memoria RAM

- Total, usada, libre, disponible
- Memoria en caché y buffers
- Memoria compartida (shared)
- Porcentaje de uso
- Swap: total, usada, libre, porcentaje

---

## 💾 3. Almacenamiento (Discos)

- Espacio total, usado y libre por partición/mountpoint
- Porcentaje de uso por partición
- Inodos usados/libres (en Linux, fundamentales)
- Velocidad de lectura/escritura (MB/s)
- Operaciones de I/O por segundo (IOPS)
- Tiempo de espera de I/O (I/O wait %)
- Estado S.M.A.R.T. del disco (salud del dispositivo físico)
- Temperatura del disco

---

## 🌡️ 4. Temperaturas

- Temperatura de cada núcleo de CPU
- Temperatura de la CPU (paquete total)
- Temperatura del disco duro / SSD
- Temperatura de la GPU
- Temperatura de la placa base (motherboard)
- Temperatura de otros sensores del sistema (chipset, VRMs)

---

## 🎮 5. GPU (Tarjeta Gráfica)

- Uso de GPU (%)
- Memoria de GPU: total, usada, libre
- Temperatura de GPU
- Velocidad del ventilador de GPU (RPM)
- Frecuencia de núcleo y memoria de GPU
- Consumo energético de GPU (W)
- Procesos que usan la GPU

---

## 🌐 6. Red (Network)

- Interfaces disponibles (eth0, wlan0, lo, etc.)
- Bytes/paquetes enviados y recibidos por interfaz
- Velocidad actual de subida y bajada (KB/s o MB/s)
- Total acumulado de tráfico (desde el arranque)
- Errores y paquetes descartados por interfaz
- Estado de cada interfaz (UP/DOWN)
- Dirección IP, MAC, MTU por interfaz

---

## ⚡ 7. Energía y Batería *(si es portátil)*

- Estado: cargando / descargando / cargado
- Porcentaje de batería
- Tiempo estimado restante
- Ciclos de carga acumulados
- Voltaje y capacidad actual vs. capacidad de diseño
- Consumo del sistema (W) *(si hay sensor disponible)*

---

## 🔄 8. Ventiladores (Cooling)

- Velocidad de cada ventilador en RPM (CPU fan, case fans, GPU fan)
- Estado de los ventiladores (activo/inactivo)

---

## 🏃 9. Procesos del Sistema

- Número total de procesos en ejecución, durmiendo, zombies
- Top N procesos por uso de CPU
- Top N procesos por uso de RAM
- Top N procesos por uso de I/O de disco
- PIDs, usuarios propietarios y comandos

---

## ⏱️ 10. Tiempo de Sistema (Uptime)

- Tiempo desde el último arranque (días, horas, minutos)
- Fecha y hora del último arranque

---

## 🖥️ 11. Información estática del hardware *(útil como cabecera del reporte)*

- Hostname y sistema operativo
- Versión del kernel
- Arquitectura del sistema
- Modelo de CPU y GPU
- Marca/modelo de la placa base
- BIOS/UEFI versión y fecha
- Total de RAM instalada y tipo (DDR4, DDR5…)

---

## 📋 Resumen visual

| Categoría | Herramientas Linux útiles |
| --- | --- |
| CPU | `top`, `mpstat`, `/proc/stat` |
| RAM | `free`, `/proc/meminfo` |
| Disco (espacio) | `df`, `du` |
| Disco (I/O) | `iostat`, `iotop` |
| S.M.A.R.T. | `smartctl` |
| Temperaturas | `sensors` (lm-sensors), `hddtemp` |
| GPU | `nvidia-smi`, `rocm-smi` |
| Red | `ip`, `ifstat`, `/proc/net/dev` |
| Batería | `upower`, `/sys/class/power_supply` |
| Ventiladores | `sensors` (lm-sensors) |
| Procesos | `ps`, `top`, `pidstat` |
| Info estática | `dmidecode`, `lscpu`, `lshw` |

> 💡 **Analogía:** Monitorizar el hardware es como ser el médico de un paciente (tu PC). Tienes que revisar el **pulso** (CPU), la **presión** (RAM), la **temperatura corporal** (sensores térmicos), el **estado de los pulmones** (ventiladores), el **peso** (espacio en disco) y la **dieta energética** (batería/consumo). Si solo revisas uno, puedes perderte el diagnóstico real.
>

Evidentemente estamos considerando "monitorización", es decir, debemos separar lo que es "obtener información estática" como tal, de lo que es "monitorizar", saber cuál es la diferencia entre **obtener info** (snapshot) vs **monitorizar** (continuo en el tiempo), **puede ser determinante**.

Pero tranquilos, vamos a verlo por partes. 😉👍

---

## ⭐ Lenguaje de programación ideal para la monitorización

Lo primero que debemos definir es tener claro que lenguaje de programación elegir, puesto que se puede desarrollar en varios, depende del nivel y el objetivo, aunque tenemos uno bastante claro para esta finalidad “la monitorización”.

### 🥇 Python: El más adecuado para este propósito

| **Librería nativa** | `psutil` fue diseñada **específicamente** para monitorizar hardware multiplataforma |
| --- | --- |
| **Legibilidad** | Código limpio, ideal para Administradores de Sistemas y Redes |
| **Flexibilidad** | Puedes generar logs, alertas, gráficas, informes HTML... etc. |
| **Multiplataforma** | Funciona en Linux, Windows y macOS sin cambiar el código, un plus! |
| **Ecosistema** | Se integra con `smtplib` (emails), `matplotlib` (gráficas), etc. |

### 🥈 PowerShell: El mejor en Windows

Sin embargo también veremos cómo realizarlo en `PowerShell` de Windows, puesto que sabemos que es el **Sistema Operativo** con mayor porcentaje de uso global, en todas sus versiones, **Home**, **Pro** y **Server**, ¿comenzamos? 🫵😎✨

---

## Python & PowerShell

[🧩 PYTHON | Gabriel Ternero](Monitorizacion_Gabriel_Ternero/PYTHON_Gabriel_Ternero.md)

[🧩 POWERSHELL (Windows) | Gabriel Ternero](Monitorizacion_Gabriel_Ternero/POWERSHELL_Gabriel_Ternero.md)

> Agradecimiento especial a nuestro porfesor **Jesús Ninoc** por el esfuerzo y sus consejos sobre el sector, conocer la importancia de la monitorización me ha servido para estar un paso más cerca de mi objetivo. 💫
