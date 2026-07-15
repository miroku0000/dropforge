from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.action_chains import ActionChains

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path


from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
from selenium.webdriver.common.by import By
import time
import math
import sys
import argparse
import datetime
import glob
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys


def clickExportToCSV(driver):
    print("Begin function clickExportToCSV")
    p = driver.find_element(By.XPATH, "//*[text()='Export to CSV']")
    parentdiv = p.find_element(By.XPATH, (".."))
    parentbutton = parentdiv.find_element(By.XPATH, (".."))
    actions = ActionChains(driver)
    actions.move_to_element(parentbutton).click().perform()
    # parentbutton.click()
    print("end function clickExportToCSV")


def clickExportButton(driver):
    print("Begin function clickExportButton")
    p = driver.find_element(By.XPATH, "//*[text()='Export all items']")
    parentdiv = p.find_element(By.XPATH, (".."))
    parentbutton = parentdiv.find_element(By.XPATH, (".."))
    actions = ActionChains(driver)
    actions.move_to_element(parentbutton).click().perform()
    # parentbutton.click()
    print("End function clickExportButton")


def isPending(driver):
    try:
        p = driver.find_element(By.XPATH, "//*[text()='Pending!']")
        return True
    except:
        return False


def clickTopScan(driver):
    links = driver.find_elements(By.TAG_NAME, "a")
    for lnk in links:
        h = lnk.get_attribute("href")
        if "zik-pro/turbo-scanner/" in h:
            print(h)
            try:
                lnk.click()
            except Exception as e:
                print("Link was not clickable... trying driver.get")
                driver.get(lnk)
                time.sleep(10)
            return h


def clickTopReport(driver):
    print("Begin function clickTopReport")
    links = driver.find_elements(By.TAG_NAME, "a")
    for lnk in links:
        h = lnk.get_attribute("href")
        if "zik-pro/turbo-scanner/" in h:
            print(h)
            lnk.click()
            print("end function clickTopReport")
            return h
        print("end function clickTopReport")


def clickbyid(driver, id, name=""):
    while True:
        try:
            element = driver.find_element(By.ID, id)
            element.click()
            return 0
        except Exception as e:
            print("Got exception trying to find by id " + id)
            try:
                if name:
                    p = driver.find_element(By.XPATH, "//*[text()='" + name + "']")
                    p.click()
                    return 0
            except Exception as e:
                print("got exception trying to get by name " + name)
                pass


def setstringbyid(driver, id, val):
    debug = True
    debugtime = 10
    if debug:
        print("setstringbyid(driver," + id + "," + str(val) + ") called")
    element = driver.find_element(By.ID, id)
    if debug:
        print("clearing " + id)
    element.click()
    element.clear()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(Keys.BACKSPACE)
    if val:
        if debug:
            print("setting " + id + "to " + str(val))
        for key in str(val):
            element.send_keys(key)
        if debug:
            print("setting " + id + "to " + str(val) + " completed")
            time.sleep(debugtime)


def gettrendingkeywords(driver):
    driver.get("https://app.zikanalytics.com/dashboard")
    time.sleep(30)
    print("running script to get keywords")
    r = driver.execute_script(
        "ret=[]; urls = document.getElementsByTagName('a'); for (url in urls) {if(urls[url].href && urls[url].href.includes(\"/product-research\")){ret.push( urls[url].href)};}; return ret"
    )
    ret = []
    for url in r:
        if "search=" in url:
            url = url.split("search=")[1]
            if "&" in url:
                url = url.split("&")[0]
            url = url.replace("%20", " ")
            ret.append(url)
    return ret

    print("done running script to get gettrendingkeywords")
    return (",".join(ret)).replace('"', "")


def waitingFor(message, sleeptime=30):
    print(message + " begin sleep for " + str(sleeptime))
    time.sleep(sleeptime)
    print(message + " end sleep for " + str(sleeptime))


def implicitlyWaitingFor(driver, message, waittime):
    print(message + " begin implictly wait for " + str(waittime))
    driver.implicitly_wait(waittime)
    print(message + " end implicitly wait for " + str(waittime))


