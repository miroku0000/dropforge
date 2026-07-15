from selenium import webdriver
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path

from selenium import webdriver
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import math
import sys
import glob
import os
import shutil
import pyautogui
import datetime
import os.path
from os import path

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


nosort = False
reverse = False
import config
optiseller_username = config.EBAY_USER
password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
skip = 0
maxlink = 1
reverse = False


processnum = 1
numprocesses = 1
# skip is the percentage of listings that need updated to skip before straring in this process
skip = ((processnum - 1) * 1.0) / (1.0 * numprocesses)
# maxlink is the percentage of the last link to process in this process
maxlink = ((processnum) * 1.0) / (1.0 * numprocesses)
userProfile = (
    "C:\\Users\\"
    + username
    + "\\AppData\\Local\\Google\\Chrome\\User Data\\opti"
    + str(processnum)
)
debugstring = "debug " + str(processnum) + ": "
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(options=options)

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)


def is_text_present(text):
    return str(text) in driver.page_source


def needToLogin():
    if "auth" in driver.current_url:
        return True
    r = is_text_present("SIGN IN TO CONTINUE")
    print(debugstring + "need to login: " + str(r))
    return r


def login():
    try:
        print(debugstring + "login called")
        # Log in
        driver.get(
            "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
        )
        # driver.implicitly_wait(60)
        time.sleep(15)
        driver.maximize_window()
        # driver.implicitly_wait(30)
        email_address = driver.find_element("xpath", '//*[@id="signInName"]')
        if email_address:
            email_address.send_keys(optiseller_username)
            driver.implicitly_wait(5)
            pw = driver.find_element("xpath", '//*[@id="password"]')
            pw.send_keys(password)
            continueButton = driver.find_element("xpath", '//*[@id="next"]')
            continueButton.click()
            time.sleep(10)
            driver.get(
                "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
            )
    except Exception as e:
        print(debugstring)
        print(e)
        pass
    print(debugstring + "Done with login()")


driver.get(
    "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
)
time.sleep(2)
if needToLogin():
    print(debugstring + "need to login")
    login()
else:
    print(debugstring + "skipping logging in")

print(debugstring + "Done logging in Getting page")
time.sleep(2)
try:
    driver.get(
        "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
    )
except Exception as e:
    print(debugstring)
    print(e)
    pass
print(debugstring + "Got page")
time.sleep(5)
print(debugstring + "finished sleeping 5")
loopsleeptime = 1
maxloopsleeptime = 30
while (
    not driver.current_url
    or driver.current_url
    == "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
):
    driver.get(
        "https://app.optiseller.com/SubscribedServices?serviceTypeId=47&serviceLevelId=33&storeId=73830"
    )
    time.sleep(5)
    try:
        text = "Downloading Listings..."
        textonpage = ""
        try:
            textonpage = driver.find_element(
                "xpath", "//*[contains(text(),'" + text + "')]"
            )
        except Exception as e:
            pass
        print(debugstring + "tried finding texton page")
        if not textonpage:
            print(debugstring + "Trying to find viewReport")
            viewReport = driver.find_element(
                "xpath", "/html/body/main/table/tbody/tr[1]/td[3]/a"
            )
            if not viewReport:
                print(debugstring + "View Report not found")
            else:
                print(debugstring + "Clicking View Report")
                viewReport.click()
                time.sleep(10)
        else:
            print(debugstring + text + " found on page")
    except Exception as e:
        print(e)
        pass
    print(debugstring + "sleeping between loops")
    time.sleep(loopsleeptime)
    loopsleeptime = loopsleeptime * 2
    if loopsleeptime > maxloopsleeptime:
        loopsleeptime = maxloopsleeptime
print(debugstring + "driver.current_url=" + driver.current_url)

driver.execute_script("$('#FileSelected option:eq(1)').prop('selected', true)")
time.sleep(1)
driver.execute_script('$("#DownloadFileButton").click()')
time.sleep(5 * 30)
