from pydantic import BaseModel
from typing import List


class ValidateModel(BaseModel):
    '''This class is used to validate '''
   
    accountId:str 
    companyId:str 
    deviceId:str 
    cameraId:str 
    locationId:str 
    laneId:str 

    numberPlate:str 
    numberPlateConfidenceScore: float
    ocrConfidenceScore: float
    numberPlateColor:str 
    numberPlateImageUrl:str 

    vehicleType:str 
    vehicleOrientation:str 
    vehicleClassification:str 
    vehicleImageBoundingBox:List
    vehicleImageUrl:str

    anprProcessingTime:float
    edgeProcessingTime:float
    detectionDate:str 
    isCommercial:bool
    payLoad1:dict
    payload2:dict
    cameraView:str
    anprId:str
