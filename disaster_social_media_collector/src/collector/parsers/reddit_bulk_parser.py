
import json
import logging
import re
import shutil
import tempfile
import unicodedata

from pathlib import Path
from datetime import datetime
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

from collector.util import subreddit_index as si
from collector.util import keyword_index as ki

# Choose: "subreddit" or "keywords"
PROCESS_MODE = "keywords"

NUM_WORKERS = 10
CHUNK_SIZE = 5000
MIN_WORDS = 5

local_data = Path("../../../data_store")
submission_folder = Path("../../../data_store/submissions_filtered")

submissions_path_drive = Path(r"D:\Submission_Filtered")

# Original date-filtered submissions
RAW_SUBMISSION_FILES = [
    submissions_path_drive / "RS_2017-08_filtered.ndjson",
    submissions_path_drive / "RS_2017-09_filtered.ndjson",
]

# Output from Stage 2
out_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Output from Stage 1
SUBREDDIT_FILTERED_FILE = (
    submission_folder / f"RS_{out_timestamp}_subreddit_filtered.ndjson"
)

KEYWORD_FILTERED_FILE = (
    submission_folder / f"RS_keyword_filtered_{out_timestamp}.ndjson"
)

# Select inputs and outputs based on processing mode
if PROCESS_MODE == "subreddit":
    INPUT_FILES = RAW_SUBMISSION_FILES
    OUTPUT_FILE = SUBREDDIT_FILTERED_FILE

elif PROCESS_MODE == "keywords":
    INPUT_FILES = RAW_SUBMISSION_FILES
    OUTPUT_FILE = KEYWORD_FILTERED_FILE

else:
    raise ValueError("PROCESS_MODE must be 'subreddit' or 'keywords'")


def normalize_text(text):

    text = text.casefold()
    text = unicodedata.normalize("NFKD", text)

    return "".join(
        char for char in text
        if not unicodedata.combining(char)
    )


def tokenize(text):

    return re.findall(
        r"[^\W\d_]+",
        normalize_text(text),
        re.UNICODE
    )


KEYWORD_SEQUENCES = {
    tuple(tokenize(keyword))
    for keyword in ki.ALL_KEYWORDS
    if tokenize(keyword)
}

KEYWORD_LENGTHS = {
    len(keyword)
    for keyword in KEYWORD_SEQUENCES
}


ALLOWED_SUBREDDITS = (
    si.PRIMARY_SUBREDDITS
    | si.SECONDARY_SUBREDDITS
)


def get_subreddit(record):

    subreddit = (
        record.get("subreddit")
        or record.get("subreddit_name_prefixed")
        or record.get("community")
    )

    if not isinstance(subreddit, str):
        return None

    return subreddit.strip().lower() or None


def valid_subreddit(record):

    subreddit = get_subreddit(record)

    if subreddit is None:
        return False

    if subreddit in si.EXCLUDED_SUBREDDITS:
        return False

    return subreddit in ALLOWED_SUBREDDITS

def get_record_text(record):

    text_parts = []

    for field in ("title", "selftext"):

        value = record.get(field)

        if not isinstance(value, str):
            continue

        value = value.strip()

        if not value:
            continue

        if value.casefold() in {
            "[deleted]", "[removed]", "deleted", "removed"
        }:
            continue

        text_parts.append(value)

    return " ".join(dict.fromkeys(text_parts)).strip()


def valid_body(body):

    if not isinstance(body, str):
        return False

    words = tokenize(body)

    # Reject short text and emoji-only content.
    return len(words) >= MIN_WORDS


def valid_submission(record):

    # Image submissions with no meaningful text
    # are not useful for text-based extraction.
    if record.get("post_hint") == "image":

        title = record.get("title", "")
        selftext = record.get("selftext", "")

        if not title.strip() and not selftext.strip():
            return False

    return True


def matches_disaster_keywords(body):

    words = tokenize(body)

    for length in KEYWORD_LENGTHS:

        for i in range(len(words) - length + 1):

            phrase = tuple(words[i:i + length])

            if phrase in KEYWORD_SEQUENCES:
                return True

    return False

def process_record(record):

    # Stage 1: Only check subreddit membership.
    if PROCESS_MODE == "subreddit":

        if not valid_subreddit(record):
            return None

        return record

    # Stage 2: Keyword filtering.
    if PROCESS_MODE == "keywords":

        body = get_record_text(record)

        if not valid_body(body):
            return None

        if not valid_submission(record):
            return None

        if not matches_disaster_keywords(body):
            return None

        return record

    return None

