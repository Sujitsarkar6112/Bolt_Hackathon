import logging
import mlflow
from mlflow.tracking import MlflowClient
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class MLflowClient:
    """MLflow client for experiment tracking"""
    
    def __init__(self):
        self.client: Optional[MlflowClient] = None
        self.experiment_id: Optional[str] = None
    
    async def initialize(self):
        """Initialize MLflow client and experiment"""
        try:
            # Set tracking URI
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            
            # Initialize client
            self.client = MlflowClient()
            
            # Create or get experiment
            try:
                experiment = mlflow.get_experiment_by_name(settings.mlflow_experiment_name)
                if experiment:
                    self.experiment_id = experiment.experiment_id
                else:
                    self.experiment_id = mlflow.create_experiment(settings.mlflow_experiment_name)
            except Exception as e:
                logger.warning(f"Could not create/get MLflow experiment: {e}")
                self.experiment_id = "0"  # Default experiment
            
            # Set experiment
            mlflow.set_experiment(settings.mlflow_experiment_name)
            
            logger.info(f"MLflow initialized with experiment: {settings.mlflow_experiment_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MLflow: {e}")
            # Continue without MLflow
            self.client = None
            self.experiment_id = None
    
    def is_available(self) -> bool:
        """Check if MLflow is available"""
        return self.client is not None
    
    async def log_model_metrics(self, model_name: str, metrics: dict):
        """Log model metrics to MLflow"""
        if not self.is_available():
            logger.warning("MLflow not available, skipping metrics logging")
            return
        
        try:
            with mlflow.start_run(run_name=f"{model_name}_metrics"):
                mlflow.log_metrics(metrics)
                logger.info(f"Logged metrics for {model_name}: {metrics}")
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")