"""
anchors.py — Ordered anchor-pattern classifiers for week1.py

Each list is ordered most-specific first so the first match wins.
Edit this file to tune subcategory rules; week1.py imports everything from here.
"""

import re

# =============================================================================
# Plumbing subcategory anchors — problem type first, bare fixture last
# =============================================================================
PLUMBING_ANCHORS = [
    (
        "Sewer/Backup",
        r"sewer|sewage|basement back|back ?up in basement|toilet bowl back",
    ),
    (
        "Clog/Drain",
        # added: back ?up / backed ?up / backin\.? ?up
        r"clog|cloog|cloged|overflow|backing up|backup|back ?up|backed ?up"
        r"|backin\.? ?up|\bdrain\b|not flushing|stoppage|snake",
    ),
    # Gas leaks are a safety issue, not a water issue — isolate before "Leak",
    # which would otherwise swallow "Gas leak" on the word "leak" alone.
    ("Gas Leak (Safety)", r"gas leak|smell(?:s|ing)? (?:of )?gas|gas odor"),
    (
        "Leak",
        # added: \blesk\b (misspelling)
        r"leak|leek|drip|water damage|leaky|\blesk\b",
    ),
    (
        "Hot Water/Supply",
        r"hot water|no water|water heater|expansion tank|storage tank"
        r"|water booster|domestic|no heat|hw supply",
    ),
    (
        "Toilet Internal Parts",
        # added: running water|water running — running-toilet descriptions;
        # Leak sits above and catches genuine "water running down the wall" phrases
        # that also contain leak/drip keywords before reaching this rule.
        r"flapper|wax ?ring|waxring|waxing|fill ?valve|fluid ?master|fluidmaster"
        r"|fluid-master|fludmaster|fluidvalve|\bfloat\b|flushmate|toilet tank"
        r"|speedy valve|tip ?toe|toilet.*running|running.*toilet|toilet.*pump"
        r"|running water|water running"
        r"|screws? (?:in|inside).*tank|supply line.*tank|tank.*supply line"
        r"|washes.*tank|\bchain\b",
    ),
    (
        "Faucet/Fixture Hardware",
        # added: back ?flow (widens "backflow" → "Back Flow Preventer")
        r"faucet|shower ?head|shower ?body|cartridge|shower handle|water handle"
        r"|water stopper|strainer|sump pump|backflow|back ?flow|grab bar|soap dish"
        r"|diverter|spout|push ?pop|pop ?up|\bknob\b|\bhandle\b|seat",
    ),
    # NEW — heat/steam risers; intercepts before Valve/Pressure
    ("Heating-Adjacent (Review)", r"heat riser|heat valve|\briser\b|steam"),
    # NEW — valve mechanisms, pumps, pressure issues
    (
        "Valve/Pressure",
        r"\bvalves?\b|\bvlave\b|\bpumps?\b|pressure|water main|water cut"
        r"|\bmeter\b|flushometer|flushometor",
    ),
    (
        "Pipe Repair",
        r"\bpipe\b|pipes|waste ?bend|waste ?line|wasteline|waist been|weastben",
    ),
    (
        "Caulking/Sealing",
        # added: chaulk, cualking (phonetic misspellings)
        r"caulk|calk|chaulk|cualking|cork|\bseal\b|mold|mildew",
    ),
    # NEW — administrative/regulatory driver
    ("Violation-Driven", r"violation|\bhpd\b|court order|section 8|abate"),
    ("Plumbing Inspection", r"inspection"),
    ("Toilet (General)", r"toilet|toliet"),
    ("Bathtub (General)", r"bathtub|bath tub|\btub\b"),
    ("Kitchen Sink (General)", r"kitchen sink|kitchen"),
    ("Bathroom Sink (General)", r"bathroom sink|\blav\b|vanity"),
    ("Bathroom (General)", r"bathroom|bath ?room|shower"),
    ("Basement (General)", r"basement"),
]

