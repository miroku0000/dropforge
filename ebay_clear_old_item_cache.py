import os
import time

dir_path = r"D:\zikprocessor\src\.cache_item_details"
limit_days = 1
max_deletions = 200

threshold = time.time() - limit_days * 86400

# Collect eligible files with their modification times
files = []
for filename in os.listdir(dir_path):
    file_path = os.path.join(dir_path, filename)
    if os.path.isfile(file_path):
        file_mtime = os.path.getmtime(file_path)
        if file_mtime < threshold:
            files.append((file_mtime, file_path))

# Sort by oldest first and select up to max_deletions
files.sort()
files_to_delete = files[:max_deletions]

# Delete selected files
for mtime, file_path in files_to_delete:
    os.remove(file_path)
    print(f"Deleted: {file_path}")
