import csv
import glob
import requests
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time
import traceback
from pathlib import Path
import random
from filelock import Timeout, FileLock
from selenium import webdriver
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()  # Check if the current version of chromedriver exists
# and if it doesn't exist, download it automatically,
# then add chromedriver to path

num = random.random()


srcdir = "D:\\zikprocessor\\data\\aspectfinder"
dstdir = "D:\\zikprocessor\\data\\aspectfinder\\output"

currentDescription = ""
currentID = ""

# user_agent = 'Chrome/73.0.3683.86'
# username = os.getenv("USERNAME")
# userProfile = "C:\\Users\\" + username + "\\AppData\\Local\\Google\\Chrome\\User Data\\processoptiseller" + str(num)
# options = webdriver.ChromeOptions()
# options.add_argument(f'user-agent={user_agent}')
# options.add_experimental_option('excludeSwitches', ['enable-logging'])
# options.add_argument("user-data-dir={}".format(userProfile))
# driver = webdriver.Chrome(options=options)
# sleeptime = 1

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)

# driver.get("https://www.ebay.com/sh/lst/active?pill_status=sioEligible&action=search")
# driver.implicitly_wait(10)
# time.sleep(20)


def getItemSpecificsFromFile(id):
    print("debug getItemSpecificsFromFile called with id = " + id)
    myvars = {}
    with open(
        "D:\\zikprocessor\\data\\itemspecifics\\" + id,
        encoding="utf-8",
        errors="ignore",
    ) as myfile:
        for line in myfile:
            name, var = line.partition(":")[::2]
            myvars[name.strip()] = var.strip()
        #   print("debug key= |"+ name +"|")
        #   print("debugvalue= |"+ var +"|")
        return myvars


cachehit = 0
cachemiss = 0


def getItemSpecificsFromEbay(id):
    global cachemiss
    global cachehit
    path = Path("D:\\zikprocessor\\data\\itemspecifics\\" + str(id))
    print(path)
    if not path.is_file():
        cachemiss = cachemiss + 1
        cachemissspercenttr = round(100 * cachemiss / (cachehit + cachemiss), 2)
        print(
            "cachemiss "
            + str(cachemiss)
            + " misses out of "
            + str(cachemiss + cachehit)
            + " "
            + str(cachemissspercenttr)
            + "%"
        )
        os.system(
            "getitemspecificsfromebay.py "
            + id
            + " > D:\\zikprocessor\\data\\itemspecifics\\"
            + id
        )
    else:
        cachehit = cachehit + 1
        print("cachehit " + str(cachehit) + " hits out of " + str(cachemiss + cachehit))

    specifics = getItemSpecificsFromFile(id)
    return specifics
    # url="https://vi.raptor.ebaydesc.com/ws/eBayISAPI.dll?ViewItemDescV4&item=" + str(id)
    # driver.get(url)
    # time.sleep(1)
    # #print(driver.current_url)
    # try:
    #     specifics = driver.execute_script('r=[];count = document.getElementsByTagName("li").length; for(i=0; i<count; i++){r.push(document.getElementsByTagName("li")[i].textContent);}; return r.toString();')
    # except Exception as e:
    #     print("error running script" )
    #     print(e)
    #     traceback.print_exc()
    #     time.sleep(2)
    #     specifics = driver.execute_script('r=[];count = document.getElementsByTagName("li").length; for(i=0; i<count; i++){r.push(document.getElementsByTagName("li")[i].textContent);}; return r.toString();')
    #     pass

    # print("----------------------")
    # print(specifics)
    # print("----------------------")
    # r={}
    # if specifics and "," in specifics:
    #     specifics=specifics.replace("\\u200e","").replace("\u200e","").replace("\\u200f","").replace("\u200f","")
    #     lines = specifics.split(",")
    #     for line in lines:
    #         if ":" in line:
    #             key=line.split(":")[0].strip()
    #             value=line.split(":")[1].strip()
    #             if "MPN" in key:
    #                 key="Manufacturer Part Number"
    #             if "OE" in key:
    #                 key="OE/OEM Part Number"
    #                 if len(value) >64:
    #                     value=value[0:64]
    #             if "Country of Origin" in key:
    #                 key="Country/Region of Manufacture"
    #             if "recommended age" in key:
    #                 key ="Age Level"
    #             if 'Product Dimensions' in key:
    #                 if "x" in value:
    #                     unit =" in"
    #                     if "inches" in value:
    #                         value=value.replace("inches","")
    #                         unit=" in"
    #                     if "cm" in value:
    #                         value=value.replace("cm","")
    #                         unit=" cm"
    #                     if "&quot;" in value:
    #                         value=value.replace("&quote;","")
    #                         unit=" in"
    #                     try:
    #                         r["Item Length="] = value.split("x")[0].strip() + unit
    #                         r["Item Width="] = value.split("x")[1].strip() + unit
    #                         r["Item Height="] = value.split("x")[2].strip() + unit
    #                     except Exception as e:
    #                         pass
    #                     #'1.35 x 3 x 4.7 inches'
    #             r[key]=value
    #             #print(key + " : " + value)
    # return r


