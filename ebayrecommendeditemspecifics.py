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
import json
import math
import traceback
import sys
from pathlib import Path
import wmi


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


def getItemSpecificsFromFile(id):
    # print("debug getItemSpecificsFromFile called with id = " + id)
    myvars = {}
    with open(
        "D:\\zikprocessor\\data\\itemspecifics\\" + id,
        encoding="utf-8",
        errors="ignore",
    ) as myfile:
        for line in myfile:
            name, var = line.partition(":")[::2]
            myvars[name.strip()] = var.strip()
        # 	print("debug key= |"+ name +"|")
        # 	print("debugvalue= |"+ var +"|")
        return myvars


def getDone(filename="../data/isdone.json"):
    with open(filename) as f:
        j = json.load(f)
    if "done" in j:
        return j
    else:
        return {"done": [], "skipped": []}


def storeDone(done, filename="../data/isdone.json"):
    s = json.dumps(done)
    with open(filename, "w") as json_file:
        json.dump(done, json_file, indent=4)


def clickIfTitleContains(title, pattern, buttonText, excludeText=""):
    # title= driver.execute_script('return $("a").text()')
    # title = driver.find_element("xpath",'//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-ITEM_CARD__-ITEM_CARD_TEXT__-itemTitle__"]/span[2]/a')
    # title = driver.find_element("xpath",'//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-ITEM_CARD__-ITEM_CARD_TEXT__-itemTitle__"]/a')
    if title:
        # title = title.text
        print(title)
    else:
        title = ""

    if pattern in title and (excludeText == "" or excludeText not in title):
        nButton = ""
        try:
            nButton = driver.find_elements(
                "xpath", "//*[contains(text(), '" + buttonText + "')]"
            )
            if nButton:
                for b in nButton:
                    if b and b.text != title:
                        print(
                            buttonText
                            + " Button found!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                        )
                        try:
                            driver.execute_script("arguments[0].click();", b)
                        except:
                            pass
        except Exception as e:
            print(
                "Got error in clickIfTitleContains("
                + pattern
                + ", "
                + buttonText
                + ", "
                + excludeText
                + "): "
                + str(e)
            )
            pass


def clickIfTitleDoesNotContain(title, pattern, buttonText, excludeText=""):
    # title = driver.find_element("xpath",'//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-ITEM_CARD__-ITEM_CARD_TEXT__-itemTitle__"]/a')
    if title:
        print("title:" + title)
        # title = title.text
    else:
        title = ""

    if pattern not in title and (excludeText == "" or excludeText not in title):
        nButton = ""
        try:
            nButton = driver.find_elements(
                "xpath", "//*[contains(text(), '" + buttonText + "')]"
            )
            if nButton:
                for b in nButton:
                    if b and b.text != title:
                        print(
                            buttonText
                            + " Button found!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                        )
                        try:
                            driver.execute_script("arguments[0].click();", b)
                        except:
                            pass
        except Exception as e:
            print(
                "Got error in clickIfTitleContains("
                + pattern
                + ", "
                + buttonText
                + ", "
                + excludeText
                + "): "
                + str(e)
            )
            pass


if isRunning("D:\\zikprocessor\\src\\ebayrecommendeditemspecifics.py"):
    print("ebayrecommendeditemspecifics is already running")
    exit(1)


import config
ebay_username = config.EBAY_USER
ebay_password = config.EBAY_PASS

user_agent = "Chrome/73.0.3683.86"
username = os.getenv("USERNAME")
userProfile = (
    "C:\\Users\\"
    + username
    + "\\AppData\\Local\\Google\\Chrome\\User Data\\ebayrecommendeditemspecifics"
)
options = webdriver.ChromeOptions()
options.add_argument(f"user-agent={user_agent}")
options.add_argument("user-data-dir={}".format(userProfile))
options.add_experimental_option("excludeSwitches", ["enable-logging"])
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    # os.system('rmdir /q /s "' +userProfile +'"')
    # time.sleep(30)
    # os.system('mkdir "' +userProfile +'"')
    # time.sleep(30)
    # driver = webdriver.Chrome(options=options)
    pass
sleeptime = 1

# driver = webdriver.Remote(
#  command_executor='http://127.0.0.1:4444/wd/hub',
# desired_capabilities=DesiredCapabilities.CHROME)

driver.get("https://www.ebay.com/sh/lst/active")
driver.implicitly_wait(5)


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

# Get the web page this lists all listings with required item specifics

# url="https://www.ebay.com/sh/lst/active?pill_status=itemSpecificsRecommended&action=search"
todo = []
done = getDone()
# for offset in range(0,200,200):
skiprest = False
print("Looking for listings in need of updates")
for offset in range(0, 2800, 200):
    if not skiprest:
        url = (
            "https://www.ebay.com/sh/lst/active?pill_status=itemSpecificsRecommended&action=paginati on&&limit=200&offset="
            + str(offset)
        )
        driver.get(url)
        # Waitt for the page to load
        driver.implicitly_wait(5)
        time.sleep(5)
        # Find the ebay id for each item that needs specifics updated
        # These are stored in the "data-id attribute of each tr with the class 'grid-row'
        # first fins all tr with class grid-row:
        ids = driver.find_elements(By.CSS_SELECTOR, "tr.grid-row")

        if not ids or len(ids) == 0:
            skiprest = True
        # Extract the data-id attribute from each one and store it in an array called todo:
        for id in ids:
            did = id.get_attribute("data-id")
            todo.append(did)

print("\n***********found " + str(len(todo)) + " items to process")

skipped = []
complete = []
# one["skipped"]=[]
# done["done"]=[]
# todo=["224476657111"]

filteredtodo = []
alreadydone = 0
alreadyskipped = 0
for id in todo:
    if id in done["done"]:
        alreadydone = alreadydone + 1
    else:
        if id in done["skipped"]:
            alreadyskipped = alreadyskipped + 1
        else:
            filteredtodo.append(id)

print("\n*************************************************")
print("filteredtodo: " + str(len(filteredtodo)))
print("alreadyskipped: " + str(alreadyskipped))
print("alreadydone: " + str(alreadydone))
print("*************************************************")

count = 0
for id in filteredtodo:
    if id not in done["skipped"] and id not in done["done"]:
        count = count + 1
        # driver.implicitly_wait(10)
        print(
            "PROCESSING EBAY ITEM ID: "
            + id
            + " #"
            + str(count)
            + " of "
            + str(len(filteredtodo))
        )
        path = Path('D:\\zikprocessor\\data\\itemspecifics\\" + id')
        if not path.is_file():
            os.system(
                "getitemspecificsfromebay.py "
                + id
                + " > D:\\zikprocessor\\data\\itemspecifics\\"
                + id
            )

        # Go to the ReviseItem web page for this id:
        driver.get(
            "https://www.ebay.com/sl/list/grasshopper?mode=ReviseItem&itemId="
            + id
            + "&maxHeight=847"
        )
        driver.implicitly_wait(3)
        time.sleep(5)
        print("clicking show more item specifics")
        s = "$(\"span:contains('Show more item specifics')\").click()"
        driver.execute_script(s)
        try:
            s = 'r=[];count= $("textarea:empty").length;for(i=0; i<count; i++){r.push($($("textarea:empty")[i]).attr("aria-label"))}; return r.toString();'
            missing = driver.execute_script(s)
            missingcount = int(
                driver.execute_script('return $("textarea:empty").length;')
            )
            print("missingcount=")
            print(missingcount)
            itemspecifics = getItemSpecificsFromFile(id)
            # print("found the following item specifics:")
            # for key in itemspecifics:
            # 	print("debug processing item specics: |" + key + "| : |" + itemspecifics[key] +"|")
            for m in missing.split(","):
                m = m.strip()
                print("Missing: |" + m + "|")
                if m in itemspecifics:
                    # print ("\n!!!!!!!!!!!!!!!!!!found " +m + " in item specifics")
                    # print("setting " + m + " to " + itemspecifics[m])
                    key = m
                    value = itemspecifics[m].replace('"', '"')
                    s = (
                        "$('textarea[aria-label=\""
                        + key
                        + '"]\').val("'
                        + str(value)
                        + '")'
                    )
                    # s=json.dumps(s)
                    print(s)
                    driver.execute_script(s)
                else:
                    # print("Not Found: " + m +" in " + json.dumps(itemspecifics))
                    value = "Does Not Apply"
                    if "Manufacturer Part Number" in m:
                        try:
                            v = driver.execute_script(
                                "return $(\"textarea[aria-label='MPN']\").text()"
                            )
                            if v:
                                value = v
                                print(
                                    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
                                )
                                print(
                                    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^found mpn "
                                    + v
                                    + " in mpn field"
                                )
                                print(
                                    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
                                )
                                s = (
                                    '$(\'textarea[aria-label="Manufacturer Part Number"]\').text("'
                                    + value
                                    + '")'
                                )
                                print(s)
                                print("Filling in Manufacturer Part Number:")
                                driver.execute_script(s)
                                print("Done Filling in Manufacturer Part Number:")
                                time.sleep(10)
                                print("----")
                        except Exception as e:
                            print(e)
                            pass
                    # s=json.dumps(s)
                    s = "$('textarea[aria-label=\"" + m + '"]\').val("' + value + '")'
                    print(s)
                    driver.execute_script(s)
            for k in itemspecifics:
                try:
                    driver.execute_script(
                        "$(\".inputField__label[data-value='"
                        + itemspecifics[k]
                        + "']\")"
                    )
                except Exception as e:
                    pass

            # if m and m in itemspecifics:
            # 	print("setting " + m + " to " + itemspecifics[m])
            # 	key=m
            # 	value=itemspecifics[m]
            # 	s="$('textarea[aria-label=\"" + key +"\"]').val(\""+ value +"\")"
            # 	s=json.dumps(s)
            # 	print(s)
            # 	driver.execute_script(s)
            # else:
            # 	print("not found |" +m +"|in " +json.dumps(itemspecifics))
        except Exception as e:
            print(e)
            print(traceback.print_exc())
            pass
        # try:
        # 	print("trying to click don't remind me")
        # 	s='$(\'span:contains(\"remind me\")\').click()'
        # 	print(s)
        # 	driver.execute_script(s)
        # except Exception as e:
        # 	print("got error trying to click don't remind me")
        # 	print(e)
        # 	pass

        # Look for the "Accept all" text link which may or may not exist
        try:
            acceptAllButton = driver.find_element("link text", "Accept all")
            # If the acceptButton exists, then click it using the javacript method:
            if not acceptAllButton:
                print("*** didn't find Accept all using partial link")
                acceptAllButton = driver.find_element(
                    "xpath", '//a[@text="Accept all"]'
                )
            if not acceptAllButton:
                acceptAllButton = driver.find_element(
                    "xpath", "//*[contains(text(), 'Accept all')]"
                )
            if acceptAllButton:
                print("*********************acceptAllButton found... clicking")
                driver.execute_script("arguments[0].click();", acceptAllButton)
                print("acceptAll clicked sucessfully")
                # We will wait some amount of time for the page to update
                driver.implicitly_wait(30)
                time.sleep(2)
                print("wait complete")

        except Exception as e:
            print("AcceptButton not found using xpath 1")
            skipped.append(id)
            done["skipped"].append(id)
            storeDone(done)
            pass

        buttons = driver.find_elements("xpath", "//*[contains(text(), 'Save')]")
        for btn in buttons:
            print("clicking save***************")
            driver.execute_script("arguments[0].click();", btn)
            print("save clicked***************")
            driver.implicitly_wait(1)
            time.sleep(5)
            print("wait complete")
            complete.append(id)
            done["done"].append(id)
            storeDone(done)

        try:
            print("trying to click don't remind me")
            s = "$('span:contains(\"remind me\")').click()"
            print(s)
            driver.execute_script(s)
        except Exception as e:
            print("got error trying to click don't remind me")
            print(e)
            pass

        buttons = driver.find_elements("xpath", "//*[contains(text(), 'Save')]")
        for btn in buttons:
            print("clicking save***************")
            driver.execute_script("arguments[0].click();", btn)
            print("save clicked***************")
            driver.implicitly_wait(1)
            time.sleep(3)
            print("wait complete")

        try:
            driver.execute_script("$('a:contains(\"Accept all\")').click()")
            title = driver.execute_script('return $("a").text()')
            # title= driver.find_element("xpath",'//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-ITEM_CARD__-ITEM_CARD_TEXT__-itemTitle__"]/a')
            if title:
                print("title: " + title)
            else:
                title = ""

            clickIfTitleContains(title, "Magnifying Lamp", "Magnifying Lamp")
            clickIfTitleContains(title, "Magnifier", "Magnifying Lamp")
            clickIfTitleContains(title, "String Lights", "LED String")
            clickIfTitleContains(title, "Multicolor", "Multicolor")
            clickIfTitleContains(title, "Women", "Women")
            clickIfTitleContains(title, "Men", "Men", "Women")
            clickIfTitleContains(title, "women", "Women")
            clickIfTitleContains(title, "Nail Drill", "Nail File & Drill")
            clickIfTitleContains(title, "Nail Sticker", "Nail Art Decor")
            clickIfTitleContains(title, "Nail Powder", "Nail Art Decor")
            clickIfTitleContains(title, "Nail Glitter", "Nail Art Decor")
            clickIfTitleContains(title, "Chin Reducer", "Face Slimming Mask")
            clickIfTitleContains(title, "Lanyard", "ID & Badge Holders")
            clickIfTitleContains(title, "Blackhead", "Blackhead Mask")
            clickIfTitleContains(title, "Seeder", "Seed Sower")
            clickIfTitleContains(title, "Ionic Hair Dryer Brush", "Detangling Brush")
            clickIfTitleContains(
                title, "Summers Eve Cleansing Cloths", "Feminine Care Wash"
            )
            clickIfTitleContains(title, "Planter", "Pot")
            clickIfTitleContains(title, "Paver Lighting", "Deck/Step Light")
            clickIfTitleContains(title, "Netting", "Netting")
            clickIfTitleContains(title, "Patches", "Patches")
            clickIfTitleContains(title, "Hook", "Hook")
            clickIfTitleContains(title, "Backpack", "Backpack")
            clickIfTitleContains(title, "Mixed", "Assorted")
            clickIfTitleContains(title, "Grow Bag", "Plant Bag")
            clickIfTitleContains(title, "Massage Pillow", "Massage Cushion")
            clickIfTitleDoesNotContain(title, "Boy", "Adults", excludeText="Girl")

        # 	# Try setting the isbn from the sku
        # 	try:
        # 		showmore=driver.find_element_by_xpath('//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-LIST_PAGE_GRASSHOPPER_BODY__-ATTRIBUTES__-ATTRIBUTES_GH__-ATTRIBUTES_DIY_VIEW__-RECOMMENDED_GROUP__-recommendedAttributesMoreOptions__-ADDITIONAL_GROUP__-additionalAttributesMoreOptions__-w0"]/span[2]')
        # 		#showmore.click()
        # 		driver.execute_script("arguments[0].click();",showmore)
        # 		time.sleep(2)
        # 		#driver.execute_script('$("#isbn").val($("#editpane_skuNumber").val())')
        # 		#driver.execute_script("$(\"Input[Fieldname='Personalized']\").val(\"No\")")
        # 		#driver.execute_script("$(\"Input[Fieldname='Signed']\").val(\"No\")")
        # 		#driver.execute_script("$(\"Input[Fieldname='Vintage']\").val(\"No\")")
        # 		#driver.execute_script("$(\"Input[Fieldname='Ex Libris']\").val(\"No\")")
        # 		driver.execute_script("$(\"Input[Fieldname='Book Title']\").val($(\"Input[name='title']\").val())")
        # 		driver.execute_script("$('input[name=\"attributes.Vintage\"][value=\"No\"]').click()")
        # 		driver.execute_script("$('input[name=\"attributes.Personalized\"][value=\"No\"]').click()")
        # 		driver.execute_script("$('input[name=\"attributes.Custom Bundle\"][value=\"No\"]').click()")
        # 		driver.execute_script("$('input[name=\"attributes.Ex Libris\"][value=\"No\"]').click()")
        # 		driver.execute_script("$('input[name=\"attributes.Signed\"][value=\"No\"]').click()")

        except Exception as e:
            print(e)
            pass

            # <input type="checkbox" name="attributes.Department" data-index="0" value="Teens" checked="" id="wc0-w0-LIST_PAGE_WRAPPER__-LIST_PAGE_GRASSHOPPER_BODY__-ATTRIBUTES__-ATTRIBUTES_GH__-ATTRIBUTES_DIY_VIEW__-RECOMMENDED_GROUP__-RECOMMENDED_ATTRIBUTE_GRID__-topRecommendedAttrList.8__-Teens" data-w-onclick="selectFromFrequentValues|wc0-w0-LIST_PAGE_WRAPPER__-LIST_PAGE_GRASSHOPPER_BODY__-ATTRIBUTES__-ATTRIBUTES_GH__-ATTRIBUTES_DIY_VIEW__-RECOMMENDED_GROUP__-RECOMMENDED_ATTRIBUTE_GRID__-topRecommendedAttrList.8__">

            try:
                # regularButton = driver.find_element_by_xpath("//*[@id='wc0-w0-LIST_PAGE_WRAPPER__-LIST_PAGE_GRASSHOPPER_BODY__-ATTRIBUTES__-ATTRIBUTES_GH__-ATTRIBUTES_DIY_VIEW__-RECOMMENDED_GROUP__-RECOMMENDED_ATTRIBUTE_GRID__-topRecommendedAttrList.1__-Regular']")
                # if regularButton:
                # 	driver.execute_script("arguments[0].click();",regularButton)
                # regularButton = driver.find_element_by_xpath('//*[@id="wc0-w0-LIST_PAGE_WRAPPER__-LIST_PAGE_GRASSHOPPER_BODY__-ATTRIBUTES__-ATTRIBUTES_GH__-ATTRIBUTES_DIY_VIEW__-RECOMMENDED_GROUP__-RECOMMENDED_ATTRIBUTE_GRID__-topRecommendedAttrList.0__-Regular"]	')
                # if regularButton:
                # 	driver.execute_script("arguments[0].click();",regularButton)
                regularButton = driver.find_element(
                    "xpath", "//*[contains(text(), 'Regular')]"
                )
                if regularButton:
                    print(
                        "regularButton found!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    )
                    driver.execute_script("arguments[0].click();", regularButton)
                print("size type Regular clicked")
            except Exception as e:
                pass
                # print("Regular button not found")
                # Try to find the Save button and click it.  This will click all buttons that contain the text "Save"

print("skipped (" + str(len(skipped)) + "): " + str(skipped))
print("complete (" + str(len(complete)) + "): " + str(complete))
print("quitting chrome")
driver.quit()
