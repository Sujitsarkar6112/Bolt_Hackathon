#!/usr/bin/env python3
"""
Data flow validation script
Validates that data flows correctly through the entire pipeline
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pymongo import MongoClient
from kafka import KafkaConsumer, TopicPartition
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@localhost:27017/demandbot?authSource=admin")
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"


class DataFlowValidator:
    """Validates data flow through the pipeline"""
    
    def __init__(self):
        self.mongo_client = MongoClient(MONGODB_URL)
        self.kafka_consumer = None
    
    def setup_kafka_consumer(self):
        """Setup Kafka consumer for validation"""
        self.kafka_consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
    
    def validate_kafka_topics(self) -> Dict[str, Any]:
        """Validate Kafka topics exist and have data"""
        logger.info("Validating Kafka topics...")
        
        results = {}
        topics_to_check = ['sales_txn', 'sales_ingested', 'model_retrain']
        
        for topic in topics_to_check:
            try:
                # Get topic metadata
                partitions = self.kafka_consumer.partitions_for_topic(topic)
                if partitions is None:
                    results[topic] = {"exists": False, "message_count": 0}
                    continue
                
                # Count messages in topic
                topic_partitions = [TopicPartition(topic, p) for p in partitions]
                self.kafka_consumer.assign(topic_partitions)
                
                # Get earliest and latest offsets
                earliest_offsets = self.kafka_consumer.beginning_offsets(topic_partitions)
                latest_offsets = self.kafka_consumer.end_offsets(topic_partitions)
                
                total_messages = sum(
                    latest_offsets[tp] - earliest_offsets[tp] 
                    for tp in topic_partitions
                )
                
                results[topic] = {
                    "exists": True,
                    "partitions": len(partitions),
                    "message_count": total_messages
                }
                
                logger.info(f"Topic {topic}: {total_messages} messages across {len(partitions)} partitions")
                
            except Exception as e:
                logger.error(f"Error checking topic {topic}: {e}")
                results[topic] = {"exists": False, "error": str(e)}
        
        return results
    
    def validate_mongodb_collections(self) -> Dict[str, Any]:
        """Validate MongoDB collections have expected data"""
        logger.info("Validating MongoDB collections...")
        
        results = {}
        
        try:
            db = self.mongo_client["demandbot"]
            
            # Check sales collection
            sales_collection = db["raw_sales"]
            sales_count = sales_collection.count_documents({})
            
            # Get recent sales (last hour)
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_sales = sales_collection.count_documents({
                "processed_at": {"$gte": recent_cutoff.timestamp()}
            })
            
            # Get unique SKUs
            unique_skus = len(sales_collection.distinct("sku"))
            
            results["raw_sales"] = {
                "total_documents": sales_count,
                "recent_documents": recent_sales,
                "unique_skus": unique_skus
            }
            
            # Check forecast collections if they exist
            try:
                forecast_db = self.mongo_client["forecast_db"]
                
                models_collection = forecast_db["models"]
                models_count = models_collection.count_documents({})
                
                predictions_collection = forecast_db["predictions"]
                predictions_count = predictions_collection.count_documents({})
                
                results["forecast_models"] = {"total_documents": models_count}
                results["forecast_predictions"] = {"total_documents": predictions_count}
                
            except Exception as e:
                logger.warning(f"Forecast collections not accessible: {e}")
            
            # Check RAG collections if they exist
            try:
                rag_db = self.mongo_client["enterprise_rag"]
                
                docs_collection = rag_db["docs_vectors"]
                docs_count = docs_collection.count_documents({})
                unique_docs = len(docs_collection.distinct("document_name"))
                
                results["rag_documents"] = {
                    "total_chunks": docs_count,
                    "unique_documents": unique_docs
                }
                
            except Exception as e:
                logger.warning(f"RAG collections not accessible: {e}")
            
            logger.info(f"MongoDB validation complete: {sales_count} sales records, {unique_skus} unique SKUs")
            
        except Exception as e:
            logger.error(f"Error validating MongoDB: {e}")
            results["error"] = str(e)
        
        return results
    
    def validate_data_consistency(self) -> Dict[str, Any]:
        """Validate data consistency across systems"""
        logger.info("Validating data consistency...")
        
        results = {}
        
        try:
            db = self.mongo_client["demandbot"]
            sales_collection = db["raw_sales"]
            
            # Check for data quality issues
            
            # 1. Check for negative quantities
            negative_qty = sales_collection.count_documents({"qty": {"$lt": 0}})
            
            # 2. Check for negative prices
            negative_price = sales_collection.count_documents({"price": {"$lt": 0}})
            
            # 3. Check for missing required fields
            missing_sku = sales_collection.count_documents({"sku": {"$exists": False}})
            missing_ts = sales_collection.count_documents({"ts": {"$exists": False}})
            
            # 4. Check for duplicate events (same SKU + timestamp)
            pipeline = [
                {"$group": {
                    "_id": {"sku": "$sku", "ts": "$ts"},
                    "count": {"$sum": 1}
                }},
                {"$match": {"count": {"$gt": 1}}},
                {"$count": "duplicates"}
            ]
            
            duplicate_result = list(sales_collection.aggregate(pipeline))
            duplicates = duplicate_result[0]["duplicates"] if duplicate_result else 0
            
            # 5. Check timestamp validity
            invalid_timestamps = 0
            try:
                # Sample some documents to check timestamp format
                sample_docs = sales_collection.find().limit(100)
                for doc in sample_docs:
                    try:
                        datetime.fromisoformat(doc["ts"].replace('Z', '+00:00'))
                    except (ValueError, KeyError):
                        invalid_timestamps += 1
            except Exception:
                pass
            
            results = {
                "negative_quantities": negative_qty,
                "negative_prices": negative_price,
                "missing_sku": missing_sku,
                "missing_timestamp": missing_ts,
                "duplicate_events": duplicates,
                "invalid_timestamps": invalid_timestamps,
                "data_quality_score": self._calculate_quality_score({
                    "negative_qty": negative_qty,
                    "negative_price": negative_price,
                    "missing_sku": missing_sku,
                    "missing_ts": missing_ts,
                    "duplicates": duplicates,
                    "invalid_ts": invalid_timestamps
                })
            }
            
            logger.info(f"Data consistency check complete. Quality score: {results['data_quality_score']:.2f}")
            
        except Exception as e:
            logger.error(f"Error validating data consistency: {e}")
            results["error"] = str(e)
        
        return results
    
    def _calculate_quality_score(self, issues: Dict[str, int]) -> float:
        """Calculate data quality score (0-100)"""
        total_issues = sum(issues.values())
        
        # Get total document count for context
        try:
            db = self.mongo_client["demandbot"]
            total_docs = db["raw_sales"].count_documents({})
            
            if total_docs == 0:
                return 100.0
            
            # Calculate score based on issue percentage
            issue_percentage = (total_issues / total_docs) * 100
            quality_score = max(0, 100 - issue_percentage)
            
            return quality_score
            
        except Exception:
            return 0.0
    
    def validate_pipeline_performance(self) -> Dict[str, Any]:
        """Validate pipeline performance metrics"""
        logger.info("Validating pipeline performance...")
        
        results = {}
        
        try:
            db = self.mongo_client["demandbot"]
            sales_collection = db["raw_sales"]
            
            # Check ingestion latency (time between event timestamp and processed_at)
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_docs = sales_collection.find({
                "processed_at": {"$gte": recent_cutoff.timestamp()}
            }).limit(100)
            
            latencies = []
            for doc in recent_docs:
                try:
                    event_time = datetime.fromisoformat(doc["ts"].replace('Z', '+00:00'))
                    processed_time = datetime.fromtimestamp(doc["processed_at"])
                    latency = (processed_time - event_time.replace(tzinfo=None)).total_seconds()
                    latencies.append(latency)
                except Exception:
                    continue
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                min_latency = min(latencies)
                
                results["ingestion_latency"] = {
                    "average_seconds": avg_latency,
                    "max_seconds": max_latency,
                    "min_seconds": min_latency,
                    "sample_size": len(latencies)
                }
            
            # Check ingestion rate (events per minute)
            last_5_minutes = datetime.utcnow() - timedelta(minutes=5)
            recent_count = sales_collection.count_documents({
                "processed_at": {"$gte": last_5_minutes.timestamp()}
            })
            
            ingestion_rate = recent_count / 5.0  # events per minute
            
            results["ingestion_rate"] = {
                "events_per_minute": ingestion_rate,
                "events_last_5_minutes": recent_count
            }
            
            logger.info(f"Performance validation complete. Ingestion rate: {ingestion_rate:.2f} events/min")
            
        except Exception as e:
            logger.error(f"Error validating pipeline performance: {e}")
            results["error"] = str(e)
        
        return results
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete data flow validation"""
        logger.info("Starting full data flow validation")
        
        try:
            self.setup_kafka_consumer()
            
            validation_results = {
                "timestamp": datetime.utcnow().isoformat(),
                "kafka_topics": self.validate_kafka_topics(),
                "mongodb_collections": self.validate_mongodb_collections(),
                "data_consistency": self.validate_data_consistency(),
                "pipeline_performance": self.validate_pipeline_performance()
            }
            
            # Calculate overall health score
            health_score = self._calculate_overall_health(validation_results)
            validation_results["overall_health_score"] = health_score
            
            logger.info(f"Data flow validation complete. Overall health score: {health_score:.2f}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Data flow validation failed: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
        
        finally:
            if self.kafka_consumer:
                self.kafka_consumer.close()
            self.mongo_client.close()
    
    def _calculate_overall_health(self, results: Dict[str, Any]) -> float:
        """Calculate overall pipeline health score"""
        scores = []
        
        # Kafka health (topics exist and have data)
        kafka_results = results.get("kafka_topics", {})
        kafka_score = 0
        if kafka_results:
            existing_topics = sum(1 for topic_data in kafka_results.values() 
                                if isinstance(topic_data, dict) and topic_data.get("exists", False))
            kafka_score = (existing_topics / len(kafka_results)) * 100
        scores.append(kafka_score)
        
        # MongoDB health (collections exist and have data)
        mongo_results = results.get("mongodb_collections", {})
        mongo_score = 100 if mongo_results.get("raw_sales", {}).get("total_documents", 0) > 0 else 0
        scores.append(mongo_score)
        
        # Data quality score
        consistency_results = results.get("data_consistency", {})
        quality_score = consistency_results.get("data_quality_score", 0)
        scores.append(quality_score)
        
        # Performance score (based on ingestion rate)
        performance_results = results.get("pipeline_performance", {})
        ingestion_rate = performance_results.get("ingestion_rate", {}).get("events_per_minute", 0)
        performance_score = min(100, ingestion_rate * 10)  # Scale ingestion rate to 0-100
        scores.append(performance_score)
        
        # Return average score
        return sum(scores) / len(scores) if scores else 0


def main():
    """Main validation execution"""
    validator = DataFlowValidator()
    results = validator.run_full_validation()
    
    # Print results
    print("\n" + "="*60)
    print("DATA FLOW VALIDATION RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2, default=str))
    print("="*60)
    
    # Determine success/failure
    health_score = results.get("overall_health_score", 0)
    
    if health_score >= 80:
        print(f"\n✅ Data flow validation PASSED (Health Score: {health_score:.2f})")
        exit(0)
    else:
        print(f"\n❌ Data flow validation FAILED (Health Score: {health_score:.2f})")
        exit(1)


if __name__ == "__main__":
    main()