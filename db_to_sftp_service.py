import logging
import time

from qr_anpr_mapping import (
    export_pending_to_csv_and_upload,
    get_export_interval_sec,
    init_db,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_forever() -> None:
    init_db()

    # Startup behavior: always flush pending (previously unsent) events first.
    try:
        startup_export = export_pending_to_csv_and_upload()
        if startup_export:
            logger.info("Startup pending export completed: %s", startup_export)
        else:
            logger.info("Startup pending export: no unsent events.")
    except Exception as e:
        logger.exception("Startup pending export failed: %s", e)

    interval = get_export_interval_sec(3600.0)
    logger.info(
        "DB->SFTP export service started. Scheduled interval: %s seconds",
        interval,
    )

    while True:
        interval = get_export_interval_sec(3600.0)
        time.sleep(interval)
        try:
            exported_path = export_pending_to_csv_and_upload()
            if exported_path:
                logger.info("Exported and uploaded: %s", exported_path)
        except Exception as e:
            logger.exception("Export cycle failed: %s", e)
        time.sleep(interval)


if __name__ == "__main__":
    run_forever()