# =============================================================================
# Extermination subcategory anchors
# =============================================================================
EXTERMINATION_ANCHORS = [
    (
        "Bedbugs",
        # widened: bed ?bugs? → bed ?bu[gd]s?; bedbgs → bedb[gu]+s
        r"bed ?bu[gd]s?|bedb[gu]+s|begs bugs|bed  bug",
    ),
    ("Rodents", r"\bmice\b|\bmouse\b|mices|\brat\b|\brats\b|rodent|raccoon|racoon"),
    ("Roaches", r"roach|roahes|roches"),
    (
        "Other Pest",
        r"\bant\b|\bants\b|termite|maggot|moth|hornet|\bfly\b|flies|flying"
        r"|\bnats\b|gnat|worm|wasp|fungus",
    ),
    (
        "Violation-Driven",
        # added: \bdoh\b (Dept of Health)
        r"violation|\bhpd\b|\bdoh\b|court order|abate|nycha",
    ),
    (
        "General/Unspecified",
        # added: infectation|infections? (misspellings of "infestation")
        r"exterminat|exermination|extermaination|\bpest\b|infestation|infested"
        r"|infectation|infections?\b|sanitiz|spray|treat|\bhole",
    ),
]

# =============================================================================
# Doors and Locks
# =============================================================================
DOORS_AND_LOCKS_ANCHORS = [
    ("Intercom/Buzzer", r"intercom|inter ?com|buzzer|door ?bell"),
    (
        "Lock/Cylinder/Key",
        # cilinder is a recurring misspelling of cylinder; chain covers door chains
        r"\block\b|\blocks\b|lockset|cylinder|cilinder|dead ?bolt|\bkeys?\b"
        r"|latch|locked out|lock ?out|lock issue|\bchain\b",
    ),
    ("Closer/Hinge", r"clos(?:er|ing)|hinge|self.?clos|spring|off track|sagging"),
    (
        "Handle/Hardware",
        r"handle|\bknob\b|peep ?hole|door ?stop|kick ?plate|threshold|\bplate\b"
        r"|strike|panic bar",
    ),
    (
        "Frame/Glass Damage",
        r"frame|\bjamb\b|glass|broking glass|broken|\bbroke\b|damage|crack|\bhole\b",
    ),
    ("Door Replacement/Install", r"replace|install|new door"),
    ("Violation-Driven", r"violation|\bhpd\b|court order"),
    # "repair"/"not work"/"ok" were removed from this pattern: they are common
    # enough to steal rows that never mention a door at all — an audited sample
    # found "COURT ORDER REPAIRS", "555:Bell is not working" (intercom), and
    # "555Bus- telecom repaired" all mislabeled Door (General) before this fix.
    ("Door (General)", r"\bdoors?\b|\bgates?\b"),
]

# =============================================================================
# Electrical
# =============================================================================
ELECTRICAL_ANCHORS = [
    ("Inspection/Violation", r"inspection|violation|\bhpd\b"),
    (
        "Outlet/Switch",
        # gfic/gfi/gri are common miskeyings of gfci
        r"outlet|receptacle|\bswitch|\bgfci\b|\bgfic\b|\bgfi\b|\bgri\b|\bplug\b|socket",
    ),
    (
        "Power Loss/Outage",
        r"no (?:power|electric|current|electricity)|power (?:out|loss)|outage"
        r"|\bshort\b|sparking|tripping",
    ),
    (
        "Breaker/Panel/Wiring",
        r"breaker|\bpanel\b|\bfuse\b|circuit|\bmeter\b|riser|wiring|\bwire",
    ),
    ("Smoke/CO Detector", r"smoke (?:alarm|detector)|carbon monoxide|\bco2\b|detector"),
    ("Intercom", r"intercom|buzzer"),
    (
        "Lighting Fixture",
        r"\blights?\b|light ?fixture|\bfixtures?\b|bulb|ballast|flu?o?rescent|lamp|lighting",
    ),
    ("Fan/Exhaust", r"\bfan\b|exhaust|\bhood\b"),
    (
        "Appliance Circuit",
        r"stove|refrigerator|fridge|dryer|washer|\bac\b|air ?condition|oven",
    ),
    (
        "Electrical (General)",
        # eletrical/electic are recurring misspellings
        r"electric|eletric|electic|\belec\b",
    ),
]

# =============================================================================
# Appliances
# =============================================================================
APPLIANCES_ANCHORS = [
    # Gas leaks are a safety issue — isolate them before the stove/range rule,
    # which would otherwise swallow them on the word "gas".
    ("Gas Leak", r"gas leak|smell(?:s|ing)? (?:of )?gas|gas odor"),
    ("Range Hood/Vent", r"range ?hood|\bhood\b|exhaust|\bvent\b"),
    ("Refrigerator", r"refrig|fridge|freezer|ice ?maker|gasket|not cooling"),
    ("Stove/Oven/Range", r"stove|\boven\b|\brange\b|burner|pilot|\bgas\b|cook"),
    ("Dishwasher", r"dish ?washer"),
    ("Washer/Dryer", r"washer|dryer|laundry"),
    ("Microwave", r"microwave"),
    ("Air Conditioner", r"\bac\b|air ?condition|\ba/c\b"),
    ("Appliance (General)", r"appliance"),
]

