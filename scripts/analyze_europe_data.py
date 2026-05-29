import collections
import glob
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
EUROPE_FILES = ["europe-1.json", "europe-2.json", "europe-3.json"]


def load_rows():
    rows = []
    for name in EUROPE_FILES:
        rows.extend(json.loads((ROOT / name).read_text(encoding="utf-8")))
    return rows


def print_properties():
    for name in sorted(glob.glob(str(DOWNLOADS / "*merged*.geojson"))):
        data = json.loads(Path(name).read_text(encoding="utf-8"))
        keys = collections.Counter()
        for feature in data.get("features", []):
            keys.update((feature.get("properties") or {}).keys())
        print(Path(name).name, dict(keys))


def print_type(rows, type_name, limit=30):
    print(f"TYPE {type_name}")
    items = [
        row
        for row in rows
        if row.get("h") is not None and str(row.get("t")).replace("_", " ") == type_name.replace("_", " ")
    ]
    for row in sorted(items, key=lambda item: item["h"], reverse=True)[:limit]:
        print(f"{row['h']}\t{row['country']}\t{row['t']}\t{row['n']}\t{row['lat']}\t{row['lng']}")


def print_near_targets():
    targets = [
        (49.6433983, 12.2290855),
        (53.2037074, 10.3855457),
        (41.4458711, 20.9838466),
        (60.7358115, 24.9446037),
    ]
    for name in sorted(glob.glob(str(DOWNLOADS / "*merged*.geojson"))):
        data = json.loads(Path(name).read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            for lat, lng in targets:
                if abs(coords[1] - lat) < 0.00003 and abs(coords[0] - lng) < 0.00003:
                    print(Path(name).name, coords, feature.get("properties"))


def print_top(rows, limit=80):
    for row in sorted([r for r in rows if r.get("h") is not None], key=lambda item: item["h"], reverse=True)[:limit]:
        print(f"{row['h']}\t{row['country']}\t{row['t']}\t{row['n']}\t{row['lat']}\t{row['lng']}")


def main():
    rows = load_rows()
    print("PROPERTIES")
    print_properties()
    print()
    print("TARGETS")
    print_near_targets()
    print()
    print("TOP")
    print_top(rows)
    print()
    for type_name in ("CHIMNEY", "WIND TURBINE", "WIND_TURBINE"):
        print_type(rows, type_name)
        print()


if __name__ == "__main__":
    main()
