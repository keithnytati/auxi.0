import sys
sys.path.insert(0, '/home/christoff/em/software/exmente.set.1.prototypes/EMOBjectsFromXSDGenerator/2.0/')
from EMObjectsFromXSDGenerator import *

templateFilePath_h = "/home/christoff/em/software/auxi.0/src/auxi/tools/code_generation/bind.cplusplusH.mako"
templateFilePath_cpp = "/home/christoff/em/software/auxi.0/src/auxi/tools/code_generation/bind.cplusplusCPP.mako"
templateFilePath_py = "/home/christoff/em/software/auxi.0/src/auxi/tools/code_generation/bind.pythonwrapper.mako"
templateFilePath_unittest_py = "/home/christoff/em/software/auxi.0/src/auxi/tools/code_generation/bind.python_unit_test.mako"

def generateClass(name):
    xsdFilePath = name[0].lower() + name[1:] + ".xsd"
    resultFilePath = "../" + name + ".h"
    generateEMObjectsFromTemplate(xsdFilePath, resultFilePath, templateFilePath_h, name)
    resultFilePath = "../" + name + ".cpp"
    generateEMObjectsFromTemplate(xsdFilePath, resultFilePath, templateFilePath_cpp, name) 
    resultFilePath = "../../../../auxi4py/modelling/business/" + name + "Wrapper.cpp"
    generateEMObjectsFromTemplate(xsdFilePath, resultFilePath, templateFilePath_py, name) 
    resultFilePath = "../../../../../test/auxi4py/modelling/business/unittest_" + name + ".py"
    generateEMObjectsFromTemplate(xsdFilePath, resultFilePath, templateFilePath_unittest_py, name) 

generateClass("Activity")
generateClass("Component")
generateClass("Entity")

generateClass("BasicActivity")
generateClass("CapitalLoanActivity")
generateClass("AssetPurchaseActivity")

generateClass("Clock")
generateClass("TimeBasedModel")