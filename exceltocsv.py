import pandas as pd
import glob
import os




def exceltovsv(filename):    
    read_file = pd.read_excel (filename, sheet_name='Listings')
    write_file= filename.split(".")[0]+ ".csv"
    print(write_file)
    read_file.to_csv (write_file, index = None, header=True)
    os.remove(filename) 



for filename in  glob.glob("D:\\zikprocessor\\data\\ebayitemspecifics\\*.xlsx"):
    print(filename)
    exceltovsv(filename)