# =============================================================================
# Boiler
# =============================================================================
BOILER_ANCHORS = [
    (
        "Heat Complaint",
        r"no heat|not heating|lack of heat|little heat|high heat|heat complaint"
        r"|\bcold\b|too hot",
    ),
    ("No Hot Water", r"no hot water|hot water|\bhw\b|\bdhw\b|domestic|water heater"),
    ("Leak", r"leak|drip|water damage"),
    ("Pump/Circulator", r"\bpump\b|circulat"),
    ("Tank/Expansion", r"expansion|\btank\b|relief|\bcoil\b"),
    ("Burner/Pilot/Ignition", r"burner|pilot|ignit|flame|\blit\b|re.?lit"),
    (
        "Controls/Sensor",
        r"control|aquastat|thermostat|sensor|gauge|\bvalves?\b|\bswitch\b|low water",
    ),
    # Broken venting is a carbon-monoxide risk, not routine wear — keep it out
    # of the undifferentiated General bucket.
    ("Flue/Venting (Safety)", r"\bflue\b|venting|\bchimney\b"),
    ("Violation-Driven", r"violation|\bhpd\b|court order"),
    ("Cleaning/Annual Maintenance", r"clean|annual|maintenance|service|tune|inspect"),
    (
        "Boiler (General)",
        # \bheat(?:ing)?\b, not \bheat\b: the strict form doesn't match "heating"
        # (no word boundary between "heat" and "ing") — found via a 2026-07 audit
        # row, "Inadeqauate heating baseboards", which fell all the way to the
        # Carpentry topic fallback on the substring "baseboard" instead of
        # matching here.
        r"boiler|furnace|\bheat(?:ing)?\b|steam",
    ),
]

# =============================================================================
# Inspection — anchored on inspection PROGRAM. Descriptions that name the thing
# inspected rather than the program ("lights", "stove") fall through to the
# tier-1 topic fallback in categorize.py.
# =============================================================================
INSPECTION_ANCHORS = [
    ("REAC/HUD", r"\breac\b|\bhud\b"),
    ("Section 8/HQS", r"section ?8|\bhqs\b"),
    ("Violation-Driven", r"violation|\bhpd\b|\bdob\b|\bdoh\b|court order|\bfdny\b"),
    (
        "Move-In/Move-Out",
        r"move ?in|move ?out|vacate|vacant|turn ?over|apartment prep|apt\.? ?prep",
    ),
    (
        "Annual/Routine",
        r"annual|routine|inspection maintenance|general/misc|periodic|quarterly"
        r"|monthly|semi.?annual",
    ),
    ("Inspection (General)", r"inspect"),
]

# =============================================================================
# Painting and Plastering
# =============================================================================
PAINTING_ANCHORS = [
    ("Mold/Mildew", r"mold|mildew|fungus"),
    ("Water Damage", r"water dam|water stain|\bstain\b|leak|ceiling"),
    ("Violation-Driven", r"violation|\bhpd\b|court order"),
    (
        "Plaster/Sheetrock Repair",
        r"plaster|sheet ?rock|dry ?wall|spackle|skim|patch|\bhole|crack"
        r"|compound|sanding|scrap",
    ),
    ("Painting", r"paint|prime|priming|\bcoat\b"),
]

# =============================================================================
# Windows
# =============================================================================
WINDOWS_ANCHORS = [
    ("Window Guard", r"\bguards?\b|child ?safe|\bbars?\b"),
    ("Screen", r"screen"),
    ("Blind/Shade", r"blind|shade|curtain"),
    ("Glass/Pane Damage", r"glass|\bpane\b|broken|\bbroke\b|crack|shatter|\bbrek\b"),
    ("Lock/Hardware", r"\block|latch|handle|balance|\bsash\b|hinge|crank|\bstop\b"),
    ("Leak/Draft/Seal", r"leak|draft|drafty|caulk|\bseal\b|weather ?strip|\bwater\b"),
    ("Window (General)", r"window"),
]

