import zipfile
import glob
import os

username = os.getenv("USERNAME")

pathtozipfile=glob.glob("C:\\Users\\" + username + "\\Downloads\\AspectFinder_*_Basic_file_per_category.zip")[0]
#pathtozipfile = "C:\\Users\\mirok\\Downloads\\AspectFinder_rafl-10_179627_Basic_file_per_category.zip"
extractdir = "D:\\zikprocessor\\data\\aspectfinder"
with zipfile.ZipFile(pathtozipfile, 'r') as zip_ref:
    zip_ref.extractall(extractdir)
