from selenium import webdriver
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import math
import sys
import argparse
import datetime
import glob

def waitingFor(message,sleeptime=30):
	print(message + " begin sleep for " + str(sleeptime))
	time.sleep(sleeptime)
	print(message + " end sleep for " + str(sleeptime))
	
def implicitlyWaitingFor(driver, message, waittime):
	print(message + " begin implictly wait for " + str(waittime))
	driver.implicitly_wait(waittime)
	print(message + " end implicitly wait for " + str(waittime))

def killoldestscan(driver):
	try:
		driver.execute_script('$(".fas.fa-trash")[$(".fas.fa-trash").length-1].click()')
	except Exception as e:
		pass



def arg_parser():
	parser = argparse.ArgumentParser(description='Export some csv files from ZIK.')
	parser.add_argument("-u","--username", default=None, required=False)
	parser.add_argument("-p","--password", default=None, required=False)
	parser.add_argument("-minc","--min_competition", default=None, required=False)
	parser.add_argument("-maxc","--max_competition", default=None, required=False)
	parser.add_argument("-mins","--min_sales", default=None, required=False)
	parser.add_argument("-maxs","--max_sales", default=None, required=False)
	parser.add_argument("-minroi","--min_roi", default=None, required=False)
	parser.add_argument("-maxroi","--max_roi", default=None, required=False)
	parser.add_argument("-minsucc","--min_sucessRate", default=None, required=False)
	parser.add_argument("-maxsucc","--max_sucessRate", default=None, required=False)
	parser.add_argument("-'minsellThrough'","--min_sellThrough", default=None, required=False)
	parser.add_argument("-'maxsellThrough'","--max_sellThrough", default=None, required=False)
	parser.add_argument("-numProducts","--numberOfProducts", default=None, required=False)
	parser.add_argument("-bsrFrom","--bsrFrom", default=None, required=False)
	parser.add_argument("-bsrTo","--bsrTo", default=None, required=False)

				

	if len(sys.argv) == 1:
		parser.print_help()
		exit()
	 
	return parser.parse_args()


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

args=arg_parser()
print(str(args))

import config
zik_username =config.EBAY_USER
password =config.EBAY_PASS

user_agent = 'Chrome/73.0.3683.86'
username = os.getenv("USERNAME")
userProfile = "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\zikexport"
options = webdriver.ChromeOptions()
options.add_experimental_option('excludeSwitches', ['enable-logging'])
options.add_argument(f'user-agent={user_agent}')
options.add_argument("user-data-dir={}".format(userProfile))
driver = webdriver.Chrome(options=options)

#driver = webdriver.Remote(
 #  command_executor='http://127.0.0.1:4444/wd/hub',
  # desired_capabilities=DesiredCapabilities.CHROME)


# Log in to ebay
driver.get("https://www.zikanalytics.com/Tr/Autopilot")
driver.implicitly_wait(10)
driver.maximize_window()
driver.implicitly_wait(10)

def is_text_present(driver, text):
	return str(text) in driver.page_source
try:
	email_address = driver.find_element("xpath",'//*[@id="Username"]')
	email_address.send_keys(zik_username)
	driver.implicitly_wait(5)
	pw = driver.find_element("xpath",'//*[@id="Password"]')
	pw.send_keys(password)
	continueButton = driver.find_element("xpath",'//*[@id="loginForm"]/div[3]/button')
	#continueButton.click()
	driver.execute_script("arguments[0].click();",continueButton)
	continueButton
	#driver.implicitly_wait(5)
	waitingFor("login",10)
	#implicitlyWaitingFor(driver,"login", 10)
	print("should be logged in now...")
	time.sleep(5)
	#driver.get("https://www.zikanalytics.com/BulkScanner/Amazon")
except Exception as e:
	print(e)
	pass

try:

	
	#driver.implicitly_wait(10)
	driver.get("https://www.zikanalytics.com/Tr/Autopilot")
	driver.implicitly_wait(1)
	time.sleep(5)
	#print("killing oldest scan")
	#killoldestscan(driver)
	time.sleep(1)
	print("Pressing open new scan button")	
	# Press new scan button
	#driver.execute_script("$('#openNewScan').click();")
	if args.min_competition:	
		driver.execute_script('$("#Competitionfrom").val("' +str( args.min_competition) + '")')
	if args.max_competition:
		driver.execute_script('$("#Competition").val("' + str(args.max_competition) + '")')	
	#sales in the last month=8
	if args.min_sales:
		driver.execute_script('$("#salesfrom").val("' + str(args.min_sales) +'")')
	else:
		driver.execute_script('$("#salesfrom").val("' + str("") +'")')
	if args.max_sales:
		driver.execute_script('$("#sales").val("' + str(args.max_sales)+ '")')
	if args.min_roi:
		driver.execute_script('$("#roifrom").val("' + str(args.min_roi)+ '")')
	else:
		driver.execute_script('$("#roifrom").val("")')		
	if args.max_roi:
		driver.execute_script('$("#roi").val("' + str(args.max_roi)+ '")')
	if args.min_sellThrough:
		driver.execute_script('$("#sellThroughfrom").val("' + str(args.min_sellThrough)+ '")')
	if args.max_sellThrough:
		driver.execute_script('$("#sellThrough").val("' + str(args.max_sellThrough)+ '")')
	if args.min_sucessRate:
		driver.execute_script('$("#sucessRatefrom").val("' + str(args.min_sucessRate)+ '")')
	if args.max_sucessRate:
		driver.execute_script('$("#sucessRate").val("' + str(args.max_sucessRate)+ '")')
	if args.bsrFrom:
		driver.execute_script('$("#bsrFrom").val("' + str(args.bsrFrom)+ '")')
	if args.bsrTo:
		driver.execute_script('$("#bsrTo").val("' + str(args.bsrTo)+ '")')

	if args.numberOfProducts:
		driver.execute_script('$("#numberOfProducts").val("' + str(args.numberOfProducts)+ '")')
	driver.execute_script('$("#Similar").prop("checked", true);')
	print("should be done filling in values")
	time.sleep(1)
	driver.execute_script('$("#name").val("foo")')
	driver.execute_script("$('.trScanStart').click()")
	time.sleep(10)
	while driver.execute_script('return $(".progress-bar-warning").length;'):
		print("Waiting for completion of zik scan")
		driver.get("https://www.zikanalytics.com/Tr/Autopilot")
		time.sleep(10)
	print("Zik Scan complete... Exporting all items")
	driver.execute_script("$('.touchable')[0].click()")
	time.sleep(2)
	driver.execute_script('$("span:contains(\'Export all items\')")[0].click()')
	time.sleep(1)
	driver.execute_script("$('#exportverowords').click()")
	driver.execute_script("$('#exportriskyWords').click()")
	driver.execute_script("$('#exportListings').click()")
	while len(glob.glob("C:\\Users\\" + username + "\\Downloads\\ZikAnalytics*.csv"))==0:
		print("Wating for Download of Zik Results file")
		time.sleep(10)
	print("Detected Zik file. Sleeping a bit more for download to complete")
	time.sleep(5)
	# -min_roi 0.19 -min_sales 3
except Exception as e:
	print(e)