# =============================================================================
# Fire Safety
# =============================================================================
FIRE_SAFETY_ANCHORS = [
    (
        "Smoke/CO Detector",
        # "sd" is the abbreviation used in NYCHA-referencing work orders
        r"smoke|carbon monoxide|\bco2?\b|detector|\bsd\b|\balarm",
    ),
    (
        "Sprinkler/Standpipe",
        r"sprinkler|sprink|standpipe|siamese|\bhose\b|flow test|hydrostatic"
        r"|pressure test|\briser\b",
    ),
    ("Extinguisher", r"extinguish"),
    ("Self-Closing Door", r"self.?clos|closer|fire ?door"),
    ("Emergency Light/Exit", r"\bexit\b|emergency light|egress"),
    ("Inspection/Local Law", r"inspect|local law|\bfdny\b|violation|annual|\bll\d+\b"),
]

# =============================================================================
# Heating
# =============================================================================
HEATING_ANCHORS = [
    (
        "No Heat",
        r"no heat|not heating|lack of heat|little heat|\bcold\b|heat complaint",
    ),
    ("Radiator/Convector", r"radiator|convector|\bheater\b|fin ?tube|baseboard heat"),
    (
        "Valve/Trap/Riser",
        r"\bvalves?\b|\btrap\b|\briser\b|air ?vents?|\bvents?\b|\bzone\b",
    ),
    (
        "Thermostat/Controls",
        # thermostant is a recurring misspelling
        r"thermostat|thermostant|control|sensor|ignit",
    ),
    ("Leak", r"leak|drip|\bwater\b"),
    ("Heating (General)", r"\bheat|steam|boiler"),
]

# =============================================================================
# Carpentry
# =============================================================================
CARPENTRY_ANCHORS = [
    ("Cabinet/Countertop", r"cabinet|cabin |counter|vanity|medicine"),
    (
        "Bathroom Accessory",
        # soap dishes and towel racks are filed here rather than under Plumbing
        r"soap ?dish|towel|toothbrush|tissue|\brack\b|\brak\b",
    ),
    (
        "Water Damage/Ceiling",
        # mis-filed plaster work; "sral" is a recurring typo for "seal"
        r"water damage|ceiling|\bsral\b|\bseal\b",
    ),
    ("Sheetrock/Wall", r"sheets? ?rock|dry ?wall|\bwalls?\b"),
    ("Closet/Shelving", r"closet|shelf|shelv|\brod\b|\bpole\b"),
    ("Trim/Molding", r"molding|moulding|baseboard|\btrim\b|threshold"),
    ("Drawer", r"drawer"),
    ("Railing/Bench/Fixture", r"railing|\brail\b|bench|\bbanister\b"),
    ("Door/Frame", r"\bdoors?\b|\bframe\b|\bjamb\b"),
    ("Carpentry (General)", r"carpentr|\bwood\b|lumber|plywood"),
]

# =============================================================================
# Lighting
# =============================================================================
LIGHTING_ANCHORS = [
    ("Bulb Replacement", r"bulb|\blamp\b|\bled\b"),
    ("Ballast/Fixture", r"ballast|fixture|flu?o?resc|\bcover\b|globe"),
    ("Switch/Sensor/Timer", r"\bswitch|sensor|timer|photo ?cell"),
    (
        "Common Area/Exterior",
        r"hall ?way|\bhall\b|lobby|stair|exterior|outside|basement|common"
        r"|compound|yard|entrance",
    ),
    ("Out/Not Working", r"not work|no light|burn|\bout\b|\bdark\b"),
    ("Lighting (General)", r"light"),
]

# =============================================================================
# HVAC
# =============================================================================
HVAC_ANCHORS = [
    # PTAC (packaged terminal air conditioner) is the dominant unit type here and
    # gets written a dozen ways: PTAC, Ptac, P-tac, PTACS.
    ("PTAC Unit", r"\bp.?tacs?\b"),
    (
        "Make-Up Air/Air Handler",
        r"make.?up air|air ?handler|\bahu\b|\bmuau?\b|roof ?top|\brtu\b",
    ),
    (
        "Air Conditioning",
        r"\bac\b|air ?condition|\ba/c\b|condenser|chiller|split|compressor",
    ),
    (
        "Exhaust Fan/Ventilation",
        r"exhaust|\bfans?\b|ventilat|\bvents?\b|\bduct\b|blower|filtration",
    ),
    ("Leak/Flood", r"leak|drip|condensate|flood"),
    ("Pump/Motor", r"\bpump\b|circulat|\bmotors?\b"),
    (
        "Temperature Complaint",
        # "no eat" is a recurring typo for "no heat"
        r"\bcold\b|to+ hot|no eat|no heat|not heating",
    ),
    (
        "Filter/Maintenance",
        r"filter|clean|maintenance|service|inspect|\bbelt\b|\bcovers?\b",
    ),
    ("Thermostat/Controls", r"thermostat|control|sensor|\bswitch\b"),
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Heating-Adjacent (Review)", r"\bheat|boiler|\bsteam\b"),
    ("HVAC (General)", r"hvac|trouble ?shoot|\binstall\b|\brepairs?\b"),
]

