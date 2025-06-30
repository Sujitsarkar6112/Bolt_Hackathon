#!/usr/bin/env python3
"""
MLflow experiment setup script
Usage: python scripts/setup_mlflow.py
"""

import mlflow
from mlflow.tracking import MlflowClient
import os
import sys

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "demand_forecasting")


def setup_mlflow_experiment():
    """Setup MLflow experiment and model registry"""
    
    print(f"Setting up MLflow experiment: {EXPERIMENT_NAME}")
    print(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")
    
    # Set tracking URI
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    
    # Initialize client
    client = MlflowClient()
    
    try:
        # Create experiment if it doesn't exist
        try:
            experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
            if experiment:
                print(f"Experiment '{EXPERIMENT_NAME}' already exists with ID: {experiment.experiment_id}")
            else:
                experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
                print(f"Created experiment '{EXPERIMENT_NAME}' with ID: {experiment_id}")
        except Exception as e:
            print(f"Error creating experiment: {e}")
            return False
        
        # Create registered models
        model_names = [
            f"{EXPERIMENT_NAME}_prophet",
            f"{EXPERIMENT_NAME}_tft"
        ]
        
        for model_name in model_names:
            try:
                client.create_registered_model(
                    name=model_name,
                    description=f"Registered model for {model_name.split('_')[-1].upper()} forecasting"
                )
                print(f"Created registered model: {model_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"Registered model '{model_name}' already exists")
                else:
                    print(f"Error creating registered model {model_name}: {e}")
        
        print("MLflow setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"MLflow setup failed: {e}")
        return False


if __name__ == "__main__":
    success = setup_mlflow_experiment()
    sys.exit(0 if success else 1)