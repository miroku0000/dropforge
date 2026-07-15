import random
import string
import logging
import time
from datetime import datetime, timezone

logging.basicConfig(level=30)

from nodriver import *

import config
ebay_username = config.EBAY_USER
ebay_password = config.EBAY_PASS
daysold = 30
mindaysago = 10
maxtodelete = 833
# Assume the number deleted on average = the number listed.  Then we want to delete:
# 25000/30 = 833

import re


def period_to_days(period_str):
    # Define conversion factors
    DAYS_IN_YEAR = 365
    DAYS_IN_MONTH = 30

    # Initialize counters
    years = months = days = 0

    # Use regex to extract numbers before 'y', 'm', and 'd'
    match = re.findall(r"(\d+)\s*y", period_str)
    if match:
        years = int(match[0])
    match = re.findall(r"(\d+)\s*m", period_str)
    if match:
        months = int(match[0])
    match = re.findall(r"(\d+)\s*d", period_str)
    if match:
        days = int(match[0])

    # Calculate total days
    total_days = years * DAYS_IN_YEAR + months * DAYS_IN_MONTH + days
    return total_days


def days_ago(date_string):
    # Parse the input date string
    given_date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")

    # Set the timezone to UTC
    given_date = given_date.replace(tzinfo=timezone.utc)

    # Get the current date and time in UTC
    current_date = datetime.now(timezone.utc)

    # Calculate the difference
    difference = current_date - given_date

    # Return the number of days
    return difference.days


async def loginifneeded(tab):
    try:
        await tab.get("https://www.ebay.com/sh/lst/active")
        time.sleep(10)
        # Find login text field
        # print("finding the email input field")
        try:
            email = await tab.select("input[id=userid]")
            await email.click()
            # await email.send_keys(ebay_username)
            # await send_keys_slowly(email, ebay_username, 0.1)
        except Exception as e:
            # print("Attempting to Bypass the Bot Detection. I don't want to prove I am human so let's try again:")
            tab = await tab.get(
                "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&sgfl=gh&ru=https%3A%2F%2Fwww.ebay.com%2F"
            )
            email = await tab.select("input[id=userid]")
            pass
        await email.click()
        time.sleep(1)
        # print("Sending email address")
        # await email.send_keys(ebay_username)
        await send_keys_slowly(email, ebay_username, 0.1)
        time.sleep(1)
        # print("Finding continue button")
        continuebutton = await tab.find("signin-continue-btn", best_match=True)
        # print("Pressing continue button")
        await continuebutton.click()
        # print("continue button was clicked")
        time.sleep(10)
        # print("looking for password")
        password = await tab.select("input[id=pass]")
        time.sleep(1)
        # print("clicking password")
        await password.click()
        time.sleep(10)
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
    # driver = await uc.start()
    driver = await start(
        headless=False,
        user_data_dir="D:\\zikprocessor\\data\\profiles\\a",  # by specifying it, it won't be automatically cleaned up when finished
        # browser_executable_path="/path/to/some/other/browser",
        # browser_args=['--some-browser-arg=true', '--some-other-option'],
        lang="en-US",  # this could set iso-language-code in navigator, not recommended to change
    )

    tab = await driver.get(
        "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&sgfl=gh&ru=https%3A%2F%2Fwww.ebay.com%2F"
    )
    await loginifneeded(tab)
    # print("We should be logged in now")
    skiprest = False
    numdeleted = 0
    for offset in range(0, 5000, 200):
        if not skiprest:
            url = (
                "https://www.ebay.com/sh/lst/active?action=sort&sort=visitCount&offset="
                + str(offset)
            )
            await tab.get(url)
            # print("got page of listings")
            # Find the ebay id for each item that needs specifics updated
            # These are stored in the "data-id attribute of each tr with the class 'grid-row'
            # first fins all tr with class grid-row:
            # **********************
            # Remove all listings that are > daysold that have 0 views and sales
            # *********************
            # Remove all listings with views greater than 1:
            time.sleep(45)
            allids = await tab.query_selector_all("tr.grid-row")
            if len(allids) < 1:
                time.sleep(45)
                allids = await tab.query_selector_all("tr.grid-row")
                if len(allids) < 1:
                    skiprest = True

            # print(str(len(allids)))

            for id in allids:
                try:
                    daysago = 0
                    # data-id="226241280017"
                    theid = str(id)
                    # print("theid=" + theid)

                    # print(theid)
                    if "data-id=" in theid:
                        theid = theid.split('data-id="')[1]
                    # print(theid)
                    if '"' in theid:
                        theid = theid.split('"')[0]
                    # print("theid" + "|" + theid + "|")
                    listingdate = str(id)
                    if "column__scheduledStartDate" in listingdate:
                        daysago = period_to_days(
                            listingdate.split("column__scheduledStartDate")[1]
                            .split("(")[1]
                            .split(")")[0]
                        )

                    else:
                        daysago = 0
                    views = str(id)
                    views = int(
                        views.split(
                            '<button class="fake-link" type="button">0<span class="clipped">Link. Views'
                        )[1].split(".")[0]
                    )
                    # print(str(views))
                    sales = str(id)
                    if (
                        'shui-dt-column__soldQuantity shui-dt--right"><div class="cell-wrapper"><div class="shui-dt--text-column"><div >'
                        in sales
                    ):
                        sales = int(
                            sales.split(
                                'shui-dt-column__soldQuantity shui-dt--right"><div class="cell-wrapper"><div class="shui-dt--text-column"><div >'
                            )[1].split("</div>")[0]
                        )
                    else:
                        sales = 0

                    # print(
                    #     "**************\n"
                    #     + str(theid)
                    #     + " "
                    #     + " daysago: "
                    #     + str(daysago)
                    #     + " views: "
                    #     + str(views)
                    #     + " sales: "
                    #     + str(sales)
                    #     + "****************\n"
                    # )
                    # exit(0)
                    min_views_per_day = 0.1  # 0.1 means 1 view every 10 days
                    if daysago > mindaysago:
                        if (
                            views < (daysago * min_views_per_day)
                            and sales < 1
                            and numdeleted < maxtodelete
                        ):
                            numdeleted = numdeleted + 1
                            print(theid)
                            # print(
                            #     theid
                            #     + " "
                            #     + listingdate
                            #     + " daysago: "
                            #     + str(daysago)
                            #     + " views: "
                            #     + str(views)
                            #     + " sales: "
                            #     + str(sales)
                            # )
                except Exception as e:
                    # print(e)
                    pass


if __name__ == "__main__":
    # since asyncio.run never worked (for me)
    # i use
    loop().run_until_complete(main())
