import collections
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def feature_height(props):
    for key in ("height_m", "height", "h"):
        value = props.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def in_poland(lat, lng):
    return 49.0 <= lat <= 55.1 and 14.0 <= lng <= 24.3


def main():
    data = json.loads((ROOT / "map.umap").read_text(encoding="utf-8"))
    layer_stats = []
    all_features = []
    for index, layer in enumerate(data.get("layers", [])):
        features = layer.get("features", [])
        counter = collections.Counter()
        high = 0
        with_height = 0
        for feature in features:
            props = feature.get("properties") or {}
            h = feature_height(props)
            if h is not None:
                with_height += 1
                if h > 100:
                    high += 1
            counter[str(props.get("type") or props.get("TYPE") or "UNKNOWN").upper()] += 1
            all_features.append((index, layer.get("name") or f"layer {index}", feature))
        layer_stats.append((index, layer.get("name") or f"layer {index}", len(features), with_height, high, counter.most_common(10)))

    print("LAYERS")
    for item in layer_stats:
        print(item)

    print("\nGLOBAL TOP")
    top = []
    for layer_index, layer_name, feature in all_features:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        h = feature_height(props)
        if h is not None:
            top.append((h, props.get("type") or props.get("TYPE"), props.get("name"), coords[1], coords[0], layer_name))
    for row in sorted(top, reverse=True)[:80]:
        print(row)

    print("\nPOLAND POLES/LINES")
    pl = []
    for layer_index, layer_name, feature in all_features:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        typ = str(props.get("type") or props.get("TYPE") or "").upper()
        name = str(props.get("name") or "")
        if in_poland(lat, lng) and ("POLE" in typ or "PYLON" in typ or "TRANSMISSION" in typ or "SŁUP" in typ or "SLUP" in typ or "LINIA" in typ or "WN" in name.upper()):
            pl.append((feature_height(props), typ, name, lat, lng, layer_name))
    for row in sorted(pl, key=lambda item: item[0] or -1, reverse=True)[:100]:
        print(row)
    print("poland pole/line count", len(pl), "with height", sum(1 for r in pl if r[0] is not None))


if __name__ == "__main__":
    main()
