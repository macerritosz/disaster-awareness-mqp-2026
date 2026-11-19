
import json
import logging

from pathlib import Path
from datetime import datetime, timedelta, timezone


# ==================================================
# CONFIGURATION
# ==================================================

INPUT_FILES = [
    Path(
        r"C:\Users\MCerr\CSCourses\MQP\MQPmainRepo\reddit"
        r"\submissions\RS_2017-09\RS_2017-09"
    ),
    Path(
        r"C:\Users\MCerr\CSCourses\MQP\MQPmainRepo\reddit"
        r"\submissions\RS_2017-08\RS_2017-08"
    ),
]

OUTPUT_DIRECTORY = Path(
    r"C:\Users\MCerr\CSCourses\MQP\MQPmainRepo\reddit"
    r"\submissions\filtered"
)

LOG_FILE = OUTPUT_DIRECTORY / "timestamp_filter.log"

SELECTED_DATE = datetime(
    2017, 8, 22, tzinfo=timezone.utc
)

START_DATE = SELECTED_DATE
END_DATE = SELECTED_DATE + timedelta(weeks=3)

START_TIMESTAMP = START_DATE.timestamp()
END_TIMESTAMP = END_DATE.timestamp()

BUFFER_SIZE = 8 * 1024 * 1024


# ==================================================
# LOGGING
# ==================================================

OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True
)

logger = logging.getLogger(__name__)


# ==================================================
# TIMESTAMP EXTRACTION
# ==================================================

def extract_timestamp(line):

    try:
        record = json.loads(line)

        if not isinstance(record, dict):
            raise ValueError("Invalid JSON record")

        return float(record["created_utc"])

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise ValueError("Invalid or missing created_utc")


def read_record_at(file, offset, file_size):

    if offset >= file_size:
        return None

    # Find the beginning of the line containing offset.
    if offset == 0:
        line_start = 0

    else:
        file.seek(offset - 1)

        if file.read(1) == b"\n":
            line_start = offset

        else:
            # Search backward in blocks for the previous newline.
            position = offset - 1
            line_start = 0
            block_size = 8192

            while position >= 0:

                block_start = max(0, position - block_size + 1)

                file.seek(block_start)

                block = file.read(
                    position - block_start + 1
                )

                newline_position = block.rfind(b"\n")

                if newline_position != -1:

                    line_start = (
                        block_start + newline_position + 1
                    )

                    break

                position = block_start - 1

    file.seek(line_start)

    line = file.readline()

    if not line:
        return None

    line_end = file.tell()

    timestamp = extract_timestamp(line)

    return line_start, line_end, timestamp


def binary_search(input_file, target_timestamp, mode):

    file_size = input_file.stat().st_size

    low = 0
    high = file_size

    iterations = 0

    logger.info(
        "Starting %s search | File size: %.2f GB",
        mode.upper(),
        file_size / (1024 ** 3)
    )

    with open(input_file, "rb") as infile:

        while low < high:

            midpoint = (low + high) // 2

            result = read_record_at(
                infile,
                midpoint,
                file_size
            )

            if result is None:
                break

            line_start, line_end, timestamp = result

            iterations += 1

            previous_low = low
            previous_high = high

            if mode == "left":

                # First timestamp >= target

                if timestamp >= target_timestamp:
                    high = line_start

                else:
                    low = line_end

            elif mode == "right":

                # First timestamp > target

                if timestamp > target_timestamp:
                    high = line_start

                else:
                    low = line_end

            else:
                raise ValueError("Invalid search mode")

            # Safety: guarantee that every iteration progresses.
            if low == previous_low and high == previous_high:
                raise RuntimeError(
                    f"Binary search stalled at iteration {iterations}. "
                    f"Low={low}, High={high}, Midpoint={midpoint}"
                )

            if iterations % 5 == 0:

                logger.info(
                    "%s search | Iteration: %s | "
                    "Remaining: %.2f MB",
                    mode.upper(),
                    iterations,
                    (high - low) / (1024 ** 2)
                )

    logger.info(
        "%s search complete | Iterations: %s | Offset: %s",
        mode.upper(),
        iterations,
        low
    )

    return low



# ==================================================
# COPY SELECTED BYTE RANGE
# ==================================================

def copy_range(input_file, output_file, start_offset, end_offset):

    total_bytes = end_offset - start_offset

    if total_bytes <= 0:
        logger.warning("No records found in requested range")

        output_file.touch()
        return

    copied = 0

    logger.info(
        "Starting copy | Selected size: %.2f GB",
        total_bytes / (1024 ** 3)
    )

    with open(input_file, "rb") as infile, \
         open(output_file, "wb") as outfile:

        infile.seek(start_offset)

        while copied < total_bytes:

            chunk = infile.read(
                min(BUFFER_SIZE, total_bytes - copied)
            )

            if not chunk:
                break

            outfile.write(chunk)

            copied += len(chunk)

            if copied % (256 * 1024 * 1024) < len(chunk):

                logger.info(
                    "Copy progress: %.2f / %.2f GB (%.1f%%)",
                    copied / (1024 ** 3),
                    total_bytes / (1024 ** 3),
                    copied / total_bytes * 100
                )

    logger.info(
        "Copy complete | Written: %.2f MB",
        copied / (1024 ** 2)
    )


# ==================================================
# FILTER FILE
# ==================================================

def filter_file(input_file):

    if not input_file.exists():
        logger.error("File not found: %s", input_file)
        return

    output_file = OUTPUT_DIRECTORY / (
        f"{input_file.stem}_filtered.ndjson"
    )

    logger.info("========================================")
    logger.info("Processing: %s", input_file)

    file_size = input_file.stat().st_size

    logger.info(
        "Input size: %.2f GB",
        file_size / (1024 ** 3)
    )

    # Find first record >= start timestamp

    start_offset = binary_search(
        input_file,
        START_TIMESTAMP,
        "left"
    )

    # Find first record > end timestamp

    end_offset = binary_search(
        input_file,
        END_TIMESTAMP,
        "right"
    )

    logger.info(
        "Selected byte range: %s - %s",
        start_offset,
        end_offset
    )

    logger.info(
        "Selected percentage: %.2f%%",
        (end_offset - start_offset) / file_size * 100
        if file_size else 0
    )

    # Copy only selected records

    copy_range(
        input_file,
        output_file,
        start_offset,
        end_offset
    )

    logger.info("Output: %s", output_file)


# ==================================================
# MAIN
# ==================================================

def main():

    logger.info("Starting timestamp filtering")

    logger.info("Start date: %s", START_DATE)
    logger.info("End date: %s", END_DATE)

    for input_file in INPUT_FILES:

        try:
            filter_file(input_file)

        except (OSError, ValueError):
            logger.exception(
                "Failed processing: %s",
                input_file
            )

    logger.info("All files processed")


if __name__ == "__main__":
    main()
