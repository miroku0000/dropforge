import os
import json
import time
import math
import sys
import csv
import glob
import os

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


try:
	f =open("..\\data\\label.txt", "r")
	label=(f.read())
	with open("..\\data\\uploads\\" + label + ".csv", 'w') as f:
		print('BuyId,Title,Price', file=f)  # Python 3.x
		banned=getVero()
		bannedWords=["Obagi","Blue BluBlocker", "SpeedTalk","Blunt","Yakima","Pendleton","SkinMedica","Vixen"]
		for fn in glob.glob("C:\\Users\\mirok\\Downloads\\AmazonExcel*"):
			try:
				input_file = csv.DictReader(open(fn))
				for row in input_file:
					if row["ASIN"].strip() not in banned:
						found=False
						for word in bannedWords:
							if word in row["Title"]: 
								found=True
						if not found:
							print(row["ASIN"].strip()+",,", file=f)
			except Exception as e:
				#print(e)
				pass

except Exception as e:
	print(e)


