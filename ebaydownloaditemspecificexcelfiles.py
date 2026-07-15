import os
import time
import undetected_chromedriver as uc  # Importing undetected_chromedriver instead of selenium's webdriver
from selenium.webdriver.common.by import By
from nodriver import *
import os
import json
import wmi
import time
import fasteners


import chromedriver_autoinstaller

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists

# and if it doesn't exist, download it automatically,
# then add chromedriver to path


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


def getcaegorycount(driver):
    return driver.execute_script(
        "return $(\".textual-display.category-name:contains('(')\").length"
    )


def iscategorycheked(driver, i):
    print("iscategorycheked called for i= " + str(i))
    r = driver.execute_script(
        "return $($($($($($(\".textual-display.category-name:contains('(')\")["
        + str(i)
        + ']).parent()).parent()).children()[0])).children().is(":checked")'
    )
    if r:
        print("iscategorycheked is returnning True")
    else:
        print("iscategorycheked is returnning False ")
    return r

    # driver.execute_script('return $($($($(".textual-display.category-name:contains(\'(\')")[' + str(i)+']).parent().parent()[0]).children()[0]).is(":checked")')
    # $($($(".textual-display.category-name:contains('(')")[2]).parent().parent()[0]).children()[0]


def clickcategory(driver, i):
    return driver.execute_script(
        "$($($($(\".textual-display.category-name:contains('(')\")["
        + str(i)
        + "]).parent().parent()[0]).children()[1]).click()"
    )


def isDownloadEnabled(driver):
    disabled = driver.execute_script(
        'return $($("button:contains(\'Download selected\')")[0]).is(":disabled")'
    )
    print("******************")
    print(disabled)
    print("***********")
    if "True" in str(disabled):
        print("downlown is not enabled")
        return False
    print("download is enabled")
    return True


def maximizeSelection(driver, start, end):
    print("maxamizeselection(driver," + str(start), ", " + str(end) + ") called ")
    i = start
    while isDownloadEnabled(driver) and i < end:
        print("starting maximizeSelection Loop i=" + str(i))
        if not iscategorycheked(driver, i):
            print("Clicking category: " + str(i))
            clickcategory(driver, i)
        else:
            print("iscategorycheked is true for " + str(i))
        i = i + 1
    if not isDownloadEnabled(driver):
        clickcategory(driver, i - 1)
        print("returning " + str(i - 1))
        return i - 1
    print("returning " + str(i))
    return i


def isRunning(s):
    print("starting isRuning( " + s + ")")
    # Iterating through all the running processes
    # Initializing the wmi constructor
    f = wmi.WMI()
    # Printing the header for the later columns
    # Iterating through all the running processes
    count = 0
    for process in f.Win32_Process():
        print(f"{process.ProcessId:<10} {process.Name}")
        # Displaying the P_ID and P_Name of the process
        if process.CommandLine and s in process.CommandLine:
            count = count + 1
            print(str(process.ProcessId) + " " + process.CommandLine)
        else:
            if process.CommandLine:
                cmdline = process.CommandLine
            else:
                cmdline = ""
            print("NOT: " + str(process.ProcessId) + " " + cmdline)

            if count > 1:
                return True
    print("isRunning Returning False")
    return False


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


def async downloadall(driver, index):
    print("Getting reccomended item specific page")
    tab = driver.get(
        "https://www.ebay.com/sh/lst/active?pill_status=itemSpecificsRecommended&sort=visitCount&action=pagination"
    )
    time.sleep(5)
    print("Clicking Download Button")
    if tab:
        print("tab is not none")
    downloadButton = await tab.find("Downlaod Selected", best_match=True)
    downloadButton.click()
    # driver.execute_script(
    #     "$(\"span:contains('Missing required or recommended item specifics')\").click()"
    # )
    time.sleep(5)
    # try:
    #     driver.execute_script('$(".sh-flag-us")[' + str(index) + "].click()")
    # except Exception as e:
    #     print("Couldn't select category")
    #     pass
    # time.sleep(2)
    # count=driver.execute_script('return $($("li.category").has(\':not(.category)\')).length')
    count = getcaegorycount(driver)
    # $($("li.category").has(':not(.category)')[40]).children().click()
    end = 0
    print(str(count))
    for i in range(count):
        print("starting loop " + str(i) + " of " + str(count) + " and end= " + str(end))
        if i >= end:
            clickcategory(driver, i)
            # driver.execute_script('$($("li.category").has(\':not(.category)\')['+ str(i) +']).children().click()')
            enabled = isDownloadEnabled(driver)
            # driver.execute_script('return $($("button:contains(\'Download selected\')")[0]).is(":disabled")')
            print(enabled)
            if isDownloadEnabled(driver):
                # end=maximizeSelection(driver, i, count-1);
                # print("checked until can't click button done")
                end = maximizeSelection(driver, i, count)
                time.sleep(5)
                print("disabled != True")
                print("Clicking Download Button")
                downloadButton = await tab.find("Downlaod Selected", best_match=True)
                downloadButton.click()
                # driver.execute_script('$(".btn--primary").click()')
                time.sleep(60)
                os.system("start populateitemspecificcache.py")
                print("Getting recomended item specific page")
                driver.get(
                    "https://www.ebay.com/sh/lst/active?pill_status=itemSpecificsRecommended&sort=visitCount&action=pagination"
                )
                time.sleep(5)
                print("Clicking Download Button")
                downloadButton = await tab.find("Downlaod Selected", best_match=True)
                downloadButton.click()

                # print("Clicking Download Button")
                # driver.execute_script(
                #    "$(\"span:contains('Missing required or recommended item specifics')\").click()"
                # )
                time.sleep(3)
                driver.execute_script('$(".sh-flag-us")[' + str(index) + "].click()")
                time.sleep(3)
            else:
                print("Download not enabled so clicking  again")
                clickcategory(driver, i)


