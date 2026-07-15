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
import random
from filelock import Timeout, FileLock

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


def removeFile(filename):
    print("Removing file: " + filename)
    while os.path.exists(filename):
        print("File exists so let's wait longer and try again")
        time.sleep(1)
        try:
            print("Calling os.remove...")
            os.remove("D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv")
        except Exception as e:
            print("got error trying to remove again")
            pass
    print("File was sucessfully deleted")


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

if len(sys.argv) < 3:
    print("Usage: optisellerfilessubmit.py <processnum> <numprocesses>")
    exit()

processnum = int(sys.argv[1])
numprocesses = int(sys.argv[2])
# skip is the percentage of listings that need updated to skip before straring in this process
skip = ((processnum - 1) * 1.0) / (1.0 * numprocesses)
print("skip=" + str(skip))
# maxlink is the percentage of the last link to process in this process
maxlink = ((processnum) * 1.0) / (1.0 * numprocesses)
print("maxink=" + str(maxlink))

userProfile = (
    "C:\\Users\\"
    + username
    + "\\AppData\\Local\\Google\\Chrome\\User Data\\opti"
    + str(processnum)
)
debugstring = "debug " + str(processnum) + ": "
print(debugstring + "using " + str(sys.argv[1]))

options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    print("Got exception so clearing directory and retrying")
    os.system('rmdir /q /s "' + userProfile + '"')
    time.sleep(10)
    os.system('mkdir "' + userProfile + '"')
    time.sleep(10)
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
        time.sleep(10)
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
            time.sleep(5)
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
                time.sleep(5)
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
reportpage = driver.current_url
toprocess = []

if not nosort:
    print("sorting...")
    driver.execute_script('$("#column_5").click();')
    if reverse:
        driver.execute_script('$("#column_5").click();')
# driver.execute_script('$("tr").filter(function( index ) {return $( this ).find("td:eq(4)").text() == "0";}).remove();')
driver.execute_script(
    '$("tr").filter(function( index ) {return $( this ).find("td:eq(5)").text() == "0";}).remove();'
)

links = driver.find_elements("xpath", "//a[@href]")
for link in links:
    # print(link.get_attribute("href"))
    if "eBayAspectFinder/report/Index/" in link.get_attribute("href"):
        toprocess.append(link.get_attribute("href"))
        print("link:" + link.get_attribute("href"))

print(debugstring + " found " + str(len(toprocess)) + " links to process")
i = 1
very_beginning = time.time()


skipped = 0
completed = 0
start = time.perf_counter()

numlinksforthisinstance = maxlink * len(toprocess) - skip * len(toprocess)

