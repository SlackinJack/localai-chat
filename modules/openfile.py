from PyPDF2 import PdfReader

from modules.utils import *

def getPDFText(pathtofile):
    printWarning("PDF support is very primative!")
    pdfFile = PdfReader(pathtofile)
    pdfPages = len(pdfFile.pages)
    pdfText = ""
    while i < pdfPages:
        pdfText += pdfFile.pages[i].extract_text()
    return pdfText


def getFileText(pathtofile):
    f = open(filePath, "r")
    content = f.read()
    f.close()
    return content
