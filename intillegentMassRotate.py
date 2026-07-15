

import datetime
import os
import subprocess
import time


def removeallzikdownloads():
	#print("not removing downlaods")
	r= subprocess.run(["python", "removeallzikdownloads.py"])

def export_minsuc(minsucc=0, n=100, skip=0):	
	print("skip = " + str(skip))
	export = subprocess.run(["python", "zikexport.py",  "-minsucc", str(minsucc), "-n", str(n),  "-skip", str(skip)])

def export_minsuc_and_minsales(minsucc=0, minsales=0, n=100, skip=0):
	print("skip = " + str(skip))
	export = subprocess.run(["python", "zikexport.py", "-mins", str(minsales), "-minsucc", str(minsucc), "-n", str(n),  "-skip", str(skip)])


def export_minsuc_and_maxcomp(minsucc=100, maxcomp=10, n=100, skip=0):
	print("skip = " + str(skip))
	export = subprocess.run(["python", "zikexport.py", "-maxc", str(maxcomp), "-minsucc", str(minsucc), "-n", str(n),  "-skip", str(skip)])

def export_minsales_and_maxcomp(mins=2, maxcomp=10, n=100, skip=0):
	print("skip = " + str(skip))
	export = subprocess.run(["python", "zikexport.py", "-maxc", str(maxcomp), "-mins", str(mins), "-n", str(n),  "-skip", str(skip)])

def export_sales(mins=0, maxs=10000, n=100, skip=0):
	print("skip = " + str(skip))
	export = subprocess.run(["python", "zikexport.py",  "-mins", str(mins), "-maxs", str(maxs),  "-n", str(n),  "-skip", str(skip)])


def bulkupload():
	bulkupload= subprocess.run(["python", "preparebulkupload.py"])

def fetch_and_upload_by_sales(mins=5, maxs=10000, expected_numpages=10):
	print("fetch_and_upload_by_sales(" + str(mins) +", " +str(maxs) + " , " + str(expected_numpages)) 
	n= round(expected_numpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	export_sales(mins, maxs, n, skip)
	#bulkupload()
	#removeallzikdownloads()


def fetch_and_upload_by_success_rate_And_sales(minsucc=0, minsales=0, expected_numpages=24):
	print("fetch_and_upload_by_success_rate_And_sales(" + str(minsucc) +", " +str(minsales) + " , " + str(expected_numpages)) 
	n= round(expected_numpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	print("skip = " + str(skip))
	export_minsuc_and_minsales(minsucc, minsales, n, skip)
	#bulkupload()
	#removeallzikdownloads()

def fetch_and_upload_by_success_rate_And_maxcomp(minsucc=100, maxcomp=10, expected_numpages=19):
	print("fetch_and_upload_by_success_rate_And_maxcomp(" + str(minsucc) +", " +str(maxcomp) + " , " + str(expected_numpages)) 
	n= round(expected_numpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	print("skip = " + str(skip))
	export_minsuc_and_maxcomp(minsucc, maxcomp, n, skip)
	#bulkupload()
	#removeallzikdownloads()

def fetch_and_upload_by_min_sales_And_maxcomp(mins=2, maxcomp=10, expected_numpages=32):
	print("fetch_and_upload_by_min_sales_And_maxcomp(" + str(mins) +", " +str(maxcomp) + " , " + str(expected_numpages)) 
	n= round(expected_numpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	print("skip = " + str(skip))
	export_minsales_and_maxcomp(mins, maxcomp, n, skip)
	#bulkupload()
	#removeallzikdownloads()


def fetch_and_upload_by_success_rate(minsuc=5, expected_numpages=10): 
	print("fetch_and_upload_by_success_rate(" + str(minsuc) + ", "  + str(expected_numpages)) 
	n= round(expected_numpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	export_minsuc(minsuc, n, skip)
	#bulkupload()
	#removeallzikdownloads()

removeallzikdownloads()
#fetch_and_upload_by_success_rate(90)
fetch_and_upload_by_success_rate_And_maxcomp(90, 10) # was 90 10 with 5828 pages of results
#fetch_and_upload_by_min_sales_And_maxcomp(5, 30)

#fetch_and_upload_by_success_rate_And_maxcomp(80, 30)

#fetch_and_upload_by_success_rate_And_sales(50, 3)


#fetch_and_upload_by_sales(8, 10000)

#fetch_and_upload_by_sales(3, 10000)

#fetch_and_upload_by_success_rate(100)

#fetch_and_upload_by_sales(8, 1000)
#fetch_and_upload_by_sales(9, 1000)
#fetch_and_upload_by_success_rate(90, 15)
#fetch_and_upload_by_success_rate(80, 15)
#fetch_and_upload_by_success_rate(70, 16)

#
#fetch_and_upload_by_sales(9, 9, 32)
#fetch_and_upload_by_sales(7, 7, 49)
#fetch_and_upload_by_sales(6, 6, 63)
#fetch_and_upload_by_sales(5, 5, 82)
#fetch_and_upload_by_success_rate(50, 730)





