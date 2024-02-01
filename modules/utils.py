import os
import psutil
import random
import re
import time

from termcolor import colored
# https://pypi.org/project/termcolor/


configuration = dict()


def initConfig(fileConfiguration):
    for line in fileConfiguration:
        if len(line) > 0 and not line.startswith("#") and not checkEmptyString(line):
            key = line.split("=")[0]
            value = line.split("=")[1]
            configuration[key] = value


def printInput(string):
    strInput = input(colored(string, "white", attrs=["bold"]))
    return strInput


def printResponse(string, endIn="\n"):
    print(colored(string, "green"), end=endIn)
    return


def printGeneric(string):
    print(colored(string, "light_grey"))
    return


def printGreen(string):
    print(colored(string, "light_green"))
    return


def printRed(string):
    print(colored(string, "light_red"))
    return


def printError(string):
    if int(configuration["DEBUG_LEVEL"]) >= 1:
        print(colored(string, "red"))
    return


def printInfo(string):
    if int(configuration["DEBUG_LEVEL"]) >= 2:
        print(colored(string, "yellow"))
    return


def printDebug(string):
    if int(configuration["DEBUG_LEVEL"]) >= 3:
        print(colored(string, "light_grey"))
    return


def printDump(string):
    if int(configuration["DEBUG_LEVEL"]) >= 4:
        print(colored(string, "dark_grey"))
    return


def printSeparator():
    printGeneric("-------------------------------------------------------------")
    return


def printSetting(isEnabled, descriptionIn):
    if isEnabled:
        printGeneric("[ON] " + descriptionIn)
    else:
        printGeneric("[OFF] " + descriptionIn)
    return


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", " ")         # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))[0]


def trimTextBySentenceLength(textIn, maxLength):
    i = 0               # char position
    j = 0               # sentences
    k = 0               # chars since last sentence
    flag = False        # deleted a "short" sentence this run
    for char in textIn:
        i += 1
        k += 1
        if ("!" == char or 
            "?" == char or 
            "." == char and 
                (not textIn[i - 1].isnumeric() or 
                (i + 1 <= len(textIn) - 1 and not textIn[i + 1].isnumeric()))
            ):
            j += 1
            if k < 24 and not flag:
                j -= 1
                flag = True
            if j == maxLength:
                return textIn[0:i]
            k = 0
            flag = False
    return textIn


def checkEmptyString(strIn):
    blanks = [" ", "\t", "\n", "\v", "\r", "\f"]
    for s in strIn:
        if s not in blanks:
            return False
    return True


def killLlama():
    hasResult = False
    for process in psutil.process_iter():
        if process.name() == "llama":
            process.kill()
            printDebug("llama has been killed off!")
            hasResult = True
            time.sleep(1)
    if not hasResult:
        printError("Couldn't kill the llama process! Are you on the same machine as LocalAI?")
        printError("(You can ignore this if llama hasn't been started yet.)")
    return

