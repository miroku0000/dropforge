import os
import glob

username = os.getenv("USERNAME")

for fn in glob.glob("C:\\Users\\" + username +"\\Downloads\\zik*.csv"):
	os.remove(fn)
	#print("skipping remove" +str(fn))

