import socket
import threading
import queue
import datetime
import time
import logging
import os
import json
from logging.handlers import TimedRotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "integration_config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


cfg = load_config()
QR_READERS = cfg.get("qr_readers", {}).get("devices", [])
PLANT_NAME = cfg.get("plant", {}).get("plant_name", "Plant")
PLANT_CODE = cfg.get("plant", {}).get("plant_code", "3101")
RETRY_DELAY = int(cfg.get("qr_readers", {}).get("retry_delay_sec", 5))
SOCKET_TIMEOUT = int(cfg.get("qr_readers", {}).get("socket_timeout_sec", 10))
LOG_CFG = cfg.get("logging", {})
LOG_BASE_DIR = LOG_CFG.get("base_dir", "/home/jbmai/PFS/Logs")
QR1_LOG_NAME = LOG_CFG.get("qr1_log_name", "QR-1.log")
QR2_LOG_NAME = LOG_CFG.get("qr2_log_name", "QR-2.log")
QR_MAIN_LOG_NAME = LOG_CFG.get("qr_main_log_name", "QR-main.log")
QR_LINES_ROOT_RELPATH = LOG_CFG.get("qr_lines_root_relpath", "QR")

qr_queue = queue.Queue()

try:
    os.makedirs(LOG_BASE_DIR, exist_ok=True)
except Exception as e:
    print(f"[WARN] Could not create QR log dir '{LOG_BASE_DIR}': {e}. File logging disabled.")
    LOG_BASE_DIR = None
LOG_FORMAT = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

main_logger = logging.getLogger("qr_main")
main_logger.setLevel(logging.INFO)
main_logger.propagate = False
if not main_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(LOG_FORMAT)
    main_logger.addHandler(console_handler)
    if LOG_BASE_DIR:
        main_file_handler = TimedRotatingFileHandler(
            os.path.join(LOG_BASE_DIR, QR_MAIN_LOG_NAME), when="midnight", interval=1
        )
        main_file_handler.setFormatter(LOG_FORMAT)
        main_file_handler.suffix = "%Y%m%d"
        main_logger.addHandler(main_file_handler)

qr_line_loggers = {}


def _line_folder_name(line_name: str) -> str:
    return f"{line_name} QR"


def _get_or_create_line_logger(line_name: str):
    if line_name in qr_line_loggers:
        return qr_line_loggers[line_name]

    logger_obj = logging.getLogger(f"qr_packets_{line_name}")
    logger_obj.setLevel(logging.INFO)
    logger_obj.propagate = False
    if not logger_obj.handlers:
        if LOG_BASE_DIR:
            line_dir = os.path.join(LOG_BASE_DIR, QR_LINES_ROOT_RELPATH, _line_folder_name(line_name))
            os.makedirs(line_dir, exist_ok=True)
            file_path = os.path.join(line_dir, "qr.log")
            file_handler = TimedRotatingFileHandler(file_path, when="midnight", interval=1)
            file_handler.setFormatter(LOG_FORMAT)
            file_handler.suffix = "%Y%m%d"
            logger_obj.addHandler(file_handler)
    qr_line_loggers[line_name] = logger_obj
    return logger_obj


for reader in QR_READERS:
    line_name = reader.get("name", "").strip()
    if not line_name:
        continue
    _get_or_create_line_logger(line_name)

# Backward-compatible flat logs if someone still monitors old files.
legacy_line_map = {"LINE-1": QR1_LOG_NAME, "LINE-2": QR2_LOG_NAME}
for line_name, file_name in legacy_line_map.items():
    if line_name not in qr_line_loggers:
        continue
    if not LOG_BASE_DIR:
        continue
    file_path = os.path.join(LOG_BASE_DIR, file_name)
    handler_exists = any(
        getattr(h, "baseFilename", "") == file_path for h in qr_line_loggers[line_name].handlers
    )
    if not handler_exists:
        legacy_handler = TimedRotatingFileHandler(file_path, when="midnight", interval=1)
        legacy_handler.setFormatter(LOG_FORMAT)
        legacy_handler.suffix = "%Y%m%d"
        qr_line_loggers[line_name].addHandler(legacy_handler)


def connect_socket(ip, port):
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((ip, port))
            main_logger.info("[CONNECTED] %s:%s", ip, port)
            return sock
        except Exception as e:
            main_logger.error("[SOCKET ERROR] %s:%s -> %s", ip, port, e)
            time.sleep(RETRY_DELAY)


def reader_thread(reader):
    ip = reader["ip"]
    port = reader["port"]
    line_name = reader["name"]

    while True:
        sock = None

        try:
            # CONNECT
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(None)  # BLOCKING MODE (industrial stable)
            sock.connect((ip, port))

            main_logger.info("[CONNECTED] %s (%s:%s)", line_name, ip, port)

            buffer = ""

            while True:
                data = sock.recv(1024)

                # If recv returns empty → connection closed
                if not data:
                    raise ConnectionError("Device closed connection")

                buffer += data.decode(errors="ignore")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    qr = line.strip()

                    if qr:
                        record = {
                            "timestamp": datetime.datetime.now(),
                            "line": line_name,
                            "plant_name": PLANT_NAME,
                            "plant_code": PLANT_CODE,
                            "qr": qr
                        }

                        qr_queue.put(record)
                        line_logger = _get_or_create_line_logger(line_name)
                        line_logger.info(
                            "packet_qr=%s line=%s plant_code=%s timestamp=%s",
                            qr,
                            line_name,
                            PLANT_CODE,
                            record["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        )
                        main_logger.info(
                            "[QR RECEIVED] line=%s qr=%s queue_size=%s",
                            line_name,
                            qr,
                            qr_queue.qsize(),
                        )

        except (ConnectionError, socket.error, OSError) as e:
            main_logger.warning("[DISCONNECTED] %s -> %s", line_name, e)
            main_logger.info("[RECONNECTING] %s in %s sec...", line_name, RETRY_DELAY)
            time.sleep(RETRY_DELAY)

        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass


def start():
    try:
        from qr_anpr_mapping import start_qr_consumer

        start_qr_consumer(qr_queue)
    except Exception as e:
        main_logger.exception("Could not start QR->ANPR DB consumer: %s", e)

    for reader in QR_READERS:
        t = threading.Thread(target=reader_thread, args=(reader,), daemon=True)
        t.start()


if __name__ == "__main__":
    start()
    while True:
        time.sleep(3600)

