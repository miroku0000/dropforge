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

def waitingFor(message,sleeptime=30):
	print(message + " begin sleep for " + str(sleeptime))
	time.sleep(sleeptime)
	print(message + " end sleep for " + str(sleeptime))
	
def implicitlyWaitingFor(driver, message, waittime):
	print(message + " begin implictly wait for " + str(waittime))
	driver.implicitly_wait(waittime)
	print(message + " end implicitly wait for " + str(waittime))
	
		

def arg_parser():
	parser = argparse.ArgumentParser(description='Export some csv files from ZIK.')
	parser.add_argument("-u","--username", default=None, required=False)
	parser.add_argument("-p","--password", default=None, required=False)
	parser.add_argument("-minc","--min_competition", default=None, required=False)
	parser.add_argument("-maxc","--max_competition", default=None, required=False)
	parser.add_argument("-mins","--min_sales", default=None, required=False)
	parser.add_argument("-maxs","--max_sales", default=None, required=False)
	parser.add_argument("-n","--numpages", default=10, required=False)
	parser.add_argument("-minsucc","--min_successful_listings", default=None, required=False)
	parser.add_argument("-maxsucc","--max_successful_listings", default=None, required=False)
	parser.add_argument("-skip","--skip_pages", default=None, required=False)
	 

	if len(sys.argv) == 1:
		parser.print_help()
		exit()
	 
	return parser.parse_args()


def getTotalPages(driver):
	try:
		totalpages=driver.execute_script('buttons=$(".paginate_button"); l=buttons.length; return buttons[buttons.length-2].text')
		print("total pages = " + totalpages)
	except:
		print("got error trying to get total pages")
		time.sleep(120)
		totalpages=driver.execute_script('buttons=$(".paginate_button"); l=buttons.length; return buttons[buttons.length-2].text')
		print("total pages = " + totalpages)
		pass
	try:
		 totalpages= int(totalpages)
		 if totalpages:
		 	return totalpages
		 else:
		    return 1
		 end
	except:
		return 1



def getNumberToSkip(totalpages):
	n= round(totalpages/7)
	# weekday will be a number from 0 to 6
	# Do this in reverse order and if these are rotated, then we will never repeat 
	weekday = 6 - datetime.datetime.today().weekday()
	skip = weekday * n
	return skip

def getNumberOfPagesToDownload(totalpages):
	numpages= math.ceil(totalpages/7)

	return numpages

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


