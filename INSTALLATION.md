# Installation and runbook

This guide lists commands to **install dependencies**, **build** the TensorRT plugin, and **start or stop** the ANPR stack. Adjust paths to match your machine (the repo includes example paths under `/home/jbmai/...` that you may replace or symlink).

---

## 1. Prerequisites

- **Linux** with **NVIDIA GPU**, **CUDA**, and **TensorRT** installed (match versions to your Jetson image or PC).
- **Python 3** (3.8+ typical).
- **Build tools**: `g++`, `make`, `nvcc` (CUDA toolkit).

---

## 2. Get the project and enter the directory

```bash
cd /path/to/ANPR
```

Replace `/path/to/ANPR` with the folder that contains `run.py`, `start.sh`, and `plugins/`.

---

## 3. Build the TensorRT YOLO plugin

The inference code loads `plugins/libyolo_layer.so`. Build it from the project root:

```bash
cd plugins
make
cd ..
```

If `make` fails, open `plugins/Makefile` and adjust `TENSORRT`, CUDA, and `NVCC` paths to your install locations. On some systems you can pass compute capability explicitly:

```bash
cd plugins
make computes=72
cd ..
```

After a successful build, `plugins/libyolo_layer.so` must exist.

---

## 4. Python dependencies

### Main ANPR pipeline (`run.py`, `qr_anpr_mapping.py`, etc.)

Install the **same stack** your device uses: at minimum **OpenCV**, **NumPy**, **PyCUDA**, **TensorRT Python API**. Exact package names depend on Jetson vs x86 (e.g. `pip` wheels vs `apt` from NVIDIA).

Example (only if you use pip for generic packages; **TensorRT/CUDA often come from the system or NVIDIA SDK**):

```bash
pip3 install opencv-python numpy
```

### Edge fleet service only (`anprservices/`)

```bash
cd anprservices
pip3 install -r requirements.txt
cd ..
```

---

## 5. Configuration (before first run)

1. Edit **`config/config.json`** — RTSP URL, crop, gate/lane IDs, API flags.
2. Edit **`config/model_config.json`** — paths to TensorRT engines and model files.
3. Edit **`config/integration_config.json`** — database path, QR readers, export/SFTP, logging paths.

Ensure **hardcoded paths** inside Python files (if any) point to your install root or use symlinks. See **`README.md`** for an overview.

---

## 6. Make shell scripts executable (once)

From the project root:

```bash
chmod +x start.sh stop.sh
```

---

## 7. Start all services (recommended)

Starts **three** background processes:

| Service        | Command run by script        | Purpose              |
|----------------|------------------------------|----------------------|
| `run`          | `python3 run.py`             | Main ANPR            |
| `qr_tagging`   | `python3 "qr_tagging .py"`   | QR tagging worker    |
| `db_to_sftp`   | `python3 db_to_sftp_service.py` | Export + upload  |

```bash
./start.sh
```

**Optional — custom log directory for service logs** (default is `/home/jbmai/PFS/Logs/services` if unset):

```bash
export ANPR_SERVICE_LOG_DIR="/your/custom/logs/services"
./start.sh
```

Logs are written as:

- `$ANPR_SERVICE_LOG_DIR/run.log`
- `$ANPR_SERVICE_LOG_DIR/qr_tagging.log`
- `$ANPR_SERVICE_LOG_DIR/db_to_sftp.log`

PID files are stored under **`pids/`** in the project root (`run.pid`, `qr_tagging.pid`, `db_to_sftp.pid`).

---

## 8. Stop all services

```bash
./stop.sh
```

This stops processes recorded in `pids/*.pid` and also cleans up orphan `python3` processes that match `run.py`, `qr_tagging .py`, or `db_to_sftp_service.py` with this project directory as the current working directory.

---

## 9. Start or stop components manually (foreground)

Use these when debugging. Run from the **project root** so `./plugins/libyolo_layer.so` loads correctly.

**Main ANPR only**

```bash
python3 run.py
```

**QR tagging only** (filename contains a space)

```bash
python3 "qr_tagging .py"
```

**DB → CSV → SFTP worker only**

```bash
python3 db_to_sftp_service.py
```

Stop foreground processes with **Ctrl+C**.

---

## 10. Optional: `anpr.sh` pattern

`anpr.sh` in the repo runs `send_data.py` in the background and then `run.py` in the foreground. **Edit the `cd` path inside `anpr.sh`** to your install directory before use:

```bash
chmod +x anpr.sh
./anpr.sh
```

Stop the foreground process with **Ctrl+C**; stop the background `send_data.py` with `kill` using its PID if needed.

---

## 11. Optional: Docker for `anprservices` only

From the `anprservices` directory (adjust image name/tag as you like):

```bash
cd anprservices
docker build -t anprservices .
docker run --rm -p 8001:8001 anprservices
```

This runs `main.py` per the `Dockerfile`; it is **not** the same as `./start.sh` for the full ANPR pipeline.

---

## Quick reference

| Action              | Command |
|---------------------|---------|
| Build plugin        | `cd plugins && make && cd ..` |
| Start all (background) | `./start.sh` |
| Stop all            | `./stop.sh` |
| Run ANPR only (foreground) | `python3 run.py` |
| Custom service logs | `export ANPR_SERVICE_LOG_DIR="/path"` then `./start.sh` |

For architecture and file layout, see **`README.md`**.
