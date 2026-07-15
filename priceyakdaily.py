
import os
import time

# Remove All temp files from zik
print("1. Cleaning up old files")
os.system("removeallzikdownloads.py")
os.system("removezikautopilotdownloads.py")
os.system("del C:\\Users\\mirok\\Downloads\\eBay-ListingsTrafficReport-*")

print("2. Sending ebay offers")

#Send ebay offers
os.system("ebaysendoffers.py")

#Delete 200 oldest listings with no views preferably with missing item specifics
print("3. Deleting oldest 200 listings")
print("3.1 Downloading Ebay Traffic Report")
os.system("ebaydownloadlistingtrafficreport.py")
print("3.2 Generating safetokill")
os.system("preparelistingstokill.py >d:\\zikprocessor\\data\\safetokill.txt")

os.system("kill200priceyak.py")

# print("3.3 Finding 200 listings to kill")
# os.system("findlistingstokill.py 200 > d:\\zikprocessor\\data\\kill.txt")
# print("3.4 Sending listings to priceyak bulk delete")
# os.system("priceyakbulkdelete.py")

print("4 Generate and list some new listings")
# Generate listings on zik and list them on priceyak
os.system("priceyakgetandlistsomeproducts.bat")

# # Generate new listings on Zik
# os.system("zikautopilotport.py --min_roi 0.2 --min_sales 7 -numProducts 2000")

# # Extract all the Amazon ASINs from the CSV file where the seller price is > $25
# os.system("priceyakprocesszikautodownloadcsv.py >d:\\zikprocessor\\data\\listme.txt")

# # Read amazon ids from d:\\zikprocessor\\data\\listme.txt and submit them to be listed
# os.system("priceyakbulkupload.py")

print("Done with everything up to submitting listings.  Need to wait a while before starting item specific optimization")
#wait for some time
time.sleep(60*5)

# Accept ebays reccomedations for item specifics
os.system("ebayrecommendeditemspecifics.py")

#start analyzing all listings with optiseller
os.system("startoptiseller.py")

# os.system("opti.bat")

