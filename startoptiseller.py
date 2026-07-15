from selenium import webdriver
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import math

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




reverse = False

import config
optiseller_username =config.EBAY_USER
password =config.EBAY_PASS

user_agent = 'Chrome/73.0.3683.86'
username = os.getenv("USERNAME")
userProfile = "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\opti"
options = webdriver.ChromeOptions()
options.add_argument(f'user-agent={user_agent}')	            
options.add_argument("user-data-dir={}".format(userProfile))
try:
	driver = webdriver.Chrome(options=options)
except Exception as e:
	userProfile = "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\opti2"
	options = webdriver.ChromeOptions()
	options.add_argument(f'user-agent={user_agent}')
	options.add_argument("user-data-dir={}".format(userProfile))
	driver = webdriver.Chrome(options=options)
	reverse = True
	pass
#driver = webdriver.Remote(
 #  command_executor='http://127.0.0.1:4444/wd/hub',
  # desired_capabilities=DesiredCapabilities.CHROME)


try:
	# Log in to optisller
	driver.get("https://app.optiseller.com/DataSourceHome")
	#driver.implicitly_wait(60)
	driver.maximize_window()
	#driver.implicitly_wait(30)
	time.sleep(20)
	email_address = driver.find_element("xpath",'//*[@id="signInName"]')
	if not email_address:
		print("email_address not found")
		exit
	email_address.send_keys(optiseller_username)
	driver.implicitly_wait(5)
	pw = driver.find_element("xpath",'//*[@id="password"]')
	pw.send_keys(password)
	continueButton = driver.find_element("xpath",'//*[@id="next"]')
	continueButton.click()
	driver.implicitly_wait(1)
	time.sleep(20)
	driver.get("https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830")
	driver.implicitly_wait(1)
	print("driver.current_url=" +driver.current_url)
except:
	print("got error")
	exit
	pass

url="https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
while not driver.current_url or driver.current_url != url:
	driver.implicitly_wait(10)
	print("getting "+ url )
	driver.get(url)
try:
	time.sleep(5)
	print("clicking Run service again buton...")
	try:
		driver.execute_script('$("a:contains(\'Run service\')")[0].click()')
		
	except Exception as e:
		print("couldn'click run service again... Trying start")
		driver.execute_script('$("a:contains(\'Start\')")[0].click()')
		pass
	time.sleep(10)
	print("Submitting form")
	driver.execute_script('$("form").submit()')
		
except Exception as e:
	print("Got exception")
	print(e)
	pass
print("driver.current_url="+driver.current_url)

time.sleep(5)
driver.quit()







