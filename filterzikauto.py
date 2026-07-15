from selenium import webdriver
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import math
import sys
import csv
import glob
import os
import codecs

# Install the chromedriver from:
# https://chromedriver.chromium.org/downloads
# Get the version that matches the build of chrome you are using.
# You can find this in chrome by going to Help->About Google Chrome

# After you have installed your driver, 
# make sure to add the driver to your path
# To setup the path to the chrome driver run the following command from an admin command prompt:
# setx /m path "%path%;C:\WebDriver\bin\"
# Asssuming chromedriver is installed in c:\WebDriver\bin
# (Adjust the path to wherever you installed it)

# For other operating systems besides Windows, see https://www.selenium.dev/documentation/en/webdriver/driver_requirements/

outhash={}

bannedWords=["Obagi","Blue BluBlocker", "SpeedTalk","Blunt","Yakima","Pendleton","SkinMedica","Vixen"]
 
 
def getVero():
	text_file = open("../data/vero.csv", "r")
	lines = text_file.read().split('\n')
	ret=[]
	for line in lines:
		line=line.replace("ï»¿","")
		if line:
			ret.append(line)
	text_file.close()
	return ret

def fix_nulls(s):
    for line in s:
        yield line.replace('\0', ' ')


def filterFile(fn,outhash, bannedWords):
	input_file = csv.DictReader(fix_nulls(codecs.open(fn, 'rU', 'utf-8')))
	
	for row in input_file:
		if "ASIN" in row:
			ASIN="ASIN"
		else:
			ASIN="BuyId"

		if row[ASIN].strip() not in banned:
			found=False
			for word in bannedWords:
				for key in row:
			 		if word in row[key]: 
			 			found=True
			if not found:
				outhash[(row[ASIN].strip())]=1
	return outhash

banned=getVero()

#
for fn in glob.glob("C:\\Users\\mirok\\Downloads\\AmazonExcel*"):
	filterFile(fn,outhash, bannedWords)
for fn in glob.glob("C:\\Users\\mirok\\Downloads\\ZikAnalytics*"):
	filterFile(fn,outhash, bannedWords)

for fn in glob.glob("D:\\zikprocessor\\data\\uploads\\*.csv"):
	filterFile(fn,outhash, bannedWords)
for h in outhash:
	print(h)

