"""
File to parse the twitter API with defined terms
"""


"""
Parallel historical tweet scraper
Strategy: day sharding + per-day until_time sliding + 15 threads
"""
import requests
import json
import time
import threading
import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv("disaster_social_media_collector/.env")
# === Config ===
API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
API_KEY = os.environ.get("API_KEY_X")

GENERAL_QUERY = "( \"Houston\" OR \"Texas\" OR \"TX\") AND (\"evacuating\" OR evacuate OR \"no power\" OR \"FEMA\") AND (\"Harvey\" OR)"
DECISION_QUERY = '("Hurricane Harvey" OR #Harvey) (warning OR forecast OR worried OR "did not expect" OR \"didn\'t expect\" OR decided OR \"changed my mind\" OR waited)'
EVACUATION_QUERY = '("Hurricane Harvey" OR #Harvey) (evacuate OR evacuated OR evacuating OR "shelter in place" OR stayed OR leaving OR stranded)'
RECOVERY_QUERY_v1 = '("Hurricane Harvey" OR #Harvey) ("return home" OR cleanup OR rebuilding OR insurance OR shelter OR supplies OR recovery)'
RECOVERY_QUERY_v2  = '("Houston" OR "Texas" OR "Harris County") ("Harvey" OR #Harvey) (decided OR waited OR returned OR rebuilding OR cleanup OR insurance OR "changed my mind" OR "stay home" OR "leave now")'

LOCATION_ROADS_QUERY = (
    '(#Harvey OR #HurricaneHarvey OR "Hurricane Harvey" OR #HoustonFlooding OR "Houston flooding" OR "Harvey flooding") ("highway" OR "freeway" OR "interstate" OR "exit ramp" OR "overpass" OR "underpass" OR "intersection" OR "cross street" OR "intersection of" OR "near the intersection" OR "at the corner of" OR "off of" OR "along" OR "road is flooded" OR "street is flooded" OR "highway is closed") '
)

KEYWORD = LOCATION_ROADS_QUERY
QUERY_FILTERS = "lang:en -filter:verified -filter:images -is:retweet"  # Skip replies, keep originals + quotes



# -filter:images to remove images

# Time range (UTC)
START_DATE = datetime(2017, 8,23 , tzinfo=timezone.utc)
END_DATE   = datetime(2017, 9, 24, tzinfo=timezone.utc)

WORKERS = 15

OUTPUT_FILE   = "../../data/twitter_data/tweets.jsonl"
RAW_FILE      = "../../data/twitter_data/tweets_raw.jsonl"
PROGRESS_FILE = "../../data/twitter_data/twitter_progress.json"

# Thread-safety
write_lock = threading.Lock()
stats_lock = threading.Lock()
seen_ids = set()
seen_ids_lock = threading.Lock()

stats = {
    "total": 0, "api_calls": 0, "days_done": 0, "days_total": 0,
    "duplicates": 0, "retweet_filtered": 0, "quotes": 0,
    "originals": 0, "errors": 0, "empty_days": 0,
}


