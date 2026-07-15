import math
import sys
import os

# import random
import random
import os
import glob
import datetime
import calendar

username = os.getenv("USERNAME")


def getmaxpaidproductstolist():
    filename = "D:\\zikprocessor\\data\\numberlisted.txt"
    # This contains the remaining number of free listings
    f = open(filename, "r")
    numberlisted = int(f.read())
    remaining = 25000 - numberlisted
    # get current time
    d = datetime.datetime.now()
    # get the day of month
    day = int(d.strftime("%d"))
    numdaysinmonth = calendar.monthrange(
        datetime.datetime.now().year, datetime.datetime.now().month
    )[1]
    if numberlisted > day * (25000 / numdaysinmonth):
        return 0
    else:
        return min((day * (25000 / numdaysinmonth) - numberlisted) * 46, 4000)


def turboscan(
    numproducts=1000,
    min_price=35,
    max_price=100,
    min_sales=1,
    usetrendingkeywords="y",
    filterkeywords="",
):
    os.system("zikpreparetolist.bat")
    removezikdownloads()
    print("********************** Using trending categories, numsales=1")
    command = (
        "zikturboscanner.py --min_price "
        + str(min_price)
        + " --max_price  "
        + str(max_price)
        + " --min_sales  "
        + str(min_sales)
        + " --numberOfProducts "
        + str(numproducts)
    )
    if usetrendingkeywords == "y":
        command = command + " --usetrendingkeywords " + usetrendingkeywords
    if filterkeywords:
        command = command + ' -filterKeywords "' + freekeywords + '"'
    print(command)
    os.system(command)


def removezikdownloads():
    for fn in glob.glob("C:\\Users\\" + username + "\\Downloads\\zik*"):
        os.remove(fn)
        # print("skipping remove" +str(fn))


def checkresults(file_path):
    try:
        with open(file_path, "r", encoding="utf8", errors="ignore") as fp:
            for count, line in enumerate(fp):
                pass
            lines = count + 1
            return lines
    except Exception as e:
        return 0


def remove(file_path):
    try:
        remove(file_path)
    except Exception as e:
        pass


try:
    filename = "D:\\zikprocessor\\data\\dollarstolist.txt"
    f = open(filename, "r")
    dollarstolist = float(f.read())
    if dollarstolist > 8000:
        dollarstolist = dollarstolist - 8000.00
    productstolist = math.floor(dollarstolist / 10.1)
    if productstolist > 2000:
        productstolist = 2000
    if productstolist < 1000:
        productstolist = 1000
except Exception as e:
    productstolist = 1100

print(productstolist)
# os.system( "zikautopilotport.py --min_roi 0.1 --min_sales 2 -numProducts " + str(productstolist))
# os.system( "zikautopilotport.py  --bsrFrom 800 --bsrTo 1 -numProducts " + str(productstolist))

print("***Using free products, numsales=0")

freekeywords = "crafts, party supplies, party, paint brushes, craft kits, arts and crafts, knitting, knitting supplies, yarn, adult coloring book, paper craft kits, jewelry making kit, sewing kit, mosaic kit, paint with water kit, basket making supplies, candle making supplies, doll making supplies, floral arranging supplies, leathercraft supplies, mosaic making supplies, paper craft supplies, woodcrafts, yarn, knitting needles, crochet hooks, crochet kits, knitting kits, charms, engraving machines and tools, breading supplies, die-cut machines, die-cuts, die-cut accessories, albums, adhesive vinyl, drawing, easels, art paper, drawing, paintbrushes, outdoor decorative stones, crafts yarn, knitting kits, ball winders, weaving looms, wool roving,needle felting supplies, collectibles toy figure, collectibles display enclosure, collectibles lamp, collectibles, collectibles digital movie,collectibles book"

os.system(
    "zikturboscanner.py -minprice 25 -maxprice 200 -mins 0 -numProducts "
    + str(productstolist)
    + ' -filterKeywords "'
    + freekeywords
    + '"'
)
file_path = "c:\\users\\" + os.environ["USERNAME"] + "\\Downloads\\ZikAnalytics.csv"

maxpaidproducts = getmaxpaidproductstolist()
print("***********************************maxpaidproducts = " + str(maxpaidproducts))
lines = checkresults(file_path)
if lines < min(2000, productstolist) and maxpaidproducts:
    print("*******************")
    print(
        "not enough products "
        + str(lines)
        + " out of  "
        + str(productstolist)
        + " so trying again with some trending products"
    )
    print("*******************")
    turboscan(
        numproducts=maxpaidproducts,
        min_price=35,
        max_price=200,
        min_sales=1,
        usetrendingkeywords="y",
        filterkeywords="",
    )
    # os.system('zikpreparetolist.bat')
    # removezikdownloads()
    # print("***trying again Using trending categories, numsales=1")
    # os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 1 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
lines = checkresults(file_path)
if lines < min(200, maxpaidproducts) and maxpaidproducts:
    turboscan(
        numproducts=maxpaidproducts,
        min_price=35,
        max_price=200,
        min_sales=0,
        usetrendingkeywords="y",
        filterkeywords="",
    )
    # os.system('zikpreparetolist.bat')
    # removezikdownloads()
    # print("***Trying again with trending categories but sales=0")
    # removezikdownloads()
    # os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 0 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
lines = checkresults(file_path)
if lines < min(200, maxpaidproducts):
    turboscan(
        numproducts=maxpaidproducts,
        min_price=35,
        max_price=200,
        min_sales=1,
        usetrendingkeywords="n",
        filterkeywords=productstolist,
    )
    # os.system('zikpreparetolist.bat')
    # removezikdownloads()
    # print("***Trying again with trending categories but sales=1")
    # os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 1 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
# lines=checkresults(file_path)
# if lines< 200:
#   turboscan(numproducts=numproducts, min_price=25, max_price=100, min_sales=1, usetrendingkeywords ="n",filterkeywords=productstolist)
#   # print("***Trying again without trending categories sales=3")
#   # os.system('zikpreparetolist.bat')
#   # removezikdownloads()
#   # os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 3 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
lines = checkresults(file_path)
# if lines< 200:
#   turboscan(numproducts=numproducts, min_price=25, max_price=100, min_sales=2, usetrendingkeywords ="y",filterkeywords="")
# #     print("***Trying again without trending categories and less sales (2)")
# #     os.system('zikpreparetolist.bat')
# #     removezikdownloads()
# #     os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 2 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
# # lines=checkresults(file_path)
if lines < min(200, maxpaidproducts and maxpaidproducts):
    print("***Trying again without trending categories and less sales (1)")
    turboscan(
        numproducts=maxpaidproducts,
        min_price=35,
        max_price=200,
        min_sales=1,
        usetrendingkeywords="n",
        filterkeywords="",
    )
    # os.system('zikpreparetolist.bat')
    # removezikdownloads()
    # os.system( "zikturboscanner.py --min_price 25 --max_price 100 --min_sales 1 --usetrendingkeywords n --numberOfProducts " + str(productstolist))
if lines < min(200, maxpaidproducts) and maxpaidproducts:
    print(
        "***Trying again without trending categories and less sales (1) and maxprice=150"
    )
    turboscan(
        numproducts=maxpaidproducts,
        min_price=35,
        max_price=200,
        min_sales=1,
        usetrendingkeywords="n",
        filterkeywords="",
    )
    # os.system('zikpreparetolist.bat')
    # removezikdownloads()
    # os.system( "zikturboscanner.py --min_price 25 --max_price 200 --min_sales 1 --usetrendingkeywords y --numberOfProducts " + str(productstolist))