def worker_process(args):

    chunk_number, lines, temp_directory = args

    temp_file = Path(temp_directory) / (
        f"chunk_{chunk_number}.ndjson"
    )

    processed = 0
    selected = 0
    dropped = 0
    errors = 0

    subreddit_counts = Counter()

    with open(temp_file, "w", encoding="utf-8") as outfile:

        for line in lines:

            try:

                record = json.loads(line)

                if not isinstance(record, dict):
                    errors += 1
                    continue

                processed += 1

                subreddit = get_subreddit(record)

                filtered_record = process_record(record)

                if filtered_record is not None:

                    outfile.write(
                        json.dumps(
                            filtered_record,
                            ensure_ascii=False
                        ) + "\n"
                    )

                    selected += 1

                    if subreddit:
                        subreddit_counts[subreddit] += 1

                else:
                    dropped += 1

            except (json.JSONDecodeError, TypeError, ValueError):

                errors += 1

    logging.info(
        "Chunk %s | Processed: %s | Selected: %s | "
        "Dropped: %s | Errors: %s",
        chunk_number,
        processed,
        selected,
        dropped,
        errors
    )

    return (
        chunk_number,
        processed,
        selected,
        dropped,
        errors,
        dict(subreddit_counts),
    )


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

def main():

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    log_file = (
        local_data / "progress_logs" /
        f"progress_{out_timestamp}.log"
    )

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | "
               "%(processName)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ],
        force=True
    )

    logger = logging.getLogger(__name__)

    logger.info("====================================")
    logger.info("STARTING REDDIT SUBMISSION FILTER")
    logger.info("Mode: %s", PROCESS_MODE)
    logger.info("====================================")

    logger.info("Input files: %s", INPUT_FILES)
    logger.info("Output file: %s", OUTPUT_FILE)
    logger.info("Workers: %s", NUM_WORKERS)
    logger.info("Chunk size: %s", CHUNK_SIZE)

    if PROCESS_MODE == "subreddit":
        logger.info("Filtering allowed subreddits")

    else:
        logger.info("Filtering disaster keywords")
        logger.info("Minimum words: %s", MIN_WORDS)
        logger.info("Keyword count: %s", len(KEYWORD_SEQUENCES))

    # Validate inputs.
    for input_path in INPUT_FILES:

        if not input_path.exists():

            logger.error("Missing input file: %s", input_path)
            return

    total_processed = 0
    total_selected = 0
    total_dropped = 0
    total_errors = 0

    total_subreddits = Counter()
    chunk_number = 0

    with tempfile.TemporaryDirectory() as temp_directory:

        temp_directory = Path(temp_directory)

        with ProcessPoolExecutor(
            max_workers=NUM_WORKERS
        ) as executor:

            pending = deque()

            for input_path in INPUT_FILES:

                logger.info("Reading: %s", input_path)

                for chunk in read_chunks(input_path, CHUNK_SIZE):

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

                        result = pending.popleft().result()

                        (
                            _,
                            processed,
                            selected,
                            dropped,
                            errors,
                            subreddits,
                        ) = result

                        total_processed += processed
                        total_selected += selected
                        total_dropped += dropped
                        total_errors += errors

                        total_subreddits.update(subreddits)

            # Collect remaining workers.
            while pending:

                result = pending.popleft().result()

                (
                    _,
                    processed,
                    selected,
                    dropped,
                    errors,
                    subreddits,
                ) = result

                total_processed += processed
                total_selected += selected
                total_dropped += dropped
                total_errors += errors

                total_subreddits.update(subreddits)

        # Combine chunk outputs.
        logger.info("Combining output chunks")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:

            for i in range(chunk_number):

                temp_file = temp_directory / f"chunk_{i}.ndjson"

                if temp_file.exists():

                    with open(
                        temp_file, "r", encoding="utf-8"
                    ) as infile:

                        shutil.copyfileobj(infile, outfile)

    # Final summary.
    logger.info("====================================")
    logger.info("PROCESSING COMPLETE")
    logger.info("====================================")

    logger.info("Chunks: %s", chunk_number)
    logger.info("Processed: %s", total_processed)
    logger.info("Selected: %s", total_selected)
    logger.info("Dropped: %s", total_dropped)
    logger.info("Errors: %s", total_errors)

    logger.info("TOP SUBREDDITS")

    for subreddit, count in total_subreddits.most_common(30):
        logger.info("%s: %s", subreddit, count)

    logger.info("Output: %s", OUTPUT_FILE)
    logger.info("Log: %s", log_file)


if __name__ == "__main__":
    main()