def parse_twitter_time(s: str) -> int:
    return int(datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").timestamp())


def standardize_tweet(t: dict) -> dict:
    a = t.get("author", {})
    e = t.get("entities", {})
    return {
        "tweet_id": t.get("id"),
        "created_at": t.get("createdAt"),
        "text_raw": t.get("text"),
        "language": t.get("lang"),
        "is_reply": t.get("isReply", False),
        "is_quote": t.get("quoted_tweet") is not None,
        "is_retweet": bool(t.get("retweeted_tweet")),
        "hashtags":  [h.get("text", "") for h in e.get("hashtags", [])],
        "cashtags":  [s.get("text", "") for s in e.get("symbols", [])],
        "mentions":  [m.get("screen_name", "") for m in e.get("user_mentions", [])],
        "urls":      [u.get("expanded_url") or u.get("url", "") for u in e.get("urls", [])],
        "likes":     t.get("likeCount", 0),
        "retweets":  t.get("retweetCount", 0),
        "replies":   t.get("replyCount", 0),
        "impressions": t.get("viewCount", 0),
        "author": {
            "id": a.get("id"), "username": a.get("userName"), "name": a.get("name"),
            "followers": a.get("followers", 0), "following": a.get("following", 0),
            "location": a.get("location"),
            "verified": a.get("isBlueVerified", False),
            "created_at": a.get("createdAt"),
        },
    }


def api_get(params, retries=3):
    headers = {"x-api-key": API_KEY}
    for i in range(retries):
        try:
            r = requests.get(API_URL, headers=headers, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i < retries - 1:
                time.sleep(1)
            else:
                with stats_lock:
                    stats["errors"] += 1
                return {"tweets": []}


def fetch_day(since_ts: int, until_ts: int, date_str: str, f_out, f_raw):
    """
    Fetch all tweets in [since_ts, until_ts] using until_time sliding.
    Each call returns at most 20; use earliest-1 as next until_time.
    """
    day_calls = 0
    day_new = 0
    current_until = until_ts
    max_calls = 50  # safety cap

    while current_until > since_ts and day_calls < max_calls:
        query = f"{KEYWORD} since_time:{since_ts} until_time:{current_until} {QUERY_FILTERS}"
        data = api_get({"queryType": "Latest", "query": query})
        tweets = data.get("tweets", [])
        day_calls += 1

        if not tweets:
            break

        # Filter retweets in code (API flag isn't 100% reliable)
        valid = [t for t in tweets if not bool(t.get("retweeted_tweet"))]
        with stats_lock:
            stats["retweet_filtered"] += len(tweets) - len(valid)

        batch_std, batch_raw = [], []
        for t in valid:
            tid = t.get("id")
            if not tid:
                continue
            with seen_ids_lock:
                if tid in seen_ids:
                    with stats_lock:
                        stats["duplicates"] += 1
                    continue
                seen_ids.add(tid)
            batch_std.append(json.dumps(standardize_tweet(t), ensure_ascii=False) + "\n")
            batch_raw.append(json.dumps(t, ensure_ascii=False) + "\n")
            day_new += 1
            with stats_lock:
                if t.get("quoted_tweet"):
                    stats["quotes"] += 1
                else:
                    stats["originals"] += 1

        if batch_std:
            with write_lock:
                f_out.writelines(batch_std)
                f_raw.writelines(batch_raw)

        # Slide: next until = earliest in this batch - 1 second
        earliest = min(parse_twitter_time(t["createdAt"]) for t in tweets)
        if earliest < current_until:
            current_until = earliest - 1
        else:
            break  # guard against infinite loop

        # Fewer than 20 = this window is exhausted
        if len(tweets) < 20:
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
        days.append((int(cur.timestamp()), int(nxt.timestamp()), cur.strftime("%Y-%m-%d")))
        cur = nxt
    return days


def load_progress():
    try:
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_progress(done_days):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({
            "completed_days": done_days,
            "total": stats["total"],
            "api_calls": stats["api_calls"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def main():
    all_days = generate_days()
    stats["days_total"] = len(all_days)

    # Resume support
    progress = load_progress()
    completed = set()
    if progress:
        completed = set(progress.get("completed_days", []))
        stats["days_done"] = len(completed)
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        seen_ids.add(json.loads(line).get("tweet_id"))
                    except json.JSONDecodeError:
                        pass
            stats["total"] = len(seen_ids)
        except FileNotFoundError:
            pass
        mode = "a"
    else:
        mode = "w"

    pending = [(s, u, d) for s, u, d in all_days if d not in completed]
    print(f"Days: {stats['days_total']} total, {len(pending)} pending, {WORKERS} workers")

    f_out = open(OUTPUT_FILE, mode, encoding="utf-8")
    f_raw = open(RAW_FILE, mode, encoding="utf-8")
    start = time.time()
    done_list = list(completed)

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(fetch_day, s, u, d, f_out, f_raw): d for s, u, d in pending}
            for fut in as_completed(futures):
                d, n, c = fut.result()
                done_list.append(d)
                elapsed = time.time() - start
                print(f"[{d}] +{n} ({c} calls) | {stats['days_done']}/{stats['days_total']} | total={stats['total']} | {elapsed:.0f}s", flush=True)
                if stats["days_done"] % 100 == 0:
                    f_out.flush(); f_raw.flush(); save_progress(done_list)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        f_out.close(); f_raw.close(); save_progress(done_list)

    elapsed = time.time() - start
    print(f"\n=== DONE ===  total={stats['total']}  api_calls={stats['api_calls']}  elapsed={elapsed:.0f}s")


if __name__ == "__main__":
    main()
