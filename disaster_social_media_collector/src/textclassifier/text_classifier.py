"""
Text Classifier - basic outline
===============================
Goal: sort social-media-style posts about a storm/event into classes so we can
keep or drop them from the processing pool.

Approach (hybrid):
  1. Rule-based layer  -> catches the "direct mention" requirements (OR logic)
                          and the "indirect mention" requirements (AND logic)
  2. ML layer          -> TF-IDF + Logistic Regression trained on the golden
                          (labeled) dataset, used for everything the rules
                          can't decide
  3. Router            -> splits results into class buckets (post-condition)

Dependencies: scikit-learn, pandas  (pip install scikit-learn pandas)
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# ---------------------------------------------------------------------------
# 1. DATA CLASSES (labels)
# ---------------------------------------------------------------------------
IRRELEVANT = "irrelevant"
DECISION = "direct_decision"  # "evacuating", "staying put"
LOCATION = "direct_location"  # location mention bucket
INDIRECT = "indirect_mention"  # only if indirect AND context rules pass

LABELS = [IRRELEVANT, DECISION, LOCATION, INDIRECT]


# ---------------------------------------------------------------------------
# 2. CONFIG: keyword / pattern lists (edit these for your event)
# ---------------------------------------------------------------------------
@dataclass
class Config:
    storm_names: list = field(default_factory=lambda: ["hurricane example"])
    weather_terms: list = field(default_factory=lambda: [
        "storm surge", "flooding", "wind", "rain bands", "landfall", "tornado",
    ])
    decision_terms: list = field(default_factory=lambda: [
        "evacuating", "evacuated", "leaving town", "staying put",
        "staying home", "riding it out", "not leaving", "heading inland",
    ])
    # Fill with city/county/place names relevant to the event
    known_locations: list = field(default_factory=lambda: ["miami", "tampa"])
    # Indirect cues: need one of these AND a context hit (see below)
    indirect_terms: list = field(default_factory=lambda: [
        "my neighbors", "my family", "everyone around", "streets are empty",
        "roads are packed", "shelter is full", "friends are leaving",
    ])


CFG = Config()


def _any(patterns, text):
    """True if any term appears in text (word-boundary, case-insensitive)."""
    return any(re.search(rf"\b{re.escape(p)}\b", text, re.I) for p in patterns)


# ---------------------------------------------------------------------------
# 3. FEATURE EXTRACTION (rule signals)
# ---------------------------------------------------------------------------
def extract_signals(text: str, cfg: Config = CFG) -> dict:
    """Boolean signals matching the requirements outline."""
    hashtags = re.findall(r"#\w+", text)
    storm_hashtag = any(
        re.sub(r"\W", "", s).lower() in h.lower()
        for h in hashtags for s in cfg.storm_names
    )
    return {
        "weather": _any(cfg.weather_terms, text),
        "storm": _any(cfg.storm_names, text) or storm_hashtag,
        "decision": _any(cfg.decision_terms, text),
        "location": _any(cfg.known_locations, text),
        "indirect": _any(cfg.indirect_terms, text),
    }


# ---------------------------------------------------------------------------
# 4. RULE LAYER
# ---------------------------------------------------------------------------
def rule_classify(text: str, cfg: Config = CFG):
    """
    Returns a label if the rules are confident, else None (defer to ML).

    Direct mentions  -> OR logic  (any one is enough)
    Indirect mention -> AND logic (indirect cue + storm/location context)
    """
    s = extract_signals(text, cfg)

    # Highest priority: explicit decision
    if s["decision"]:
        return DECISION

    # Direct location (best case)
    if s["location"] and (s["storm"] or s["weather"]):
        return LOCATION

    # Indirect: cue AND (storm/event OR city)
    if s["indirect"] and (s["storm"] or s["location"]):
        return INDIRECT

    return None  # rules can't decide


# ---------------------------------------------------------------------------
# 5. ML LAYER
# ---------------------------------------------------------------------------
def build_model() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=2,
            stop_words="english",
        )),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])


def train(golden_csv: str, text_col="text", label_col="label"):
    """Train on the golden dataset and print a validation report."""
    df = pd.read_csv(golden_csv).dropna(subset=[text_col, label_col])
    X_train, X_test, y_train, y_test = train_test_split(
        df[text_col], df[label_col],
        test_size=0.2, stratify=df[label_col], random_state=42,
    )
    model = build_model()
    model.fit(X_train, y_train)
    print(classification_report(y_test, model.predict(X_test)))
    return model


# ---------------------------------------------------------------------------
# 6. COMBINED PREDICTION
# ---------------------------------------------------------------------------
def classify(text: str, model: Pipeline, min_conf: float = 0.6):
    """Rules first, then ML. Low-confidence ML results fall back to IRRELEVANT."""
    rule_label = rule_classify(text)
    if rule_label:
        return rule_label, 1.0, "rule"

    probs = model.predict_proba([text])[0]
    best = probs.argmax()
    label, conf = model.classes_[best], float(probs[best])
    if conf < min_conf:
        return IRRELEVANT, conf, "ml_low_conf"
    return label, conf, "ml"


# ---------------------------------------------------------------------------
# 7. ROUTER (post-condition): organize into class sets
# ---------------------------------------------------------------------------
def route(texts, model, keep=(DECISION, LOCATION, INDIRECT)):
    """
    Returns (buckets, pool):
      buckets -> {label: [(text, conf, source), ...]}
      pool    -> items that stay in the processing pool
    Everything not in `keep` (e.g. IRRELEVANT) is removed from the pool.
    """
    buckets = defaultdict(list)
    for t in texts:
        label, conf, src = classify(t, model)
        buckets[label].append((t, conf, src))

    pool = [item for lbl in keep for item in buckets.get(lbl, [])]
    return dict(buckets), pool


# ---------------------------------------------------------------------------
# 8. EXAMPLE USAGE
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    model = train("golden_dataset.csv")  # columns: text,label

    new_posts = [
        "We're evacuating Tampa tonight #HurricaneExample",
        "Staying put, not leaving the house",
        "Roads are packed and my neighbors are all gone, Miami is a ghost town",
        "lol great game last night",
    ]
    buckets, pool = route(new_posts, model)

    for label, items in buckets.items():
        print(f"\n[{label}] ({len(items)})")
        for text, conf, src in items:
            print(f"  {conf:.2f} {src:<12} {text}")
