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


import sys
import argparse


def arg_parser():
    parser = argparse.ArgumentParser(description="Export some csv files from ZIK.")
    parser.add_argument("-u", "--username", default=None, required=False)
    parser.add_argument("-p", "--password", default=None, required=False)
    parser.add_argument("-n", "--numlistingstoend", default="200", required=False)

    if len(sys.argv) == 1:
        parser.print_help()
        exit()

    return parser.parse_args()


import config
autods_username = config.EBAY_USER
password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\opti"
)
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
driver = webdriver.Chrome(options=options)

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)


args = arg_parser()

try:
    # Log in to AUTODS
    driver.get(
        "http://app.autods.com/accounts/login/?next=/active_listings/%3Fln%3D200"
    )
    driver.implicitly_wait(10)
    driver.maximize_window()
    # try:
    # 	email_address = driver.find_element_by_xpath('//*[@id="popup-login-modal"]/div/input')
    # 	if email_address:
    # 		email_address.send_keys(autods_username)
    # 		continueButton = driver.find_element_by_xpath('//*[@id="popup-login-modal"]/button')
    # 		continueButton.click()
    # 		driver.implicitly_wait(5)
    # except Exception as e:
    # 	pass
    try:
        email_address = driver.find_element_by_xpath('//*[@id="email"]')
        email_address.click()
        email_address.send_keys(autods_username)
        driver.implicitly_wait(5)
        pw = driver.find_element_by_xpath('//*[@id="password"]')
        pw.click()
        pw.send_keys(password)
        continueButton = driver.find_element_by_xpath(
            '//*[@id="form_login"]/div[5]/button'
        )
        # 	continueButton.click()
        driver.execute_script("arguments[0].click();", continueButton)
        driver.implicitly_wait(5)
    except Exception as e:
        pass

    # Go To Active Listings page
    # driver.get("http://app.autods.com/active_listings/?ln=200")
    # driver.implicitly_wait(5)
    # time.sleep(5)
    filterButton = driver.find_element_by_xpath('//*[@id="filter_table"]')
    # filterButton.click()im
    driver.execute_script("arguments[0].click();", filterButton)

    driver.implicitly_wait(5)
    time.sleep(5)

    fromInput = driver.find_element_by_xpath('//*[@id="sold_from"]')
    fromInput.click()
    fromInput.send_keys("0")
    toInput = driver.find_element_by_xpath('//*[@id="sold_to"]')
    toInput.click()
    toInput.send_keys("0")
    filterButton = driver.find_element_by_xpath(
        "/html/body/div[3]/div[2]/div[15]/div/div/div[3]/button[2]"
    )

    filterButton.click()

    # driver.execute_script('$("button.btn.btn-info.txn_filter_button").click()')
    # driver.execute_script("arguments[0].click();",filterButton)
    time.sleep(5)
    print("finding daysWithoutSales")
    daysWithoutSales = driver.find_element_by_xpath(
        '//*[@id="products_table"]/thead/tr/th[18]/label'
    )
    driver.execute_script("arguments[0].click();", daysWithoutSales)
    time.sleep(1)
    daysWithoutSales = driver.find_element_by_xpath(
        '//*[@id="products_table"]/thead/tr/th[18]/label'
    )
    driver.execute_script("arguments[0].click();", daysWithoutSales)
    time.sleep(10)

    if args.numlistingstoend == "200":
        twohundred = driver.find_element_by_xpath(
            '//*[@id="products_table_length"]/label/select/option[5]'
        )
        # driver.execute_script("arguments[0].click();",twohundred)
        twohundred.click()
    if args.numlistingstoend == "500":
        fivehundred = driver.find_element_by_xpath(
            '//*[@id="products_table_length"]/label/select/option[8]'
        )
        # driver.execute_script("arguments[0].click();",fivehundred)
        fivehundred.click()
    if args.numlistingstoend == "100":
        onehundred = driver.find_element_by_xpath(
            '//*[@id="products_table_length"]/label/select/option[4]'
        )
        # driver.execute_script("arguments[0].click();",onehundred)
        onehundred.click()

    all = driver.find_element_by_xpath('//*[@id="checkbox_select_all"]')
    driver.execute_script("arguments[0].click();", all)

    bulkChange = driver.find_element_by_xpath('//*[@id="change_selected"]')

    bulkChange.click()
    driver.execute_script("arguments[0].click();", bulkChange)
    time.sleep(1)
    endListings = driver.find_element_by_xpath('//*[@id="bulk_end_listing_button"]')
    # endListings.click()
    driver.execute_script("arguments[0].click();", endListings)
    time.sleep(2)
    try:
        print("confirming")
        driver.execute_script("$('.confirm').click();")
        print("confirming complete")
        # exit(0)
        # letmeendtheselistings=driver.find_element_by_xpath('/html/body/div[15]/div[7]/div/button')
        # letmeendtheselistings.click()
    except Exception as e:
        print(e)
        exit(0)
        pass


except Exception as e:
    print(e)


time.sleep(90)

driver.quit()
