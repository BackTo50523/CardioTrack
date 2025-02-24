import json
import numpy as np
from MyMQTT import *
import time
from datetime import datetime
import neurokit2 as nk
import matplotlib.pyplot as plt
import scipy.signal as signal
import requests
import traceback



class ProcessECGData():
    def __init__(self, clientID, broker, port, topic_subscribe,topic_publish):
        self.topic_subscribe=topic_subscribe
        self.topic_publish=topic_publish
        

        self.client = MyMQTT(clientID,broker,port,self)

    def notify(self,topic,payload):
        '''
        message_received:
            {
                "bn":{deviceID}
                "e":[
                    {"n": "ecg", "u": "mV", "t": {sampletime}, "v": {samplevalue}},
                    ...
                ]
            }
        '''
        
        try:
            senML_ecg = json.loads(payload)
            deviceID=senML_ecg["bn"]
            print(f"Data received from SENSOR-{deviceID} to {topic} at {datetime.now()}")

            #Calculate the sampling frequency from the samples received
            N=len(senML_ecg["e"]) #Number of samples
            T=int(senML_ecg["e"][-1]["t"]-senML_ecg["e"][0]["t"]) #Time interval
            fc=N/T

            ecg_array=[]
            for event in senML_ecg["e"]:
                if event["n"] =="ecg":
                    v=event["v"]
                    ecg_array.append(v)

            ecg_array = np.array(ecg_array)

            #Each chunk of the ECG is processed and parameters such as hr and stdrr are calculated
            #(Note: the time associated to the parameters is the time of the last sample of ECG)
            heart_rate,std_rr = processing_ECG(ecg_array,fc)
            t=senML_ecg["e"][-1]["t"]


            self.publish(deviceID,t,heart_rate,std_rr)

        except json.JSONDecodeError as j:
            print(f"JSON DecodeError for data sent at {datetime.now()}: {j} ")

        except Exception as e:
            print(f"An exception occurred for data sent at {datetime.now()}: {e}\n {traceback.format_exc()}")
        

    def startSim(self):
        self.client.start()
        self.client.mySubscribe(self.topic_subscribe)

    def publish(self, deviceID,t,heart_rate,std_rr):


        #Publish the HEART RATE - There is only one value for the entire chunk of ECG analyzed
        senML_hr = {
            "bn":deviceID,
            "e":[
                {"n": "hr", "u": "bpm", "t": t, "v": heart_rate}
            ]
        }
        self.client.myPublish(self.topic_publish[0], senML_hr)

        #Publish the STANDARD DEVIATION OF RR INTERVAL - There is only one value for the entire chunk of ECG analyzed
        senML_stdrr = {
            "bn":deviceID,
            "e":[
                {"n": "stdrr", "u": "ms", "t": t, "v": std_rr}
            ]
        }
        
        self.client.myPublish(self.topic_publish[1], senML_stdrr)
        print(f"Data sent from SIGNAL PROCESSING to {self.topic_publish[0]} and {self.topic_publish[1]} at {datetime.now()}")

    def stopSim(self):
        self.client.stop()




def processing_ECG(ecg_values,fc):
    conf=json.load(open('configuration_sp.json'))
    cutoff_frequency=conf["cutoff_frequency"]
    order_filter=conf["order_filter"]

    #To remove the trend at low frequencies, a butterworth filter is used
    clean_ecg=noise_removal(ecg_values,cutoff_frequency,fc,order_filter)

    #Calculate the R peaks
    signal, info=nk.ecg_peaks(clean_ecg,sampling_rate=fc)
    indices=info['ECG_R_Peaks']

    '''# For plotting only
    global plot_flag, data_to_plot
    plot_flag = True
    data_to_plot = (clean_ecg, indices)  # Store the processed ECG data'''


    #Convert the indices in time samples
    t_samples=indices/fc

    #Calculate the RR distance
    rr_array=np.diff(t_samples)

    #Calculate the STD-RR distance
    std_rr=np.std(rr_array*1000) #ms

    #Calculate the HEART RATE
    heart_rate=60/np.mean(rr_array) #bpm

    return heart_rate,std_rr



