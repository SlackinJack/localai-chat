import glob
import os
import re


from pathlib import Path


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))


def readFile(pathIn, filenameIn = "", splitter = ""):
    testpath = Path(pathIn + filenameIn)
    if testpath.is_file() is not True:
        if len(filenameIn) == 0:
            pathInSplit = pathIn.split("/")
            filenameIn = pathInSplit[len(pathInSplit) - 1]
        writeFile(pathIn, filenameIn)
    openFile = open(pathIn + filenameIn, "r")
    theFile = openFile.read()
    openFile.close()
    if len(splitter) > 0:
        theFile = theFile.split(splitter)
    return theFile


def writeFile(pathIn, filenameIn):
    testpath = Path(pathIn + filenameIn)
    if testpath.is_file() is not True:
        open(pathIn + filenameIn, "w").close()
    return


def appendFile(pathIn, filenameIn, strIn):
    testpath = Path(pathIn + filenameIn)
    if testpath.is_file() is not True:
        writeFile(pathIn, filenameIn)
    openFile = open(pathIn + filenameIn, "a")
    openFile.write(strIn)
    openFile.close()
    return


def deleteFile(pathIn, filenameIn):
    testpath = Path(pathIn + filenameIn)
    if testpath.is_file() is not True:
        printDebug("Tried to delete a non-existent file at: " + str(testpath))
    else:
        os.remove(testpath)
    return


# unused for now
def getPathTree(pathIn):
    fileTree = []
    for name in glob.glob(pathIn + "/**", recursive=True):
        fileTree.append(name)
    return fileTree