async def loginifneeded(tab):
    try:
        ebay_username = os.getenv("ebay_username")
        ebay_password = os.getenv("ebay_password")
        await tab.get("https://www.ebay.com/sh/lst/active")
        # time.sleep(20)
        # Find login text field
        # print("finding the email input field")
        # email = await tab.select("input[id=userid]")
        email = await tab.find("username", best_match=True)
        # if not email:
        #     print("Email not found")
        # else:
        #     print("email found" + str(email))
        # await email.click()
        # await email.send_keys(ebay_username)
        await email.send_keys("\n")
        await send_keys_slowly(email, ebay_username, 0.1)
        time.sleep(1)
        print("Finding continue button")
        continuebutton = await tab.find("signin-continue-btn", best_match=True)
        # print("Pressing continue button")
        await continuebutton.click()
        # print("continue button was clicked")
        time.sleep(10)
        # print("looking for password")
        password = await tab.select("input[id=pass]")
        time.sleep(1)
        # print("clicking password")
        # await password.click()
        await password.send_keys("\n")
        time.sleep(1)
        # await password.send_keys(ebay_password)
        await send_keys_slowly(password, ebay_password, 0.1)
        time.sleep(1)
        signinbutton = await tab.find("Sign in", best_match=True)
        time.sleep(1)
        await signinbutton.click()
        time.sleep(10)
    except Exception as e:
        print(e)
        pass


async def send_keys_slowly(element, text, delay=0.1):
    for character in text:
        await element.send_keys(character)
        time.sleep(delay)


async def main():
    # Replace with your actual eBay credentials

    # User agent for Chrome
    # user_agent = "Chrome/73.0.3683.86"
    username = os.getenv("USERNAME")
    userProfile = (
        "C:\\Users\\"
        + username
        + "\\AppData\\Local\\Google\\Chrome\\User Data\\ebaydownloaditemspecificexcelfiles3"
    )

    # Setting up undetected-chromedriver options
    options = uc.ChromeOptions()
    # options.add_argument("user-agent={user_agent}")
    # options.add_argument("user-data-dir={}".format(userProfile))
    # options.add_experimental_option("excludeSwitches", ["enable-logging"])

    try:
        driver = uc.Chrome(options=options)
        # driver= await start(
        #     headless=False,
        #     user_data_dir=userProfile,
        #     lang="en-US",  # this could set iso-language-code in navigator, not recommended to change
        # )
    except Exception as e:
        print("Got exception" + str(e) + " so clearing directory and retrying")
        os.system('rmdir /q /s "' + userProfile + '"')
        time.sleep(20)
        os.system('mkdir "' + userProfile + '"')
        time.sleep(20)
        driver = uc.Chrome(options=options)
    time.sleep(60)
    sleeptime = 1

    tab = driver.get(
        "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&srcAppId=3564&ru=https%3A%2F%2Fwww.ebay.com"
    )

    await loginifneeded(tab)
    try:
        downloadall(driver, 2)  # ebay Motors
    except Exception as e:
        print(e)
        pass
    try:
        downloadall(driver, 1)  # ebay US
    except Exception as e:
        print(e)
        pass


if __name__ == "__main__":
    # since asyncio.run never worked (for me)
    # i use
    loop().run_until_complete(main())
