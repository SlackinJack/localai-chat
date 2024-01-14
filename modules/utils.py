import os
import random
import re

from termcolor import colored


configuration = dict()


def initConfig(fileConfiguration):
    for line in fileConfiguration:
        if len(line) > 0 and not line.startswith("#"):
            key = line.split("=")[0]
            value = line.split("=")[1]
            configuration[key] = value


################################################
################## BEGIN CHAT ##################
################################################


# https://pypi.org/project/termcolor/


def printInput(string):
    strInput = input(colored(string, "white", attrs=["bold"]))
    return strInput


def printResponse(string, endIn="\n", modifier = False):
    if modifier and endIn == "":
        outString = string.lower()
        if random.randint(0, 100) > 15:
            match string:
                case "m":
                    outString = "mm"
                case "n":
                    outString = "nn"
                case "i":
                    outString = "ii"
                case "c":
                    outString = "k"
                case "l":
                    outString = "w"
                case "r":
                    outString = "w"
                case "y":
                    outString = "yyy"
                case "g":
                    outString = "gg"
                case ",":
                    if random.randint(0, 100) > 95:
                        outString = "..."
                case ".":
                    if random.randint(0, 100) > 95:
                        outString = "......"
                    elif random.randint(0, 100) > 90:
                        outString = "..."
                case "o":
                    if random.randint(0, 100) > 95:
                        outString = "OwO"
                    else:
                        outString = "oo"
                case "u":
                    if random.randint(0, 100) > 95:
                        outString = "UwU"
                    else:
                        outString = "uu"
                case "\n":
                    if random.randint(0, 100) > 90:
                        outString = "\nuhhhh "
                    elif random.randint(0, 100) > 90:
                        outString = "\nmmm "
                    elif random.randint(0, 100) > 90:
                        outString = "\numm "
        print(colored(outString, "green"), end=endIn)
        return
    else:
        print(colored(string, "green"), end=endIn)
        return


def printGeneric(string):
    print(colored(string, "light_grey"))
    return


def printGreen(string):
    print(colored(string, "light_green"))


def printRed(string):
    print(colored(string, "light_red"))


def printError(string):
    if int(configuration["DEBUG_LEVEL"]) >= 1:
        print(colored(string, "red"))


def printInfo(string):
    if int(configuration["DEBUG_LEVEL"]) >= 2:
        print(colored(string, "yellow"))


def printDebug(string):
    if int(configuration["DEBUG_LEVEL"]) >= 3:
        print(colored(string, "light_grey"))


def printDump(string):
    if int(configuration["DEBUG_LEVEL"]) >= 4:
        print(colored(string, "dark_grey"))


def printSeparator():
    printGeneric("-------------------------------------------------------------")


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", " ")          # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))[0]


def trimTextBySentenceLength(textIn, maxLength):
    i = 0 # char position
    j = 0 # sentences
    k = 0 # chars since last sentence
    for char in textIn:
        i += 1
        k += 1
        if "." == char or "!" == char or "?" == char:
            j += 1
            if k < 32:
                j -= 1
            if j == maxLength:
                return textIn[0:i]
            k = 0
    return textIn


def checkEmptyString(strIn):
    blanks = [" ", "\t", "\n", "\v", "\r", "\f"]
    for s in strIn:
        if s not in blanks:
            return False
    return True

