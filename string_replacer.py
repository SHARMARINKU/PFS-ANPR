"""
Purpose: ANPR String Replacer Script - FILE-06    
Author: Rinku Sharma
Edited by: Rinku Sharma
Device : Ubuntu server
Project: GANTRY ANPR

"""


import gc

class IndianPlateNumberCorrectionService():
  
    def __init__(self):
        super().__init__()
        self.__L0 = ["Q", "0", "O", "B"]
        self.__L1 = ["J", "1"]
        self.__L2 = ["H", "8", "X"]
        self.__L3 = ["W", "M"]
        self.__L4 = ["N", "M"]


    def getCorrectedPlateNumber(self, data):
        try:

            originalPlateNumber = data["plate_number"].upper()
            
            
            if originalPlateNumber.startswith("R") and originalPlateNumber[1]!="J":
                originalPlateNumber = "H"+originalPlateNumber
            if originalPlateNumber.startswith("J") and originalPlateNumber[1]!="H" :
                originalPlateNumber = "R"+ originalPlateNumber
            if originalPlateNumber.startswith("B") and originalPlateNumber[1]!="R":
                originalPlateNumber = "P"+ originalPlateNumber
            detectedPlateNumber = list(originalPlateNumber)
            
            if len(detectedPlateNumber)>=3:
                if detectedPlateNumber[0] == "D":
                    if detectedPlateNumber[1] == "J" and detectedPlateNumber[2] == "L":
                        detectedPlateNumber.remove("J")
                if detectedPlateNumber[0]=="H" and detectedPlateNumber[1]=="H" and detectedPlateNumber[2]=="R":
                    detectedPlateNumber.remove("H")
                if detectedPlateNumber[0]=="H" and (detectedPlateNumber[1]=="R" or detectedPlateNumber[1]=="B") and detectedPlateNumber[2]=="H":
                    first_index = detectedPlateNumber.index('H')
                    second_index = detectedPlateNumber.index('H', first_index + 1)
                    detectedPlateNumber.pop(second_index)
                if detectedPlateNumber[0]=="H" and detectedPlateNumber[1]=="H" and detectedPlateNumber[2]=="B":
                    detectedPlateNumber[2]="8"
                    detectedPlateNumber[1]="R"
                if detectedPlateNumber[0]=="P" and detectedPlateNumber[1]=="B" and detectedPlateNumber[2]=="B":
                    detectedPlateNumber.remove("B")
                if detectedPlateNumber[0]=="8" and detectedPlateNumber[1]=="R":
                    detectedPlateNumber[0]="H"
                
                if detectedPlateNumber[0]=="R" and detectedPlateNumber[1]=="J" and detectedPlateNumber[2]=="J":
                    detectedPlateNumber.remove("J")

                if detectedPlateNumber[2]=="A":
                    detectedPlateNumber[2]="4"
                
            lengthOfDetectedPlateNumber = len(detectedPlateNumber)

            if lengthOfDetectedPlateNumber>10:
                if detectedPlateNumber[0]=="L" and detectedPlateNumber[1]=="1" and detectedPlateNumber[2]=="L":
                    detectedPlateNumber.insert(0,"D")
                elif detectedPlateNumber[0]=="L" and detectedPlateNumber[1]!="1":
                    detectedPlateNumber.insert(0,"N")
                detectedPlateNumber = detectedPlateNumber[0:10]

            if detectedPlateNumber[0] == "D" and detectedPlateNumber[1] == "L" and detectedPlateNumber[2] == "1" and \
                    detectedPlateNumber[3] == "J":
                detectedPlateNumber[3] = "L"

            if len(detectedPlateNumber) >= 7 and len(detectedPlateNumber)<=10:
                if (detectedPlateNumber[0] in self.__L0) and detectedPlateNumber[
                    1] == "L":  # replace first char with D if it is "Q","0","O","B"
                    detectedPlateNumber[0] = "D"

                if (detectedPlateNumber[0] in self.__L2) and detectedPlateNumber[
                    1] in self.__L2:  # replace HH,H8,HU,HX------> HR
                    detectedPlateNumber[1] = "R"

                if (detectedPlateNumber[0] in self.__L3) and detectedPlateNumber[1] == "L":  # replace WL,ML------> NL
                    detectedPlateNumber[0] = "N"

                if (detectedPlateNumber[0] in self.__L1) and detectedPlateNumber[
                    1] == "L":  # replace JL,1L,WL------> DL
                    detectedPlateNumber[0] = "D"

                if (detectedPlateNumber[0] in self.__L1) and detectedPlateNumber[
                    1] == "R":  # replace JR,1R,WR------> HR
                    detectedPlateNumber[0] = "H"

                if (detectedPlateNumber[0] == "W") and detectedPlateNumber[1] == "R":  # replace WR------> HR
                    detectedPlateNumber[0] = "H"

                if (detectedPlateNumber[0] in self.__L4) and detectedPlateNumber[1] == "B":  # replace MB-----> WB
                    detectedPlateNumber[0] = "W"

                if (detectedPlateNumber[0] in self.__L2) and detectedPlateNumber[
                    1] == "K":  # replace HK,8K,XK------> HR
                    detectedPlateNumber[1] = "h"
                    detectedPlateNumber[1] = "R"

                if (detectedPlateNumber[0] == "U") and detectedPlateNumber[1] == "X":  # replace  UX------> UK
                    detectedPlateNumber[1] = "K"

                if (detectedPlateNumber[0] in self.__L2) and detectedPlateNumber[
                    1] == "L":  # replace  HL,8L,UL,XL------> KL
                    detectedPlateNumber[0] = "K"
                if detectedPlateNumber[0] == "S" and detectedPlateNumber[1] == "X":  # replace  SX------> SK
                    detectedPlateNumber[1] = "K"

                if (detectedPlateNumber[0] in self.__L0) and (detectedPlateNumber[
                                                                    1] in self.__L1):  # replace first and second char with D  and L if it is ["Q","0","O","B"]["J","1"]
                    detectedPlateNumber[0] = "D"
                    detectedPlateNumber[1] = "L"
                if detectedPlateNumber[0] == "D" and (
                        detectedPlateNumber[1] in self.__L1):  # replace  DJ,D1,DW,------> DL
                    detectedPlateNumber[1] = "L"
                # if detectedPlateNumber[0] == "X" and detectedPlateNumber[1]:  # replace  XJ,X1,XW------> KL
                #     detectedPlateNumber[0] = "H"
                if detectedPlateNumber[-1] == "B":  # replace last char with 8 if it is ["B"]
                    detectedPlateNumber[-1] = "8"
                if detectedPlateNumber[-1] == "S":  # replace last char with 5 if it is ["s"]
                    detectedPlateNumber[-1] = "5"
                if detectedPlateNumber[-1] == "T":  # replace last char with T if it is ["1"]
                    detectedPlateNumber[-1] = "1"
                if detectedPlateNumber[-1] == "D" or detectedPlateNumber[-1] == "Q":  # replace last char with 0 if it is ["D","Q"]
                    detectedPlateNumber[-1] = "0"
                if detectedPlateNumber[-1] == "E":  # replace last char with 3 if it is ["E"]
                    detectedPlateNumber[-1] = "3"
                
                if detectedPlateNumber[-2] == "B":  # replace last char with 8 if it is ["B"]
                    detectedPlateNumber[-2] = "8"
                if detectedPlateNumber[-2] == "S":  # replace last char with 5 if it is ["S"]
                    detectedPlateNumber[-2] = "5"
                if detectedPlateNumber[3] == "Q":  # replace last char with 5 if it is ["S"]
                    detectedPlateNumber[3] = "0"
                if detectedPlateNumber[-2] == "T":
                    detectedPlateNumber[-2] = "1"
                if detectedPlateNumber[-2] == "D" or detectedPlateNumber[-2] == "Q":
                    detectedPlateNumber[-2] = "0"
                if detectedPlateNumber[-2] == "E":
                    detectedPlateNumber[-2] = "3"
                if detectedPlateNumber[-3] == "B":
                    detectedPlateNumber[-3] = "8"
                if detectedPlateNumber[-3] == "S":
                    detectedPlateNumber[-3] = "5"
                if detectedPlateNumber[-3] == "T":
                    detectedPlateNumber[-3] = "1"
                if detectedPlateNumber[-3] == "D" or detectedPlateNumber[-3] == "Q":
                    detectedPlateNumber[-3] = "0"
                if detectedPlateNumber[-3] == "E":
                    detectedPlateNumber[-3] = "3"
                if len(detectedPlateNumber) >= 9 and len(detectedPlateNumber)<=10:
                    if detectedPlateNumber[-5] == "2":
                        detectedPlateNumber[-5] = "Z"
                if len(detectedPlateNumber) == 10:
                    if detectedPlateNumber[-5] == "9":
                        detectedPlateNumber[-5] = "P"
                    if detectedPlateNumber[-5] == "8":
                        detectedPlateNumber[-5] = "B"
                    if detectedPlateNumber[-4] == "B":
                        detectedPlateNumber[-4] = "8"
                    if detectedPlateNumber[-4] == "S":
                        detectedPlateNumber[-4] = "5"
                    if detectedPlateNumber[-4] == "Z":
                        detectedPlateNumber[-4] = "2"
                    if detectedPlateNumber[-4] == "Q":
                        detectedPlateNumber[-4] = "0"

            if len(detectedPlateNumber)>=9  and len(detectedPlateNumber)<=10:
                for i in range(-1,-5,-1):
                    if detectedPlateNumber[i]=="A":
                        detectedPlateNumber[i]="4"


                
            data.update({"plate_number": "".join(e for e in detectedPlateNumber)})
            return data["plate_number"]
        except Exception as error:
            # [Information]: << logging error and aborting with return type. >>
            print(error)
            return data["plate_number"]
        finally:
            gc.collect()

if __name__ == "__main__":
    """
        # [Information]: << Driver Code. >>
        lets make thing's happen, grab a coffee and start coding.
        Best of Luck Mate... <3    
    """
    # [Information]: << start coding from here. >>
    a = IndianPlateNumberCorrectionService()
    print(a.getCorrectedPlateNumber({"plate_number": "HR73B9H4619"}))
    # AWW.... Look You Did It I Am Really Proud Of You....!!!
    pass