# =============================================================================
# Flooring
# =============================================================================
FLOORING_ANCHORS = [
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Tile", r"\btiles?\b|\bvct\b|linoleum|vinyl|grout"),
    ("Carpet", r"carpet|\brug\b"),
    ("Wood/Parquet", r"parquet|\bwood\b|hardwood|\bsand(?:ing)?\b|refinish"),
    ("Damage/Crack", r"damage|crack|broken|\bhole|buckl|loose|uneven"),
    ("Flooring (General)", r"floor"),
]

# =============================================================================
# Apt. Prep.
# =============================================================================
APT_PREP_ANCHORS = [
    ("Inspection", r"inspect|section ?8|sec ?8|\bhpd\b"),
    (
        "Vacant/Turnover",
        r"vacan(?:t|cy|cies)|move ?out|turn ?over|turnover|empty|pre ?apartment",
    ),
    ("Painting", r"paint"),
    ("Kitchen/Bath Renovation", r"kitchen|bath|counter ?top|cabinet|\bsink\b|\btub\b"),
    ("Flooring", r"floor|\btile"),
    (
        "Apt. Prep. (General)",
        # covers "apartment prep", "apt prep", "apt.prep", "apt .prep"
        r"apartment ?prep|apt\s*\.?\s*prep|\bprep\b",
    ),
]

# =============================================================================
# Roofing
# =============================================================================
ROOFING_ANCHORS = [
    ("Roof Leak", r"leak|\bwater\b|infiltrat"),
    ("Exhaust Fan (Roof)", r"exhaust ?fan|fan ?belt|\bfan\b"),
    ("Chimney/Parapet", r"chimney|parapet|coping|\bcap\b"),
    ("Gutter/Drain", r"gutter|\bdrain\b|downspout|scupper"),
    ("Skylight", r"sky ?light|bulkhead"),
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Roof (General)", r"roof"),
]

# =============================================================================
# Elevator
# =============================================================================
ELEVATOR_ANCHORS = [
    (
        "Out of Service",
        r"not working|shut ?down|stuck|out of service|\bdown\b|trapped|stall",
    ),
    ("Door", r"\bdoors?\b|won'?t close|not clos"),
    ("Noise/Vibration", r"\bbang|rattl|noise|\bsound|shak|vibrat|squeak"),
    ("Violation/Inspection", r"violation|inspect|\bcat ?[15]\b|\bdob\b"),
    ("Phone/Emergency", r"\bphone\b|emergency|intercom|\balarm\b"),
    ("Lighting", r"\blight"),
    ("Lock/Hardware", r"\block|button|panel|\bkey\b"),
    ("Elevator (General)", r"elevator|\blift\b|\bevator\b"),
]

# =============================================================================
# Miscellaneous — a catch-all category in Yardi. Most rows describe work that
# belongs elsewhere, so the tier-1 topic fallback does the heavy lifting here.
# =============================================================================
MISCELLANEOUS_ANCHORS = [
    ("Smoke/CO Detector", r"smoke|detector|carbon monoxide|\bco2\b|\balarms?\b"),
    ("Intercom", r"intercom|buzzer|door ?bell"),
    ("Mailbox", r"mail ?box"),
    ("Window Treatment", r"shade|blind|curtain"),
    ("Grab Bar/Accessibility", r"grab ?bar|hand ?rail|\bramp\b"),
    ("Bathroom Accessory", r"soap ?dish|towel|toothbrush|\brack\b|\brak\b"),
    ("Violation/Court Order", r"court order|violation|\bhpd\b"),
    (
        "Caulking/Sealing",
        # culking is a recurring phonetic misspelling
        r"caulk|culking|\bholes?\b|\bseal\b",
    ),
    ("Lock/Door", r"\blocks?\b|\bdoors?\b"),
]

