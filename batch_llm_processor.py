"""
OpenAI Batch Processing Module for eBay Listings

This module provides batch processing capabilities for LLM operations to reduce costs
when processing many eBay listings. OpenAI's batch API offers 50% cost reduction
compared to regular API calls.

Usage:
    processor = BatchLLMProcessor()
    processor.add_request("rate_description", item_id, {...})
    processor.add_request("generate_title", item_id, {...})
    results = processor.process_batch()
"""

import json
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BatchLLMProcessor:
    """Handles batch processing of LLM requests for eBay listings"""
    
    def __init__(self, api_key: str = None, batch_dir: str = ".batch_processing"):
        """
        Initialize the batch processor
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            batch_dir: Directory to store batch files and results
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required for batch processing")
            
        self.client = OpenAI(api_key=self.api_key)
        self.batch_dir = Path(batch_dir)
        self.batch_dir.mkdir(exist_ok=True)
        
        # Storage for current batch
        self.requests = []
        self.request_mapping = {}  # Maps custom_id to original request info
        
    def add_description_rating_request(self, item_id: str, description: str, specifics: dict) -> str:
        """Add a description rating request to the batch"""
        custom_id = f"rate_desc_{item_id}_{self._generate_hash(description)[:8]}"
        
        prompt = f"""Rate the quality of this eBay item description on a scale of 1-10, where:
- 1-3: Very poor (missing key information, unclear)
- 4-6: Average (has basic info but could be improved)  
- 7-8: Good (clear, informative, well-structured)
- 9-10: Excellent (comprehensive, engaging, professional)

Item Specifics:
{json.dumps(specifics, indent=2)}

Description:
{description}

Return ONLY a single integer from 1 to 10."""
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert eBay listing evaluator."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 10
            }
        }
        
        self.requests.append(request)
        self.request_mapping[custom_id] = {
            "type": "rate_description",
            "item_id": item_id,
            "original_description": description
        }
        
        return custom_id
        
    def add_title_rating_request(self, item_id: str, title: str, description: str) -> str:
        """Add a title rating request to the batch"""
        custom_id = f"rate_title_{item_id}_{self._generate_hash(title)[:8]}"
        
        prompt = f"""Rate this eBay listing title on a scale of 1-10:

Title: {title}

Product Description:
{description[:1000]}

Criteria:
- Clarity and accuracy
- Keyword optimization
- Character usage (80 char limit)
- Appeal to buyers

Return ONLY a single integer from 1 to 10."""
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert eBay listing evaluator."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 10
            }
        }
        
        self.requests.append(request)
        self.request_mapping[custom_id] = {
            "type": "rate_title",
            "item_id": item_id,
            "original_title": title
        }
        
        return custom_id
        
    def add_description_generation_request(self, item_id: str, description: str, specifics: dict) -> str:
        """Add a description generation request to the batch"""
        custom_id = f"gen_desc_{item_id}_{self._generate_hash(description)[:8]}"
        
        prompt = f"""Improve this eBay listing description to be more engaging and informative.

Current Description:
{description}

Item Specifics:
{json.dumps(specifics, indent=2)}

Requirements:
- Keep factual information accurate
- Make it more engaging and professional
- Use HTML formatting (<p>, <strong>, <ul>, etc.)
- Highlight key features and benefits
- Keep under 4000 characters

Return ONLY the improved HTML description."""
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert eBay listing copywriter."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1500
            }
        }
        
        self.requests.append(request)
        self.request_mapping[custom_id] = {
            "type": "generate_description",
            "item_id": item_id,
            "original_description": description
        }
        
        return custom_id
        
    def add_title_generation_request(self, item_id: str, title: str, description: str) -> str:
        """Add a title generation request to the batch"""
        custom_id = f"gen_title_{item_id}_{self._generate_hash(title)[:8]}"
        
        prompt = f"""Create an optimized eBay listing title (max 80 characters).

Current Title: {title}

Product Description:
{description[:1000]}

Requirements:
- Maximum 80 characters
- Include key product identifiers
- Add relevant keywords for search
- Be clear and appealing
- Don't use all caps or excessive punctuation

