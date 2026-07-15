if "%DELETE_MAX%"=="" set DELETE_MAX=333
 ai_process_all_listings.py  --numlistings %DELETE_MAX%> d:\\zikprocessor\\data\\kill.txt
priceyakbulkdelete.py