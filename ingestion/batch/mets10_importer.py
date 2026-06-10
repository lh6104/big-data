"""MeTS-10 Bangkok traffic dataset importer."""

import logging
import sys

logger = logging.getLogger(__name__)


def import_mets10(warehouse_path: str):
    """Download and parse MeTS-10 Bangkok → Bronze table."""
    try:
        from processing.utils.spark_session import get_spark_session
        
        logger.info("Importing MeTS-10 Bangkok...")
        spark = get_spark_session("mets10-importer")
        
        # TODO: Download MeTS-10 data
        # Parse CSV/HDF5 files
        # Load into bronze_traffic_mets10_raw
        
        logger.info("MeTS-10 import complete (implementation needed)")
        spark.stop()
        
    except Exception as e:
        logger.error(f"Error importing MeTS-10: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"
    import_mets10(warehouse_path)
