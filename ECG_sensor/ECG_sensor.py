#In this script, an ECG signal acquired from a sensor is simulated, corrupted by noise and trends. 
#Indeed, by running this script, you can visualize the generated signal for a defined period.
import neurokit2 as nk
import matplotlib.pyplot as plt
import numpy as np
from MyMQTT import * 
import time
import requests
from datetime import datetime
import os
import traceback

class PublishECGData():
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


class simulateSensorECG():

    def __init__(self,conf):

        self.deviceInfo=conf["deviceInfo"]
        self.catalog=conf["catalog"]

        self.fc=conf["sampling_frequency"] #Sampling frequency (Hz)
        self.T=conf["time_interval"] #Time interval of the simulation (s). It is selected to 12 seconds because the first 2 seconds will be removed

        self.distribution_heart_rate_mean=conf["distribution_heart_rate_mean"] #Mean of the heart rate distribution (bpm)
        self.distribution_heart_rate_std=conf["distribution_heart_rate_std"] #Standard deviation of the heart rate distribution (bpm)
        self.distribution_heart_rate_std_std=conf["distribution_heart_rate_std_std"] #Standard deviation of the heart rate standard deviation distribution (bpm)


    def _simulate_ECG(self,fc,T):
        #To simulate some variability in the hearth rate, it's value is extracted by a normal distribution with mean heart_rate_mean 
        #and standard deviation as std_dev_heart_rate
        heart_rate = np.random.normal(self.distribution_heart_rate_mean, self.distribution_heart_rate_std)

        #To simulate an hearth failure it is possible to extract the value of the heart rate std from a normal distribution
        #that has the mean equal to 0 and a defined standard deviation
        heart_rate_std = np.random.normal(0, self.distribution_heart_rate_std_std)

        #Simulate the ECG
        simulated_ECG = nk.ecg_simulate(duration=self.T, sampling_rate=self.fc,  heart_rate=heart_rate,  heart_rate_std=heart_rate_std)

        # At this point, the initial transient of the simulated signal is removed (first 2 seconds) 
        simulated_ECG = simulated_ECG[self.fc*2:]  

        senML_ecg={
            "bn": self.deviceInfo["deviceID"],
            "e":[]
        }

        new_time=time.time()
        delta_time=1/fc
        for sample in simulated_ECG:
            senML_ecg["e"].append({"n": "ecg", "u": "mV", "t": new_time, "v": sample})
            new_time=new_time+delta_time
            

        #plt.plot(simulated_ECG)
        #plt.title("Simulated ECG")
        #plt.xlabel("Time (samples)")
        #plt.ylabel("Amplitude")
        #plt.show()
        return senML_ecg
    

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
    def start_ecg_simulation(self):

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
            senMLecg = self._simulate_ECG(self.fc, self.T)
            ecg_simulation.publish(topic_publish, senMLecg)
            print(f"Data sent from SENSOR-{deviceID} to {topic_publish} at {datetime.fromtimestamp(time.time())}")
            time.sleep(10)
            a=a+1
            
               
            

if __name__=='__main__':
    try:
        conf = json.load(open("configuration_ecg_sensor.json"))

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
        device=simulateSensorECG(conf)

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
        
        ecg_simulation=PublishECGData(clientID,broker,port)
        ecg_simulation.startSim()

        #Start to send data in loop and update device to the catalog
        device.start_ecg_simulation()

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

    if "ecg_simulation" in locals():
        ecg_simulation.stopSim()
    

    

    