# =============================================================================
# Site Work
# =============================================================================
SITE_WORK_ANCHORS = [
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Fence/Gate", r"\bfence\b|\bgates?\b|railing|\bmesh\b"),
    (
        "Landscaping/Yard",
        r"\btree\b|weed|grass|\byard\b|\bmow|shrub|garden|lawn|over ?grown|hedge",
    ),
    ("Garbage/Sanitation", r"garbage|trash|\bpails?\b|refuse|recycl|\bclean|sweep"),
    (
        "Sidewalk/Steps/Paving",
        r"sidewalk|\bsteps?\b|\bcurb\b|concrete|pav(?:e|ing|ement)|asphalt|stoop",
    ),
    ("Masonry", r"masonry|brick|pointing|\bstones?\b|cement"),
    ("Supplies/Materials", r"supplies|materials|\bplans\b|\bsalt\b|equipment|handyman"),
    ("Signage", r"\bsigns?\b|awning"),
    ("Painting", r"paint"),
]

# =============================================================================
# Exterior
# =============================================================================
EXTERIOR_ANCHORS = [
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Leak/Water Infiltration", r"leak|\bwater\b|infiltrat|\bdamp\b"),
    (
        "Facade/Wall/Masonry",
        r"\bwall|brick|pointing|facade|stucco|\bmasonry\b|\bsiding\b|\bstones?\b"
        r"|cement|concrete",
    ),
    ("Window/Door", r"window|\bdoors?\b|screen"),
    ("Gate/Fence/Security", r"\bgates?\b|\bfence\b|\block|chain"),
    ("Steps/Walkway", r"\bsteps?\b|stoop|stair|trip hazard|entrance|sidewalk"),
    ("Yard/Grounds", r"\byard\b|\bmow|clean|\bsalt\b|snow|shovel|garbage|\bcans?\b"),
    ("Exterior (General)", r"exterior|outside|building"),
]

# =============================================================================
# Landscaping — dominated by one recurring phrasing, "[address]-Backyard
# Cleaning", repeated near-verbatim across dozens of properties.
# =============================================================================
LANDSCAPING_ANCHORS = [
    ("Tree Work", r"\btrees?\b|shrub|branch|bamboo|deforestation|\bhedge\b"),
    ("Grass/Weed", r"\bgrass\b|weed|\bmow(?:ing)?\b|\blawn\b"),
    ("Garbage/Cans", r"garbage|\bcans?\b|compost"),
    ("Yard/Backyard Cleaning", r"\bclean|\byard\b|back ?yard"),
    ("Landscaping (General)", r"landscap|garden|graffiti"),
]

# =============================================================================
# Compactor
# =============================================================================
COMPACTOR_ANCHORS = [
    ("Chute/Door", r"\bchutes?\b|\bdoors?\b|\blatch(?:es)?\b|\bhinges?\b"),
    ("Electrical/Mechanical", r"\bsensor\b|\bac\b|a/c"),
    ("Leak", r"\bleak|\boil\b"),
    ("Out of Service", r"(?:not|stopped|is not) working|out of order|\bdown\b"),
    ("Room/Housekeeping", r"\bclosets?\b|\bpaint|\bclean"),
    ("Inspection", r"inspect"),
    # Distinct from equipment issues above — these are pickup-day scheduling
    # complaints ("garbage for Thursday for Friday"), filed under Compactor
    # because the two share a physical location, not because they're the
    # same kind of problem.
    ("Garbage Collection/Schedule", r"garbage|compost|\bcarts?\b"),
    ("Compactor (General)", r"compact"),
]

# =============================================================================
# Security — cameras dominate by a wide margin; door hardware deliberately
# does not include bare "handle" (only "\bdoors?\b|\bbuzzer\b|stricker"), since
# a real row — "support handle bar for bathtub", a mis-filed grab-bar request —
# would otherwise match "handle" and get labeled as door hardware.
# =============================================================================
SECURITY_ANCHORS = [
    ("Camera/Surveillance", r"\bcamera|\bdvr\b|\bcctv\b|surveillance"),
    ("Alarm System", r"\balarms?\b"),
    ("Lock/Key/Cylinder", r"\block\b|\blocks\b|padlock|cylinder|\bkeys?\b|\bmailbox\b"),
    ("Door Hardware", r"\bdoors?\b|\bbuzzer\b|stricker"),
    ("Security (General)", r"security|civilian"),
]

