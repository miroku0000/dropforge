import json
import time
import os
import threading
from datetime import datetime
from pathlib import Path

# Configuration
QUEUE_FILE = os.path.join("..", "data", "scrape_queue.jsonl")
PROCESSING_FILE = os.path.join("..", "data", "scrape_processing.jsonl")
COMPLETED_FILE = os.path.join("..", "data", "scrape_completed.jsonl")
STATUS_FILE = os.path.join("..", "data", "scrape_status.json")
BATCH_SIZE = 1000  # Number of items to accumulate before triggering upload


class BatchManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.items_scraped = 0
        self.items_uploaded = 0
        self.batch_ready = False
        self.current_batch = []

    def add_scraped_item(self, url, data):
        """Add a scraped item to the queue"""
        with self.lock:
            item = {
                "url": url,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "status": "queued",
            }

            # Append to queue file
            with open(QUEUE_FILE, "a") as f:
                f.write(json.dumps(item) + "\n")

            self.current_batch.append(url)
            self.items_scraped += 1

            # Check if we have enough for a batch
            if len(self.current_batch) >= BATCH_SIZE:
                self.batch_ready = True

            self.update_status()

    def get_batch_for_upload(self, max_items=None):
        """Get a batch of items ready for upload"""
        with self.lock:
            if not os.path.exists(QUEUE_FILE):
                print("debug: QUEUE_FILE does not exist: " + QUEUE_FILE)
                return []

            # Read all queued items
            items = []
            remaining = []

            with open(QUEUE_FILE, "r") as f:
                for line in f:
                    line_content = line.strip()
                    if line_content:
                        try:
                            item = json.loads(line_content)
                            if len(items) < (max_items or BATCH_SIZE):
                                items.append(item)
                                # Move to processing file
                                with open(PROCESSING_FILE, "a") as pf:
                                    pf.write(line)
                            else:
                                remaining.append(line)
                        except json.JSONDecodeError as e:
                            print(f"Warning: Skipping invalid JSON line: {line_content[:100]}... Error: {e}")
                            continue

            # Rewrite queue file with remaining items
            with open(QUEUE_FILE, "w") as f:
                for line in remaining:
                    f.write(line)

            return items

    def mark_uploaded(self, items):
        """Mark items as successfully uploaded"""
        with self.lock:
            # Move from processing to completed
            with open(COMPLETED_FILE, "a") as f:
                for item in items:
                    item["status"] = "uploaded"
                    item["upload_time"] = datetime.now().isoformat()
                    f.write(json.dumps(item) + "\n")

            self.items_uploaded += len(items)

            # Clear processing file
            if os.path.exists(PROCESSING_FILE):
                os.remove(PROCESSING_FILE)

            self.update_status()

    def update_status(self):
        """Update status file with current progress"""
        status = {
            "items_scraped": self.items_scraped,
            "items_uploaded": self.items_uploaded,
            "items_pending": self.items_scraped - self.items_uploaded,
            "last_update": datetime.now().isoformat(),
        }

        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)

    def get_status(self):
        """Get current processing status"""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        return None

    def cleanup_files(self):
        """Initialize/cleanup queue files"""
        # Create data directory if needed
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)

        # Initialize files if they don't exist
        for filepath in [QUEUE_FILE, PROCESSING_FILE, COMPLETED_FILE]:
            if not os.path.exists(filepath):
                Path(filepath).touch()


# Global instance
batch_manager = BatchManager()
