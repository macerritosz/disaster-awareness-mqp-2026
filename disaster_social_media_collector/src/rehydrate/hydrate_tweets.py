import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv("../../.env")
API_URL = "https://api.twitterapi.io/twitter/tweets"
API_KEY = os.environ.get("API_KEY_X")

# CODE IS ONLY RAN ON BATCH 13 THUS FAR; if we change input file, it should just append onto the output file
# Batch 13 have 549 tweets

INPUT_FILE   = "../data/disasterloc_data/Batch13-HurricaneHarvey-All.json"  
ID_COL       = "id"

OUTPUT_FILE  = "../data/twitter_data/disasterloc_tweet_content.jsonl"
RAW_FILE     = "../data/twitter_data/disasterloc_tweet_content_raw.jsonl"
MISSING_FILE = "../data/twitter_data/disasterloc_missing_ids.txt"

BATCH_SIZE = 50 # Don't push to 75  
WORKERS    = 1 # Lol I can't run with more than 1 worker

stats = {"total": 0, "missing": 0, "failed": 0, "batches_done": 0, "batches_total": 0}

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

def load_disasterloc(path: str, id_col: str = "id") -> dict[str, dict]:
    """
    Reads DisasterLoc dataset; parses for ID and ensures annotations will be maintained
    """
    records = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                tid = str(rec[id_col]).strip()
                if tid.isdigit():
                    records[tid] = rec
    return records

def fetch_batch(batch: list[str]) -> list[dict] | None:
    """
    One request for up to 100 IDs. Returns the tweets, or None if the request failed.
    """
    time.sleep(5)
    try:
        r = requests.get(
            API_URL,
            headers={"x-api-key": API_KEY},
            params={"tweet_ids": ",".join(batch)},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "error":
            raise RuntimeError(data.get("message") or data.get("msg"))
        return data.get("tweets", [])
    except Exception as e:
        print(f"batch failed ({batch[0]}..): {e}", flush=True)
        return None

def main():
    assert API_KEY, "API_KEY_X not found - check your .env path/name"
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    dl = load_disasterloc(INPUT_FILE, ID_COL)
    all_ids = list(dl)

    # Resume support: skip IDs already hydrated or already confirmed missing
    done = set()
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(str(json.loads(line).get("tweet_id")))
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        pass
    try:
        with open(MISSING_FILE, "r") as f:
            done |= {l.strip() for l in f if l.strip()}
    except FileNotFoundError:
        pass

    pending = [i for i in all_ids if i not in done]
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    stats["batches_total"] = len(batches)
    print(f"IDs: {len(all_ids)} total, {len(done)} already done, "
          f"{len(pending)} pending in {len(batches)} batches, {WORKERS} workers")

    f_out  = open(OUTPUT_FILE, "a", encoding="utf-8")
    f_raw  = open(RAW_FILE, "a", encoding="utf-8")
    f_miss = open(MISSING_FILE, "a")
    start = time.time()

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(fetch_batch, b): b for b in batches}
            for fut in as_completed(futures):
                batch = futures[fut]
                tweets = fut.result()
                stats["batches_done"] += 1

                if tweets is None:               # request failed -> leave pending for next run
                    stats["failed"] += len(batch)
                    continue

                # remember to attach annotations 
                got = set()
                for t in tweets:
                    tid = str(t.get("id"))
                    if tid in got:
                        continue
                    got.add(tid)

                    row = standardize_tweet(t)
                    row["message_topic"] = dl.get(tid, {}).get("MessageTopic")
                    row["annotations"] = dl.get(tid, {}).get("Annotation", [])

                    f_out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f_raw.write(json.dumps(t, ensure_ascii=False) + "\n")

                gone = [i for i in batch if i not in got]
                f_miss.writelines(i + "\n" for i in gone)

                stats["total"] += len(got)
                stats["missing"] += len(gone)

                elapsed = time.time() - start
                print(f"[batch {stats['batches_done']}/{stats['batches_total']}] "
                      f"+{len(got)} ({len(gone)} missing) | total={stats['total']} | "
                      f"missing={stats['missing']} | failed={stats['failed']} | {elapsed:.0f}s",
                      flush=True)

                if stats["batches_done"] % 10 == 0:
                    f_out.flush(); f_raw.flush(); f_miss.flush()
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        f_out.close(); f_raw.close(); f_miss.close()

    elapsed = time.time() - start
    print(f"\n=== DONE ===  total={stats['total']}  missing={stats['missing']}  "
          f"failed(rerun to retry)={stats['failed']}  elapsed={elapsed:.0f}s")


if __name__ == "__main__":
    main()