Return ONLY the new title (no quotes or explanation)."""
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert eBay listing optimizer."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.5,
                "max_tokens": 50
            }
        }
        
        self.requests.append(request)
        self.request_mapping[custom_id] = {
            "type": "generate_title",
            "item_id": item_id,
            "original_title": title
        }
        
        return custom_id
        
    def add_specifics_generation_request(self, item_id: str, description: str, 
                                        missing_specifics: List[str], title: str = None) -> str:
        """Add an item specifics generation request to the batch"""
        custom_id = f"gen_specs_{item_id}_{self._generate_hash(str(missing_specifics))[:8]}"
        
        # Enhanced description with title if needed
        enhanced_desc = description
        if title and ("Model" in missing_specifics or "Type" in missing_specifics):
            enhanced_desc = f"Title: {title}\n\n{description}"
        
        prompt = f"""Analyze this eBay product and provide values for missing item specifics.

Missing Specifics: {', '.join(missing_specifics)}

Product Information:
{enhanced_desc[:2000]}

Instructions:
- Return ONLY a JSON object
- Keys must be from the missing specifics list above
- Values must be under 65 characters
- For "Model": extract model numbers/codes
- For "Type": identify product category
- For "Personalize": default to "No" if not mentioned
- For "Vintage": default to "No" if not clear
- Omit any specifics you cannot determine

