# Hurricane and storm activity
HURRICANE_KEYWORDS = [
    # English
    "harvey",
    "hurricane",
    "tropical storm",
    "tropical cyclone",
    "cyclone",
    "landfall",
    "storm surge",
    "storm chasing",
    "disaster chasing",
    "storm chaser",
    "storm damage",
    "heavy rain",
    "high winds",
    "rainfall",
    # Spanish
    "huracán",
    "huracan",
    "tormenta tropical",
    "ciclón",
    "marejada",
    "caza de tormentas",
    "cazatormentas",
    "lluvia intensa",
    "vientos fuertes",
    "precipitación",
]

# Evacuation and sheltering
EVACUATION_KEYWORDS = [
    "evacuate",
    "evacuated",
    "evacuation",
    "evacuating",
    "leaving",
    "getting out",
    "shelter",
    "sheltering",
    "displaced",
    "staying behind",
    "mandatory evacuation",
    "voluntary evacuation",
    "evacuation order",
    "evacuar",
    "evacuación",
    "evacuacion",
    "evacuado",
    "evacuando",
    "refugio",
    "albergue",
    "desplazado",
    "quedarse",
    "orden de evacuación",
    "orden de evacuacion",
]

# Flooding and water conditions
FLOODING_KEYWORDS = [
    "flood",
    "flooded",
    "flooding",
    "floodwater",
    "flood waters",
    "rising water",
    "water level",
    "flash flood",
    "underwater",
    "submerged",
    "street flooding",
    "river overflow",
    "high water",
    "water inside",
    "water entering",
    "water in my house",
    "inundación",
    "inundacion",
    "inundado",
    "inundada",
    "inundaciones",
    "desbordamiento",
    "agua subiendo",
    "crecida",
    "desbordado",
    "desbordada",
    "agua en mi casa",
    "calles inundadas",
]

# Rescue and assistance requests
RESCUE_KEYWORDS = [
    "rescue",
    "rescued",
    "rescuing",
    "stranded",
    "trapped",
    "drowning",
    "boat rescue",
    "need help",
    "send help",
    "help me",
    "911",
    "emergency assistance",
    "water rescue",
    "rescue request",
    "stuck in",
    "can't get out",
    "rescate",
    "rescatado",
    "atrapado",
    "atrapada",
    "necesito ayuda",
    "necesitamos ayuda",
    "envíen ayuda",
    "ahogando",
    "ayuda de emergencia",
    "no puedo salir",
]

# Transportation and mobility
TRANSPORTATION_KEYWORDS = [
    "highway",
    "road closure",
    "road closed",
    "road conditions",
    "traffic",
    "driving",
    "stranded vehicle",
    "bridge",
    "underpass",
    "interstate",
    "freeway",
    "closed roads",
    "flooded roads",
    "highway flooding",
    "road is flooded",
    "travel conditions",
    "carretera",
    "autopista",
    "camino cerrado",
    "carretera cerrada",
    "tráfico",
    "trafico",
    "conducir",
    "puente",
    "calles cerradas",
    "carretera inundada",
    "condiciones de tráfico",
    "condiciones de trafico",
]

# Infrastructure and utilities
INFRASTRUCTURE_KEYWORDS = [
    "power outage",
    "electricity",
    "blackout",
    "internet outage",
    "cell service",
    "water supply",
    "gas shortage",
    "no power",
    "no electricity",
    "no running water",
    "water service",
    "power lines",
    "electrical damage",
    "communication outage",
    "corte de luz",
    "sin electricidad",
    "apagón",
    "apagon",
    "sin internet",
    "sin agua",
    "suministro de agua",
    "escasez de gasolina",
    "líneas eléctricas",
    "líneas electricas",
    "servicio eléctrico",
    "servicio electrico",
]

# Food, supplies, and resources
RESOURCES_KEYWORDS = [
    "food",
    "water",
    "supplies",
    "medicine",
    "gas",
    "gasoline",
    "food shortage",
    "water shortage",
    "donations",
    "donating",
    "volunteers",
    "shelter availability",
    "emergency supplies",
    "bottled water",
    "food distribution",
    "comida",
    "alimentos",
    "agua potable",
    "suministros",
    "medicamentos",
    "gasolina",
    "donaciones",
    "voluntarios",
    "distribución de alimentos",
    "agua embotellada",
]

