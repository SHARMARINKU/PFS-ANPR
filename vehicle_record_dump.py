import os
import csv
from datetime import datetime
from sftp import upload_old_excel_files  # keep your upload function as is

try:
    from qr_anpr_mapping import on_anpr_boom
except ImportError:
    on_anpr_boom = None

# Base directory inside the user's home directory
HOME_DIR = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME_DIR, "report", "vehicle_report")
os.makedirs(BASE_DIR, exist_ok=True)

PLANT_NAME = "Lalru LPG Plant"
PLANT_CODE = 5120

# Globals to keep state
current_slot_file = None
s_no = 1


def get_15min_slot():
    """Get current 15-min block timestamp formatted as YYYY-MM-DD_HH-MM"""
    now = datetime.now()
    minute_slot = (now.minute // 15) * 15
    block_time = now.replace(minute=minute_slot, second=0, microsecond=0)
    return block_time.strftime("%Y-%m-%d_%H-%M")


def ensure_csv_file():
    """
    Ensures that the CSV file for the current 15-minute slot exists.
    Creates it and writes header if missing.
    """
    global current_slot_file, s_no

    slot_name = get_15min_slot()
    file_name = f"{slot_name}.csv"
    full_path = os.path.join(BASE_DIR, file_name)

    if not os.path.exists(full_path):
        with open(full_path, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["S.No.", "Date", "Time", "Plant Name", "Plant Code", "Truck Number", "Boom No."])
        print(f"🆕 Created new CSV with header: {file_name}")
        s_no = 1
    else:
        # File exists, find last serial number
        with open(full_path, mode='r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            if len(rows) > 1:
                try:
                    last_sno = int(rows[-1][0])
                    s_no = last_sno + 1
                except Exception:
                    s_no = 1
            else:
                s_no = 1

    current_slot_file = full_path


def csv_dump(vehicle_no, boom_value):
    """
    Add a new entry to the current CSV file.
    Switches file if 15-min slot changed.
    """
    global current_slot_file, s_no

    current_slot = get_15min_slot()
    expected_file = os.path.join(BASE_DIR, f"{current_slot}.csv")

    # If slot changed, upload old and reset file
    if current_slot_file != expected_file:
        if current_slot_file:
            print(f"Uploading old CSV file: {current_slot_file}")
            upload_old_excel_files()
            print("✔ Old CSV files uploaded successfully")

        ensure_csv_file()  # Reset to new slot file

    now = datetime.now()
    with open(current_slot_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            s_no,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            PLANT_NAME,
            PLANT_CODE,
            vehicle_no,
            boom_value
        ])
    print(f"✔ Added {vehicle_no} at row {s_no} in {os.path.basename(current_slot_file)}")
    if on_anpr_boom:
        try:
            on_anpr_boom(vehicle_no, boom_value)
        except Exception as ex:
            print(f"⚠ qr_anpr_mapping ANPR hook: {ex}")
    s_no += 1


# If you want to test, uncomment this block:
# if __name__ == "__main__":
#     for i in range(3):
#         csv_dump(f"VEHICLE{i+1}", f"Boom-{i+1}")
#         import time; time.sleep(1)
