"""
MagicSteam — Enhanced MTG natural language search parser.

Accepts plain English, MTG slang, Scryfall-style "+" compound syntax, or any mix.

Split on "+" for explicit AND-compound queries. Within each segment, every word is
classified independently (stop words stripped, slang normalised, synonyms expanded).
Spaces within a segment are treated as implicit AND across that segment's words.

Supported categories
--------------------
Colors          : white / blue / black / red / green / colorless
                  + guild (azorius, izzet …), shard (bant, grixis …), wedge names
Multicolor      : multicolor / multicolored / gold / two-color / guild / shard / wedge …
Monocolor       : mono / mono-red / monoblue …
Rarity          : common / uncommon / rare / mythic
Format          : standard / pioneer / modern / legacy / vintage / commander / edh / pauper …
CMC / mana value: "2 mana", "costs 3", "cmc:4", "two-drop", "cheap" (≤2), "free" (=0),
                  "expensive" (≥5), "3 or less", "under 4 mana" …
Oracle synonyms : draw / cantrip / wrath / boardwipe / removal / counter / ramp / tutor /
                  blink / mill / burn / recursion / tokens / discard / bounce / combo …
Type synonyms   : legendary / creature / instant / sorcery / artifact / enchantment …
Free text       : anything else → searched across name + type_line + oracle_text + translations

Examples
--------
"multicolor elf"
"blue counter modern"
"red dragon haste"
"a card that helps me draw more + blue + 2 mana cost"
"cheap removal white"
"green ramp tutor legendary"
"common burn spell"
"mono red aggro two-drop"
"boardwipe white rare"
"ドラゴン" (searches translations)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Color maps
# ---------------------------------------------------------------------------

_COLOR_MAP: dict[str, list[str]] = {
    "white": ["W"], "w": ["W"],
    "blue":  ["U"], "u": ["U"],
    "black": ["B"], "b": ["B"],
    "red":   ["R"], "r": ["R"],
    "green": ["G"], "g": ["G"],
    # Guilds
    "azorius": ["W", "U"], "dimir":   ["U", "B"],
    "rakdos":  ["B", "R"], "gruul":   ["R", "G"],
    "selesnya":["G", "W"], "orzhov":  ["W", "B"],
    "izzet":   ["U", "R"], "golgari": ["B", "G"],
    "boros":   ["R", "W"], "simic":   ["G", "U"],
    # Shards
    "bant":   ["G", "W", "U"], "esper": ["W", "U", "B"],
    "grixis": ["U", "B", "R"], "jund":  ["B", "R", "G"],
    "naya":   ["R", "G", "W"],
    # Wedges
    "abzan": ["W", "B", "G"], "jeskai": ["U", "R", "W"],
    "sultai": ["B", "G", "U"], "mardu":  ["R", "W", "B"],
    "temur":  ["G", "U", "R"],
    # 5-colour
    "five": ["W", "U", "B", "R", "G"],
    "rainbow": ["W", "U", "B", "R", "G"],
    "wubrg":   ["W", "U", "B", "R", "G"],
}

_RARITIES = frozenset({"common", "uncommon", "rare", "mythic"})

_FORMAT_MAP: dict[str, str] = {
    "standard": "standard", "pioneer": "pioneer",
    "modern": "modern",     "legacy": "legacy",
    "vintage": "vintage",   "commander": "commander",
    "edh": "commander",     "pauper": "pauper",
    "brawl": "brawl",       "historic": "historic",
    "alchemy": "alchemy",   "explorer": "explorer",
    "penny": "penny",
}

# ---------------------------------------------------------------------------
# Multicolor / monocolor recognition
# ---------------------------------------------------------------------------

_MULTICOLOR_TOKENS = frozenset({
    "multicolor", "multicolored", "multicolour", "multicoloured",
    "multi-color", "multi-colored", "multi-colour", "multi-coloured",
    "gold",          # MTG slang: gold-bordered = multicolour
    "hybrid",
    "two-color", "twocolor", "2-color",
    "three-color", "threecolor", "3-color",
    "four-color", "fourcolor", "4-color",
    "five-color", "fivecolor", "5-color",
})

_MONOCOLOR_TOKENS = frozenset({
    "mono", "monocolor", "monocolored", "monocolor",
    "mono-color", "mono-colored", "mono-colour", "mono-coloured",
    "monocolour", "monocoloured",
    # Natural modifiers: "black only", "only red", "purely white"
    "only", "solely", "pure", "purely", "just",
})

# ---------------------------------------------------------------------------
# Stop words (stripped before classification)
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    # Articles / pronouns / prepositions
    "a", "an", "the", "that", "this", "these", "those",
    "i", "me", "my", "we", "you", "your", "it", "its", "they", "their",
    "itself", "himself", "herself", "themselves", "yourself",
    "at", "by", "to", "of", "in", "on", "up", "as", "or", "and", "but",
    "with", "for", "from", "into", "onto", "over", "than", "then",
    "about", "after", "against", "along", "around", "before", "behind",
    "between", "during", "through", "without",
    # Generic verbs / adjectives
    "is", "are", "be", "been", "being", "am", "was", "were",
    "has", "have", "had", "do", "does", "did",
    "can", "could", "would", "should", "may", "might", "will",
    "let", "lets", "make", "makes", "get", "gets", "give", "gives",
    "help", "helps", "allow", "allows", "use", "uses", "using",
    "find", "show", "want", "need", "looking",
    # Motion verbs — generic, no search value on their own
    "come", "comes", "came", "coming",
    "go", "goes", "went", "going",
    # Filler natural-language fragments (phrases already handled pre-split)
    "bring", "brings", "back", "itself",
    # Filler MTG context words
    "card", "cards", "magic", "mtg", "spell", "spells",
    "ability", "abilities", "effect", "effects",
    # Adverbs / qualifiers
    "very", "really", "just", "also", "too", "so", "more", "most",
    "better", "best", "good", "great", "high", "low",
    "some", "any", "all", "each", "every", "both",
    # Numbers-as-ordinals that don't map to CMC
    "first", "second", "third",
})

# ---------------------------------------------------------------------------
# Number words → int (used for CMC inference)
# ---------------------------------------------------------------------------

_NUMBER_WORDS: dict[str, float] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# ---------------------------------------------------------------------------
# CMC patterns (matched on a segment before word-splitting)
# ---------------------------------------------------------------------------

_CMC_EXACT_RE = re.compile(
    r'\b(?:cmc|mv|mana\s+value|mana\s+cost|converted\s+mana\s+cost)\s*[=:]\s*(\d+(?:\.\d+)?)\b'
    r'|\b(\d+(?:\.\d+)?)\s+(?:mana\s+cost|mana\s+value|cmc|mv)\b'
    r'|\bcosts?\s+(\d+(?:\.\d+)?)\s+mana\b'
    r'|\bcosts?\s+(\d+(?:\.\d+)?)\b'
    r'|\b(\d+(?:\.\d+)?)\s+mana\b',
    re.IGNORECASE,
)

_CMC_MAX_RE = re.compile(
    r'\b(\d+(?:\.\d+)?)\s+(?:or\s+(?:less|fewer)|max(?:imum)?)\s*(?:mana|cmc|mv)?\b'
    r'|\bunder\s+(\d+(?:\.\d+)?)\s*(?:mana|cmc|mv)?\b'
    r'|\bless\s+than\s+(\d+(?:\.\d+)?)\b',
    re.IGNORECASE,
)

_CMC_MIN_RE = re.compile(
    r'\b(\d+(?:\.\d+)?)\s+or\s+(?:more|greater)\s*(?:mana|cmc|mv)?\b'
    r'|\bmore\s+than\s+(\d+(?:\.\d+)?)\b'
    r'|\bat\s+least\s+(\d+(?:\.\d+)?)\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# CMC convenience words
# ---------------------------------------------------------------------------

_CMC_CONVENIENCE: dict[str, tuple[str, float]] = {
    # Exact
    "free": ("exact", 0),
    # Max
    "cheap": ("max", 2),
    "efficient": ("max", 3),
    "affordable": ("max", 3),
    "low-cost": ("max", 2),
    # Min
    "expensive": ("min", 5),
    "costly": ("min", 5),
    "high-cost": ("min", 5),
    "massive": ("min", 7),
    "heavy": ("min", 6),
}

# ---------------------------------------------------------------------------
# Oracle text synonyms (words → what to search in oracle_text)
# ---------------------------------------------------------------------------

_ORACLE_SYNONYMS: dict[str, str] = {
    # ── Card draw ──────────────────────────────────────────────
    "draw": "draw",
    "draws": "draw",
    "drawing": "draw",
    "carddraw": "draw",
    "cantrip": "draw a card",
    "wheel": "draw",          # wheel-of-fortune style
    "wheels": "draw",
    "loot": "draw",           # draw then discard

    # ── Counterspells ──────────────────────────────────────────
    "counter": "counter target",
    "counterspell": "counter target spell",
    "counters": "counter target",
    "permission": "counter target",
    "negate": "counter target",
    "counterspells": "counter target",

    # ── Single-target removal ──────────────────────────────────
    "removal": "destroy target",
    "remove": "destroy target",
    "kill": "destroy target",
    "killspell": "destroy target",
    "answer": "destroy target",
    "destroy": "destroy",
    "exile": "exile target",
    "edict": "each opponent sacrifices",

    # ── Board wipes ────────────────────────────────────────────
    # Pipe-separated OR patterns (see _BOARDWIPE_OR defined above the dict).
    # Using EXACT broad-category phrases avoids false positives like
    # "Destroy all Auras attached to Hakim" (scoped to one permanent).
    "boardwipe": "destroy all creatures|destroy all permanents|destroy all artifacts|destroy all enchantments|destroy all nonland|destroy all lands|return all nonland|return each nonland",
    "wrath":     "destroy all creatures|destroy all permanents|destroy all artifacts|destroy all enchantments|destroy all nonland|destroy all lands|return all nonland|return each nonland",
    "sweeper":   "destroy all creatures|destroy all permanents|destroy all artifacts|destroy all enchantments|destroy all nonland|destroy all lands|return all nonland|return each nonland",
    "sweep":     "destroy all creatures|destroy all permanents|destroy all artifacts|destroy all enchantments|destroy all nonland|destroy all lands|return all nonland|return each nonland",
    "reset":     "destroy all creatures|destroy all permanents|destroy all artifacts|destroy all enchantments|destroy all nonland|destroy all lands|return all nonland|return each nonland",
    "damnation": "destroy all creatures",
    "armageddon": "destroy all lands",
    # Specific-type sweeper synonyms produced by "destroy all [type]" phrase routing.
    # These keep results precise: "destroy all artifacts" finds artifact sweepers only.
    "creaturedestroy": "destroy all creatures",
    "artifactwipe":    "destroy all artifacts",
    "enchantwipe":     "destroy all enchantments",

    # ── Mana ramp ──────────────────────────────────────────────
    "ramp": "add {",
    "manaramp": "add {",
    "manarock": "add {",
    "manadork": "add {",
    "landramp": "search your library for a basic land",
    "dork": "add {",
    "rock": "add {",
    "accelerant": "add {",

    # ── Tutors / library search ────────────────────────────────
    "tutor": "search your library",
    "tutors": "search your library",
    "tutoring": "search your library",
    "fetch": "search your library",
    "search": "search your library",

    # ── Tokens ─────────────────────────────────────────────────
    "token": "create",
    "tokens": "create",
    "gowide": "create",
    "tokenmaker": "create",

    # ── Life gain ──────────────────────────────────────────────
    "lifegain": "gain",
    "healing": "gain",
    "lifelink": "lifelink",

    # ── Discard / hand disruption ──────────────────────────────
    "discard": "discard",
    "handdisruption": "discard",

    # ── Bounce (return to hand) ────────────────────────────────
    "bounce": "return",
    "unsummon": "return target",

    # ── Graveyard / reanimation ────────────────────────────────
    # "graveyard" alone → broad: any card that mentions the graveyard
    "graveyard": "graveyard",
    # Reanimation-specific → OR-pattern via pipe separator (handled in service.py).
    # "graveyard to" catches "from your graveyard to the battlefield/hand".
    # "graveyard onto" catches "from a graveyard onto the battlefield" (Reanimate).
    # Both exclude graveyard hate (exile from graveyard has no "to/onto" suffix).
    "reanimation": "graveyard to|graveyard onto",
    "reanimate":   "graveyard to|graveyard onto",
    "reanimator":  "graveyard to|graveyard onto",
    "graverobber": "graveyard to|graveyard onto",
    "recursion":   "graveyard to|graveyard onto",
    "recur":       "graveyard to|graveyard onto",
    # unearth IS a Scryfall keyword → route through JSON array via self-reference
    "unearth": "unearth",
    "dredge": "dredge",
    "dies": "dies",

    # ── Mill ───────────────────────────────────────────────────
    "mill": "mill",
    "selfmill": "mill",
    "decking": "mill",

    # ── Burn / damage ──────────────────────────────────────────
    "burn": "damage",
    # "bolt" deliberately NOT mapped — it is primarily a card-name fragment
    # ("Lightning Bolt"). Mapping it to "deals 3 damage" caused false positives:
    # Lightning Helix and others appeared for "lightning bolt" searches.
    # Users wanting damage-spell searches can use "burn" or "3 damage" instead.
    "shock": "deals 2 damage",
    "directdamage": "damage",
    "ping": "damage",

    # ── Blink / flicker ────────────────────────────────────────
    "blink": "exile",
    "flicker": "exile",

    # ── Copy ───────────────────────────────────────────────────
    "copy": "copy",
    "clone": "copy",

    # ── Combo / untap ──────────────────────────────────────────
    "combo": "untap",
    "infinite": "untap",
    "wincon": "win the game",
    "winconition": "win the game",
    "finisher": "win the game",

    # ── Sacrifice ──────────────────────────────────────────────
    "sacrifice": "sacrifice",
    "sac": "sacrifice",
    "aristocrats": "sacrifice",

    # ── Evasion / unblockable ──────────────────────────────────
    "evasion": "can't be blocked",
    "unblockable": "can't be blocked",

    # ── Green fight mechanic ───────────────────────────────────
    # Canonical oracle text: "Target creature you control fights target creature."
    "fight": "fights",
    "fighting": "fights",

    # ── Blue/Black steal / gain control ───────────────────────
    # Modern steal spells use "gain control of target".  Older aura steals
    # (Control Magic, Treachery) say "you control enchanted creature" and are
    # found via the broad "black graveyard" / "blue control" searches.
    "steal": "gain control",
    "steals": "gain control",
    "confiscate": "gain control",

    # ── Red extra combat ───────────────────────────────────────
    # "extracombat" is produced by phrase replacement below.
    "extracombat": "additional combat",

    # ── Red impulse draw ───────────────────────────────────────
    # Cards that exile top cards and let you play them this turn.
    "impulsedraw": "exile the top",
    "impulse": "exile the top",

    # ── Protection / hexproof ──────────────────────────────────
    "protection": "protection",
    "hexproof": "hexproof",
    "shroud": "shroud",
    "indestructible": "indestructible",
    "ward": "ward",
    "pillowfort": "can't attack",

    # ── Extra turns ────────────────────────────────────────────
    "extraturn": "extra turn",

    # ── Stax / prison ─────────────────────────────────────────
    "stax": "can't",
    "prison": "can't",
    "hatebear": "can't",
    "hatebears": "can't",

    # ── Land destruction ───────────────────────────────────────
    "landdestruction": "destroy target land",

    # ── Scry / surveil ─────────────────────────────────────────
    "scry": "scry",
    "surveil": "surveil",

    # ── Proliferate ────────────────────────────────────────────
    "proliferate": "proliferate",

    # ── Keywords that players search by name ──────────────────
    "flying": "flying",
    "haste": "haste",
    "trample": "trample",
    "vigilance": "vigilance",
    "deathtouch": "deathtouch",
    "firststrike": "first strike",
    "doublestrike": "double strike",
    "reach": "reach",
    "flash": "flash",
    "menace": "menace",
    "cascade": "cascade",
    "annihilator": "annihilator",
    "cycling": "cycling",
    "kicker": "kicker",
    "flashback": "flashback",
    "morph": "morph",
    "madness": "madness",
    "convoke": "convoke",
    "delve": "delve",
    "emerge": "emerge",
    "evoke": "evoke",
    "undying": "undying",
    "persist": "persist",
    "infect": "infect",
    "wither": "wither",
    "landfall": "landfall",
    "magecraft": "magecraft",
    "ninjutsu": "ninjutsu",
    "prowl": "prowl",
    "suspend": "suspend",
    "threshold": "threshold",
    "delirium": "delirium",
    "revolt": "revolt",
    "morbid": "morbid",
    "ferocious": "ferocious",
    "overload": "overload",
    "foretell": "foretell",
    "boast": "boast",
    "champion": "champion a",
    "exploit": "exploit",
    "tribute": "tribute",
    "bolster": "bolster",
    "scavenge": "scavenge",
    "bestow": "bestow",
    "constellation": "constellation",
    "devotion": "devotion",
    "enrage": "enrage",
    "explore": "explore",
    "raid": "raid",
    "ascend": "ascend",
    "spectacle": "spectacle",
    "addendum": "addendum",
    "adapt": "adapt",
    "afterlife": "afterlife",
    "amass": "amass",
    "escape": "escape",
    "mutate": "mutate",
    "companion": "companion",
    "foretell": "foretell",
    "learn": "learn",
    "coven": "coven",
    "decayed": "decayed",
    "disturb": "disturb",
    "exploit": "exploit",
    "daybound": "daybound",
    "training": "training",
    "blitz": "blitz",
    "casualty": "casualty",
    "connive": "connive",
    "battalion": "battalion",
    "bloodthirst": "bloodthirst",
    "tribute": "tribute",
    "absorb": "absorb",
    "soulbond": "soulbond",
    "detain": "detain",
    "battalion": "battalion",
    "unleash": "unleash",
    "inspired": "inspired",
    "heroic": "heroic",
    "monstrosity": "monstrosity",
    "populate": "populate",
    "provoke": "provoke",
    "regenerate": "regenerate",
    "regeneration": "regenerate",
}

# ---------------------------------------------------------------------------
# Type line synonyms
# ---------------------------------------------------------------------------

_TYPE_SYNONYMS: dict[str, str] = {
    "legendary": "Legendary",
    "legends": "Legendary",
    "legend": "Legendary",
    "nonbasic": "Nonbasic",
    "basic": "Basic Land",
    "planeswalker": "Planeswalker",
    "battle": "Battle",
    "saga": "Saga",
    "tribal": "Tribal",
    "kindred": "Kindred",
    "vehicle": "Vehicle",
    "equipment": "Equipment",
    "aura": "Aura",
    # Creature types (also matched by text search but faster here)
    "dragon": "Dragon",
    "goblin": "Goblin",
    "elf": "Elf",
    "wizard": "Wizard",
    "vampire": "Vampire",
    "zombie": "Zombie",
    "angel": "Angel",
    "demon": "Demon",
    "human": "Human",
    "merfolk": "Merfolk",
    "warrior": "Warrior",
    "shaman": "Shaman",
    "rogue": "Rogue",
    "cleric": "Cleric",
    "knight": "Knight",
    "druid": "Druid",
    "beast": "Beast",
    "soldier": "Soldier",
    "elemental": "Elemental",
    "spirit": "Spirit",
    "giant": "Giant",
    "faerie": "Faerie",
    "snake": "Snake",
    "cat": "Cat",
    "wolf": "Wolf",
    "bird": "Bird",
    "troll": "Troll",
    "dwarf": "Dwarf",
    "pirate": "Pirate",
    "dinosaur": "Dinosaur",
    "merfolk": "Merfolk",
    "sphinx": "Sphinx",
    "hydra": "Hydra",
    "phoenix": "Phoenix",
    "sliver": "Sliver",
    "horror": "Horror",
    "zombie": "Zombie",
    "vampire": "Vampire",
    "shapeshifter": "Shapeshifter",
    "construct": "Construct",
    "golem": "Golem",
    "wurm": "Wurm",
    "drake": "Drake",
    "rat": "Rat",
    "ogre": "Ogre",
    "orc": "Orc",
    "imp": "Imp",
    "archer": "Archer",
    "berserker": "Berserker",
    "bard": "Bard",
    "monk": "Monk",
    "ranger": "Ranger",
    "scout": "Scout",
    "assassin": "Assassin",
    "shaman": "Shaman",
    "warlock": "Warlock",
    # Additional types confirmed in the audit — benefit from word-boundary
    # protection because their names appear as substrings in other type words
    # (e.g. "Monkey" contains "monk", "Werewolf" contains "wolf").
    "werewolf": "Werewolf",
    "monkey": "Monkey",
    "minotaur": "Minotaur",
    "centaur": "Centaur",
    "vedalken": "Vedalken",
    "leonin": "Leonin",
    "kor": "Kor",
    "fox": "Fox",
    "kithkin": "Kithkin",
    "satyr": "Satyr",
    "naga": "Naga",
    "fox": "Fox",
    "rabbit": "Rabbit",
    "raccoon": "Raccoon",
    "mouse": "Mouse",
    "frog": "Frog",
    "fish": "Fish",
    "shark": "Shark",
    "crab": "Crab",
    "bear": "Bear",
    "boar": "Boar",
    "rhino": "Rhino",
    "hippo": "Hippo",
    "turtle": "Turtle",
    "crocodile": "Crocodile",
    "spider": "Spider",
    "insect": "Insect",
    "fungus": "Fungus",
    "plant": "Plant",
    "treefolk": "Treefolk",
    "dryad": "Dryad",
    "nymph": "Nymph",
    "archon": "Archon",
    "avatar": "Avatar",
    "elder": "Elder",
    "nightmare": "Nightmare",
    "illusion": "Illusion",
    "djinn": "Djinn",
    "efreet": "Efreet",
    "sphinx": "Sphinx",
    "unicorn": "Unicorn",
    "pegasus": "Pegasus",
    "griffin": "Griffin",
    "kirin": "Kirin",
    "leviathan": "Leviathan",
    "kraken": "Kraken",
    "serpent": "Serpent",
    "wurm": "Wurm",
    "viashino": "Viashino",
    "ally": "Ally",
    "eldrazi": "Eldrazi",
    "processor": "Processor",
    "drone": "Drone",
    # Card types
    "creature": "Creature",
    "creatures": "Creature",
    "instant": "Instant",
    "instants": "Instant",
    "sorcery": "Sorcery",
    "sorceries": "Sorcery",
    "artifact": "Artifact",
    "artifacts": "Artifact",
    "enchantment": "Enchantment",
    "enchantments": "Enchantment",
    "land": "Land",
    "lands": "Land",
}

# ---------------------------------------------------------------------------
# Auto-generate missing plural forms for every type synonym.
# Keeps the dict maintainable: add a new singular entry above and the plural
# is handled automatically.  Irregular MTG plurals are listed explicitly.
# ---------------------------------------------------------------------------

def _add_type_plurals(d: dict[str, str]) -> dict[str, str]:
    _IRREGULAR: dict[str, str] = {
        # Common English irregulars that appear in MTG creature/card types
        "elf":       "elves",
        "wolf":      "wolves",
        "werewolf":  "werewolves",
        "dwarf":     "dwarves",
        "mouse":     "mice",
        "fungus":    "fungi",
        "pegasus":   "pegasi",
        "ally":      "allies",
        "monkey":    "monkeys",   # ends in vowel+y → regular, override just in case
    }
    additions: dict[str, str] = {}
    for word, canonical in d.items():
        # Derive the plural
        if word in _IRREGULAR:
            plural = _IRREGULAR[word]
        elif word.endswith(("s", "x", "ch", "sh", "z")):
            plural = word + "es"
        elif word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
            plural = word[:-1] + "ies"
        else:
            plural = word + "s"
        # Only add if not already present (preserves hand-crafted entries)
        if plural not in d and plural != word:
            additions[plural] = canonical
    d.update(additions)
    return d


_TYPE_SYNONYMS = _add_type_plurals(_TYPE_SYNONYMS)

# ---------------------------------------------------------------------------
# Multi-word phrase pre-processing (before space-splitting)
# ---------------------------------------------------------------------------
# NOTE: _PHRASE_REPLACEMENTS_SORTED is built once at module load below the list.
# Never sort inside _preprocess() — that re-sorts 178 tuples on every keystroke.

_PHRASE_REPLACEMENTS: list[tuple[str, str]] = [
    # ── "destroy/destroys all [type]" — route BEFORE type synonyms are parsed ──
    # Without these, "lands/creatures/artifacts/enchantments" in the query become
    # type-line filters (finding land cards that destroy something) instead of being
    # part of a mass-destruction oracle concept.
    #
    # Routes to SPECIFIC oracle synonyms — not all to "boardwipe" — so that
    # "destroy all artifacts" finds artifact sweepers only, not creature wipes.
    # The generic "boardwipe"/"wrath" keyword still returns ALL mass-removal types.
    # Conjugated form ("destroys") also covered so stemming doesn't leak type tokens.
    ("destroys all nonland permanents", "boardwipe"),
    ("destroys all nonland", "boardwipe"),
    ("destroys all creatures", "creaturedestroy"),
    ("destroys all permanents", "boardwipe"),
    ("destroys all artifacts and enchantments", "boardwipe"),
    ("destroys all artifacts", "artifactwipe"),
    ("destroys all enchantments", "enchantwipe"),
    ("destroys all lands", "armageddon"),
    ("destroys all land", "armageddon"),
    ("destroy all nonland permanents", "boardwipe"),
    ("destroy all nonland", "boardwipe"),
    ("destroy all creatures", "creaturedestroy"),
    ("destroy all permanents", "boardwipe"),
    ("destroy all artifacts and enchantments", "boardwipe"),
    ("destroy all artifacts", "artifactwipe"),
    ("destroy all enchantments", "enchantwipe"),
    ("destroy all lands", "armageddon"),
    ("destroy all land", "armageddon"),
    # "return all nonland" (Cyclonic Rift style) — prevent "nonland"/"permanent" leaking
    ("return all nonland permanents", "boardwipe"),
    ("return all nonland", "boardwipe"),
    ("return each nonland permanent", "boardwipe"),
    ("return each nonland", "boardwipe"),
    # CMC / mana
    ("mana value", "cmc"),
    ("mana cost", "mana"),     # keep "mana" for CMC regex
    ("converted mana cost", "cmc"),
    ("one drop", "1 mana"),   ("1 drop", "1 mana"),   ("one-drop", "1 mana"),
    ("two drop", "2 mana"),   ("2 drop", "2 mana"),   ("two-drop", "2 mana"),
    ("three drop", "3 mana"), ("3 drop", "3 mana"),   ("three-drop", "3 mana"),
    ("four drop", "4 mana"),  ("4 drop", "4 mana"),   ("four-drop", "4 mana"),
    ("five drop", "5 mana"),  ("5 drop", "5 mana"),   ("five-drop", "5 mana"),
    ("six drop", "6 mana"),   ("6 drop", "6 mana"),   ("six-drop", "6 mana"),
    ("low cost", "cheap"),    ("low-cost", "cheap"),
    ("high cost", "expensive"), ("high-cost", "expensive"),
    ("big mana", "expensive"),
    ("zero mana", "free"),    ("free spell", "free"),  ("costs nothing", "free"),
    ("no cost", "free"),
    # Multicolor phrases
    ("multi color", "multicolor"), ("multi coloured", "multicolored"),
    # Monocolor combos (handled by regex below)
    # Strategic phrases
    ("board wipe", "boardwipe"),   ("board-wipe", "boardwipe"),
    ("mass removal", "boardwipe"),
    ("mana ramp", "manaramp"),
    ("mana rock", "manarock"),
    ("mana dork", "manadork"),
    ("land ramp", "landramp"),
    ("card draw", "carddraw"),
    ("card advantage", "carddraw"),
    ("life gain", "lifegain"),
    ("life link", "lifelink"),
    ("hand disruption", "handdisruption"),
    ("direct damage", "directdamage"),
    ("extra turn", "extraturn"),
    ("land destruction", "landdestruction"),
    ("first strike", "firststrike"),
    ("double strike", "doublestrike"),
    ("go wide", "gowide"),
    ("self mill", "selfmill"),
    ("win condition", "wincon"),
    ("win con", "wincon"),
    ("pillow fort", "pillowfort"),
    ("hate bear", "hatebear"),
    ("group hug", "grouphug"),
    ("draw a card", "draw"),
    ("draws a card", "draw"),
    ("draws cards", "draw"),
    ("spot removal", "removal"),
    ("kill spell", "removal"),
    ("search your library", "tutor"),
    # Natural language ability descriptions → normalised MTG terms
    ("can fly", "flying"),
    ("has flying", "flying"),
    ("able to fly", "flying"),
    ("give flying", "flying"),
    ("can fly over", "flying"),
    # Graveyard / resurrection phrases — "grave" variant (stem map handles
    # single-word "grave", these catch the multi-word expressions)
    ("comes back from the grave", "recursion"),
    ("comes back from grave", "recursion"),
    ("come back from the grave", "recursion"),
    ("come back from grave", "recursion"),
    ("return from the grave", "recursion"),
    ("returns from the grave", "recursion"),
    ("return from grave", "recursion"),
    ("returns from grave", "recursion"),
    ("rise from the grave", "recursion"),
    ("rises from the grave", "recursion"),
    ("rise from grave", "recursion"),
    ("rises from grave", "recursion"),
    ("crawls from the grave", "recursion"),
    ("crawl from the grave", "recursion"),
    # "dead" variants
    ("bring itself back from the dead", "recursion"),
    ("bring back from the dead", "recursion"),
    ("come back from the dead", "recursion"),
    ("rise from the dead", "recursion"),
    ("back from the dead", "recursion"),
    ("bring itself back from dead", "recursion"),
    ("bring back from dead", "recursion"),
    ("come back from dead", "recursion"),
    ("rise from dead", "recursion"),
    ("back from dead", "recursion"),
    ("back to life", "recursion"),
    ("from the dead", "recursion"),
    ("from the graveyard", "recursion"),
    ("from graveyard", "recursion"),
    ("in the graveyard", "graveyard"),
    ("can't be killed", "indestructible"),
    ("cant be killed", "indestructible"),
    ("can't die", "indestructible"),
    ("cant die", "indestructible"),
    ("cannot die", "indestructible"),
    ("cannot be killed", "indestructible"),
    ("can't be destroyed", "indestructible"),
    ("cant be destroyed", "indestructible"),
    ("cannot be destroyed", "indestructible"),
    ("survives removal", "indestructible"),
    ("can't be targeted", "hexproof"),
    ("cant be targeted", "hexproof"),
    ("cannot be targeted", "hexproof"),
    ("can't be blocked", "unblockable"),
    ("cant be blocked", "unblockable"),
    ("cannot be blocked", "unblockable"),
    ("attack immediately", "haste"),
    ("attack right away", "haste"),
    ("tap for mana", "ramp"),
    ("add mana", "ramp"),
    ("produce mana", "ramp"),
    ("makes mana", "ramp"),
    ("generates mana", "ramp"),
    ("deal damage", "burn"),
    ("deals damage", "burn"),
    ("deal direct damage", "directdamage"),
    ("kill everything", "boardwipe"),
    ("kills everything", "boardwipe"),
    ("clear the board", "boardwipe"),
    ("wipe the board", "boardwipe"),
    ("destroy everything", "boardwipe"),
    ("wipes the board", "boardwipe"),
    ("look at the top", "scry"),
    ("look at top", "scry"),
    # Steal / gain control (blue, black)
    ("take control of", "steal"),
    ("take control", "steal"),
    ("gain control of", "steal"),
    ("gain control", "steal"),
    ("mind control", "steal"),
    ("steal target", "steal"),
    ("steal a creature", "steal"),
    ("steal creatures", "steal"),
    # Extra combat (red)
    ("extra combat phase", "extracombat"),
    ("extra combat", "extracombat"),
    ("additional combat phase", "extracombat"),
    ("additional combat", "extracombat"),
    ("extra attack step", "extracombat"),
    ("extra attack", "extracombat"),
    # Red impulse draw
    ("impulse draw", "impulsedraw"),
    # Green fight mechanic
    ("make them fight", "fight"),
    ("makes them fight", "fight"),
    ("force to fight", "fight"),
    ("forced to fight", "fight"),
    ("fight a creature", "fight"),
]

# Pre-sorted longest-first — computed ONCE at import, reused on every request.
# Sorting inside _preprocess() was O(P log P) = ~1,335 comparisons per keystroke wasted.
_PHRASE_REPLACEMENTS_SORTED: list[tuple[str, str]] = sorted(
    _PHRASE_REPLACEMENTS, key=lambda x: -len(x[0])
)

# ---------------------------------------------------------------------------
# Stem map — word variants → canonical oracle/type synonym key
# Applied inside _classify_word before synonym lookups, covering common
# verb conjugations and natural-language phrasings that slip through
# phrase-replacement (e.g. "any card that can fly" → "fly" → "flying").
# ---------------------------------------------------------------------------

_STEM_MAP: dict[str, str] = {
    # Flying variants
    "fly":    "flying", "flies":   "flying",
    "flier":  "flying", "fliers":  "flying",
    # Graveyard / death — natural language ("the dead", "it died", "from the grave")
    "dead":   "graveyard", "die":   "graveyard", "died":   "graveyard",
    "dying":  "graveyard",
    # Physical graveyard synonyms — "grave", "tomb", "crypt" all mean graveyard
    "grave":  "graveyard", "graves": "graveyard",
    "tomb":   "graveyard", "tombs":  "graveyard",
    "crypt":  "graveyard", "crypts": "graveyard",
    "bury":   "graveyard", "buried": "graveyard", "buries": "graveyard",
    # Resurrect / revive — direct reanimation intent
    "resurrect":    "recursion", "resurrects":  "recursion",
    "resurrected":  "recursion", "resurrection":"recursion",
    "revive": "recursion", "revives": "recursion", "revived": "recursion",
    # Destroy / removal variants
    "kills":   "removal",  "killing": "removal",  "killed":  "removal",
    "destroys":"destroy",  "destroyed":"destroy",
    # Draw
    "draws": "draw",   "drew": "draw",
    # Exile
    "exiles": "exile", "exiled": "exile",
    # Discard
    "discards": "discard",
    # Mill
    "mills": "mill", "milling": "mill",
    # Sacrifice
    "sacrifices": "sacrifice",
    # Counter
    "countered": "counter", "countering": "counter",
    # Life gain
    "heals": "lifegain", "heal": "lifegain", "healing": "lifegain",
    # Speed → haste (natural English: "a fast creature")
    "quick": "haste", "fast": "haste", "speed": "haste", "speedy": "haste",
    # Immune / untargetable
    "immune": "hexproof", "immunity": "hexproof",
    # Indestructible colloquials
    "unkillable": "indestructible", "immortal": "indestructible",
    # Unstoppable → unblockable
    "unstoppable": "unblockable",
    # Token creation
    "creates": "tokens", "created": "tokens",
    # Fight (green mechanic)
    "fights": "fight", "fighting": "fight", "fought": "fight",
    # Steal (blue/black)
    "steals": "steal", "stolen": "steal", "stole": "steal",
    # Bounce
    "bounces": "bounce", "bounced": "bounce",
    # Copy
    "copies": "copy", "clones": "clone",
    # Proliferate
    "proliferates": "proliferate",
    # Search / tutor
    "searches": "tutor",
    # Protect
    "protects": "protection",
    # Regenerate
    "regenerates": "regenerate",
}

# Regex for N-drop patterns not caught above
_NDROP_RE = re.compile(r'\b(\d)[-\s]?drop\b', re.IGNORECASE)

# Pre-compiled bare-number pattern — avoids re-compiling on every word in _classify_word
_NUMBER_PATTERN = re.compile(r'\d+(?:\.\d+)?')

# Regex for mono-[color] compound words: "monored" → "mono red"
_MONOCOLOUR_RE = re.compile(
    r'\bmono[-]?(white|blue|black|red|green|w|u|b|r|g)\b', re.IGNORECASE
)


def _preprocess(text: str) -> str:
    """Normalise slang and multi-word phrases before parsing."""
    t = text.lower()

    # mono-[color] compound words
    def _split_mono(m: re.Match) -> str:
        return f"mono {m.group(1)}"
    t = _MONOCOLOUR_RE.sub(_split_mono, t)

    # N-drop → "N mana"
    def _drop_to_mana(m: re.Match) -> str:
        return f"{m.group(1)} mana"
    t = _NDROP_RE.sub(_drop_to_mana, t)

    # Multi-word phrase replacements — use pre-sorted list (sorted once at import)
    for phrase, replacement in _PHRASE_REPLACEMENTS_SORTED:
        t = t.replace(phrase, replacement)

    return t


# ---------------------------------------------------------------------------
# ParsedQuery
# ---------------------------------------------------------------------------

@dataclass
class ParsedQuery:
    colors: list[str] = field(default_factory=list)
    colorless: bool = False
    multicolor: bool = False
    monocolor: bool = False
    rarities: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    text_tokens: list[str] = field(default_factory=list)
    oracle_tokens: list[str] = field(default_factory=list)
    type_tokens: list[str] = field(default_factory=list)
    cmc_exact: float | None = None
    cmc_max: float | None = None
    cmc_min: float | None = None
    is_empty: bool = False


# ---------------------------------------------------------------------------
# CMC extraction
# ---------------------------------------------------------------------------

def _extract_cmc(segment: str) -> tuple[str, float | None, float | None, float | None]:
    """Remove CMC patterns from segment text and return the values."""
    cmc_exact = cmc_max = cmc_min = None

    m = _CMC_MAX_RE.search(segment)
    if m:
        cmc_max = float(next(v for v in m.groups() if v is not None))
        segment = segment[:m.start()] + " " + segment[m.end():]

    m = _CMC_MIN_RE.search(segment)
    if m:
        cmc_min = float(next(v for v in m.groups() if v is not None))
        segment = segment[:m.start()] + " " + segment[m.end():]

    m = _CMC_EXACT_RE.search(segment)
    if m:
        cmc_exact = float(next(v for v in m.groups() if v is not None))
        segment = segment[:m.start()] + " " + segment[m.end():]

    return segment.strip(), cmc_exact, cmc_max, cmc_min


# ---------------------------------------------------------------------------
# Per-word classifier
# ---------------------------------------------------------------------------

def _classify_word(word: str, result: ParsedQuery) -> bool:
    """Classify one lowercase word. Returns True if fully consumed."""
    # Normalise word variants to canonical form before classification
    word = _STEM_MAP.get(word, word)

    # Color (including guilds / shards)
    if word in _COLOR_MAP:
        if word == "colorless":
            result.colorless = True
        else:
            for c in _COLOR_MAP[word]:
                if c not in result.colors:
                    result.colors.append(c)
        return True

    # Multicolor modifier
    if word in _MULTICOLOR_TOKENS:
        result.multicolor = True
        return True

    # Monocolor modifier
    if word in _MONOCOLOR_TOKENS:
        result.monocolor = True
        return True

    # Rarity
    if word in _RARITIES:
        result.rarities.append(word)
        return True

    # Format
    if word in _FORMAT_MAP:
        result.formats.append(_FORMAT_MAP[word])
        return True

    # CMC convenience word
    if word in _CMC_CONVENIENCE:
        kind, val = _CMC_CONVENIENCE[word]
        if kind == "exact" and result.cmc_exact is None:
            result.cmc_exact = val
        elif kind == "max" and result.cmc_max is None:
            result.cmc_max = val
        elif kind == "min" and result.cmc_min is None:
            result.cmc_min = val
        return True

    # Bare number → CMC (pre-compiled pattern — avoids re-compiling on every word)
    if _NUMBER_PATTERN.fullmatch(word):
        if result.cmc_exact is None:
            result.cmc_exact = float(word)
        return True

    # Number word → CMC
    if word in _NUMBER_WORDS:
        if result.cmc_exact is None:
            result.cmc_exact = _NUMBER_WORDS[word]
        return True

    # Type synonym (searched in type_line)
    if word in _TYPE_SYNONYMS:
        t = _TYPE_SYNONYMS[word]
        if t not in result.type_tokens:
            result.type_tokens.append(t)
        return True

    # Oracle synonym (searched in oracle_text)
    if word in _ORACLE_SYNONYMS:
        o = _ORACLE_SYNONYMS[word]
        if o not in result.oracle_tokens:
            result.oracle_tokens.append(o)
        return True

    # Stop word — consume silently
    if word in _STOP_WORDS:
        return True

    return False   # caller adds to text_tokens


# ---------------------------------------------------------------------------
# Main parse entry point
# ---------------------------------------------------------------------------

def parse(raw: str) -> ParsedQuery:
    result = ParsedQuery()
    if not raw or not raw.strip():
        result.is_empty = True
        return result

    # Normalise slang / multi-word phrases
    normalised = _preprocess(raw)

    # Split on "+" for explicit compound queries
    segments = [s.strip() for s in normalised.split("+") if s.strip()]

    for segment in segments:
        # Extract CMC regex patterns first
        segment, cmc_e, cmc_x, cmc_n = _extract_cmc(segment)
        if cmc_e is not None:
            result.cmc_exact = cmc_e
        if cmc_x is not None:
            result.cmc_max = cmc_x
        if cmc_n is not None:
            result.cmc_min = cmc_n

        # Split on spaces and classify each word
        leftover: list[str] = []
        for raw_word in segment.split():
            w = raw_word.strip(".,!?;:'\"()[]").lower()
            if not w:
                continue
            consumed = _classify_word(w, result)
            if not consumed:
                leftover.append(raw_word.strip(".,!?;:'\"()[]"))

        # Add each remaining word as its own token (ANDed in service.py).
        # Joining as a phrase breaks stop-word-separated names like
        # "Delver of Secrets" → "delver secrets" (no match) and card names
        # with apostrophes like "Black Sun's Zenith" → "black sun zenith" (no match).
        # Individual words also fix "the Aeons Torn" → search each word separately.
        for word in leftover:
            if word and word not in result.text_tokens:
                result.text_tokens.append(word)

    return result
