import pandas as pd
from arcgis.features import FeatureSet, Feature
from arcgis.geometry import Point

def df_to_featureset(df: pd.DataFrame) -> FeatureSet:
    # Detect geometry columns
    lat_col = next((c for c in df.columns if c.lower() in ("latitude", "lat", "y")), None)
    lon_col = next((c for c in df.columns if c.lower() in ("longitude", "lon", "lng", "x")), None)
    features = []
    for _, row in df.iterrows():
        attrs = row.to_dict()
        if lat_col and lon_col and pd.notnull(row[lat_col]) and pd.notnull(row[lon_col]):
            geom = Point({"x": float(row[lon_col]), "y": float(row[lat_col]), "spatialReference": {"wkid": 4326}})
        else:
            geom = Point({"x": 0, "y": 0, "spatialReference": {"wkid": 4326}})
        features.append(Feature(geometry=geom, attributes=attrs))
    return FeatureSet(features)