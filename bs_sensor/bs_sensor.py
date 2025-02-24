#In this script, an ECG signal acquired from a sensor is simulated, corrupted by noise and trends. 
#Indeed, by running this script, you can visualize the generated signal for a defined period.
import matplotlib.pyplot as plt
import numpy as np
from MyMQTT import * 
import time
import requests
from datetime import datetime
import json
import os
import traceback

class PublishBSData():
    def __init__(self,clientID,broker,port):
        self.clientID=clientID
        self.broker=broker
        self.port=port
        self.publisher=MyMQTT(clientID,broker,port,None)

    def startSim(self):
        self.publisher.start()

    def publish(self,topic,data):
        self.publisher.myPublish(topic,data)

    def stopSim(self):
        self.publisher.stop()


class simulateSensorBS():

    def __init__(self,conf):

        self.deviceInfo=conf["deviceInfo"]
        self.catalog=conf["catalog"]
        #Ref for values: https://journals.sagepub.com/doi/10.1177/26324636221081585#:~:text=Monitoring%20and%20Target%20Saturation&text=British%20Thoracic%20Society%20Guideline%20for,to%2098%25%20for%20AHF%20patients.&text=This%20target%20should%20be%20reduced,risk%20of%20hypercapnic%20respiratory%20failure.
        self.bs_mean=conf["distribution_blood_saturation_mean"] #%
        self.bs_std=conf["distribution_blood_saturation_std"] #%


    def _simulate_BS(self):

        senML_bs={
            "bn": "",
            "e":[]
        }



        while True:
            sample = np.random.normal(self.bs_mean, self.bs_std, 1).item()

            # If the sample is within the [0, max_value] range, add it to the result list
            if 0 <= sample <= 100:
                #Simulate the time of the ECG and convert it in senML
                now=time.time()

                senML_bs["bn"]=self.deviceInfo["deviceID"]
                senML_bs["e"].append({"n": "bs", "u": "%", "t": now, "v": sample})
                break

        return senML_bs
    

    #To connect the sensor once it's started to the catalog
    def register_device(self): 
        url=self.catalog + "registerDevice"
        servicesDetails=self.deviceInfo["servicesDetails"]
        for service in servicesDetails:
            if service["serviceType"] == "MQTT":
                service["topic"][0]=service["topic"][0] +str(self.deviceInfo["deviceID"])
        self.deviceInfo["timestamp"]=time.time()

        headers = {'Accept': 'application/json'}
        
        response=requests.post(url, json=self.deviceInfo, headers=headers)
        #Will raise an exception only if the status code is of the families 4xx/5xx (Note: the exception will be caught by the main)
        response.raise_for_status() 
        # If the request is successful (no exception raised)
        response=response.json()
        print(response["message"])
    

    #If the registration of the device is successful, this method will start sending data and updating the device
    def start_bs_simulation(self):

        url=self.catalog + "updateDevice"
        deviceID=self.deviceInfo["deviceID"]
        servicesDetails=self.deviceInfo["servicesDetails"]
        for service in servicesDetails:
            if service["serviceType"] == "MQTT":
                topic_publish=service["topic"][0]
        a=0
        while True:
            headers = {'Accept': 'application/json'}
            #A put request is done every 30 seconds
            if a == 3:
                response = requests.put(url, json=self.deviceInfo,headers=headers)
                #Will raise an exception only if the status code is of the families 4xx/5xx (Note: the exception will be caught by the main)
                response.raise_for_status() 
                a=0 
            # If the request is successful (no exception raised)
            senMLbs = self._simulate_BS()
            bs_simulation.publish(topic_publish, senMLbs)
            print(f"Data sent from SENSOR-{deviceID} to {topic_publish} at {datetime.fromtimestamp(time.time())}")
            time.sleep(10)
            a=a+1

if __name__=='__main__':
    try:
        conf = json.load(open("configuration_bs_sensor.json"))

        #Load the config device template for registration and update to the catalog
        deviceInfo=conf["deviceInfo"]
        deviceID = os.getenv('deviceID')
        conf["deviceInfo"]["deviceID"]=int(deviceID)
        #Istanciate the device
        

        print(
f"""
==============================================
       Welcome to the BS sensor {deviceID}
==============================================
The following commands are available:
- CTRL+C: to exit the program
==============================================
""")

        device=simulateSensorBS(conf)
        url_catalog=conf["catalog"]+"broker"

        #Connect the device to the catalog
        device.register_device()

        #Ask for the broker endpoint to the catalog
        r=requests.get(url_catalog)
        r.raise_for_status()  
        r=r.json()

        clientID="IoTprojectID" + str(np.random.randint(1,1000000000))
        broker=r["IP"]
        port=r["port"]
        
        bs_simulation=PublishBSData(clientID,broker,port)
        bs_simulation.startSim()

        #Start to send data in loop and update device to the catalog
        device.start_bs_simulation()

    except ValueError as j:
        print(f"Value Error: {j}") 
    except json.JSONDecodeError as j:
        print(f"JSON Decode Error: {j}") 

    except requests.exceptions.HTTPError as e:
        body=e.response.json()
        print(f"\nHTTP {body['status']} {body['error']}URL: {url_catalog}\nDEVICE INFO: {deviceInfo}\n")
    except Exception as e:
        print(f"\nAn unexpected exception occurred: {e}\n{traceback.format_exc()}\n")
    except KeyboardInterrupt:
        print("Exiting the program...")

    if "bs_simulation" in locals():
        bs_simulation.stopSim()
    

    