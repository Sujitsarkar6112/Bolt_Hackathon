import json
import numpy as np
import triton_python_backend_utils as pb_utils
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TritonPythonModel:
    """Ensemble model that orchestrates guardrail validation"""
    
    def initialize(self, args):
        """Initialize the ensemble model"""
        logger.info("Ensemble guardrail model initialized")
    
    def execute(self, requests):
        """Execute ensemble validation with HTTP-like response codes"""
        responses = []
        
        for request in requests:
            try:
                # Get input text
                input_tensor = pb_utils.get_input_tensor_by_name(request, "TEXT")
                input_text = input_tensor.as_numpy()[0].decode('utf-8')
                
                logger.info(f"Ensemble processing: {input_text[:50]}...")
                
                # Create request for guardrail model
                guardrail_request = pb_utils.InferenceRequest(
                    model_name="guardrail",
                    requested_output_names=["VALIDATION_RESULT"],
                    inputs=[input_tensor]
                )
                
                # Execute guardrail validation
                guardrail_response = guardrail_request.exec()
                
                if guardrail_response.has_error():
                    raise Exception(f"Guardrail model error: {guardrail_response.error().message()}")
                
                # Get validation result
                validation_tensor = pb_utils.get_output_tensor_by_name(
                    guardrail_response, "VALIDATION_RESULT"
                )
                validation_json = validation_tensor.as_numpy()[0].decode('utf-8')
                validation_result = json.loads(validation_json)
                
                # Determine HTTP status code based on validation
                if validation_result["is_safe"]:
                    status_code = 200  # OK
                    status_message = "VALID"
                else:
                    status_code = 400  # Bad Request
                    status_message = "VALIDATION_FAILED"
                
                # Prepare ensemble response
                ensemble_response = {
                    "status_code": status_code,
                    "status_message": status_message,
                    "is_safe": validation_result["is_safe"],
                    "violations": validation_result["violations"],
                    "sanitized_text": validation_result["sanitized_text"],
                    "entities_found": validation_result["entities_found"],
                    "confidence_score": validation_result["confidence_score"],
                    "original_text": input_text
                }
                
                # Convert to JSON
                response_json = json.dumps(ensemble_response)
                
                # Create output tensors
                status_tensor = pb_utils.Tensor(
                    "STATUS_CODE",
                    np.array([status_code], dtype=np.int32)
                )
                
                result_tensor = pb_utils.Tensor(
                    "RESULT",
                    np.array([response_json.encode('utf-8')], dtype=object)
                )
                
                # Create inference response
                inference_response = pb_utils.InferenceResponse(
                    output_tensors=[status_tensor, result_tensor]
                )
                
                responses.append(inference_response)
                
                logger.info(f"Ensemble completed. Status: {status_code}, Safe: {validation_result['is_safe']}")
                
            except Exception as e:
                logger.error(f"Ensemble error: {str(e)}")
                
                # Return error response with 500 status
                error_response = {
                    "status_code": 500,
                    "status_message": "INTERNAL_ERROR",
                    "is_safe": False,
                    "violations": [f"Internal error: {str(e)}"],
                    "sanitized_text": "[ERROR]",
                    "entities_found": [],
                    "confidence_score": 0.0,
                    "original_text": input_text if 'input_text' in locals() else ""
                }
                
                error_json = json.dumps(error_response)
                
                error_status_tensor = pb_utils.Tensor(
                    "STATUS_CODE",
                    np.array([500], dtype=np.int32)
                )
                
                error_result_tensor = pb_utils.Tensor(
                    "RESULT",
                    np.array([error_json.encode('utf-8')], dtype=object)
                )
                
                error_inference_response = pb_utils.InferenceResponse(
                    output_tensors=[error_status_tensor, error_result_tensor]
                )
                
                responses.append(error_inference_response)
        
        return responses
    
    def finalize(self):
        """Clean up resources"""
        logger.info("Ensemble guardrail model finalized")