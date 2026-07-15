import os

print("3.3 Finding 200 listings to kill")
os.system("findlistingstokill.py 200 > d:\\zikprocessor\\data\\kill.txt")
print("3.4 Sending listings to priceyak bulk delete")
os.system("priceyakbulkdelete.py")
