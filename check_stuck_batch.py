"""Check for stuck batches and attempt recovery"""
import os
import time
from openai import OpenAI
from batch_llm_processor import BatchLLMProcessor

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# List recent batches
print("Checking recent batches...")
batches = client.batches.list(limit=10)

stuck_batches = []
for batch in batches.data:
    time_elapsed = (time.time() - batch.created_at) / 60
    if batch.status == 'finalizing' and time_elapsed > 30:
        stuck_batches.append({
            'id': batch.id,
            'status': batch.status,
            'time_elapsed': time_elapsed,
            'completed': batch.request_counts.completed,
            'total': batch.request_counts.total,
            'has_output': batch.output_file_id is not None
        })
        
if stuck_batches:
    print(f"\nFound {len(stuck_batches)} stuck batch(es):")
    for b in stuck_batches:
        print(f"\n  Batch ID: {b['id']}")
        print(f"  Status: {b['status']}")
        print(f"  Time elapsed: {b['time_elapsed']:.1f} minutes")
        print(f"  Progress: {b['completed']}/{b['total']}")
        print(f"  Has output file: {b['has_output']}")
        
    # Try to recover the most recent stuck batch
    latest_stuck = stuck_batches[0]
    print(f"\nAttempting to recover batch {latest_stuck['id']}...")
    
    processor = BatchLLMProcessor()
    
    # Wait a bit more for output file
    max_wait = 120  # 2 more minutes
    start = time.time()
    
    while time.time() - start < max_wait:
        batch = client.batches.retrieve(latest_stuck['id'])
        if batch.output_file_id:
            print(f"Output file appeared! ID: {batch.output_file_id}")
            try:
                results = processor.get_batch_results(latest_stuck['id'], wait_for_output=False)
                print(f"Successfully retrieved results for {len(results)} items")
                break
            except Exception as e:
                print(f"Error retrieving results: {e}")
                break
        print(f"Waiting... ({int(time.time() - start)}s elapsed)")
        time.sleep(10)
    else:
        print(f"\nBatch {latest_stuck['id']} is still stuck after waiting.")
        print("This appears to be an OpenAI API issue.")
        print("Options:")
        print("1. Wait longer and try again")
        print("2. Cancel the batch and resubmit")
        print("3. Contact OpenAI support")
else:
    print("\nNo stuck batches found.")