def killoldestscan(driver):
    try:
        print("killing all scans")
        p = driver.find_element(By.XPATH, "//*[text()='Delete All Scans']")
        parentdiv = p.find_element(By.XPATH, (".."))
        parentbutton = parentdiv.find_element(By.XPATH, (".."))
        actions = ActionChains(driver)
        actions.move_to_element(parentbutton).click().perform()
        # parentbutton.click()
        time.sleep(10)
        p = driver.find_element(By.XPATH, "//*[text()='Yes']")
        parentdiv = p.find_element(By.XPATH, (".."))
        parentbutton = parentdiv.find_element(By.XPATH, (".."))
        parentbutton.click()
        # buttons= driver.find_elements(By.XPATH, '//button')
        # button=buttons[buttons.length-3].click()
        # # driver.execute_script('$(".fas.fa-trash")[$(".fas.fa-trash").length-1].click()')
        print("done killing oldest scan")
    except Exception as e:
        pass


def arg_parser():
    parser = argparse.ArgumentParser(description="Export some csv files from ZIK.")
    parser.add_argument("-u", "--username", default=None, required=False)
    parser.add_argument("-p", "--password", default=None, required=False)
    parser.add_argument("-minprice", "--min_price", default="", required=False)
    parser.add_argument("-maxprice", "--max_price", default="", required=False)
    parser.add_argument("-mins", "--min_sales", default="", required=False)
    parser.add_argument(
        "-numProducts", "--numberOfProducts", default=1000, required=False
    )
    parser.add_argument("-bsrFrom", "--bsrFrom", default="", required=False)
    parser.add_argument("-bsrTo", "--bsrTo", default="", required=False)
    parser.add_argument(
        "-filterKeywords", "--filterKeywords", default="", required=False
    )
    parser.add_argument("-t", "--usetrendingkeywords", default=None, required=False)
    parser.add_argument("-k", "--killallscans", default=False, required=False)

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

args = arg_parser()
print(str(args))

import config
zik_username = config.EBAY_USER
password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\zikexport4"
)
options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
driver = webdriver.Chrome(options=options)

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)


# Log in to ebay
driver.get("https://app.zikanalytics.com/")
driver.implicitly_wait(10)
driver.maximize_window()
driver.implicitly_wait(10)


def is_text_present(driver, text):
    return str(text) in driver.page_source


try:
    email_address = driver.find_element("xpath", '//*[@id="email"]')
    email_address.send_keys(zik_username)
    driver.implicitly_wait(5)
    pw = driver.find_element("xpath", '//*[@id="password"]')
    pw.send_keys(password)
    continueButton = driver.find_element(
        "xpath", '//*[@id="root"]/div[1]/div[1]/div[2]/div/form/button'
    )
    # continueButton.click()
    driver.execute_script("arguments[0].click();", continueButton)
    continueButton
    # driver.implicitly_wait(5)
    waitingFor("login", 10)
    # implicitlyWaitingFor(driver,"login", 10)
    print("should be logged in now...")
    time.sleep(5)
    # driver.get("https://www.zikanalytics.com/BulkScanner/Amazon")
except Exception as e:
    # print(e)
    pass

