import os
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


def printInfo(string):
    if int(configuration["DEBUG_LEVEL"]) >= 2:
        print(colored(string, "yellow"))


def printResponse(string, endIn="\n", modifier = False):
    # TODO: break print
    if modifier and endIn == "":
        outString = string.lower()
        match string:
            case "o":
                outString = "OwO"
            case "u":
                outString = "UwU"
            case "m":
                outString = "mmm"
            case "i":
                outString = "ii"
            case "c":
                outString = "k"
            case "r":
                outString = "w"
        print(colored(outString, "green"), end=endIn)
        return
    else:
        print(colored(string, "green"), end=endIn)
        return


def printGeneric(string):
    print(colored(string, "light_grey"))
    return


def printError(string):
    if int(configuration["DEBUG_LEVEL"]) >= 1:
        print(colored(string, "red"))


def printSuccess(string):
    print(colored(string, "green"))


def printDebug(string):
    if int(configuration["DEBUG_LEVEL"]) >= 3:
        print(colored(string, "light_grey"))


def printSeparator():
    printGeneric("-------------------------------------------------------------")


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", "")          # remove all newlines
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

