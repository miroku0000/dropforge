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
import csv
import glob
import os

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
autods_username = config.EBAY_USER
password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\auto1"
)
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])
driver = webdriver.Chrome(options=options)

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)


def getVero():
    text_file = open("../data/vero.csv", "r")
    lines = text_file.read().split("\n")
    ret = []
    for line in lines:
        line = line.replace("ï»¿", "")
        if line:
            ret.append(line)
    text_file.close()
    return ret


try:
    # Log in to AUTODS
    driver.get("http://app.autods.com/uploader/")
    driver.implicitly_wait(1)
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
        print("sent username")

        driver.implicitly_wait(5)
        pw = driver.find_element_by_xpath('//*[@id="password"]')
        # pw.click()
        print("sending password")
        pw.send_keys(password)

        print("continuing")
        continueButton = driver.find_element_by_xpath(
            '//*[@id="form_login"]/div[5]/button'
        )
        # 	continueButton.click()
        driver.execute_script("arguments[0].click();", continueButton)
        driver.implicitly_wait(5)
    except Exception as e:
        print(e)
        pass

    # time.sleep(60)
    # Go To uploads page

    bulkUpload = driver.find_element_by_xpath('//*[@id="bulk_upload_tab"]/a')
    bulkUpload.click()

    print("finding tag")

    tagInput = driver.find_element_by_xpath('//*[@id="bulk_upload_tag-selectized"]')
    tagInput.click()

    # driver.execute_script("arguments[0].click();",tagInput)
    f = open("..\\data\label.txt", "r")
    label = f.read()
    tagInput.send_keys(label + "\n")
    time.sleep(1)
    driver.execute_script(
        '$("#bulk_upload_upload_variations").prop( "checked", true );'
    )
    driver.execute_script(
        '$("#bulk_upload_set_watermark_on_all_pictures").prop( "checked", true );'
    )
    print("label was set to " + label)

    products = driver.find_element_by_xpath('//*[@id="upload_products_ids"]')
    products.click()

    banned = getVero()
    bannedWords = [
        "Obagi",
        "Blue BluBlocker",
        "SpeedTalk",
        "Blunt",
        "Yakima",
        "Pendleton",
        "SkinMedica",
        "Vixen",
    ]
    for fn in glob.glob("C:\\Users\\mirok\\Downloads\\AmazonExcel*"):
        try:
            input_file = csv.DictReader(open(fn))
            for row in input_file:
                if row["ASIN"].strip() not in banned:
                    found = False
                    for word in bannedWords:
                        if word in row["Title"]:
                            found = True
                    if not found:
                        products.send_keys(row["ASIN"].strip() + "\n")
        except Exception as e:
            # print(e)
            pass

    time.sleep(2)

    # driver.execute_script('$("#bulk_upload_upload_variations").prop( "checked", true );')
    # driver.execute_script('$("#bulk_upload_set_watermark_on_all_pictures").prop( "checked", true );')

    print("the boxes should be checked now")
    ebayus = driver.find_element_by_xpath('//*[@id="bulk_selling_site"]/option[1]')
    ebayus.click()
    # couponsInput = driver.find_element_by_xpath('//*[@id="slider_div4_numbers_input"]')
    # #filterButton.click()
    # couponsInput.click() q
    # couponsInput.send_keys("200") # (becomes 200)

    # uploadButton=driver.find_element_by_xpath('//*[@id="uploader_form"]/button')
    # driver.execute_script("arguments[0].click();",uploadButton)

    # taginput= driver.find_element_by_xpath('//*[@id="bulk_upload_tag-selectized"]')
    # taginput.click()
    # taginput.send_keys("amcoupman\n")

    uploadButton = driver.find_element_by_xpath(
        '//*[@id="bulk_upload_panel"]/div[2]/div/button[1]'
    )
    driver.execute_script("arguments[0].click();", uploadButton)
    time.sleep(2)
    driver.execute_script("$('.confirm').click();")
    print("upload initiated.... waiting to quit")
    time.sleep(30)
    driver.quit()


except Exception as e:
    print(e)
    driver.quit()
