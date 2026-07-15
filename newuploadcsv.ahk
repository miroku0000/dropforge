#Requires AutoHotkey v2.0

SetTitleMatchMode 3
SetTitleMatchMode "Slow"

WinActivate "Open"
ControlSetText("Open","","[CLASSNN:Edit1]","D:\zikprocessor\data\ebayitemspecifics\upload.csv")
ControlClick("Open","","Button1")
