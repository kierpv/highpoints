import json
import reverse_geocoder as rg

files = [
    "europe-1-fixed-fixed.json",
    "europe-2-fixed-fixed.json",
    "europe-3-fixed-fixed.json",
    "europe-4-fixed-fixed.json"
]

for file in files:

    print("\nProcessing:", file)

    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_coords = []
    valid_items = []

    for d in data:

        try:
            lat = float(d["lat"])
            lng = float(d["lng"])

            # filtr Europy
            if not (30 <= lat <= 75):
                continue

            if not (-25 <= lng <= 45):
                continue

            valid_coords.append((lat, lng))
            valid_items.append(d)

        except:
            continue

    print("Valid coords:", len(valid_coords))

    results = rg.search(valid_coords, mode=1)

    print("Sample:", results[:5])

    for d, r in zip(valid_items, results):
        d["country"] = r["cc"]

    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    print("Saved:", file)

print("\nDONE")