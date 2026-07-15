import os
import glob

for fn in glob.glob("C:\\Users\\mirok\\Downloads\\AmazonExcel*"):
	os.remove(fn)
	#vprint("skipping remove" +str(fn))