def getDescription(id):
    """Gets description from ebay"""
    # https://www.ebay.com/itm/225357398327
    global currentID
    global currentDescription
    if id == currentID:
        return currentDescription

    r = requests.get("https://www.ebay.com/itm/" + str(id))
    soup = BeautifulSoup(r.text, "html.parser")
    # cache description of product we are working on
    # Also replace things like |MPN:|1234| with |MPN:1234|

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
        case "Personalize":
            return "No"
        case "Handmade":
            return "No"
        case "Vintage":
            return "No"
        case "Antique":
            return "No"
        case "Recipient":
            return "Multipurpose"
        case "Department":
            return "Adults"
        case "Origin":
            return "Unknown"
        case "Pattern":
            return "Solid"
        case "Theme":
            return "Art"
        case "Style":
            return "Classicism"
        case default:
            return "See Listing"


def getItemSpecific(key, file, specifics):
    # print("???looking for key |" + key + "|\n\n in " + str(specifics) +"\n\n")
    if key in specifics:
        print("**************************")
        print("*****item specific found: " + str(key) + " : " + str(specifics[key]))
        return specifics[key]
    # if key + ":" in description:
    #     right = description.split(key + ":")[1]
    #     value = right.split("|")[0]
    #     if value == "See Listing":
    #         if key + ":" in right:
    #             right = right.split(key+":")[1]
    #             value = right.split("|")[0]
    # if value:
    #     return value
    return getDefaultkey(key, file, id)


def processSourceFiles():
    srcfiles = glob.glob(srcdir + "\\*.csv")
    random.shuffle(srcfiles)
    for file in srcfiles:
        lock = FileLock(file + ".lock")
        if not os.path.exists(file + ".lock"):
            with lock:
                print(file)
                outfile = dstdir + "\\" + file.split("\\")[-1]
                try:
                    with open(
                        file, newline="", encoding="utf-8", errors="ignore"
                    ) as csvfile:
                        with open(
                            outfile, "w+", newline="", encoding="utf-8", errors="ignore"
                        ) as outputfile:
                            reader = csv.DictReader(csvfile)
                            rownum = 0
                            for row in reader:
                                print(row.keys())

                                if rownum == 0:
                                    # print(row.keys())
                                    writer = csv.DictWriter(
                                        outputfile, row.keys(), quoting=csv.QUOTE_ALL
                                    )
                                    writer.writeheader()
                                if row["Item Id"]:
                                    specifics = getItemSpecificsFromEbay(row["Item Id"])
                                    for key in row:
                                        if key:
                                            # print("Seeking " + row["Item Id"] + " " +str(key))
                                            before = row[key]
                                            if (
                                                not row[key]
                                                or row[key] == "See Listing"
                                            ):
                                                # description = getDescription(row["Item Id"])
                                                row[key] = getItemSpecific(
                                                    key, file, specifics
                                                )
                                            if (
                                                key
                                                and key in row
                                                and row[key] != before
                                            ):
                                                print(
                                                    "!!!!!!! "
                                                    + row["Item Id"]
                                                    + " "
                                                    + key
                                                    + " changed from |"
                                                    + before
                                                    + "| to |"
                                                    + str(row[key])
                                                    + "|"
                                                )
                                    # if len(row.keys())>44:
                                    #     row = fixTooManyItemSpecifics(row)
                                    writer.writerow(row)
                                rownum = rownum + 1
                    os.remove(file)
                except Exception as e:
                    print("error processing " + file)
                    print(e)
                    traceback.print_exc()
                    pass


processSourceFiles()