# =============================================================================
# Fixed Assets/Repair — Yardi's true miscellaneous-ticket bucket. Far more
# heterogeneous than any category anchored so far: mold, violations, cabinet
# replacement, plumbing fixtures, appliances, fire safety, and site work all
# appear. Ordered by the clearest, highest-frequency clusters; "Fixed Assets
# (General)" catches anything left that at least says "repair" or "replace".
# =============================================================================
FIXED_ASSETS_ANCHORS = [
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Mold/Mildew", r"mold|mildew"),
    ("Fire Safety", r"fire retardant|smoke detector|\bfire\b"),
    ("Countertop/Cabinet", r"counter ?top|\bcabinets?\b"),
    (
        "Plumbing Fixture",
        r"\btoilet\b|\bsink\b|\btub\b|soap ?dish|\btowel|flapper|flow switch"
        r"|\bdrain\b|gas shut",
    ),
    ("Appliance", r"\bstove\b|\boven\b|vacuum|refrigerator|fridge"),
    ("HVAC/AC", r"air ?vent|\bac\b|radiator cover"),
    ("Flooring", r"\bfloor|\btiles?\b"),
    ("Camera/Security", r"\bcamera"),
    ("Site Work/Exterior", r"pavement|snowblower|\bgate\b|graffiti"),
    ("Supplies/Prep", r"supplies|\btools\b|moving day|vacant"),
    ("Fixed Assets (General)", r"repair|replace"),
]

# =============================================================================
# Building Signs — despite the name, dominated by "no access" complaints
# (crews turned away from a locked heating/basement room) far more than
# actual signage, plus a recurring cluster of HPD violation notices.
# =============================================================================
BUILDING_SIGNS_ANCHORS = [
    ("Violation-Driven", r"violation|\bhpd\b"),
    ("Gas Leak (Safety)", r"gas leak"),
    ("Smoke/CO Detector", r"smoke alarm|smoke detector"),
    (
        "No Access",
        # "acess" is a recurring misspelling of "access"
        r"acc?ess|key to heat|door lock",
    ),
    ("Sign/Notice", r"\bsigns?\b|notice|\babc\b"),
    ("Building Signs (General)", r"building|\bheat\b"),
]

# =============================================================================
# Tier-1 category anchors — used to infer category for blank rows, and as the
# topic fallback for rows whose description doesn't match their own category
# =============================================================================
TIER1_ANCHORS = [
    (
        "Extermination",
        r"bed ?bug|bedbgs|\bmice\b|\bmouse\b|\brat\b|\brats\b|rodent|raccoon"
        r"|roach|roahes|exterminat|\bpest\b|infestation|infested|termite|maggot",
    ),
    ("Elevator", r"elevator|\blift\b"),
    ("Compactor", r"compactor"),
    ("Boiler", r"boiler"),
    ("Heating", r"\bheat(?:ing)?\b|radiator|thermostat|steam"),
    (
        "Fire Safety",
        # \balarms?\b and detector added so a bare "Alarm" or "Combo Alarm" resolves.
        # \bsmoke\b (bare) added 2026-07: Yardi truncates brief_desc around 34
        # chars, so "INSTALLATION OF AT LEAST ONE SMOKE" cuts off before ever
        # reaching "detector" — 9 real rows were unmatched purely from truncation.
        r"smoke (?:detector|alarm)|fire (?:extinguish|alarm|safety)|co2"
        r"|carbon monoxide|sprinkler|standpipe|fdny|local law|self.?clos"
        r"|smoke alarm|smoke detector|\balarms?\b|detector|\bco/sd\b|\bsmoke\b",
    ),
    (
        "Plumbing",
        r"clog|cloog|leak|leek|toilet|toliet|faucet|sink|bathtub|\btub\b"
        r"|sewer|sewage|caulk|calk|flapper|wax ?ring|shower|\bpipe\b|\bdrain\b"
        r"|fluid ?master|fill ?valve|speedy valve|hot water|water heater|plumb|drip"
        r"|grab ?bar",
    ),
    ("Electrical", r"electric|outlet|wiring|breaker|circuit|gfci|\bwire\b|sparking"),
    ("Lighting", r"\blight\b|lights|bulb|ballast|fluorescent|lamp"),
    (
        "Appliances",
        r"refrigerator|fridge|stove|oven|range|dishwasher|microwave|washer"
        r"|dryer|\bac\b|air condition|appliance|freezer",
    ),
    (
        "Doors and Locks",
        # Plurals matter here: \bdoor\b does not match "doors", which is how these
        # were written. Same for lock/keys.
        r"\bdoors?\b|\blocks?\b|lockset|deadbolt|hinge|cylinder|\bkeys?\b|peephole"
        r"|intercom|closer|mail ?box",
    ),
    ("Windows", r"window|\bsash\b|\bpane\b|glass|screen|\bguard\b|blind|shade"),
    ("Flooring", r"floor|tile|linoleum|vinyl|carpet|parquet|grout"),
    (
        "Painting and Plastering",
        r"paint|plaster|spackle|skim coat|sheet ?rock|dry ?wall|water damage"
        r"|ceil?ling|ceiling|\bwalls?\b",
    ),
    (
        "Carpentry",
        # \btrim\b, not bare "trim": unbounded it matched "tree trimming" and
        # "grass trimming" (landscaping work) as Carpentry — found via a 2026-07
        # test that caught the topic fallback resolving a Landscaping-filed row
        # to Carpentry on the "trim" substring inside "trimming".
        r"cabinet|counter|closet|shelf|shelv|molding|baseboard|\btrim\b|carpentr"
        r"|drawer|vanity|medicine cabinet",
    ),
    ("Roofing", r"roof|gutter|skylight|parapet"),
    (
        "HVAC",
        r"hvac|ventilation|exhaust fan|\bvent\b|air handler|condenser|make up air",
    ),
    (
        "Landscaping",
        r"landscap|tree|shrub|garden|lawn|hedge|weed|grass|backyard|back yard",
    ),
    (
        "Site Work",
        r"sidewalk|pav(?:e|ing|ement)|concrete|asphalt|\bfence\b|\bgates?\b|curb"
        r"|powerwash|\bsigns?\b|masonry",
    ),
    ("Security", r"security|camera|cctv|surveillance|alarm system"),
    ("Apt. Prep.", r"apartment prep|apt prep|vacant|make ready|turnover|paint vacant"),
]

