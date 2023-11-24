import os

from termcolor import colored

################################################
################## BEGIN CHAT ##################
################################################

# https://pypi.org/project/termcolor/


def printInput(string):
    strInput = input(colored(string, "white", attrs=["bold"]))
    return strInput


def printInfo(string):
    print(colored(string, "yellow"))


def printResponse(string):
    print(colored(string, "green"))


def printGeneric(string):
    print(colored(string, "light_grey"))


def printWarning(string):
    print(colored(string, "red"))


def printSuccess(string):
    print(colored(string, "green"))


def printDebug(string):
    print(colored(string, "light_grey"))


def printSeparator():
    printGeneric("-------------------------------------------------------------")


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", "")          # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


def detectModels(pathtomodels, ignoredModelsIn):
    modelsList = []
    modelsBuilder = ""
    ignoredModelsList = ignoredModelsIn.split(",")
    for fileName in os.listdir(pathtomodels):
        if fileName.endswith(".yaml"):
            strModelName = fileName.split(".")
            if strModelName[0] not in ignoredModelsList:
                modelsList.append(strModelName[0])
    i = 0
    while i < len(modelsList):
        if i + 1 == len(modelsList):
            modelsBuilder = modelsBuilder + modelsList[i]
        else:
            modelsBuilder = modelsBuilder + modelsList[i] + ", "
        i += 1
    return modelsBuilder


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
