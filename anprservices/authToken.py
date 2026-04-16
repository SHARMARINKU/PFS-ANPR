import requests

class MobileAuth(requests.auth.AuthBase):
    def __init__(self,mac_address,base_url):
        user_info ={"applicationId":"ASG000002AA",
                "deviceId":mac_address,
                "userName":"omdev.singh@jbmgroup.com",
                "password":"12345",
                "fireBaseToken":"b18e-5186b0b59207-69f22127-nnnn"}
        response = requests.post(f'{base_url}/anpr-fleet/authentication/mobile/login/create-token/',user_info,timeout=5)
        if response.status_code == 200:
            data = response.json()
            self.token = data['metaData']['accessTokenInformation']['accessToken']
        else:
            print(f"Error: {response.json()}")

    def __call__(self, res,contnet_type=None):
        res.headers["authorization"] = "Bearer " + self.token
        # res.headers["Content-Type"] = "multipart/form-data"
        return res      
          