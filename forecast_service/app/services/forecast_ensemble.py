import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from prophet import Prophet
import torch
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer
from pytorch_forecasting.metrics import MAE, MAPE
import mlflow
import mlflow.pytorch
import mlflow.sklearn
import joblib
import os

from ..config import settings
from ..models import ForecastResponse, ForecastPoint, ModelMetadata
from .data_loader import DataLoader
from .mlflow_client import MLflowClient

logger = logging.getLogger(__name__)


class ForecastEnsemble:
    """Ensemble forecasting service combining Prophet and TFT"""
    
    def __init__(self):
        self.prophet_model: Optional[Prophet] = None
        self.tft_model: Optional[TemporalFusionTransformer] = None
        self.prophet_metadata: Optional[ModelMetadata] = None
        self.tft_metadata: Optional[ModelMetadata] = None
        self.data_loader = DataLoader()
        self.mlflow_client = MLflowClient()
        
    def models_loaded(self) -> bool:
        """Check if models are loaded"""
        return self.prophet_model is not None or self.tft_model is not None
    
    async def load_models(self):
        """Load existing models from MLflow"""
        try:
            # Load Prophet model
            try:
                prophet_model_uri = f"models:/{settings.mlflow_experiment_name}_prophet/latest"
                self.prophet_model = mlflow.sklearn.load_model(prophet_model_uri)
                logger.info("Prophet model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load Prophet model: {e}")
            
            # Load TFT model
            try:
                tft_model_uri = f"models:/{settings.mlflow_experiment_name}_tft/latest"
                self.tft_model = mlflow.pytorch.load_model(tft_model_uri)
                logger.info("TFT model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load TFT model: {e}")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    async def predict(self, sku: str, horizon: int, confidence_level: float = 0.8) -> ForecastResponse:
        """Generate forecast using ensemble logic"""
        
        # Determine which model to use based on horizon
        if horizon <= settings.short_term_threshold:
            model_used = "prophet"
            forecast_points = await self._predict_prophet(sku, horizon, confidence_level)
        else:
            model_used = "tft"
            forecast_points = await self._predict_tft(sku, horizon, confidence_level)
        
        return ForecastResponse(
            sku=sku,
            forecast_date=datetime.utcnow().isoformat(),
            horizon_days=horizon,
            model_used=model_used,
            confidence_level=confidence_level,
            forecast=forecast_points,
            metadata={
                "prophet_available": self.prophet_model is not None,
                "tft_available": self.tft_model is not None,
                "selection_threshold": settings.short_term_threshold
            }
        )
    
    async def _predict_prophet(self, sku: str, horizon: int, confidence_level: float) -> List[ForecastPoint]:
        """Generate forecast using Prophet"""
        if self.prophet_model is None:
            raise ValueError("Prophet model not available")
        
        # Get historical data
        data = await self.data_loader.get_training_data(sku)
        df = pd.DataFrame([{
            'ds': row.timestamp,
            'y': row.units_sold
        } for row in data])
        
        # Generate future dates
        future = self.prophet_model.make_future_dataframe(periods=horizon)
        
        # Make prediction
        forecast = self.prophet_model.predict(future)
        
        # Extract forecast points
        forecast_points = []
        start_date = df['ds'].max() + timedelta(days=1)
        
        for i in range(horizon):
            date = start_date + timedelta(days=i)
            row = forecast[forecast['ds'] == date].iloc[0]
            
            # Calculate percentiles based on confidence level
            alpha = 1 - confidence_level
            p_lower = alpha / 2
            p_upper = 1 - alpha / 2
            
            forecast_points.append(ForecastPoint(
                date=date.isoformat(),
                median=max(0, row['yhat']),
                p10=max(0, row['yhat_lower']),
                p90=max(0, row['yhat_upper'])
            ))
        
        return forecast_points
    
    async def _predict_tft(self, sku: str, horizon: int, confidence_level: float) -> List[ForecastPoint]:
        """Generate forecast using TFT"""
        if self.tft_model is None:
            # Fallback to Prophet if TFT not available
            logger.warning("TFT model not available, falling back to Prophet")
            return await self._predict_prophet(sku, horizon, confidence_level)
        
        # Get historical data
        data = await self.data_loader.get_training_data(sku)
        df = pd.DataFrame([{
            'timestamp': row.timestamp,
            'sku': row.sku,
            'units_sold': row.units_sold,
            'price': row.price
        } for row in data])
        
        # Prepare data for TFT
        df['time_idx'] = range(len(df))
        df['date'] = pd.to_datetime(df['timestamp'])
        
        # Create dataset
        max_encoder_length = min(60, len(df) // 2)
        max_prediction_length = horizon
        
        training = TimeSeriesDataSet(
            df,
            time_idx="time_idx",
            target="units_sold",
            group_ids=["sku"],
            max_encoder_length=max_encoder_length,
            max_prediction_length=max_prediction_length,
            static_categoricals=["sku"],
            time_varying_known_reals=["price"],
            time_varying_unknown_reals=["units_sold"],
            target_normalizer=GroupNormalizer(groups=["sku"]),
        )
        
        # Generate predictions
        predictions = self.tft_model.predict(training.filter(lambda x: x.sku == sku))
        
        # Convert to forecast points
        forecast_points = []
        start_date = df['date'].max() + timedelta(days=1)
        
        for i in range(horizon):
            date = start_date + timedelta(days=i)
            
            # Extract prediction (assuming batch size 1)
            pred_value = float(predictions[0, i].item()) if i < len(predictions[0]) else 0
            
            # Simple confidence intervals (can be improved with quantile predictions)
            std_dev = pred_value * 0.1  # 10% standard deviation assumption
            p10 = max(0, pred_value - 1.28 * std_dev)  # ~10th percentile
            p90 = max(0, pred_value + 1.28 * std_dev)  # ~90th percentile
            
            forecast_points.append(ForecastPoint(
                date=date.isoformat(),
                median=max(0, pred_value),
                p10=p10,
                p90=p90
            ))
        
        return forecast_points
    
    async def retrain_models(self):
        """Retrain both Prophet and TFT models"""
        logger.info("Starting model retraining")
        
        try:
            # Get all available SKUs
            skus = await self.data_loader.get_available_skus()
            
            if not skus:
                logger.warning("No SKUs available for training")
                return
            
            # Train Prophet model
            await self._train_prophet(skus)
            
            # Train TFT model
            await self._train_tft(skus)
            
            logger.info("Model retraining completed successfully")
            
        except Exception as e:
            logger.error(f"Model retraining failed: {e}")
            raise
    
    async def _train_prophet(self, skus: List[str]):
        """Train Prophet model"""
        logger.info("Training Prophet model")
        
        with mlflow.start_run(run_name=f"prophet_training_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"):
            # Combine data from all SKUs
            all_data = []
            for sku in skus:
                sku_data = await self.data_loader.get_training_data(sku)
                if len(sku_data) >= settings.min_training_samples:
                    all_data.extend(sku_data)
            
            if not all_data:
                raise ValueError("Insufficient training data")
            
            # Prepare Prophet dataset
            df = pd.DataFrame([{
                'ds': row.timestamp,
                'y': row.units_sold
            } for row in all_data])
            
            # Train model
            model = Prophet(
                seasonality_mode=settings.prophet_seasonality_mode,
                yearly_seasonality=settings.prophet_yearly_seasonality,
                weekly_seasonality=settings.prophet_weekly_seasonality,
                daily_seasonality=settings.prophet_daily_seasonality
            )
            
            model.fit(df)
            
            # Validate model
            validation_mae, validation_mape = await self._validate_prophet(model, df)
            
            # Log metrics
            mlflow.log_params({
                "model_type": "prophet",
                "seasonality_mode": settings.prophet_seasonality_mode,
                "training_samples": len(all_data)
            })
            
            mlflow.log_metrics({
                "validation_mae": validation_mae,
                "validation_mape": validation_mape
            })
            
            # Save model
            mlflow.sklearn.log_model(
                model,
                "prophet_model",
                registered_model_name=f"{settings.mlflow_experiment_name}_prophet"
            )
            
            self.prophet_model = model
            self.prophet_metadata = ModelMetadata(
                model_name="prophet",
                version="latest",
                trained_at=datetime.utcnow().isoformat(),
                training_samples=len(all_data),
                validation_mae=validation_mae,
                validation_mape=validation_mape,
                mlflow_run_id=mlflow.active_run().info.run_id
            )
            
            logger.info(f"Prophet model trained successfully. MAE: {validation_mae:.2f}, MAPE: {validation_mape:.2f}")
    
    async def _train_tft(self, skus: List[str]):
        """Train TFT model"""
        logger.info("Training TFT model")
        
        with mlflow.start_run(run_name=f"tft_training_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"):
            # Prepare TFT dataset
            all_data = []
            for sku in skus:
                sku_data = await self.data_loader.get_training_data(sku)
                if len(sku_data) >= settings.min_training_samples:
                    all_data.extend(sku_data)
            
            if not all_data:
                raise ValueError("Insufficient training data")
            
            df = pd.DataFrame([{
                'timestamp': row.timestamp,
                'sku': row.sku,
                'units_sold': row.units_sold,
                'price': row.price
            } for row in all_data])
            
            # Prepare TFT data
            df['time_idx'] = df.groupby('sku').cumcount()
            df = df.sort_values(['sku', 'time_idx'])
            
            # Create training dataset
            max_encoder_length = 60
            max_prediction_length = 30
            
            training = TimeSeriesDataSet(
                df,
                time_idx="time_idx",
                target="units_sold",
                group_ids=["sku"],
                max_encoder_length=max_encoder_length,
                max_prediction_length=max_prediction_length,
                static_categoricals=["sku"],
                time_varying_known_reals=["price"],
                time_varying_unknown_reals=["units_sold"],
                target_normalizer=GroupNormalizer(groups=["sku"]),
            )
            
            # Create validation dataset
            validation = TimeSeriesDataSet.from_dataset(training, df, predict=True, stop_randomization=True)
            
            # Create data loaders
            train_dataloader = training.to_dataloader(train=True, batch_size=settings.tft_batch_size)
            val_dataloader = validation.to_dataloader(train=False, batch_size=settings.tft_batch_size)
            
            # Initialize model
            tft = TemporalFusionTransformer.from_dataset(
                training,
                learning_rate=settings.tft_learning_rate,
                hidden_size=settings.tft_hidden_size,
                attention_head_size=settings.tft_attention_head_size,
                dropout=settings.tft_dropout,
                hidden_continuous_size=settings.tft_hidden_size,
                loss=MAE(),
                log_interval=10,
                reduce_on_plateau_patience=4,
            )
            
            # Train model
            import pytorch_lightning as pl
            trainer = pl.Trainer(
                max_epochs=settings.tft_max_epochs,
                accelerator="gpu" if settings.use_gpu and torch.cuda.is_available() else "cpu",
                devices=1,
                enable_progress_bar=False,
                logger=False
            )
            
            trainer.fit(tft, train_dataloader, val_dataloader)
            
            # Validate model
            validation_mae = trainer.validate(tft, val_dataloader)[0]['val_loss']
            validation_mape = validation_mae / df['units_sold'].mean() * 100  # Approximate MAPE
            
            # Log metrics
            mlflow.log_params({
                "model_type": "tft",
                "max_epochs": settings.tft_max_epochs,
                "batch_size": settings.tft_batch_size,
                "learning_rate": settings.tft_learning_rate,
                "hidden_size": settings.tft_hidden_size,
                "training_samples": len(all_data)
            })
            
            mlflow.log_metrics({
                "validation_mae": validation_mae,
                "validation_mape": validation_mape
            })
            
            # Save model
            mlflow.pytorch.log_model(
                tft,
                "tft_model",
                registered_model_name=f"{settings.mlflow_experiment_name}_tft"
            )
            
            self.tft_model = tft
            self.tft_metadata = ModelMetadata(
                model_name="tft",
                version="latest",
                trained_at=datetime.utcnow().isoformat(),
                training_samples=len(all_data),
                validation_mae=validation_mae,
                validation_mape=validation_mape,
                mlflow_run_id=mlflow.active_run().info.run_id
            )
            
            logger.info(f"TFT model trained successfully. MAE: {validation_mae:.2f}, MAPE: {validation_mape:.2f}")
    
    async def _validate_prophet(self, model: Prophet, df: pd.DataFrame) -> tuple[float, float]:
        """Validate Prophet model"""
        # Simple validation using last 20% of data
        split_idx = int(len(df) * 0.8)
        train_df = df[:split_idx]
        test_df = df[split_idx:]
        
        # Retrain on training subset
        temp_model = Prophet(
            seasonality_mode=settings.prophet_seasonality_mode,
            yearly_seasonality=settings.prophet_yearly_seasonality,
            weekly_seasonality=settings.prophet_weekly_seasonality,
            daily_seasonality=settings.prophet_daily_seasonality
        )
        temp_model.fit(train_df)
        
        # Predict on test set
        future = temp_model.make_future_dataframe(periods=len(test_df))
        forecast = temp_model.predict(future)
        
        # Calculate metrics
        test_predictions = forecast.tail(len(test_df))['yhat'].values
        test_actual = test_df['y'].values
        
        mae = np.mean(np.abs(test_predictions - test_actual))
        mape = np.mean(np.abs((test_actual - test_predictions) / test_actual)) * 100
        
        return mae, mape
    
    async def get_model_status(self) -> Dict[str, Any]:
        """Get current model status"""
        return {
            "prophet": {
                "available": self.prophet_model is not None,
                "metadata": self.prophet_metadata.dict() if self.prophet_metadata else None
            },
            "tft": {
                "available": self.tft_model is not None,
                "metadata": self.tft_metadata.dict() if self.tft_metadata else None
            },
            "ensemble_config": {
                "short_term_threshold": settings.short_term_threshold,
                "long_term_threshold": settings.long_term_threshold
            }
        }