# Community behavior and social assistance
COMMUNITY_BEHAVIOR_KEYWORDS = [
    "neighbors",
    "family",
    "helping",
    "checking on",
    "taking in",
    "volunteering",
    "donating",
    "sharing supplies",
    "rescuing neighbors",
    "helping others",
    "community support",
    "mutual aid",
    "offering shelter",
    "opening my home",
    "vecinos",
    "familia",
    "ayudando",
    "ayudar",
    "voluntariado",
    "donando",
    "ayuda mutua",
    "apoyo comunitario",
    "ofrecer refugio",
    "ayudando a otros",
]

# Recovery and post-disaster experiences
RECOVERY_KEYWORDS = [
    "cleanup",
    "cleaning up",
    "rebuilding",
    "insurance",
    "mold",
    "repair",
    "recovery",
    "reconstruction",
    "temporary housing",
    "property damage",
    "home damage",
    "debris removal",
    "rebuilding my house",
    "flood damage",
    "limpieza",
    "reconstrucción",
    "seguro",
    "moho",
    "reparación",
    "recuperación",
    "vivienda temporal",
    "daños materiales",
    "daños en la casa",
    "escombros",
]


DISASTER_TERMS = [
    # Hurricanes and storms
    "hurricane", "hurricanes", "harvey",
    "hurricane harvey", "tropical storm",
    "tropical depression", "storm", "storms",
    "huricane", "hurricaine", "hurricance",

    # Flooding
    "flood", "floods", "flooding", "flooded",
    "flash flood", "flash flooding",
    "inundation", "inundated", "water rising",
    "water damage", "floodwater", "flood waters",

    # Evacuation
    "evacuate", "evacuated", "evacuating",
    "evacuation", "evacuations",
    "leave town", "getting out", "moving out",
    "shelter", "sheltering", "refuge",
    "stranded", "trapped", "stuck",

    # Rescue and assistance
    "rescue", "rescued", "rescuing",
    "need help", "send help", "help needed",
    "asking for help", "requesting help",
    "cajun navy", "first responders",
    "fema", "red cross", "relief",
    "supplies needed", "food needed",
    "water needed", "safe location",

    # Infrastructure
    "power outage", "no power", "without power",
    "electricity", "blackout", "water outage",
    "no water", "road closure", "road closed",
    "highway closed", "flooded roads",
    "damaged", "damage", "destroyed",
    "washed away", "closed roads",

    # Locations and roads
    "houston flood", "houston flooding",
    "galveston flood", "texas flooding",
    "highway 59", "i-10", "i-45",
    "highway 90", "highway 288",
    "highway 225", "highway 146",

    # Hashtags
    "harvey2017", "harveystorm",
    "harveyrelief", "sos houston",
    "soshouston", "sosharvey",
    "houstonflood",

    # Common misspellings
    "huricane", "hurricaine",
    "floodin", "evactuation",

    # Spanish
    "huracan", "tormenta", "inundacion",
    "inundaciones", "inundado", "inundada",
    "evacuar", "evacuacion", "evacuando",
    "refugio", "rescate", "ayuda",
    "necesito ayuda", "necesitamos ayuda",
    "sin electricidad", "sin agua",
    "sin luz", "atrapado", "atrapada",
    "desastre", "emergencia",
]


# Optional: every keyword in one deduplicated list (order preserved)
ALL_KEYWORDS = list(dict.fromkeys(
    HURRICANE_KEYWORDS
    + EVACUATION_KEYWORDS
    + FLOODING_KEYWORDS
    + RESCUE_KEYWORDS
    + TRANSPORTATION_KEYWORDS
    + INFRASTRUCTURE_KEYWORDS
    + RESOURCES_KEYWORDS
    + COMMUNITY_BEHAVIOR_KEYWORDS
    + RECOVERY_KEYWORDS
    + DISASTER_TERMS
))