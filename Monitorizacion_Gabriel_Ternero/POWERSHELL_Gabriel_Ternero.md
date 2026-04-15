# 🧩 POWERSHELL (Windows) | Gabriel Ternero

Sabemos que PowerShell es la herramienta nativa de Windows por excelencia y es fundamental para la monitorización en el perfil de cualquier administrador de sistemas; sin embargo, antes de comenzar con los scripts, veamos todo aquello que lleva integrado en Windows, y eso es a través de tres fuentes principales, que veremos a continuación:

| Fuente | ¿Qué es? | Analogía |
| --- | --- | --- |
| **CIM / WMI** | Base de datos del hardware que mantiene Windows | El "historial médico" del equipo |
| **Contadores de rendimiento** | Métricas en tiempo real del sistema | El "cuadro de mandos" del coche |
| **Cmdlets nativos** | Comandos propios de PowerShell | Las herramientas de la caja |

Vamos a definir y generar la estructura que desarrollaremos:

## Mapa para la monitorización

```powershell
📁 monitor_ps\
   ├── menu.ps1
   ├── cpu_monitor.ps1
   ├── memoria_monitor.ps1
   ├── almacenamiento_monitor.ps1
   ├── temperatura_monitor.ps1
   ├── gpu_monitor.ps1
   ├── red_monitor.ps1
   ├── bateria_monitor.ps1
   ├── ventiladores_monitor.ps1
   ├── procesos_monitor.ps1
   └── sistema_info.ps1
```

Como podemos ver, tenemos el script `menu.ps1`, que servirá como **panel de control** para seleccionar de forma práctica y didáctica cualquiera de los scripts. Pero ¡ojo!, cada script es autónomo, es decir, puede ser ejecutado independientemente.

Esta es una idea muy didáctica que nos mostró nuestro profesor `Jesús Niño C.`. 👈😉✨

>💡 **Una cosita muy importante antes de empezar** ⚠️
>
> **PowerShell** en Windows tiene una política de seguridad llamada **Execution Policy** que por defecto **impide ejecutar scripts `.ps1`**.
>
> Es lo primero que hay que tener muy en cuenta. 🫵😎✨

Entonces, hay que ejecutar esto **una sola vez** como Administrador y para hacerlo, abrimos nuestro `PowerShell ISE` (como administrador preferentemente).

> **LA PRIMERA VEZ** escribimos: 👇

```powershell
# 1ro. Ver la política actual
Get-ExecutionPolicy

# 2do. Si PowerShell bloquea la ejecución, abre PowerShell como
# Administrador y ejecuta una sola vez (LA PRIMERA VEZ).
# Esta acción permite scripts locales (lo mínimo necesario, lo más seguro posible)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

| Política | Significado |
| --- | --- |
| `Restricted` | No permite ningún script (defecto en Windows Home) |
| `RemoteSigned` | Permite scripts locales, bloquea los descargados sin firma ✅ |
| `Unrestricted` | Permite todo → no recomendado |

---

### Diferencias clave respecto a `Python`

| Concepto Python | Equivalente PowerShell |
| --- | --- |
| `import psutil` | `Get-CimInstance Win32_Processor` |
| `while True:` | `while($true)` |
| `time.sleep(2)` | `Start-Sleep -Seconds 2` |
| `print()` | `Write-Host` |
| `os.system('clear')` | `Clear-Host` |
| `def funcion():` | `function Nombre-Funcion {}` |
| `try/except` | `try/catch` |
| Colores ANSI `\033[92m` | `-ForegroundColor Green` |
| `if __name__ == "__main__"` | No necesario → cada `.ps1` es autónomo |

---

### ADVERTENCIAS

- En Windows 11 Home **"No está firmado digitalmente":** `RemoteSigned` no es suficiente si el archivo fue creado fuera del equipo (descargado, copiado...). Windows lo marca como "de origen externo". La solución más limpia y segura para un entorno versátil es añadir al inicio de cada script:

    ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
   # Scope Process solo afecta a la sesión actual, no cambia nada
   # permanente en el sistema. Es la opción más segura.
    ```

- **Tildes y caracteres especiales**: En `PowerShell` sobre Windows en español los acentos generan símbolos extraños. Por tal motivo, eliminaremos **todas las tildes** de comentarios y textos visibles, esta acción no afecta a la funcionalidad, pero sí evitará muchos problemas. También no usaremos caracteres Unicode, solo ASCII puro.

> 💡 Dato curioso, **¿Por qué las tildes dan problemas?** `PowerShell` guarda y lee los archivos `.ps1` con la codificación del sistema. En Windows en español esa codificación es Windows-1252 (también llamada "Latin-1"), que no es lo mismo que UTF-8. Los caracteres con tilde y los símbolos Unicode como `█` existen en UTF-8 pero no en Windows-1252, así que aparecen como símbolos extraños o directamente rompen el parser. La solución definitiva es evitarlos por completo.

- Sobre temperaturas y ventiladores ¡ojo! : Igual que con Python en Windows, `PowerShell` **tampoco puede leer temperaturas ni ventiladores de forma nativa fiable**. WMI tiene una clase `MSAcpi_ThermalZoneTemperature` pero en la mayoría de equipos devuelve datos incorrectos o simplemente nada. Vamos a gestionarlo del mismo modo: detectándolo y sugiriendo alternativas.

Ahora que ya tenemos todas las consideraciones cubiertas, pasamos al desarrollo. 💪💫

---

### Los siguientes, SÍ funcionan perfectamente en `PowerShell`

- *CPU:* uso total, por núcleo, frecuencia, carga
- *Memoria RAM* y página virtual (swap de Windows)
- *Almacenamiento:* espacio, velocidad I/O
- *Red:* interfaces, velocidad, estadísticas
- *Batería:* nivel, estado, tiempo estimado
- *Procesos:* top por CPU y RAM, estados
- *Sistema:* info estática completa via WMI/CIM
- *GPU:* uso y memoria vía WMI (más limitado que nvidia-smi)

---

## Scripts con PowerShell en Windows

👉🏻 [MENÚ PRINCIPAL (el que ejecuta todos)](POWERSHELL_Gabriel_Ternero/MENU_PRINCIPAL.md)

[1. cpu_monitor.ps1](POWERSHELL_Gabriel_Ternero/cpu_monitor_ps1.md)

[2. memoria_monitor.ps1](POWERSHELL_Gabriel_Ternero/memoria_monitor_ps1.md)

[3. almacenamiento_monitor.ps1](POWERSHELL_Gabriel_Ternero/almacenamiento_monitor_ps1.md)

[4. temperatura_monitor.ps1](POWERSHELL_Gabriel_Ternero/temperatura_monitor_ps1.md)

[5. gpu_monitor.ps1](POWERSHELL_Gabriel_Ternero/gpu_monitor_ps1.md)

[6. red_monitor.ps1](POWERSHELL_Gabriel_Ternero/red_monitor_ps1.md)

[7. batería_monitor.ps1](POWERSHELL_Gabriel_Ternero/batería_monitor_ps1.md)

[8. ventiladores_monitor.ps1](POWERSHELL_Gabriel_Ternero/ventiladores_monitor_ps1.md)

[9. procesos_monitor.ps1](POWERSHELL_Gabriel_Ternero/procesos_monitor_ps1.md)

[10. sistema_info.ps1](POWERSHELL_Gabriel_Ternero/sistema_info_ps1.md)

---

**Bonus:** [`LibreHardwareMonitor` en Windows](POWERSHELL_Gabriel_Ternero/LibreHardwareMonitor.md)
