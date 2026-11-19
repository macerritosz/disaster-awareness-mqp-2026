
# ==================================================
# HURRICANE HARVEY SUBREDDIT COLLECTION
# ==================================================

# Directly affected communities and surrounding areas
PRIMARY_SUBREDDITS = {
    # Houston
    "houston",
    "askhouston",
    "houstoncirclejerk",
    "katy",
    "pearland",
    "sugarland",
    "thewoodlands",
    "conroe",
    "pasadena",
    "kingwood",
    "springbranch",
    "cypresstx",
    "friendswood",
    "deerpark",
    "channelview",
    "fortbend"

    # Southeast Texas and Gulf Coast
    "texas",
    "texasnews",
    "galveston",
    "corpuschristi",
    "beaumont"

    # Louisiana communities
    "louisiana",
    "neworleans",
    "batonrouge",
    "lakecharles",
}


# Weather, disaster, emergency, and assistance
SECONDARY_SUBREDDITS = {
    # Weather and hurricanes
    "weather",
    "tropicalweather",
    "hurricanes",
    "meteorology",
    "stormchasing",

    # Natural disasters
    "naturaldisasters",
    "disasterupdate",
    "disasterrelief",
    "disasterresponse",
    "disasterpreparedness",
    "disasterrecovery",
    "disastermanagement",
    "flood",
    "floods",
    "flooding",
    "flashfloods",

    # Emergency response
    "ems",
    "firefighting",
    "firefighters"
    "firstresponders",
    "searchandrescue",
    "rescue",
    "911dispatchers",

    # Preparedness
    "preppers",
    "prepper",
    "survival",
    "survivalism",

    # Community assistance
    "assistance",
    "volunteers",
    "volunteering",
    "humanitarian",
    "nonprofit",

    # Infrastructure and transportation
    "infrastructure",
    "truckers",
    "electricians",
    "power",
    "construction",
}


# Broad communities where Harvey-related submissions
# may appear outside dedicated disaster communities.
EXPLORATORY_SUBREDDITS = {
    # General news
    "news",
    # Environment and geography
    "climate",
    "climatechange",
    "environment",
    "environmentalism",

    "travel",

    # Economic and social impacts
    "povertyfinance",
    "personalfinance",
    "foodbank",
    "foodbanks",
    "community",
    "mutualaid",
}


# Combined collection set
ALLOWED_SUBREDDITS = (
    PRIMARY_SUBREDDITS
    | SECONDARY_SUBREDDITS
    | EXPLORATORY_SUBREDDITS
)


# Exclusions: keep this conservative for high recall.
EXCLUDED_SUBREDDITS = {
    # Explicitly unrelated or consistently noisy communities
    "gonewild",
    "gonewildscrubs",
}
