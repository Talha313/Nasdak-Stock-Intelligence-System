import logging
import great_expectations as gx
from storage.db import DATABASE_URL

logger = logging.getLogger(__name__)

"""
Great Expectations Validation Logic.
This module connects to the 'prices' table in Postgres and verifies
that the data adheres to the rules defined in the expectation suite.
"""

def run_validation():
    """
    Executes the Great Expectations suite against the 'prices' table.
    Returns True if successful, raises Exception if validation fails.
    """
    logger.info("Starting Great Expectations validation...")
    
    try:
        # 1. Get the GE Data Context
        context = gx.get_context()
        
        # 2. Ensure the Datasource is configured (SQLAlchemy connection)
        datasource_name = "nasdaq_datasource"
        
        # GX requires the +psycopg2 or +asyncpg driver prefix for Postgres
        # We ensure the URL is compatible for GX's internal engine
        conn_str = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

        if datasource_name not in [ds["name"] for ds in context.list_datasources()]:
            context.sources.add_postgres(
                name=datasource_name, 
                connection_string=conn_str
            )

        # 3. Create or Update a Checkpoint
        # A checkpoint is a 'runnable' job that pairs a dataset with a suite
        checkpoint_name = "prices_checkpoint"
        context.add_or_update_checkpoint(
            name=checkpoint_name,
            validations=[
                {
                    "batch_request": {
                        "datasource_name": datasource_name,
                        "data_asset_name": "prices", # The table name in Postgres
                    },
                    "expectation_suite_name": "nasdaq_suite",
                }
            ],
        )

        # 4. Run the validation
        logger.info(f"Running checkpoint: {checkpoint_name}")
        results = context.run_checkpoint(checkpoint_name=checkpoint_name)

        # 5. Evaluate results
        if not results.success:
            logger.error("Data Validation Failed!")
            raise ValueError("Table 'prices' failed GX validation. Check Data Docs for details.")
            
        logger.info("Data Validation Passed Successfully.")
        return True

    except Exception as e:
        logger.error(f"Validation process encountered an error: {e}")
        raise