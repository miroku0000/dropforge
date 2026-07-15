import csv
import os
import glob
import sys

if len(sys.argv)>1:
    numtokill = int(sys.argv[1])
else:
    numtokill=9999999

total=0

nfirstlines = []

files=glob.glob('c:\\Users\\mirok\\Downloads\\')
srcfile="D:\\zikprocessor\\data\\safetokill.txt"
tmpfile="D:\\zikprocessor\\data\\temp.txt"


# Using readlines()
file1 = open(srcfile, 'r')
lines = file1.readlines()
n=0
for line in lines:
    if n<numtokill:
        print(line.strip())
        n = n + 1
  
# writing to file
file1 = open(tmpfile, 'w+')
file1.writelines(lines[n:])
file1.close()
  
os.replace(tmpfile,srcfile)