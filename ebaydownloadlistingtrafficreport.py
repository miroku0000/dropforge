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


import config
ebay_username = config.EBAY_USER
ebay_password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\"
    + username
    + "\\AppData\\Local\\Google\\Chrome\\User Data\\itemspecifics"
)
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(options=options)
sleeptime = 1

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)

driver.get("https://www.ebay.com/sh/lst/active")
driver.implicitly_wait(5)


try:
    # Log in to ebay
    # time.sleep(120)
    email_address = driver.find_element(
        "xpath", "/html/body/div[2]/div[2]/div[1]/form[1]/div[1]/div/div/input"
    )
    email_address.send_keys(ebay_username)
    continueButton = driver.find_element(
        "xpath", "/html/body/div[2]/div[2]/div[1]/form[1]/div[1]/div/button"
    )
    continueButton.click()
    driver.implicitly_wait(5)
    password = driver.find_element("xpath", '//*[@id="pass"]')
    password.send_keys(ebay_password)
    signInButton = driver.find_element("xpath", '//*[@id="sgnBt"]')
    signInButton.click()
    driver.implicitly_wait(5)
except Exception as e:
    # print(e)
    # reccomended_item_specifics = driver.find_element("xpath",'/html/body/div[6]/div[2]/div[1]/div/div[3]/div/div[2]/div[2]/div/section/span[1]/button')
    pass
    print("Getting performance page")
    driver.get("https://www.ebay.com/sh/performance/traffic")
    time.sleep(5)
    print("Downloading Traffic report")
    driver.execute_script('$(".download-link-active").click()')
    time.sleep(20)
    print("Clicking Download link")
    driver.execute_script("$('a:contains(\"download\")').click()")

    print("Link was clicked")
    time.sleep(30)
