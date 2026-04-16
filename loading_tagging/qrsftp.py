import os
import glob
import paramiko

# ---------- SFTP Credentials ----------
HOST = "52.172.188.62"
PORT = 888
USERNAME = "pfs-nprod"
PASSWORD = "auJUWwn9c781LSPtph6"

# ---------- Folders ----------
EXCEL_FOLDER = "QR_history"
REMOTE_EXCEL_PATH = "/upload/push"

# ------------------------------------------------------------
# 1️⃣ UPLOAD OLD EXCEL FILES ONLY
# ------------------------------------------------------------
def upload_old_excel_files():

    ssh = paramiko.SSHClient()
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, PORT, USERNAME, PASSWORD)
        sftp = ssh.open_sftp()

        # Ensure Excel remote path exists
        try:
            sftp.chdir(REMOTE_EXCEL_PATH)
        except IOError:
            sftp.mkdir(REMOTE_EXCEL_PATH)

        excel_files = sorted(glob.glob(os.path.join(EXCEL_FOLDER, "*.xlsx")))
        files_to_upload = excel_files[:-1]  # Keep last active file untouched

        if not files_to_upload:
            print("ℹ️ No old Excel files to upload")
            return

        for file_path in files_to_upload:
            file_name = os.path.basename(file_path)
            remote_path = os.path.join(REMOTE_EXCEL_PATH, file_name)

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

