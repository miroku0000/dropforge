import csv
import os
import glob
import sys


total=0
n = 5
nfirstlines = []

files=glob.glob('c:\\Users\\mirok\\Downloads\\eBay-ListingsTrafficReport-*.csv')
srcfile=files[0]
targetfile="D:\\zikprocessor\\data\\ebay-ListingsTrafficReport-latest.csv"
tempfile="D:\\zikprocessor\\data\\safetodelete.txt"

# Filter ebay download to utf8 and write it to targetfile
with open(srcfile,  encoding="utf8") as f, open(targetfile, "w",  encoding="utf8") as out:
    for x in range(n):
        nfirstlines.append(next(f))
    for line in f:
        out.write(line)

#Open targetfile and filter the ones we can safely kill to those having no page views and no sales 
with open(targetfile, newline='', encoding='utf8') as csvfile, open(tempfile, "w+",  encoding="utf8") as out:
    reader = csv.DictReader(csvfile)
    for row in reader:
        if row["Total page views"]=="0" and row["Quantity sold"]=="0":
            print(row["eBay item ID"])
            