# =============================================================================
# Registry — maps a tier-1 category to its ordered subcategory anchors.
#
# Categories absent from this dict get no subcategory anchors of their own;
# their rows are labeled by the tier-1 topic fallback instead. The 19 keys here
# cover 97% of work orders in the source-of-truth dataset.
# =============================================================================
SUBCATEGORY_ANCHORS = {
    "Plumbing": PLUMBING_ANCHORS,
    "Extermination": EXTERMINATION_ANCHORS,
    "Doors and Locks": DOORS_AND_LOCKS_ANCHORS,
    "Inspection": INSPECTION_ANCHORS,
    "Electrical": ELECTRICAL_ANCHORS,
    "Appliances": APPLIANCES_ANCHORS,
    "Boiler": BOILER_ANCHORS,
    "Painting and Plastering": PAINTING_ANCHORS,
    "Windows": WINDOWS_ANCHORS,
    "Fire Safety": FIRE_SAFETY_ANCHORS,
    "Heating": HEATING_ANCHORS,
    "Carpentry": CARPENTRY_ANCHORS,
    "Lighting": LIGHTING_ANCHORS,
    "HVAC": HVAC_ANCHORS,
    "Flooring": FLOORING_ANCHORS,
    "Apt. Prep.": APT_PREP_ANCHORS,
    "Roofing": ROOFING_ANCHORS,
    "Elevator": ELEVATOR_ANCHORS,
    "Miscellaneous": MISCELLANEOUS_ANCHORS,
    "Site Work": SITE_WORK_ANCHORS,
    "Exterior": EXTERIOR_ANCHORS,
    "Landscaping": LANDSCAPING_ANCHORS,
    "Compactor": COMPACTOR_ANCHORS,
    "Security": SECURITY_ANCHORS,
    "Fixed Assets/Repair": FIXED_ASSETS_ANCHORS,
    "Building Signs": BUILDING_SIGNS_ANCHORS,
}

# Compile every pattern once at import time. Rebinding the module-level lists
# keeps `from anchors import PLUMBING_ANCHORS` returning compiled patterns.
SUBCATEGORY_ANCHORS = {
    category: [(label, re.compile(pattern)) for label, pattern in anchors]
    for category, anchors in SUBCATEGORY_ANCHORS.items()
}

PLUMBING_ANCHORS = SUBCATEGORY_ANCHORS["Plumbing"]
EXTERMINATION_ANCHORS = SUBCATEGORY_ANCHORS["Extermination"]
TIER1_ANCHORS = [(label, re.compile(pattern)) for label, pattern in TIER1_ANCHORS]

# Retained for backwards compatibility — ANCHOR_MAP was the original name.
ANCHOR_MAP = SUBCATEGORY_ANCHORS

# Matches descriptions that are just an address with no work detail
ADDRESS_ONLY_RE = re.compile(r"^\d{2,4}")