try:
	# Log in to ebay
	driver.get("https://www.zikanalytics.com/BulkScanner/Amazon")
	driver.implicitly_wait(10)
	driver.maximize_window()
	driver.implicitly_wait(10)
	try:
		email_address = driver.find_element_by_xpath('//*[@id="Username"]')
		email_address.send_keys(zik_username)
		driver.implicitly_wait(5)
		pw = driver.find_element_by_xpath('//*[@id="Password"]')
		pw.send_keys(password)
		continueButton = driver.find_element_by_xpath('//*[@id="loginForm"]/div[3]/button')
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
		#print(e)
		# It is normal to get this error if you are already logged in
		pass

	#driver.implicitly_wait(1)


	
	#driver.implicitly_wait(10)
	driver.get("https://www.zikanalytics.com/BulkScanner/Amazon")
	driver.implicitly_wait(1)
	try:
		# sort by sucessful listings

		successfulListings= driver.find_element_by_xpath('//*[@id="orderby"]/option[3]')
		#driver.execute_script("arguments[0].click();",successfulListings)
		successfulListings.click()

		if args.min_competition:	
			driver.execute_script('$(".txtminLevel").val("' +str( args.min_competition) + '")')
		if args.max_competition:
			driver.execute_script('$(".txtmaxLevel").val("' + str(args.max_competition) + '")')	
		if args.min_successful_listings:
			driver.execute_script('$(".txtminListings").val("' + str(args.min_successful_listings) +'")')
		if args.max_successful_listings:
			driver.execute_script('$(".txtmaxListings").val("' + str(args.max_successful_listings)+ '")')

		#sales in the last month=8
		if args.min_sales:
			driver.execute_script('$(".txtminsale").val("' + str(args.min_sales) +'")')
		if args.max_sales:
			driver.execute_script('$(".txtmaxsale").val("' + str(args.max_sales)+ '")')

		f = open("..\\data\label.txt", "w")
		
		if args.min_sales:
				minsalesstr=str(args.min_sales)
		else:
				minsalesstr="N"

		if args.max_sales:
				maxsalesstr=str(args.max_sales)
		else:
				maxsalesstr="N"
				
		if args.min_competition:
				mincompstr =str(args.min_competition)
		else:
				mincompstr="N"

		if args.max_competition:
				maxcompstr =str(args.max_competition)
		else:
				maxcompstr="N"
				
		if args.min_successful_listings:
				minsuccstr =str(args.min_successful_listings)
		else:
				minsuccstr="N"

		if args.max_successful_listings:
				maxsuccstr =str(args.max_successful_listings)
		else:
				maxsuccstr="N"

		f.write("zik_sales_" + minsalesstr+"-"+ maxsalesstr+"comp_"+ mincompstr + "-" + maxcompstr + "succ_" +  minsuccstr+ "-" +maxsuccstr)
		f.close()

		search= driver.find_element_by_xpath('//*[@id="ak47btn"]')
		
		driver.execute_script("arguments[0].click();",search)
		waitingFor("search results",120)
		#driver.implicitly_wait(120)
		implicitlyWaitingFor(driver, "search results", 120)
		#try:
		#	driver.execute_script('$(".risky").parent().parent().remove();')
		#except Exception as e:
		#	pass
		waitingFor("totalpages",20)
		#implicitlyWaitingFor(driver,"totalpages", 20)
		totalpages= getTotalPages(driver)
		skippages= getNumberToSkip(totalpages)
		numpages= getNumberOfPagesToDownload(totalpages)
		print("************************** Based on there being " + str(totalpages) + " pages we will skip " + str(skippages) + " then download " + str(numpages) +" pages")

		if skippages:	
			for j in range(int(skippages)):
				#print("skipping a page " + str(j) )
				driver.execute_script("$('.paginate_button.next')[0].click();")
				time.sleep(5)

		driver.execute_script('$(".risky").parent().parent().remove();')

		#driver.execute_script('$(".checkboxexport").prop("checked",true)')
		driver.execute_script('$(".check-label").click()')
		driver.execute_script('$(".check-label").click()')
		#driver.execute_script('$(".risky").parent.parent.find(".checkboxexport).prop("checked",false);')
		time.sleep(2)
		
		foo = driver.execute_script('$(".exportBtnSelected").click()')
		time.sleep(3)
		try:
			numpages= getNumberOfPagesToDownload(totalpages)
			#numpages=int(args.numpages)
		except Exception as e:
			print(e)
			numpages=1
			pass
		
		try:	
			foo=driver.execute_script('if($(".paginate_button.next.disabled").length ==2 ){throw 42; };')
		except Exception as e:
			foo=2
		i=1
		while( foo != 2 and i< numpages): 
			driver.execute_script("$('.paginate_button.next')[0].click()")
			time.sleep(4)			
			try:
				driver.execute_script('$(".risky").parent().parent().remove();')
			except Exception as e:
				pass

			#driver.execute_script('$(".checkboxexport").prop("checked",true)')
			driver.execute_script('$(".check-label").click()')
			driver.execute_script('$(".check-label").click()')
			driver.execute_script('$(".exportBtnSelected").click()')
			time.sleep(3)
			i= i+1
			try:
				foo=driver.execute_script('if($(".paginate_button.next.disabled").length ==2 ){throw 42; };')
			except Exception as e:
				foo=2
			

		#drive
	except Exception as e:
		print(e)
		pass


except Exception as e:
	print(e)
	pass

driver.quit()

# Get the web page this lists all listings with required item specifics

