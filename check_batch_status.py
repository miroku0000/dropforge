"""Check and retrieve batch results even if timed out"""
import os
from openai import OpenAI
from batch_llm_processor import BatchLLMProcessor

# Get batch ID
batch_id = "batch_6952f0cc2ee48190bb33f30fc383a53b"

# Initialize processor
processor = BatchLLMProcessor()

# Check current status
status = processor.check_batch_status(batch_id)
print(f"Batch Status: {status['status']}")
print(f"Completed: {status['request_counts']['completed']}/{status['request_counts']['total']}")

# If the batch shows as finalizing or completed, try to get results
if status['status'] in ['completed', 'finalizing']:
    print(f"\nBatch is {status['status']}, attempting to retrieve results...")
    try:
        results = processor.get_batch_results(batch_id)
        print(f"Successfully retrieved results for {len(results)} items")
        
        # Save results summary
        import json
        with open(f"batch_results_{batch_id[:8]}.json", 'w') as f:
            json.dump({
                "batch_id": batch_id,
                "status": status,
                "item_count": len(results),
                "sample_items": list(results.keys())[:10] if results else []
            }, f, indent=2)
        print(f"Results summary saved to batch_results_{batch_id[:8]}.json")
    except Exception as e:
        print(f"Error retrieving results: {e}")
else:
    print(f"Batch is still {status['status']}, cannot retrieve results yet")