try:
    print("trying to get trending keywords")
    keywords = gettrendingkeywords(driver)
    # driver.implicitly_wait(10)
    print(keywords)
    print("getting https://app.zikanalytics.com/zik-pro?tab=turbo-scanner")
    driver.get("https://app.zikanalytics.com/zik-pro?tab=turbo-scanner")
    driver.implicitly_wait(1)
    time.sleep(10)
    if args.killallscans:
        print("killing all scan")
        try:
            killoldestscan(driver)
        except Exception as e:
            print("got error killing oldest scan")
            pass
    time.sleep(10)
    if args.usetrendingkeywords:
        search = driver.find_element(By.NAME, "search")
        print("if args.usetrendingkeywords")
        search.send_keys(", ".join(keywords))
        # print('$("#filterKeywords").val("' + keywords + '")')
        # driver.execute_script('$("#filterKeywords").val("' + keywords + '")')
        print("if args.usetrendingkeywords done")
        time.sleep(15)
    if args.min_price:
        print("if args.min_price")
        setstringbyid(driver, "pricemin", str(args.min_price))
        # driver.execute_script('$("#filterMinPrice").val("' + str(args.min_price) +'")')
    else:
        print("if args.min_price else")
        setstringbyid(driver, "pricemin", "")
        # driver.execute_script('$("#filterMinPrice").val("' + str("") +'")')
    if args.max_price:
        print("if args.max_price")
        setstringbyid(driver, "pricemax", str(args.max_price))
        # driver.execute_script('$("#filterMaxPrice").val("' + str(args.max_price) +'")')
    else:
        print("if args.max_price else")
        setstringbyid(driver, "pricemax", "")
        # driver.execute_script('$("#filterMaxPrice").val("' + str("") +'")')
        time.sleep(10)
    if args.min_sales:
        print("if args_min sales")
        setstringbyid(driver, "recentSalemin", str(args.min_sales))
        # driver.execute_script('$("#filterMinSales").val("' + str(args.min_sales) +'")')
    else:
        print("if args_min sales else")
        setstringbyid(driver, "recentSalemin", "")
        # driver.execute_script('$("#filterMinSales").val("")")')
    if args.bsrFrom:
        setstringbyid(driver, "sellerRankingmin", str(args.bsrFrom))
        # driver.execute_script('$("#bsrMin").val("' + str(args.bsrFrom)+ '")')
    else:
        setstringbyid(driver, "sellerRankingmin", str(args.bsrFrom))
    if args.bsrTo:
        setstringbyid(driver, "sellerRankingmax", str(args.bsrTo))
        # driver.execute_script('$("#bsrTo").val("' + str(args.bsrTo)+ '")')
    else:
        setstringbyid(driver, "sellerRankingmax", "")
        # driver.execute_script('$("#bsrTo").val("")')
    if args.filterKeywords:
        print("if args.filterKeywords")
        setstringbyid(driver, "search", str(args.filterKeywords))
        # driver.execute_script('$("#filterKeywords").val("' + str(args.filterKeywords)+ '")')
    else:
        if not args.usetrendingkeywords:
            print(
                "if not args.usetrendingkeywords inside else of if args.filterKeywords"
            )
            setstringbyid(driver, "search", "")
            # driver.execute_script('$("#filterKeywords").val("")')
    if args.numberOfProducts:
        setstringbyid(driver, "numberOfProductsmax", str(args.numberOfProducts))
        # driver.execute_script('$("#filterItemsAmount").val("' + str(args.numberOfProducts)+ '")')
    # driver.execute_script('$("#Similar").prop("checked", true);')
    print("should be done filling in values")

    time.sleep(1)
    p = driver.find_element(By.XPATH, "//*[text()='Start New Scan']")
    parentdiv = p.find_element(By.XPATH, (".."))
    parentbutton = parentdiv.find_element(By.XPATH, (".."))
    actions = ActionChains(driver)
    actions.move_to_element(parentbutton).click().perform()
    # parentbutton.click()
    # driver.execute_script("$('#tbSearchBtn').click()")
    print("button to start a new scan pushed")
    time.sleep(10)
    driver.get("https://app.zikanalytics.com/zik-pro?tab=turbo-scanner")
    time.sleep(10)
    while isPending(driver):
        print("still pending scan")
        driver.get("https://app.zikanalytics.com/zik-pro?tab=turbo-scanner")
        time.sleep(30)
    # while driver.execute_script('return $(".progress-bar-warning").length;'):
    #   print("Waiting for completion of zik scan")
    #   driver.get("https://app.zikanalytics.com/zik-pro?tab=turbo-scanner")
    #   time.sleep(10)
    print("Zik Scan complete... Exporting all items")
    try:
        clickTopReport(driver)
    except Exception as e:
        print("Got error trying to click top report... refreshing")
        driver.refresh()
        time.sleep(30)
        clickTopReport(driver)
        pass
    print("Should be on the listings page... Clicking Button to get to export page")
    time.sleep(15)
    clickExportButton(driver)
    # driver.execute_script('$("span:contains(\'Export all items\')")[0].click()')
    time.sleep(3)
    print("Should be on the export page")
    time.sleep(3)
    try:
        clickbyid(driver, "vero")
    except Exception as e:
        print("** Got exception trying to find id vero")
    # driver.execute_script("$('#exportverowords').click()")
    clickbyid(driver, "restricted")
    # driver.execute_script("$('#exportriskyWords').click()")
    print("checkboxes  should be clicked waitng to click export button")
    time.sleep(4)
    try:
        clickExportToCSV(driver)
    except Exception as e:
        print("Unable to locate Export button, trying again")
        driver.refresh()
        time.sleep(10)
        try:
            driver.refresh()
            time.sleep(30)
            clickExportToCSV(driver)
        except Exception as e:
            print("Unable to locate Export button, trying again")
        pass
    # driver.execute_script("$('#exportListings').click()")
    print("Export button clicked")
    time.sleep(5)
    while len(glob.glob("C:\\Users\\" + username + "\\Downloads\\zikCSV*.csv")) == 0:
        print("Wating for Download of Zik Results file")
        time.sleep(5)
    print("Detected Zik file. Sleeping a bit more for download to complete")
    time.sleep(2)
    # -min_roi 0.19 -min_sales 3
except Exception as e:
    print(e)
    pass
print("quitting browser in 2 seconds")
time.sleep(2)
driver.quit()
