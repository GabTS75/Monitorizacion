# 🧩 PYTHON | Gabriel Ternero

## Esquema de scripts

Vamos a usar **Python +** `psutil` como base, con este esquema por scripts:

```python
monitor/
├── cpu_monitor.py
├── memoria_monitor.py
├── almacenamiento_monitor.py
├── temperatura_monitor.py
├── gpu_monitor.py
├── red_monitor.py
├── bateria_monitor.py
├── ventiladores_monitor.py
├── procesos_monitor.py
└── sistema_info.py   ←   información estática (esto sí es "obtener info")
```

Cada script será **autónomo**, con un **intervalo de muestreo configurable** y preparado para que luego se pueda unificar en un `monitor_completo.py`, que veremos al final de todos.

Además, haremos un `menu.py` que actúe como "panel de control" para lanzar cualquiera de los scripts.

Esta es una idea muy didáctica que nos mostró nuestro profesor `Jesús Ninoc`. 👈😉✨

>💡 Para ejecutar archivos de Python, primero debemos verificar si lo tenemos instalado, preguntando por la versión, si no lo tenemos, procedemos a instalar siguiendo los pasos.

## Windows

```bash
# Abrimos el CMD y escribimos:
python --version

# Si no lo tenemos, instalamos Python 3 siguiendo los pasos
# Abre el navegador y descarga el ejecutable desde python.org,
# ejecuta el instalador y asegurate de marcar "Add Python to PATH"
# antes de instalar.

# Luego, volvemos al CMD e instalamos psutil usando pip (primera vez).
pip install psutil

# Pero, si nos informa que ya lo tiene y se puede actualizar, hacemos:
python -m pip install --upgrade pip

# Ejecutar el script desde el terminal.
python cpu_monitor.py
```

## Linux

```bash
# Abrimos el Terminal (Ctrl + Alt + T) en tu Linux y escribimos:
python --version

# Por lo general viene siempre pre-instalado Python en Linux
# Ahora, instalamos psutil (pip primero y luego psutil)
sudo apt install python3-pip
sudo apt-get install python3-psutil

# Ejecutar el script en el terminal
python3 cpu_monitor.py
```

---

## Scripts en Python

👉🏻 [MENÚ PRINCIPAL (el que ejecuta todos)](PYTHON_Gabriel_Ternero/MENU_PRINCIPAL.md)

[1. cpu_monitor.py](PYTHON_Gabriel_Ternero/cpu_monitor_py.md)

[2. memoria_monitor_py](PYTHON_Gabriel_Ternero/memoria_monitor_py.md)

[3. almacenamiento_monitor.py](PYTHON_Gabriel_Ternero/almacenamiento_monitor_py.md)

[4. temperatura_monitor.py](PYTHON_Gabriel_Ternero/temperatura_monitor_py.md)

[5. gpu_monitor.py](PYTHON_Gabriel_Ternero/gpu_monitor_py.md)

[6. red_monitor.py](PYTHON_Gabriel_Ternero/red_monitor_py.md)

[7. bateria_monitor.py](PYTHON_Gabriel_Ternero/bateria_monitor_py.md)

[8. ventiladores_monitor.py](PYTHON_Gabriel_Ternero/ventiladores_monitor_py.md)

[9. procesos_monitor.py](PYTHON_Gabriel_Ternero/procesos_monitor_py.md)

[10. sistema_info.py (info estática)](PYTHON_Gabriel_Ternero/sistema_info_py.md)

---

✨
