

import os
import glob
import paramiko
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "integration_config.json")


def _load_sftp_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    sftp_cfg = cfg.get("sftp", {})
    return {
        "host": sftp_cfg.get("host", ""),
        "port": int(sftp_cfg.get("port", 22)),
        "username": sftp_cfg.get("username", ""),
        "password": sftp_cfg.get("password", ""),
        "remote_base_path": sftp_cfg.get("remote_base_path", "/upload/push"),
        "remote_subdir": sftp_cfg.get("remote_subdir", "qr_mapping"),
    }

# ---------- Folders ----------
EXCEL_FOLDER = "vehicle_history"
IMAGE_FOLDER = "ocr_frames"
REMOTE_EXCEL_PATH = "/upload/push"
REMOTE_IMAGE_PATH = "/upload/push/"

SENT_IMG_LOG = "sent_images.txt"
# ------------------------------------------------------------
# 1️⃣ UPLOAD OLD EXCEL FILES
# ------------------------------------------------------------
def upload_old_excel_files():
    sftp_cfg = _load_sftp_config()
    remote_excel_path = sftp_cfg["remote_base_path"]

    ssh = paramiko.SSHClient()
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            sftp_cfg["host"],
            sftp_cfg["port"],
            sftp_cfg["username"],
            sftp_cfg["password"],
        )
        sftp = ssh.open_sftp()

        # Ensure Excel remote path exists
        try:
            sftp.chdir(remote_excel_path)
        except IOError:
            sftp.mkdir(remote_excel_path)

        excel_files = sorted(glob.glob(os.path.join(EXCEL_FOLDER, "*.xlsx")))
        files_to_upload = excel_files[:-1]  # keep last active file

        if not files_to_upload:
            print("ℹ️ No old Excel files to upload")
            return

        for file_path in files_to_upload:
            file_name = os.path.basename(file_path)
            remote_path = os.path.join(remote_excel_path, file_name)

            print(f"📤 Uploading Excel: {file_name}")

            with open(file_path, "rb") as f:
                sftp.putfo(f, remote_path)

        print("✔ Uploaded all old Excel files")

    finally:
        try:
            sftp.close()
        except:
            pass
        ssh.close()


def upload_qr_mapping_csv(local_file: str, remote_subdir: str = "qr_mapping") -> None:
    """
    Upload a single CSV file (QR–vehicle mapping export) to SFTP.
    Remote path: REMOTE_EXCEL_PATH / remote_subdir / basename(local_file)
    """
    if not os.path.isfile(local_file):
        print(f"ℹ️ QR mapping file missing: {local_file}")
        return

    sftp_cfg = _load_sftp_config()
    remote_base_path = sftp_cfg["remote_base_path"]
    if not remote_subdir:
        remote_subdir = sftp_cfg["remote_subdir"]

    ssh = paramiko.SSHClient()
    sftp = None
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            sftp_cfg["host"],
            sftp_cfg["port"],
            sftp_cfg["username"],
            sftp_cfg["password"],
        )
        sftp = ssh.open_sftp()

        remote_dir = os.path.join(remote_base_path, remote_subdir).replace("\\", "/")
        try:
            sftp.chdir(remote_dir)
        except IOError:
            # Ensure parent then child
            try:
                sftp.chdir(remote_base_path)
            except IOError:
                sftp.mkdir(remote_base_path)
                sftp.chdir(remote_base_path)
            try:
                sftp.mkdir(remote_dir)
            except IOError:
                pass
            sftp.chdir(remote_dir)

        file_name = os.path.basename(local_file)
        remote_path = os.path.join(remote_dir, file_name).replace("\\", "/")
        print(f"📤 Uploading QR mapping CSV: {file_name}")
        with open(local_file, "rb") as f:
            sftp.putfo(f, remote_path)
        print(f"✔ Uploaded QR mapping CSV to {remote_path}")

    finally:
        try:
            if sftp:
                sftp.close()
        except Exception:
            pass
        try:
            ssh.close()
        except Exception:
            pass


# ------------------------------------------------------------
# 2️⃣ UPLOAD NEW IMAGES FROM DATE SUBFOLDERS
# ------------------------------------------------------------
def upload_new_images():
    sftp_cfg = _load_sftp_config()
    remote_image_path = sftp_cfg["remote_base_path"].rstrip("/") + "/"

    """
    Uploads any new image inside nested date folders like:
    images/2025-02-01/*.jpg
    images/2025-02-02/*.jpg
    """

    # Load already uploaded images
    sent_images = set()
    if os.path.exists(SENT_IMG_LOG):
        with open(SENT_IMG_LOG, "r") as f:
            sent_images = set(line.strip() for line in f.readlines())

    # Find all date subfolders inside /images
    date_folders = [
        os.path.join(IMAGE_FOLDER, d)
        for d in os.listdir(IMAGE_FOLDER)
        if os.path.isdir(os.path.join(IMAGE_FOLDER, d))
    ]

    # Collect all new images
    new_images = []
    for folder in date_folders:
        for img in os.listdir(folder):
            local_path = os.path.join(folder, img)
            relative_path = os.path.join(os.path.basename(folder), img)  # e.g. "2025-02-01/img1.jpg"

            if relative_path not in sent_images:
                new_images.append((local_path, relative_path))

    if not new_images:
        return  # nothing new

    ssh = paramiko.SSHClient()

    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            sftp_cfg["host"],
            sftp_cfg["port"],
            sftp_cfg["username"],
            sftp_cfg["password"],
        )

        sftp = ssh.open_sftp()

        # Ensure remote root image path exists
        try:
            sftp.chdir(remote_image_path)
        except IOError:
            sftp.mkdir(remote_image_path)

        # Upload images grouped by date
        for local_path, relative_path in new_images:

            date_folder = relative_path.split("/")[0]      # "2025-02-01"
            image_name = relative_path.split("/")[1]       # "imgname.jpg"

            remote_folder = os.path.join(remote_image_path, date_folder)

            # Ensure date folder exists on SFTP
            try:
                sftp.chdir(remote_folder)
            except IOError:
                sftp.mkdir(remote_folder)

            remote_file = os.path.join(remote_folder, image_name)

            print(f"📤 Uploading: {relative_path}")

            with open(local_path, "rb") as f:
                sftp.putfo(f, remote_file)

            # Mark as uploaded
            with open(SENT_IMG_LOG, "a") as log:
                log.write(relative_path + "\n")

            print(f"✔ Uploaded: {relative_path}")

    finally:
        try:
            sftp.close()
        except:
            pass
        ssh.close()