for link in toprocess:
    if skip and skipped < skip * len(toprocess):
        skipped = skipped + 1
    else:
        if maxlink and completed > numlinksforthisinstance:
            print(debugstring + "Reached maximum number to process in this process")
            exit()
        else:
            if completed == 0:
                start = time.perf_counter()
            else:
                current = time.perf_counter()
                elapsed = current - start
                average = elapsed / completed
                remaining = numlinksforthisinstance - completed
                remaingTime = remaining * average
                print(
                    debugstring
                    + "**************** completed "
                    + str(completed)
                    + " / "
                    + str(numlinksforthisinstance)
                    + " in "
                    + str(elapsed)
                    + " seconds for an average of "
                    + str(average)
                    + " per listing with "
                    + str(datetime.timedelta(seconds=remaingTime))
                    + " time left"
                )
            driver.get(link + "&pageSize=200&modeSelected=10")
            if needToLogin():
                login()
                print(
                    debugstring
                    + "Done logging in and getting page: "
                    + link
                    + "&pageSize=200&modeSelected=10"
                )
                driver.get(link + "&pageSize=200&modeSelected=10")

            # try:
            # 	text="SIGN IN TO CONTINUE"
            # 	textonpage=driver.find_element("xpath","//*[contains(text(),'" + text + "')]")
            # 	login()
            # 	time.sleep(10)
            # 	driver.get(link+"&pageSize=200&modeSelected=10")
            # except Exception as e:
            # 	pass
            print(debugstring + "getting category")
            category = driver.execute_script('return $("#CategoryId").val()')
            if not category:
                login()
                driver.get(link + "&pageSize=400&modeSelected=10")
                time.sleep(5)
            print(debugstring + "category = " + str(category))

            # Click the upload button
            csvfiles = glob.glob(
                "D:\\zikprocessor\\data\\aspectfinder\\output\\*"
                + str(category)
                + "*.csv"
            )
            if len(csvfiles) > 0:
                driver.get(reportpage)
                time.sleep(10)
                driver.execute_script("$(\"button:contains('Import')\").click()")
                time.sleep(9)
                csvfile = ""
                try:
                    csvfiles = glob.glob(
                        "D:\\zikprocessor\\data\\aspectfinder\\output\\*"
                        + str(category)
                        + "*.csv"
                    )
                    if len(csvfiles) != 1:
                        print(debugstring + "Problem:  csvfiles = " + str(csvfiles))
                    else:
                        csvfile = csvfiles[0]
                    print(debugstring + csvfile)
                    if csvfile:
                        lock = FileLock(
                            "D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv"
                            + ".lock"
                        )
                        with lock:
                            if not path.exists(
                                "D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv"
                            ):
                                os.replace(
                                    csvfile,
                                    "D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv",
                                )
                            else:
                                print(
                                    "ERROR: File lock aquired but upload.csv already exists"
                                )
                                os.replace(
                                    csvfile,
                                    "D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv",
                                )
                            # Open chose file dialog
                            print(debugstring + "Clicking Choose File")
                            # driver.execute_script("$('input:file')[0].removeClass('hidden');")
                            # driver.execute_script("$('input:file')[0].click();")
                            button = driver.find_element(
                                "xpath", '//*[@id="filebox"]/div/p[1]/strong'
                            )
                            button.click()
                            print(debugstring + "choose file should be open")
                            time.sleep(4)
                            print(debugstring + "running the uploadcsv.exe")
                            os.system("D:\\zikprocessor\\src\\uploadcsv.au3")
                            time.sleep(3)
                            print(debugstring + "Continuing")
                            driver.execute_script('$("#submitForm").click()')
                            time.sleep(3)
                            print(
                                debugstring + "Accepting the mappings and uploading..."
                            )
                            driver.execute_script(
                                "$(\"button:contains('Upload with Mappings')\").click()"
                            )
                        # removeFile("D:\\zikprocessor\\data\\aspectfinder\\output\\upload.csv")
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)
                        if "FileMapper" in driver.current_url:
                            time.sleep(5)

                    else:
                        print(
                            debugstring
                            + "no csv file found so skipping category "
                            + str(category)
                        )
                        driver.get(link + "&pageSize=200&modeSelected=10")
                        time.sleep(5)

                except Exception as e:
                    print(debugstring)
                    print(e)
                    pass
            # Get page again because after importing file, pageSize is lost
            driver.get(link + "&pageSize=200&modeSelected=10")
            time.sleep(5)
            missingcount = int(
                driver.execute_script('return $(".afp-MissingColour").length;')
            )

            # # Apply all suggested changes to type
            # print(debugstring + "Applying suggested changes to type...")
            # print(debugstring + "... Selecting All")
            # driver.execute_script('$("#selection_all_on_page").click()')
            # time.sleep(1)
            # print(debugstring + "Click update missing buttton")
            # driver.execute_script('$("#updateMissingButton").click()')
            # time.sleep(1)
            # print(debugstring + "... Clicking update Reccomended")
            # time.sleep(1)
            # # Select Replace values with suggestions
            # driver.execute_script('$("#updateRecommendedCheckbox").click()')
            # time.sleep(1)
            # # Select Type
            # print(debugstring + "... Selecting Type")
            # try:
            # 	driver.execute_script('$("#aspectNamesDdl").val($("#aspectNamesDdl option").filter(function() {return $(this).text() === "Type";})[0].value).change();')
            # except Exception as e:
            # 	print(debugstring + "Got exception e")
            # 	pass
            # time.sleep(1)
            # print(debugstring + "... Clicking Continue")
            # driver.execute_script('$("#bulkUpdateContinueButton").click()')
            # time.sleep(10)
            missingcount = int(
                driver.execute_script('return $(".afp-MissingColour").length;')
            )
            # always apply sugestions
            if missingcount > -1:
                print(
                    debugstring
                    + "Applying all suggestions to missing fields because found "
                    + str(missingcount)
                    + " fields"
                )
                driver.execute_script('$("#selection_all_on_page").click()')
                time.sleep(1)
                driver.execute_script('$("#updateMissingButton").click()')
                time.sleep(1)
                driver.execute_script('$("#updateSuggestedCheckbox").click()')
                driver.execute_script('$("#updateRecommendedCheckbox").click()')
                time.sleep(1)
                driver.execute_script('$("#bulkUpdateContinueButton").click()')
                time.sleep(15)
                if not csvfiles:
                    missingcount = int(
                        driver.execute_script('return $(".afp-MissingColour").length;')
                    )
                    if missingcount > 0:
                        print(
                            debugstring
                            + "Because no csv file found, and there are still some fields missing we will fill in vlaues with JQUERY"
                        )
                        driver.execute_script(
                            '$(".afp-MissingColour").val("See Listing");$(\'input[dit-aspect="Bundle Description"]\').val("Does Not Apply");$(\'input[dit-aspect="Custom Bundle"]\').val("No");$(\'input[dit-aspect="Modified Item"]\').val("No");$(\'input[dit-aspect="Modification Description"]\').val("Does Not Apply");$(\'input[dit-aspect="Country/Region of Manufacture"]\').val("Unknown");$(\'input[dit-aspect="California Prop 65 Warning"]\').val("Does Not Apply");$(\'input[dit-aspect="Vintage (Y/N)"]\').val("No");$(\'input[dit-aspect="Personalize"]\').val("No");$(\'input[dit-aspect="Personalization Instructions"]\').val("Does Not Apply");$(".afp-MissingColour").trigger("blur")'
                        )
                        time.sleep(20)

            else:
                print(
                    debugstring + "No missing fields found so not applying suggestions"
                )
            print(debugstring + "Selecting all")
            driver.execute_script('$("#selection_all_on_page").click()')
            time.sleep(1)
            print("Running Jquery")
            driver.execute_script(
                '$(".afp-RecommendedColour:empty").val("See Listing");$(".afp-MissingColour").val("See Listing");$(\'input[dit-aspect="Bundle Description"]\').val("Does Not Apply");$(\'input[dit-aspect="Custom Bundle"]\').val("No");$(\'input[dit-aspect="Modified Item"]\').val("No");$(\'input[dit-aspect="Modification Description"]\').val("Does Not Apply");$(\'input[dit-aspect="Country/Region of Manufacture"]\').val("Unknown");$(\'input[dit-aspect="California Prop 65 Warning"]\').val("Does Not Apply");$(\'input[dit-aspect="Vintage (Y/N)"]\').val("No");$(\'input[dit-aspect="Personalize"]\').val("No");$(\'input[dit-aspect="Personalization Instructions"]\').val("Does Not Apply");$(".afp-MissingColour").trigger("blur")'
            )
            print(debugstring + "Sending all")
            driver.execute_script('$("#sendSelectedButton").click()')
            time.sleep(1)
            print(debugstring + "confiming")
            driver.execute_script('$("#continue-modal-btn").click()')
            numlistings = int(driver.execute_script('return $(".afp-item-id").length;'))
            iterations = 0
            while driver.execute_script(
                "return $(\"img[src='/Content/spin.gif']:visible\").length"
            ):
                time.sleep(20)
                numleft = driver.execute_script(
                    "return $(\"img[src='/Content/spin.gif']:visible\").length"
                )
                print(
                    "Sleeping more because " + str(numleft) + " still found processing"
                )
                iterations = iterations + 1
                if iterations % 3 == 0:
                    driver.execute_script('$(".afp-MissingColour").trigger("blur")')
            i = i + 1
            completed = completed + 1
