import docx2txt
import random
import re
import urllib

from PyPDF2 import PdfReader

from modules.utils import *


def getPDFText(filePath):
    printInfo("PDF support is very primative!")
    pdfFile = PdfReader(filePath)
    pdfPages = len(pdfFile.pages)
    pdfText = ""
    i = 0
    while i < pdfPages:
        pdfText += pdfFile.pages[i].extract_text()
        i += 1
    return pdfText


def getDOCXText(filePath):
    return docx2txt.process(filePath)


def getFileText(filePath):
    f = open(filePath, "r")
    content = f.read()
    f.close()
    return content


fileMap = {
    "pdf": getPDFText,
    "docx": getDOCXText,
}

def getFileContents(promptIn):
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    newPrompt = promptIn.replace("'" + filePath + "'", "")
    k = filePath.split(".")
    fileExtension = k[len(k) - 1]
    content = ""
    if fileMap[fileExtension]:
        functionCall = fileMap[fileExtension]
        content = functionCall(filePath)
    else:
        content = getFileText(filePath)
    return cleanupString(content)
