
import json
import logging
import shutil
import tempfile

from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ProcessPoolExecutor
from langdetect import detect, LangDetectException


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

folder_aug = Path("C:/Users/MCerr/CSCourses/MQP/RC_2017-08")

file_aug = folder_aug / "RC_2017-08.ndjson"

output_file = folder_aug / "RC_2017-08_filtered.ndjson"

log_file = folder_aug / "processing.log"

NUM_WORKERS = 8
CHUNK_SIZE = 5000

selected_date = datetime(
    2017, 8, 15, tzinfo=timezone.utc
)

start_date = selected_date - timedelta(days=3)
end_date = selected_date + timedelta(weeks=3)


# --------------------------------------------------
# LOGGING CONFIGURATION
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(processName)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# FILTER FUNCTIONS
# --------------------------------------------------

def valid_body(body):

    if not isinstance(body, str):
        return False

    body = body.strip()

    if len(body) <= 5:
        return False

    # Require at least one alphanumeric character
    if not any(char.isalnum() for char in body):
        return False

    return True


def english_only(body):

    try:
        return detect(body) == "en"

    except LangDetectException:
        return False


def valid_date(record):

    timestamp = record.get("created_utc")

    if timestamp is None:
        return False

    try:
        record_date = datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc
        )

        return start_date <= record_date <= end_date

    except (ValueError, TypeError, OSError):
        return False


def process_record(record):

    body = record.get("body", "")

    if not valid_body(body):
        return False

    if not english_only(body):
        return False

    if not valid_date(record):
        return False

    return True


# --------------------------------------------------
# WORKER FUNCTION
# --------------------------------------------------

def worker_process(args):

    chunk_number, lines, temp_directory = args

    temp_file = Path(temp_directory) / (
        f"chunk_{chunk_number}.ndjson"
    )

    processed = 0
    selected = 0
    dropped = 0
    errors = 0

    with open(temp_file, "w", encoding="utf-8") as outfile:

        for line in lines:

            try:
                record = json.loads(line)

                if not isinstance(record, dict):
                    errors += 1
                    continue

                processed += 1

                if process_record(record):

                    outfile.write(
                        json.dumps(
                            record,
                            ensure_ascii=False
                        ) + "\n"
                    )

                    selected += 1

                else:
                    dropped += 1

            except (json.JSONDecodeError, TypeError):
                errors += 1

    logging.info(
        "Chunk %s completed | Processed: %s | Selected: %s | "
        "Dropped: %s | Errors: %s",
        chunk_number,
        processed,
        selected,
        dropped,
        errors
    )

    return chunk_number, processed, selected, dropped, errors


# --------------------------------------------------
# STREAM INPUT FILE
# --------------------------------------------------

def read_chunks(input_file, chunk_size):

    chunk = []

    with open(input_file, "r", encoding="utf-8") as infile:

        for line in infile:

            if not line.strip():
                continue

            chunk.append(line)

            if len(chunk) >= chunk_size:

                yield chunk
                chunk = []

        if chunk:
            yield chunk


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def main():

    logger.info("Starting Reddit processing")

    logger.info("Input file: %s", file_aug)
    logger.info("Output file: %s", output_file)

    logger.info("Workers: %s", NUM_WORKERS)
    logger.info("Chunk size: %s", CHUNK_SIZE)

    logger.info(
        "Date range: %s to %s",
        start_date,
        end_date
    )

    total_processed = 0
    total_selected = 0
    total_dropped = 0
    total_errors = 0
    chunk_number = 0

    if not file_aug.exists():
        logger.error("Input file does not exist!")
        return

    with tempfile.TemporaryDirectory() as temp_directory:

        temp_directory = Path(temp_directory)

        logger.info("Created temporary directory: %s", temp_directory)

        with ProcessPoolExecutor(
            max_workers=NUM_WORKERS
        ) as executor:

            pending = []

            logger.info("Starting worker processes")

            for chunk in read_chunks(file_aug, CHUNK_SIZE):

                args = (
                    chunk_number,
                    chunk,
                    str(temp_directory)
                )

                pending.append(
                    executor.submit(worker_process, args)
                )

                chunk_number += 1

                if len(pending) >= NUM_WORKERS:

                    result = pending.pop(0).result()

                    _, processed, selected, dropped, errors = result

                    total_processed += processed
                    total_selected += selected
                    total_dropped += dropped
                    total_errors += errors

            # Collect remaining tasks
            for future in pending:

                _, processed, selected, dropped, errors = (
                    future.result()
                )

                total_processed += processed
                total_selected += selected
                total_dropped += dropped
                total_errors += errors

        # --------------------------------------------------
        # COMBINE TEMPORARY FILES
        # --------------------------------------------------

        logger.info("Combining temporary files")

        with open(
            output_file, "w", encoding="utf-8"
        ) as outfile:

            for i in range(chunk_number):

                temp_file = temp_directory / (
                    f"chunk_{i}.ndjson"
                )

                if temp_file.exists():

                    with open(
                        temp_file,
                        "r",
                        encoding="utf-8"
                    ) as infile:

                        shutil.copyfileobj(infile, outfile)

        logger.info("Temporary files combined successfully")

    # --------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------

    logger.info("====================================")
    logger.info("PROCESSING COMPLETE")
    logger.info("====================================")

    logger.info("Total chunks: %s", chunk_number)
    logger.info("Total processed: %s", total_processed)
    logger.info("Total selected: %s", total_selected)
    logger.info("Total dropped: %s", total_dropped)
    logger.info("Total errors: %s", total_errors)

    logger.info("Output saved to: %s", output_file)
    logger.info("Log saved to: %s", log_file)


if __name__ == "__main__":
    main()
