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

class PublishBPData():
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


class simulateSensorBP():

    def __init__(self,conf):

        self.deviceInfo=conf["deviceInfo"]
        self.catalog=conf["catalog"]

        #Ref: https://www.ahajournals.org/doi/10.1161/JAHA.121.022288
        self.bp_mean=conf["distribution_blood_pressure_mean"] #mmHg
        self.bp_std=conf["distribution_blood_pressure_std"] #mmHg

        # Assume a correlation coefficient between systolic and diastolic measurements (ref https://pubmed.ncbi.nlm.nih.gov/18192832/)
        self.corr=conf["correlation"]  

    def _simulate_BP(self):

        #Covariance matrix to simulate correlation between the systolic and diiastolic pressures
        covariance = [
            [self.bp_std[0]**2, self.corr * self.bp_std[0] * self.bp_std[1]],
            [self.corr * self.bp_std[0] * self.bp_std[1], self.bp_std[1]**2]
        ]

        # Simulate samples from the bivariate normal distribution
        bp_samples = np.random.multivariate_normal(self.bp_mean, covariance, size=1)

        systolic = bp_samples[:, 0].item()
        diastolic = bp_samples[:, 1].item()

        now=time.time()
        senML_bp={
            "bn": self.deviceInfo["deviceID"],
            "e":[]
        }
        senML_bp["e"].append({"n": "bp_systolic", "u": "mmHg", "t": now, "v": systolic})
        senML_bp["e"].append({"n": "bp_diastolic", "u": "mmHg", "t": now, "v": diastolic})

        return senML_bp
            
    

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
    def start_bp_simulation(self):
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
            senMLbp = self._simulate_BP()
            bp_simulation.publish(topic_publish, senMLbp)
            print(f"Data sent from SENSOR-{deviceID} to {topic_publish} at {datetime.fromtimestamp(time.time())}")
            time.sleep(10)
            a=a+1


if __name__=='__main__':
    try:
        conf = json.load(open("configuration_bp_sensor.json"))

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

        #Istanciate the device
        device=simulateSensorBP(conf)

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
        
        bp_simulation=PublishBPData(clientID,broker,port)
        bp_simulation.startSim()

        #Start to send data in loop and update device to the catalog
        device.start_bp_simulation()

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

    if "bp_simulation" in locals():
        bp_simulation.stopSim()
    

    