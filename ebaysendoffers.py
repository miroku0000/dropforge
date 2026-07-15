from selenium import webdriver
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path

import os
import time
import undetected_chromedriver as uc  # Importing undetected_chromedriver instead of selenium's webdriver
from selenium.webdriver.common.by import By
from nodriver import *

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


async def send_keys_slowly(element, text, delay=0.1):
    for character in text:
        await element.send_keys(character)
        time.sleep(delay)


async def logintoebay(driver, ebay_username, ebay_password):
    await driver.get(
        "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&srcAppId=3564&ru=https%3A%2F%2Fwww.ebay.com"
    )
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
        password = driver.find_element("xpath", '//*[@id="pass"]')
        password.send_keys(ebay_password)
        signInButton = driver.find_element("xpath", '//*[@id="sgnBt"]')
        signInButton.click()
    except Exception as e:
        time.sleep(30)
        # print(e)
        # reccomended_item_specifics = driver.find_element("xpath",'/html/body/div[6]/div[2]/div[1]/div/div[3]/div/div[2]/div[2]/div/section/span[1]/button')
        pass


async def main():
    user_agent = "Chrome/73.0.3683.86"
    username = os.getenv("USERNAME")
    userProfile = (
        "C:\\Users\\"
        + username
        + "\\AppData\\Local\\Google\\Chrome\\User Data\\sendoffers"
    )
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("user-data-dir={}".format(userProfile))
    # driver = webdriver.Chrome(options=options)
    driver = await start(
        headless=False,
        user_data_dir=userProfile,
        lang="en-US",  # this could set iso-language-code in navigator, not recommended to change
    )
    sleeptime = 1

    # driver = webdriver.Remote(
    #  command_executor='http://127.0.0.1:4444/wd/hub',
    # desired_capabilities=DesiredCapabilities.CHROME)

    logintoebay(driver, ebay_username, ebay_password)
    print("logintoebaycomplete")
    time.sleep(10)
    tab = await driver.get(
        "https://www.ebay.com/sh/lst/active?pill_status=sioEligible&action=search"
    )
    time.sleep(15)
    check_all = await tab.find("shui-dt-checkall", best_match=True)
    time.sleep(1)
    check_all.click()
    time.sleep(1)
    offertobuyers = await tab.find("offerToBuyers", best_match=True)
    offertobuyers.click()
    time.sleep(3)
    # driver.execute_script('$(".textbox__control[name=\'offerAmount\']").val(5)')
    # driver.execute_script('$(".textbox__control[name=\'offerAmount\']").trigger("change");')
    try:
        time.sleep(1)
        percentageOff = await tab.find("offerAmount", best_match=True)

        # percentageOff = driver.find_element("xpath",'/html/body/div[7]/div[2]/div[1]/div/div[4]/div/div[6]/div/div/div[2]/div[3]/div/div/div/div/form/div/div/div[2]/div/div/div[1]/input')
        print("about to send 5 in percentageOff")
        time.sleep(1)

        send_keys_slowly(percentageOff, "5", 0.1)
        print("done sending 5")
    except Exception as e:
        # print(e)
        print("no eligible listings to send offers")
        driver.quit()
        exit(0)

    time.sleep(1)

    # submit= driver.find_element_by_xpath('//*[@id="s0-0-4-16-49-62-sio-dialog"]/div/div[2]/div[4]/div/button[1]')
    # driver.execute_script("$(arguments[0]).removeAttr('disabled');",submit)
    # driver.execute_script("arguments[0].click();",submit)
    sendcoupon = await tab.find("checkbox__send-coupon", best_match=True)
    sendcoupon.click()
    time.sleep(1)
    # driver.execute_script("$('#checkbox__send-coupon').click()")
    # clicking on coupon selector
    coupon = await tab.find("se-field-card__content-value", best_match=True)
    driver.execute_script("$('.se-field-card__content-value').click()")
    time.sleep(1)
    driver.execute_script("$('span:contains(\"Extra 5\")').click()")
    # submitting
    time.sleep(3)
    print("Clicking send")
    driver.execute_script(" $('.sio-actions button:contains(\"Send\")').click() ")
    print("send was clicked")
    # driver.execute_script("$('button[data-action-name=\"submitOffer\"]').click()")
    # driver.execute_script(" $('.sio-actions button:contains(\"Send\")').click() ")

    # time.sleep(10)

    driver.quit()


if __name__ == "__main__":
    # since asyncio.run never worked (for me)
    # i use
    loop().run_until_complete(main())
