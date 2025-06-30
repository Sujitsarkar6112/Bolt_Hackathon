#!/usr/bin/env python3
"""
Cron job script for model retraining
Usage: python -m app.cron.retrain_scheduler
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.forecast_ensemble import ForecastEnsemble
from app.services.data_loader import DataLoader
from app.services.mlflow_client import MLflowClient
from app.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Main retraining function"""
    logger.info("Starting scheduled model retraining")
    
    try:
        # Initialize services
        data_loader = DataLoader()
        mlflow_client = MLflowClient()
        forecast_ensemble = ForecastEnsemble()
        
        # Connect to services
        await data_loader.connect()
        await mlflow_client.initialize()
        
        # Perform retraining
        await forecast_ensemble.retrain_models()
        
        logger.info("Scheduled model retraining completed successfully")
        
    except Exception as e:
        logger.error(f"Scheduled model retraining failed: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        try:
            await data_loader.disconnect()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())