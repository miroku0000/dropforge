import csv
import os
import glob

username = os.getenv("USERNAME")

files = glob.glob("C:\\Users\\"+ username +"\\Downloads\\zik*.csv", 
                   recursive = False)
for filename in files:
    try:
        # filename="C:\\Users\\"+ username +"\\Downloads\\ZikAnalytics.csv"
        if not os.path.isfile(filename):
            print(filename)
            print("is not a path")
            exit(0)
        with open(filename, mode='r', encoding="ISO-8859-1") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    #print(f'Column names are {", ".join(row)}')
                    line_count += 1
                else:
                    try:
                        if "Supplier price" in row and row["Supplier price"] and float(row["Supplier price"]) > 25.0 and float(row["Supplier price"]) < 200.0:
                            print(row["ASIN"])
                        else:
                            if not "Supplier price" in row:
                                print(row["ASIN"])
                        #print(row["Supplier price"])
                    except Exception as e:
                        pass
                line_count += 1
    except Exception as e:
        # print(e)
        pass