"""OSM road network importer - Downloads and parses OpenStreetMap via OSMnx."""

import logging
import sys
import geopandas as gpd
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def import_osm_for_city(city: str, warehouse_path: str, spark):
    """Download road network for a city using OSMnx."""
    try:
        import osmnx as ox

        logger.info(f"Downloading OSM road network for {city}...")

        # Download road network
        tags = {'highway': ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential']}
        G = ox.graph_from_place(city, tags=tags, simplify=True, retain_all=False, truncate_by_edge=True)

        # Convert to GeoDataFrame
        nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)

        # Prepare edges data with segment IDs
        edges_gdf = edges_gdf.reset_index()
        edges_gdf['segment_id'] = city.lower().replace(' ', '_') + '_' + edges_gdf.index.astype(str)
        edges_gdf['city'] = city
        edges_gdf['imported_at'] = datetime.utcnow().isoformat()
        edges_gdf['source'] = 'openstreetmap'

        # Keep relevant columns
        keep_cols = ['segment_id', 'city', 'source', 'imported_at', 'highway', 'geometry']
        edges_gdf = edges_gdf[[c for c in keep_cols if c in edges_gdf.columns]]

        # Convert geometry to WKT for Iceberg
        edges_gdf['geometry_wkt'] = edges_gdf['geometry'].apply(lambda x: x.wkt)

        # Convert to Spark DataFrame
        df_edges = spark.createDataFrame(
            edges_gdf[['segment_id', 'city', 'highway', 'geometry_wkt', 'source', 'imported_at']].to_dict('records')
        )

        logger.info(f"Downloaded {len(edges_gdf)} segments for {city}")

        return df_edges

    except Exception as e:
        logger.error(f"Error downloading OSM for {city}: {e}", exc_info=True)
        raise


def import_osm(warehouse_path: str):
    """Download and parse OSM for Hanoi + HCMC → Bronze Iceberg table."""
    try:
        from processing.utils.spark_session import get_spark_session

        logger.info("Starting OSM import for Vietnam cities...")
        spark = get_spark_session("osm-importer")

        # Download for Hanoi and Ho Chi Minh City
        dfs = []
        for city in ["Hanoi, Vietnam", "Ho Chi Minh City, Vietnam"]:
            try:
                df_city = import_osm_for_city(city, warehouse_path, spark)
                dfs.append(df_city)
            except Exception as e:
                logger.warning(f"Could not import {city}: {e}")

        if not dfs:
            logger.warning("No OSM data imported")
            return

        # Combine all city data
        from functools import reduce
        from pyspark.sql import functions as F

        df_combined = reduce(lambda df1, df2: df1.union(df2), dfs)

        # Write to Iceberg table
        table_path = f"{warehouse_path}/bronze_osm_raw"
        df_combined.write \
            .format("iceberg") \
            .mode("overwrite") \
            .option("path", table_path) \
            .save()

        logger.info(f"OSM data written to {table_path}")
        spark.stop()

    except Exception as e:
        logger.error(f"Error importing OSM: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"
    import_osm(warehouse_path)
