import docx2txt
import random
import re
import urllib

from pptx import Presentation
from PyPDF2 import PdfReader

from modules.utils import *


def getPDFText(filePath):
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


def getPPTXText(filePath):
    content = ""
    pres = Presentation(filePath)
    for slide in pres.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                content += shape.text + " "
    return content

def getFileText(filePath):
    f = open(filePath, "r")
    content = f.read()
    f.close()
    return content


fileMap = {
    "pdf": getPDFText,
    "docx": getDOCXText,
    "pptx": getPPTXText,
}


def getFileContents(filePath):
    k = filePath.split(".")
    fileExtension = k[len(k) - 1]
    content = ""
    if fileMap[fileExtension]:
        functionCall = fileMap[fileExtension]
        content = functionCall(filePath)
    else:
        content = getFileText(filePath)
    return cleanupString(content)

