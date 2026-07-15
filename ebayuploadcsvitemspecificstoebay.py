from selenium import webdriver
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path

from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import glob
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import sys
import wmi
import time
from selenium.webdriver.common.by import By

# Initializing the wmi constructor


def isRunning(s):
    # Iterating through all the running processes
    f = wmi.WMI()
    count = 0
    for process in f.Win32_Process():
        # Displaying the P_ID and P_Name of the process
        if (
            process.CommandLine
            and s in process.CommandLine
            and "python.exe" in process.CommandLine
        ):
            count = count + 1
            print(str(process.ProcessId) + " " + process.CommandLine)
            if count > 1:
                return True
    return False


def logintoebay(driver, ebay_username, ebay_password):
    driver.get(
        "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&srcAppId=3564&ru=https%3A%2F%2Fwww.ebay.com"
    )
    driver.implicitly_wait(5)
    time.sleep(5)
    try:
        # Log in to ebay
        # time.sleep(120)
        email_address = driver.find_element("xpath", '//*[@id="userid"]')
        email_address.send_keys(ebay_username)
        continueButton = driver.find_element("xpath", '//*[@id="signin-continue-btn"]')
        continueButton.click()
    except Exception as e:
        print("Couldn't find username")
        pass
    try:
        driver.implicitly_wait(5)
        password = driver.find_element("xpath", '//*[@id="pass"]')
        password.send_keys(ebay_password)
        signInButton = driver.find_element("xpath", '//*[@id="sgnBt"]')
        signInButton.click()
        driver.implicitly_wait(5)
    except Exception as e:
        time.sleep(30)
        # print(e)
        # reccomended_item_specifics = driver.find_element("xpath",'/html/body/div[6]/div[2]/div[1]/div/div[3]/div/div[2]/div[2]/div/section/span[1]/button')
        pass


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

if isRunning("D:\\zikprocessor\\src\\ebayuploadcsvitemspecificstoebay.py"):
    print("ebayuploadcsvitemspecificstoebay.py is already running")
    exit(1)

import config
ebay_username = config.EBAY_USER
ebay_password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\"
    + username
    + "\\AppData\\Local\\Google\\Chrome\\User Data\\ebayisupload"
)
if len(sys.argv) > 1:
    userProfile = userProfile + sys.argv[1]
    print("***********************")
    print(userProfile)
    print("***********************")
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])

try:
    userProfile = (
        "C:\\Users\\"
        + username
        + "\\AppData\\Local\\Google\\Chrome\\User Data\\ebayisupload1"
    )
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("user-data-dir={}".format(userProfile))
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)

except Exception as e:
    print("***********************")
    print(userProfile)
    print("***********************")
    driver = webdriver.Chrome(options=options)


sleeptime = 1

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)

logintoebay(driver, ebay_username, ebay_password)
print("should be logged in")


driver.get(
    "https://www.ebay.com/sh/lst/active?pill_status=soonToBeRequired&action=search"
)
driver.implicitly_wait(5)
time.sleep(5)
print("Running exceltocsv.py")
os.system("exceltocsv.py")
files = glob.glob("D:\\zikprocessor\\data\\ebayitemspecifics\\*.csv")
if "D:\\zikprocessor\\data\\ebayitemspecifics\\upload.csv" in files:
    try:
        files.remove("D:\\zikprocessor\\data\\ebayitemspecifics\\upload.csv")
    except Exception as e:
        pass
print(str(len(files)))
while len(files) > 0:
    l = len(files)
    i = 1
    for filename in files:
        try:
            os.remove("D:\\zikprocessor\\data\\ebayitemspecifics\\upload.csv")
        except Exception as e:
            pass
        print(str(i) + " of " + str(l) + " files :" + filename)
        i = i + 1
        try:
            if "upload.csv" not in filename:
                os.rename(
                    filename, "D:\\zikprocessor\\data\\ebayitemspecifics\\upload.csv"
                )
                print("Getting Reccomended Item Specifics Page")
                driver.get(
                    "https://www.ebay.com/sh/lst/active?pill_status=soonToBeRequired&action=search"
                )
                time.sleep(3)
                print("Clicking upload")
                driver.execute_script("$(\"Button:contains('Upload')\").click()")
                time.sleep(3)
                b = driver.execute_script(
                    "return $(\"Button:contains('Choose')\").length"
                )
                while b < 1:
                    time.sleep(1)
                    b = driver.execute_script(
                        "return $(\"Button:contains('Choose')\").length"
                    )
                print("Clicking choose file")

                # driver.execute_script('$(".btn.btn--primary.click()')
                # b=driver.find_element("xpath","//*[@id=\"s0-1-1-18-3-7-37-16-2-@download-upload-layer-@uploadReportComponent-_wbind\"]/div[2]/div[2]/div[4]/button[2]")
                # b=driver.execute_script('$("Button:contains(\'Choose\')")[0].click()')
                b = driver.find_element(By.XPATH, '//button[text()="Choose file"]')
                b.click()
                print("Choose File was clicked")
                time.sleep(5)
                # b=driver.execute_script('return $("Button:contains(\'Choose\')").length')
                # print(b)
                # if b:
                # 	print("trying again...")
                # 	driver.find_element("xpath",'//*[@id="s0-0-4-15-61-24-2-download-upload-layer-uploadReportComponent"]/div[2]/div[2]/div[4]/button[2]').click()
                # 	#driver.execute_script("arguments[0].click();", btn);
                print("running script to pick file:")
                os.system("start D:\\zikprocessor\\src\\uploadebaycsv.au3")
                print("Sleeping for 5 seconds")
                time.sleep(15)
                # print("killing uploadebaycsv.au3...")
                # os.system("taskkill /im uploadebaycsv.au3 /f")
                isprocessing = driver.execute_script(
                    "return $(\"body:contains('Upload in progress')\").length"
                )
                downloadlink = driver.execute_script(
                    "return $(\"a:contains('Download results')\").length"
                )

                while isprocessing and not downloadlink:
                    time.sleep(1)
                    print("waiting for processing to be complete")
                    isprocessing = driver.execute_script(
                        "return $(\"body:contains('Upload in progress'):visible\").length"
                    )
                    print(str(isprocessing))
                    downloadlink = driver.execute_script(
                        "return $(\"a:contains('Download results')\").length"
                    )
                    print(str(downloadlink))
        except Exception as e:
            print(e)
            pass
    os.system("exceltocsv.py")
    files = glob.glob("D:\\zikprocessor\\data\\ebayitemspecifics\\*.csv")
