import os

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


def printResponse(string, endIn="\n"):
    print(colored(string, "green"), end=endIn)


def printGeneric(string):
    print(colored(string, "light_grey"))


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


def splitBySentenceLength(textIn, maxLength):
    text = textIn
    output = []
    i = 0 # char position
    j = 0 # sentences
    k = 0 # chars since last sentence
    while len(text) > 0:
        for char in text:
            i += 1
            k += 1
            if "." == char or "!" == char or "?" == char:
                j += 1
                if k < 32:
                    j -= 1
                if j == maxLength:
                    outputText = text[0:i]
                    output.append(outputText)
                    text = text.replace(outputText, "")
                    i = j = 0
                k = 0
    return output

