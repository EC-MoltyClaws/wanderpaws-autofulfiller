"""
SKU Map
-------
Explicit mapping of every known Shopify pseudo SKU to its fulfilled products.

Each key is the exact SKU string as set in Shopify.
Each value is a list of display name strings (one per actual fulfilled product).
  - Multiple entries = bundle (e.g. harness includes a leash)
  - Empty list      = skip silently (not fulfilled)

Any SKU not present in this dict is treated as unknown and raises a ValueError.
"""

SKU_MAP: dict[str, list[str]] = {
    # ── Harness (includes leash) ─────────────────────────────────────────────
    "harness-black-xs":  ["Harness-Black/XS",   "Leash-Black"],
    "harness-black-s":   ["Harness-Black/S",    "Leash-Black"],
    "harness-black-m":   ["Harness-Black/M",    "Leash-Black"],
    "harness-blue-xs":   ["Harness-Blue/XS",    "Leash-Blue"],
    "harness-blue-s":    ["Harness-Blue/S",     "Leash-Blue"],
    "harness-blue-m":    ["Harness-Blue/M",     "Leash-Blue"],
    "harness-pink-xs":   ["Harness-Pink/XS",    "Leash-Pink"],
    "harness-pink-s":    ["Harness-Pink/S",     "Leash-Pink"],
    "harness-pink-m":    ["Harness-Pink/M",     "Leash-Pink"],
    "harness-purple-xs": ["Harness-Purple/XS",  "Leash-Purple"],
    "harness-purple-s":  ["Harness-Purple/S",   "Leash-Purple"],
    "harness-purple-m":  ["Harness-Purple/M",   "Leash-Purple"],
    "harness-orange-xs": ["Harness-Orange/XS",  "Leash-Orange"],
    "harness-orange-s":  ["Harness-Orange/S",   "Leash-Orange"],
    "harness-orange-m":  ["Harness-Orange/M",   "Leash-Orange"],
    "harness-red-xs":    ["Harness-Red/XS",     "Leash-Red"],
    "harness-red-s":     ["Harness-Red/S",      "Leash-Red"],
    "harness-red-m":     ["Harness-Red/M",      "Leash-Red"],
    "harness-yellow-xs": ["Harness-Yellow/XS",  "Leash-Yellow"],
    "harness-yellow-s":  ["Harness-Yellow/S",   "Leash-Yellow"],
    "harness-yellow-m":  ["Harness-Yellow/M",   "Leash-Yellow"],

    # ── Sip cup ──────────────────────────────────────────────────────────────
    "sipcup-blue":       ["Food and Water Dispensor-Blue"],
    "sipcup-red":        ["Food and Water Dispensor-Red"],

    # ── Retractable leash ────────────────────────────────────────────────────
    "retractableleash":  ["Retractable Leash"],

    # ── Trackers ─────────────────────────────────────────────────────────────
    "generic-tracker-apple":   ["Tracker-Apple"],
    "generic-tracker-android": ["Tracker-Android"],

    # ── Skip (not fulfilled) ─────────────────────────────────────────────────
    "freeleashupgrade":    [],
    "freepriorityshipping": [],
    "freewarranty":        [],
    "guide30":             [],
    "guide7":              [],
    "nonfulfil-shipping":  [],
    "defaultleash-black":  [],
    "defaultleash-blue":   [],
    "defaultleash-pink":   [],
    "defaultleash-orange": [],
    "defaultleash-yellow": [],
    "defaultleash-purple": [],
    "defaultleash-red":    [],
}