def noise_removal(simulated_ecg,cutoff_frequency, fc, order):
    nyquist = 0.5 * fc
    normalized_cutoff =  cutoff_frequency/ nyquist

    #Design of a Butterworth filter dual-pass filter 
    b, a = signal.butter(order, normalized_cutoff, btype='high') 

    #High pass filter application
    simulated_ecg = signal.filtfilt(b, a, simulated_ecg)
    return simulated_ecg


'''#For plotting only
def plot_data():
    global plot_flag, data_to_plot

    if plot_flag and data_to_plot is not None:
        ecg_signal, r_peaks = data_to_plot  # Unpack ECG signal and R-peaks indices

        plt.figure(figsize=(12, 5))
        plt.plot(ecg_signal, label="Filtered ECG", color="blue", linewidth=1)

        # Mark detected R-peaks
        plt.scatter(r_peaks, ecg_signal[r_peaks], color="red", label="R-peaks", marker="o")

        plt.xlabel("Samples")
        plt.ylabel("ECG Amplitude (mV)")
        plt.title("ECG Signal with Detected R-peaks")
        plt.legend()
        plt.grid()

        plt.show()

        plot_flag = False  # Reset the flag after plotting'''

if __name__ == '__main__':

    print(
"""
==============================================
      Welcome to the SIGNAL PROCESSING 
==============================================
The following commands are available:
- CTRL+C: to exit the program
==============================================
""")
    try:
        conf = json.load(open("configuration_sp.json"))
        catalog=conf["catalog"]
        serviceInfo=conf["serviceInfo"]
        topic_publish=serviceInfo["serviceDetails"][0]["topic"]


        #Headers of the requests to handle errors
        headers = {'Accept': 'application/json'}
        url_register=catalog+"registerService"
        url_update=catalog+"updateService"
    
        response = requests.post(url_register, json=serviceInfo, headers=headers)

        # Will raise an error for any 4xx/5xx status codes, except the 409 conflict error. In this case the program continues
        if response.status_code != 409: 
            response.raise_for_status() 
            response=response.json()
            print(response["message"])
        else:
            print("The service is already present in the catalog. Proceeding to update...")



        #Once the service is registered it requests the broker to the catalog
        url_broker=catalog+"broker"
        r=requests.get(url_broker, headers=headers)
        r.raise_for_status()
        r=r.json()

        clientID="IoTprojectID" + str(np.random.randint(1,1000000000))
        broker=r["IP"]
        port=r["port"]
        
        #Ask for base topic of devices to the catalog
        url_topic=catalog+"devicesBaseTopic"
        r=requests.get(url_topic, headers=headers)
        r.raise_for_status()
        r=r.json()
        
        #Format for the type of measure needed, in this case ECG
        topic_subscribe=[r["topic_template"].format(measureType="ECG",deviceID="+")]


        ecg_processing=ProcessECGData(clientID,broker,port,topic_subscribe, topic_publish)
        ecg_processing.startSim()

        #In the main thread a PUT request is made to the catalog every 30 seconds to update the service infos
        while True:
            response = requests.put(url_update, json=serviceInfo, headers=headers)
            response.raise_for_status()  # Will raise an error for any 4xx/5xx status codes
            time.sleep(30)  

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors during POST or PUT requests
        body = e.response.json()
        print(f"\nHTTP Error - {body['status']}: {body['error']}\nSERVICE INFO: {serviceInfo}") 
    
    except json.JSONDecodeError as j:
        print(f"JSONDecodeError: {j}")

    except Exception as e:
        if "ecg_processing" in locals():
            ecg_processing.stopSim()
        print(f"An exception occurred for data sent at {datetime.now()}: {e}\n {traceback.format_exc()}")
    
    except KeyboardInterrupt:
        print("Exiting program...")
    
    if "ecg_processing" in locals():
        ecg_processing.stopSim()
            

    


    
    



            