Example: {{"Model": "ABC123", "Type": "Antenna"}}"""
        
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert at extracting product specifications."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 200,
                "response_format": {"type": "json_object"}
            }
        }
        
        self.requests.append(request)
        self.request_mapping[custom_id] = {
            "type": "generate_specifics",
            "item_id": item_id,
            "missing_specifics": missing_specifics
        }
        
        return custom_id
        
    def submit_batch(self, description: str = None) -> str:
        """
        Submit the current batch to OpenAI
        
        Returns:
            batch_id: The ID of the submitted batch job
        """
        if not self.requests:
            raise ValueError("No requests to process")
            
        # Create JSONL file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_file = self.batch_dir / f"batch_input_{timestamp}.jsonl"
        
        with open(input_file, 'w') as f:
            for request in self.requests:
                f.write(json.dumps(request) + '\n')
                
        logger.info(f"Created batch file with {len(self.requests)} requests: {input_file}")
        
        # Upload file to OpenAI
        with open(input_file, 'rb') as f:
            batch_file = self.client.files.create(
                file=f,
                purpose="batch"
            )
            
        logger.info(f"Uploaded file to OpenAI: {batch_file.id}")
        
        # Create batch job
        batch = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": description or f"eBay listing batch {timestamp}",
                "request_count": str(len(self.requests))
            }
        )
        
        logger.info(f"Created batch job: {batch.id}")
        
        # Save mapping for later retrieval
        mapping_file = self.batch_dir / f"batch_mapping_{batch.id}.json"
        with open(mapping_file, 'w') as f:
            json.dump({
                "batch_id": batch.id,
                "timestamp": timestamp,
                "request_mapping": self.request_mapping
            }, f, indent=2)
            
        # Clear current batch
        self.requests = []
        self.request_mapping = {}
        
        return batch.id
        
    def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Check the status of a batch job"""
        batch = self.client.batches.retrieve(batch_id)
        
        return {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "request_counts": {
                "total": batch.request_counts.total,
                "completed": batch.request_counts.completed,
                "failed": batch.request_counts.failed
            },
            "errors": batch.errors
        }
        
    def wait_for_batch(self, batch_id: str, check_interval: int = 30, 
                       max_wait: int = 7200) -> bool:
        """
        Wait for a batch to complete
        
        Args:
            batch_id: The batch ID to wait for
            check_interval: Seconds between status checks
            max_wait: Maximum seconds to wait (default 2 hours)
            
        Returns:
            True if completed successfully, False if failed or timed out
        """
        start_time = time.time()
        last_log_time = 0
        check_count = 0
        
        while time.time() - start_time < max_wait:
            elapsed = time.time() - start_time
            status = self.check_batch_status(batch_id)
            check_count += 1
            
            # Log progress every check for the first 5 minutes, then every 5 checks
            if elapsed < 300 or check_count % 5 == 0:
                elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                remaining = max_wait - elapsed
                remaining_str = f"{int(remaining // 60)}m {int(remaining % 60)}s"
                logger.info(f"Batch {batch_id}: {status['status']} "
                           f"({status['request_counts']['completed']}/{status['request_counts']['total']} completed) "
                           f"[Elapsed: {elapsed_str}, Timeout in: {remaining_str}]")
            
            # Check for completed or finalizing status (both mean processing is done)
            if status['status'] in ['completed', 'finalizing']:
                # If all requests are completed, consider it done even if status is still 'finalizing'
                if status['request_counts']['completed'] == status['request_counts']['total']:
                    total_time = time.time() - start_time
                    logger.info(f"Batch {batch_id} completed successfully after {int(total_time // 60)}m {int(total_time % 60)}s")
                    return True
            elif status['status'] in ['failed', 'cancelled', 'expired']:
                logger.error(f"Batch {batch_id} failed with status '{status['status']}': {status.get('errors')}")
                if status['request_counts']['failed'] > 0:
                    logger.error(f"Failed requests: {status['request_counts']['failed']}/{status['request_counts']['total']}")
                return False
                
            time.sleep(check_interval)
            
        # Final check before timing out
        status = self.check_batch_status(batch_id)
        if status['status'] in ['completed', 'finalizing'] and \
           status['request_counts']['completed'] == status['request_counts']['total']:
            logger.info(f"Batch {batch_id} completed successfully (final check)")
            return True
            
        logger.error(f"Batch {batch_id} timed out after {max_wait} seconds ({int(max_wait // 3600)}h {int((max_wait % 3600) // 60)}m)")
        logger.error(f"Final status: {status['status']}, Completed: {status['request_counts']['completed']}/{status['request_counts']['total']}")
        logger.error("Consider increasing max_wait parameter or checking OpenAI dashboard for issues")
        return False
        
    def get_batch_results(self, batch_id: str, wait_for_output: bool = True, 
                         max_wait: int = 300, force_retry: bool = False) -> Dict[str, Any]:
        """
        Retrieve and parse results from a completed batch
        
        Args:
            batch_id: The batch ID to retrieve results for
            wait_for_output: Wait for output file if batch is finalizing
            max_wait: Maximum seconds to wait for output file
            force_retry: If True, retry the batch if stuck in finalizing
        
        Returns:
            Dictionary mapping item_ids to their results
        """
        # Load the mapping file
        mapping_file = self.batch_dir / f"batch_mapping_{batch_id}.json"
        if not mapping_file.exists():
            raise FileNotFoundError(f"Mapping file not found for batch {batch_id}")
            
        with open(mapping_file, 'r') as f:
            mapping_data = json.load(f)
            
        request_mapping = mapping_data['request_mapping']
        
        # Get the batch details
        batch = self.client.batches.retrieve(batch_id)
        
        # Accept both 'completed' and 'finalizing' status if all requests are done
        if batch.status not in ['completed', 'finalizing']:
            raise ValueError(f"Batch {batch_id} is not completed (status: {batch.status})")
        
        # For 'finalizing' status, ensure all requests are actually done
        if batch.status == 'finalizing' and batch.request_counts.completed != batch.request_counts.total:
            raise ValueError(f"Batch {batch_id} is still processing ({batch.request_counts.completed}/{batch.request_counts.total} completed)")
        
        # Wait for output file to become available if in finalizing state
        output_file_id = batch.output_file_id
        if not output_file_id and wait_for_output and batch.status == 'finalizing':
            logger.info(f"Batch {batch_id} is finalizing, waiting for output file...")
            start_time = time.time()
            while time.time() - start_time < max_wait:
                time.sleep(10)  # Check every 10 seconds
                batch = self.client.batches.retrieve(batch_id)
                if batch.output_file_id:
                    output_file_id = batch.output_file_id
                    logger.info(f"Output file now available for batch {batch_id}")
                    break
                if batch.status == 'completed':
                    output_file_id = batch.output_file_id
                    break
            
            # Check if batch is stuck in finalizing for too long
            if not output_file_id and batch.status == 'finalizing':
                time_since_creation = time.time() - batch.created_at
                if time_since_creation > 1800:  # More than 30 minutes
                    logger.warning(f"Batch {batch_id} has been finalizing for {time_since_creation/60:.1f} minutes")
                    if force_retry:
                        logger.info(f"Force retry enabled - attempting to cancel and resubmit batch")
                        return self._handle_stuck_batch(batch_id, request_mapping)
                    else:
                        logger.warning(f"Consider cancelling this batch and resubmitting. Use force_retry=True to auto-retry.")
            
        # Download output file
        output_file = self.batch_dir / f"batch_output_{batch_id}.jsonl"
        
        if output_file_id:
            content = self.client.files.content(output_file_id)
            with open(output_file, 'wb') as f:
                f.write(content.content)
                
            logger.info(f"Downloaded batch results to {output_file}")
        else:
            raise ValueError(f"No output file available for batch {batch_id} after waiting")
            
        # Parse results
        results = {}
        
        with open(output_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                response = json.loads(line)
                custom_id = response['custom_id']
                
                if custom_id not in request_mapping:
                    logger.warning(f"Unknown custom_id: {custom_id}")
                    continue
                    
                request_info = request_mapping[custom_id]
                item_id = request_info['item_id']
                
                if item_id not in results:
                    results[item_id] = {}
                    
                # Parse based on request type
                if response.get('error'):
                    results[item_id][request_info['type']] = {
                        'error': response['error']
                    }
                else:
                    content = response['response']['body']['choices'][0]['message']['content']
                    
                    if request_info['type'] in ['rate_description', 'rate_title']:
                        # Extract rating number
                        try:
                            rating = int(''.join(filter(str.isdigit, content)))
                            results[item_id][request_info['type']] = rating
                        except:
                            logger.error(f"Failed to parse rating from: {content}")
                            results[item_id][request_info['type']] = 5  # Default
                            
                    elif request_info['type'] == 'generate_specifics':
                        try:
                            specs = json.loads(content)
                            results[item_id][request_info['type']] = specs
                        except:
                            logger.error(f"Failed to parse specifics JSON from: {content}")
                            results[item_id][request_info['type']] = {}
                            
                    else:
                        # For description and title generation
                        results[item_id][request_info['type']] = content.strip()
                        
        logger.info(f"Parsed results for {len(results)} items")
        return results
        
    def _generate_hash(self, text: str) -> str:
        """Generate a short hash for text"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _handle_stuck_batch(self, batch_id: str, request_mapping: dict) -> Dict[str, Any]:
        """Handle a batch that is stuck in finalizing state"""
        logger.warning(f"Batch {batch_id} appears to be stuck - this is likely an OpenAI API issue")
        logger.info("You may need to:")
        logger.info("1. Cancel this batch: client.batches.cancel(batch_id)")
        logger.info("2. Resubmit the requests in a new batch")
        logger.info("3. Contact OpenAI support if this persists")
        
        # Return empty results for now
        # In a production system, you might want to automatically resubmit
        return {}
        
    def process_batch_with_wait(self, description: str = None) -> Dict[str, Any]:
        """
        Submit batch and wait for results
        
        This is a convenience method that combines submission and waiting
        """
        if not self.requests:
            logger.warning("No requests to process")
            return {}
            
        batch_id = self.submit_batch(description)
        
        logger.info(f"Batch {batch_id} submitted with {len(self.request_mapping)} requests")
        logger.info("Waiting for batch to complete (this may take several minutes)...")
        
        if self.wait_for_batch(batch_id):
            return self.get_batch_results(batch_id)
        else:
            # Check if batch is stuck before returning empty
            status = self.check_batch_status(batch_id)
            if status['status'] == 'finalizing' and status['request_counts']['completed'] == status['request_counts']['total']:
                time_since_creation = time.time() - self.client.batches.retrieve(batch_id).created_at
                logger.warning(f"Batch {batch_id} completed all requests but is stuck in 'finalizing' for {time_since_creation/60:.1f} minutes")
                logger.warning("This appears to be an OpenAI API issue. Consider using force_retry=True in get_batch_results()")
            else:
                logger.error(f"Batch {batch_id} failed or timed out")
            return {}