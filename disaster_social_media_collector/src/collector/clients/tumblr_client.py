"""
File to parse the tumblr API with defined terms
"""

"""
Tumblr API client for historical post collection.
Strategy: day sharding + per-day 'before' timestamp sliding + ThreadPoolExecutor.
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv("disaster_social_media_collector/.env")

# === Config ===
# Official Tumblr API v2 endpoint for tagged searches
API_URL = "https://api.tumblr.com/v2/tagged"
# Tumblr uses your OAuth Consumer Key / API Key
API_KEY = os.environ.get("API_KEY")

# Tumblr /tagged searches single tags (e.g., 'harvey', 'hurricane harvey', 'houston flood')
TAG = "hurricane harvey"

# Time range (UTC)
START_DATE = datetime.now(timezone.utc) - timedelta(days=2)
END_DATE = datetime.now(timezone.utc)

# Tumblr rate limit: default is 300 calls/min and 1,000/hour per key, so keep workers modest
WORKERS = 5
OUTPUT_FILE = "../../data/tumblr_data/tumblr_posts.jsonl"
RAW_FILE = "../../data/tumblr_data/tumblr_raw.jsonl"
PROGRESS_FILE = "../../data/tumblr_data/tumblr_progress.json"

# Thread-safety
write_lock = threading.Lock()
stats_lock = threading.Lock()
seen_ids = set()
seen_ids_lock = threading.Lock()

stats = {
    "total": 0,
    "api_calls": 0,
    "days_done": 0,
    "days_total": 0,
    "duplicates": 0,
    "errors": 0,
    "empty_days": 0,
}


def standardize_tumblr_post(p: dict) -> dict:
    """Standardizes a Tumblr post into a unified schema matching the collector."""
    # Handle text extraction across both legacy and Neue Post Format (NPF)
    body_text = p.get("body", "") or p.get("summary", "")
    if not body_text and "trail" in p:
        body_text = " ".join([t.get("content_raw", "") for t in p["trail"]])

    return {
        "post_id": str(p.get("id")),
        "created_at": datetime.fromtimestamp(
            p.get("timestamp", 0), tz=timezone.utc
        ).isoformat(),
        "timestamp": p.get("timestamp"),
        "text_raw": body_text,
        "type": p.get("type"),
        "url": p.get("post_url"),
        "tags": p.get("tags", []),
        "notes_count": p.get("note_count", 0),
        "is_reblog": "reblogged_root_id" in p or "reblog" in p,
        "author": {
            "name": p.get("blog_name"),
            "blog_url": f"https://{p.get('blog_name')}.tumblr.com",
            "is_nsfw": p.get("is_nsfw", False),
        },
    }


def api_get(params: dict, retries: int = 3) -> dict:
    """Makes a GET request to the Tumblr API with retries and rate limit backoff."""
    params["api_key"] = API_KEY
    for i in range(retries):
        try:
            r = requests.get(API_URL, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))  # Backoff on rate limit
                continue
            r.raise_for_status()
            return r.json().get("response", [])
        except Exception:
            if i < retries - 1:
                time.sleep(1)
            else:
                with stats_lock:
                    stats["errors"] += 1
                return []
    return []

def fetch_day(since_ts: int, until_ts: int, date_str: str, f_out, f_raw):
    """
    Fetches all posts in [since_ts, until_ts] using Tumblr's `before` parameter sliding.
    Tumblr returns at most 20 posts per call; slides `before` to the minimum observed timestamp.
    """
    day_calls = 0
    day_new = 0
    current_until = until_ts
    max_calls = 50  # Safety cap per day shard

    while current_until > since_ts and day_calls < max_calls:
        params = {
            "tag": TAG,
            "before": current_until,
            "filter": "raw",
        }
        posts = api_get(params)
        day_calls += 1

        if not posts:
            break

        # Filter posts falling strictly within our window [since_ts, until_ts]
        window_posts = [p for p in posts if p.get("timestamp", 0) >= since_ts]
        batch_std, batch_raw = [], []

        for p in window_posts:
            pid = str(p.get("id"))
            if not pid:
                continue

            with seen_ids_lock:
                if pid in seen_ids:
                    with stats_lock:
                        stats["duplicates"] += 1
                    continue
                seen_ids.add(pid)

            batch_std.append(
                json.dumps(standardize_tumblr_post(p), ensure_ascii=False)
                + "\n"
            )
            batch_raw.append(json.dumps(p, ensure_ascii=False) + "\n")
            day_new += 1

        if batch_std:
            with write_lock:
                f_out.writelines(batch_std)
                f_raw.writelines(batch_raw)

        # Slide window backward: use earliest timestamp found in returned batch
        timestamps = [
            p.get("featured_timestamp") or p.get("timestamp")
            for p in posts
            if (p.get("featured_timestamp") or p.get("timestamp"))
        ]
        if not timestamps:
            break

        earliest = min(timestamps)
        if earliest < current_until:
            current_until = earliest
        else:
            break

        # Tumblr defaults to 20; fewer than 20 means no older posts exist for the tag
        if len(posts) < 20 or earliest <= since_ts:
            break

    with stats_lock:
        stats["total"] += day_new
        stats["api_calls"] += day_calls
        stats["days_done"] += 1
        if day_new == 0:
            stats["empty_days"] += 1

    return date_str, day_new, day_calls


def generate_days():
    days = []
    cur = START_DATE
    while cur < END_DATE:
        nxt = cur + timedelta(days=1)
        days.append(
            (int(cur.timestamp()), int(nxt.timestamp()), cur.strftime("%Y-%m-%d"))
        )
        cur = nxt
    return days


def load_progress():
    try:
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_progress(done_days):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(
            {
                "completed_days": done_days,
                "total": stats["total"],
                "api_calls": stats["api_calls"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )


def main():
    all_days = generate_days()
    stats["days_total"] = len(all_days)

    progress = load_progress()
    completed = set()
    if progress:
        completed = set(progress.get("completed_days", []))
        stats["days_done"] = len(completed)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    seen_ids.add(json.loads(line).get("post_id"))
                except json.JSONDecodeError:
                    pass
        stats["total"] = len(seen_ids)
        mode = "a"
    except FileNotFoundError:
        mode = "w"

    pending = [(s, u, d) for s, u, d in all_days if d not in completed]
    print(
        f"Days: {stats['days_total']} total, {len(pending)} pending, {WORKERS} workers"
    )

    f_out = open(OUTPUT_FILE, mode, encoding="utf-8")
    f_raw = open(RAW_FILE, mode, encoding="utf-8")
    start = time.time()
    done_list = list(completed)

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {
                ex.submit(fetch_day, s, u, d, f_out, f_raw): d
                for s, u, d in pending
            }
            for fut in as_completed(futures):
                d, n, c = fut.result()
                done_list.append(d)
                elapsed = time.time() - start
                print(
                    f"[{d}] +{n} ({c} calls) | {stats['days_done']}/{stats['days_total']} | total={stats['total']} | {elapsed:.0f}s",
                    flush=True,
                )
                if stats["days_done"] % 50 == 0:
                    f_out.flush()
                    f_raw.flush()
                    save_progress(done_list)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        f_out.close()
        f_raw.close()
        save_progress(done_list)

    elapsed = time.time() - start
    print(
        f"\n=== DONE ===  total={stats['total']}  api_calls={stats['api_calls']}  elapsed={elapsed:.0f}s"
    )


if __name__ == "__main__":
    main()