import csv
import glob
import requests
import re
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from nodriver import *
from selenium import webdriver
import chromedriver_autoinstaller
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import traceback
import sys
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import By
import selenium.webdriver.support.expected_conditions as EC  # noqa
from selenium.webdriver.support.wait import WebDriverWait

chromedriver_autoinstaller.install()

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

debugflag = True


async def initializeDriver(i=1, debugflag=False):
    if debugflag:
        print("starting initializeDriver(" + str(i) + ")", file=sys.stderr)
    user_agent = "Chrome/73.0.3683.86"
    username = os.getenv("USERNAME")
    userProfile = (
        "C:\\Users\\"
        + username
        + "\\AppData\\Local\\Google\\Chrome\\User Data\\getitemspecificsforid"
        + str(i)
    )

    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("user-data-dir={}".format(userProfile))

    # driver = await start(
    #     headless=False,
    #     user_data_dir=userProfile,
    #     lang="en-US",
    # )

    driver = uc.Chrome()
    return driver


def getItemSpecificsFromEbay(driver, id):
    url = "https://vi.raptor.ebaydesc.com/ws/eBayISAPI.dll?ViewItemDescV4&item=" + str(
        id
    )
    driver.get(url)
    time.sleep(1)

    try:
        print("1")
        # WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.TAG_NAME, "li"))
        # )
        print("2")
        list_items = driver.find_elements("tag name", "li")
        list_items = driver.find_elements(By.TAG_NAME, "li")
        print("3")
        r = {}
        for item in list_items:
            try:
                key = item.find_element_by_css_selector("span").text.strip()
                print("4")
                value = item.text.replace(key, "").strip()
                print("5")
                if len(key) > 64:
                    key = key[:64]
                if len(value) > 64:
                    value = value[:64]

                if "Country of Origin" in key:
                    key = "Country/Region of Manufacture"
                if "recommended age" in key:
                    key = "Age Level"
                if "Item Weight" in key:
                    value = value.replace("Kilograms", "kg")
                if "Product Dimensions" in key:
                    if "x" in value:
                        unit = " in"
                        if "inches" in value:
                            value = value.replace("inches", "")
                            unit = " in"
                        if "cm" in value:
                            value = value.replace("cm", "")
                            unit = " cm"
                        if '"' in value:
                            value = value.replace('"', "")
                            unit = " in"
                        try:
                            r["Item Length"] = (
                                value.split("x")[0].replace("=", "").strip() + unit
                            )
                            r["Item Width"] = (
                                value.split("x")[1].replace("=", "").strip() + unit
                            )
                            r["Item Height"] = (
                                value.split("x")[2].replace("=", "").strip() + unit
                            )
                        except Exception as e:
                            pass
                r[key] = value
            except Exception as e:
                print(f"Error processing item: {e}")

        if "Superseded Part Number" not in r:
            r["Superseded Part Number"] = "Does Not Apply"
        if "California Prop 65 Warning" not in r:
            r["California Prop 65 Warning "] = "Does Not Apply"
        if "Interchange Part Number" not in r:
            r["Interchange Part Number"] = "Does Not Apply"
        if "Model" not in r:
            if "Manufacturer Part Number" in r:
                r["Model"] = r["Manufacturer Part Number"]
                r["MPN"] = r["Manufacturer Part Number"]
            if "Model Name" in r:
                r["Model"] = r["Model Name"]
        return r
    except Exception as e:
        print(f"Error in getItemSpecificsFromEbay: {e}")
        return {}


def getDescription(id):
    global currentID
    global currentDescription
    if id == currentID:
        return currentDescription
    r = requests.get("https://www.ebay.com/itm/" + str(id))
    soup = BeautifulSoup(r.text, "html.parser")
    currentDescription = soup.get_text("|").replace(":|", ":")
    currentID = id
    return currentDescription


def fixTooManyItemSpecifics(row):
    keys = reversed(row.keys())
    total = len(row.keys())
    if total < 45:
        return row
    for k in keys:
        if "MPN" not in k:
            row[k] = ""
            total = total - 1
        if total < 44:
            return row
    return row


def getDefaultkey(key, file, id):
    match key:
        case "Bundle Description":
            return "Does Not Apply"
        case "Custom Bundle":
            return "No"
        case "California Prop 65 Warning":
            return "Does Not Apply"
        case "Country/Region of Manufacture":
            return "Unknown"
        case "Personalization Instructions":
            return "Does Not Apply"
        case default:
            return "See Listing"


def getItemSpecific(key, file, specifics):
    print("???looking for key |" + key + "|\n\n in " + str(specifics) + "\n\n")
    if key in specifics:
        print("**************************")
        print("*****item specific found: " + str(key) + " : " + str(specifics[key]))
        return specifics[key]
    return getDefaultkey(key, file, id)


async def main():
    currentDescription = ""
    currentID = ""
    i = random.randint(1, 100)
    driver = 0
    while not driver:
        try:
            driver = await initializeDriver(i, debugflag)
        except Exception as e:
            if debugflag:
                print("Got exception with i=" + str(i), file=sys.stderr)
            i = i + 1
    sleeptime = 1
    if len(sys.argv) < 2:
        print("usage: getitemspecificsfromebay <item_id>")
        return
    id = sys.argv[1]
    items = getItemSpecificsFromEbay(driver, id)
    for item in items:
        key = item
        value = items[item]
        print(key + " : " + value)


if __name__ == "__main__":
    loop().run_until_complete(main())
