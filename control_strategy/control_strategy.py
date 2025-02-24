from MyMQTT import *
import time
import requests
from datetime import datetime
import traceback
import numpy as np

class Control_strategy():
    def __init__(self, clientID, broker, port, topic_subscribe,topic_publish):
        self.topic_subscribe=topic_subscribe
        self.topic_publish=topic_publish
        self.client = MyMQTT(clientID,broker,port,self)
        self.message = {"measurement":{},"alert":0}
        self.alert = 0

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
            body=json.loads(payload)
            deviceID=body["bn"]
            print(f"Data received from SENSOR-{deviceID} to {topic} at {datetime.now()}")

        except json.JSONDecodeError as j:
            print(f"JSON DecodeError for data sent at {time.ctime()}: {j} ")

        self.alert = 0
        if body["e"][0]["n"] == "bs":
            if body["e"][0]["v"] < 92:
                self.alert = 1
                self.publish(body,1)
        elif body["e"][0]["n"] == "bp_systolic":
            if (body["e"][0]["v"] > 140 and body["e"][1]["v"] > 95) or (body["e"][0]["v"] < 115 and body["e"][1]["v"] < 65):
                self.alert = 1
                self.publish(body,1)
        elif body["e"][0]["n"] == "hr":
            if body["e"][0]["v"] < 60 or body["e"][0]["v"] > 110:
                self.alert = 1
                self.publish(body,1)            
        self.publish(body,0)

    def startSim(self):
        self.client.start()
        self.client.mySubscribe(self.topic_subscribe)

    def publish(self, measurement, idx_topic):
        self.message["measurement"] = measurement
        self.message["alert"] = self.alert
        topic = self.topic_publish[idx_topic]
        self.client.myPublish(topic, self.message)
        print(f"Message sent to {topic_publish[idx_topic]} at {datetime.fromtimestamp(time.time())}")

    def stopSim(self):
        self.client.stop()


if __name__ == '__main__':
    print(
"""
==============================================
      Welcome to the CONTROL STRATEGY 
==============================================
The following commands are available:
- CTRL+C: to exit the program
==============================================
""")

    conf = json.load(open("configuration.json"))
    url = conf["catalog"]
    topic_publish = conf["serviceInfo"]["serviceDetails"][0]["topic"]
    #clientID = conf["serviceInfo"]["serviceName"] + str(conf["serviceInfo"]["serviceID"])
    clientID="ioTprojectID"+str(np.random.randint(1,10000000000))
    headers = {'Accept': 'application/json'}
    url_register=url+"registerService"
    url_update=url+"updateService"
    try:
        response = requests.post(url_register, json=conf["serviceInfo"], headers=headers)
        if response.status_code != 409: 
            response.raise_for_status() # Will raise an error for any 4xx/5xx status codes, except the 409 conflict error
            response = response.json()
            print(response["message"])
        else:
            print("The service is already present in the catalog, updating it...")

        #Ask for the broker info to the catalog
        r = requests.get(url+"broker", headers=headers)
        r.raise_for_status()
        r = r.json()
        broker = r["IP"]
        port = r["port"]

        #Ask for the devices info to the catalog
        topic_subscribe = []
        sensori = requests.get(url+"devicesBaseTopic", headers=headers) 
        sensori.raise_for_status()
        sensori = sensori.json()
        topic1 = sensori["topic_template"].format(measureType="BP",deviceID="+")
        topic2 = sensori["topic_template"].format(measureType="BS",deviceID="+")
        topic_subscribe.append(topic1)
        topic_subscribe.append(topic2) 

        #Ask for the services info of the signal processing to the catalog
        ID_sp=2
        signal_processing = requests.get(url+f"searchByService?ID={ID_sp}", headers=headers)
        #If the service to which the catalog wants to communicate is not found no exception is raised and the program will continue
        if signal_processing.status_code != 404: 
            signal_processing.raise_for_status() # Will raise an error for any 4xx/5xx status codes, except the 404 error
            signal_processing = signal_processing.json()
            flag=0
            availableServices=signal_processing["availableServices"]
            if "MQTT" in availableServices:
                for element in signal_processing["serviceDetails"]:
                    if element["serviceType"]=="MQTT":
                            for topic in element["topic"]:
                                 if "hr" in topic:
                                    topic_subscribe.append(topic)
                                    flag=1
                                    break #out of inner for           
                    if flag==1:
                        break            
        else:
            print(f"The CONTROL STRATEGY cannot communicate with the service with ID: {ID_sp}")

        cs_service = Control_strategy(clientID, broker, port, topic_subscribe,topic_publish)
        cs_service.startSim()

        while True:
            response = requests.put(url_update, json=conf["serviceInfo"], headers=headers)
            response.raise_for_status()  # Will raise an error for any 4xx/5xx status codes
            response = response.json()
            time.sleep(30)  

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors during POST or PUT requests
        body = e.response.json()
        print(f"\nHTTP Error - {body['status']}: {body['error']}") 

    except Exception as e:
        print(f"An exception occurred for data sent at {datetime.now()}: {e}\n {traceback.format_exc()}")

    except KeyboardInterrupt:
        print("Exiting program...")
                   
    if "cs_service" in locals():
        cs_service.stopSim()
    
    
    
            



    