#Link for the documentation of InfluxDBClient3: https://docs.influxdata.com/influxdb/cloud-serverless/reference/client-libraries/v3/python/#influxdbclient3query

from influxdb_client_3 import InfluxDBClient3, Point, WriteOptions, InfluxDBError, write_client_options, flight_client_options
import json
import cherrypy
from MyMQTT import *
import numpy as np
import time
import traceback
from datetime import datetime
import requests
import certifi


#https://github.com/InfluxCommunity/influxdb3-python/blob/70ceac05026a143cb8af953c306111149f89c06a/README.md?plain=1#L166-L200
fh = open(certifi.where(), "r")
cert = fh.read()
fh.close()



#==============================================#
#          WRITING AND QUERYING DATA
#==============================================#
# This class provides functionality for writing data to the database 
# This class provides functionality for querying data from the database 
# using SQL queries. 

class InfluxDBHandler():

    def __init__(self,host,bucket,token):
        #https://github.com/InfluxCommunity/influxdb3-python/blob/main/influxdb_client_3/write_client/client/write_api.py#L196
        self.write_options = write_client_options(success_callback=self.success,
                            error_callback=self.error)

        self.database = InfluxDBClient3(host=host,
                database=bucket,
                token=token, write_client_options=self.write_options, flight_client_options=flight_client_options(
        tls_root_certs=cert))

    # Define callbacks for write responses
    def success(self, conf, data: str):
        print(f"Data was successfully saved in the database. Batch: {conf}. Data: {data}")

    def error(self, conf, data: str, err: InfluxDBError):
        print(f"Cannot write batch: {conf}, data: {data} due: {err}")

    #This function writes the data to the database 
    def writeData(self,events,deviceID,patientID,alert):
        self.points=[] #This will contain a list of points to send to the database 
        for event in events:
            t=int(event["t"]* 1e9)
            v=event["v"]
            if event["n"] =="stdrr":
                point = Point("ECG") \
                .tag("deviceID", deviceID) \
                .tag("patientID", patientID) \
                .field(event["n"], v) \
                .time(t, write_precision="ns")

                self.points.append(point)

            elif event["n"] == "hr":
                point = Point("ECG") \
                .tag("deviceID", deviceID) \
                .tag("patientID", patientID) \
                .tag("alert", alert) \
                .field("hr", v) \
                .time(t, write_precision="ns")

                self.points.append(point)

            elif event["n"] == "bs":
                point = Point("BS") \
                .tag("deviceID", deviceID) \
                .tag("patientID", patientID) \
                .tag("alert", alert) \
                .field("bs", v) \
                .time(t, write_precision="ns")

                self.points.append(point)

            elif event["n"] == "bp_systolic" or event["n"] == "bp_diastolic":
                point = Point("BP") \
                .tag("deviceID", deviceID) \
                .tag("patientID", patientID) \
                .tag("alert", alert)\
                .field(event["n"], v) \
                .time(t, write_precision="ns")

                self.points.append(point)
        
        #Write data to the database and then set up for the next points
        self.database.write(self.points)
        
    def readData(self,params,patientID,measureType):

        #The query timestamp MUST BE in ns so time.time() in ms won't work
        time_start_value=int(params["time_start"])
        time_end_value=int(params["time_end"])


        #The types of measurements allowed are only ALL,ECG,BP,BS
        if measureType == 'all':
            queries = [
            f'''
            SELECT * FROM "{measurement}"
            WHERE time >= {time_start_value} AND time <= {time_end_value}
            AND "patientID" = '{patientID}'
            '''
            for measurement in ["ECG","BS","BP"]
            ]
        elif measureType == 'hr' or measureType == 'stdrr':
            queries = [f'''
            SELECT {measureType}
            FROM ECG
            WHERE time >= {time_start_value} AND time <= {time_end_value}
            AND "patientID" = '{patientID}' 
            ''']

        elif measureType == 'bp' or measureType == 'bs':
            queries = [f'''
            SELECT *
            FROM {measureType.upper()}
            WHERE time >= {time_start_value} AND time <= {time_end_value}
            AND "patientID" = '{patientID}' 
            ''']


        result_json=[]
        #The result is in panda dataframe, so it is converted to a string in json format
        for query in queries:
            result = self.database.query(query, mode="pandas", language="influxql")
            result_string=result.to_json(orient='records')
            result_json.extend(json.loads(result_string))

        return result_json

        



#-----------READING DATA FOR VISUALIZATION----------#
#The aim of this part is to retrieve data from the database 
# when a get request is made from the web app, so the user-interface. 
class DataForVisualization():
    exposed = True
    def __init__(self, db_handler):
        self.db_handler = db_handler  # Instance of InfluxDBHandler for querying

    def GET (self,*url,**params): #http://localhost:8080/database/{patientID}/{measure_type}?time_start={unix_start_ns}&time_end={unix_end_ns}

        if len(url)==3 and len(params)==2:
            patientID=url[1]
            measureType=url[2].lower().strip()
            measureTypes=["hr","stdrr","bp","bs","all"]
            if url[0] == 'database' and measureType in measureTypes:
                try:
                    result = self.db_handler.readData(params,patientID,measureType)
                except Exception as e:
                    raise cherrypy.HTTPError(500,f"During the query the following exception was raised: {e}\n{traceback.format_exc()}")
                
                if len(result) > 0:
                    result=json.dumps(result)
                    return result
                else:
                    raise cherrypy.HTTPError(404,"The query has returned no data, retry.")
            else:
                raise cherrypy.HTTPError(400,"Impossible to manage this URI")
        else:
            raise cherrypy.HTTPError(400,"Impossible to manage this URI")
                    
    
    def POST (self,*url,**params):
        pass
    def PUT (self,*url,**params):
        pass
    def DELETE (self,*url,**params):
        pass


def custom_error_page(status, message, traceback, version):
    if 'application/json' in cherrypy.request.headers.get('Accept'):
        return json.dumps({
            "status": status,
            "error": message,
        })
    else:
        raise

#----------- MANAGE DATA ----------#
#The aim of this part is to retrieve data from the message broker
#and to write them on the database


class  MQTTDataReceiver():
    def __init__(self, clientID, broker, port, topics, db_handler):
        self.topics=topics
        self.client = MyMQTT(clientID,broker,port,self)
        self.db_handler=db_handler #Instance of InfluxDBHandler for writing

    def notify(self,topic,payload):

        '''
        data received:
        {
        "alert":{0/1}
        "measurement":{senML_HEARTRATE/senML_BLOODS/senML_BLOODP/}
        }
        '''
        try:
            data=json.loads(payload)
            conf=json.load(open('config-adaptor.json'))

            #Accept json
            headers = {'Accept': 'application/json'}

            #If the topic is the one of the control strategy
            if "processed_data" in topic:
                measurement=data["measurement"]
                deviceID=measurement["bn"]
                events=measurement["e"]
                measureType=events[0]["n"]
                alert=data["alert"]

                #Based on the deviceID, patientID is retrieved from the catalog
                url=conf["catalog"]+f"searchByDeviceExtended/?ID={deviceID}"
                
                response=requests.get(url,headers=headers)
                response.raise_for_status()
                response=response.json()
                patientID=response["patient"]["patientID"]


                if measureType == "bs": #BloodSaturation 
                    self.db_handler.writeData(events,deviceID,patientID,alert)

                elif measureType == "bp_systolic": #BloodPressure
                    self.db_handler.writeData(events,deviceID,patientID,alert)

                elif measureType == "hr": #BloodPressure
                    self.db_handler.writeData(events,deviceID,patientID,alert)

            '''
            data received:
            {
            "bn":{deviceID}
            "e":[
                {"n": "std_rr", "u": "ms", "t": {sampletime}, "v": {samplevalue}},
                ...]
            }
            '''
            #If the topic is the one of the signal processing

            if "stdrr" in topic:
                deviceID=data["bn"]
                events=data["e"]

                #Based on the deviceID, patientID is retrieved from the catalog
                url=conf["catalog"]+f"searchByDeviceExtended/?ID={deviceID}"

                response=requests.get(url,headers=headers)
                response.raise_for_status()
                response=response.json()
                patientID=response["patient"]["patientID"]

                #With stdrr the alert is None
                self.db_handler.writeData(events,deviceID,patientID,alert=None)

        except requests.exceptions.HTTPError as e:
            body = e.response.json()
            print(f"\nHTTP {body['status']} {body['error']}URL: {e.response.url}\n")
            
        except json.JSONDecodeError as j:
            print(f"JSON DecodeError for data sent at {datetime.now()}: {j} ")

        except Exception as e:
            print(f"An exception occurred for data sent at {datetime.now()}: {e}\n {traceback.format_exc()}")



    def startClient(self):
        self.client.start()
        self.client.mySubscribe(self.topics)


    def stopClient(self):
        self.client.stop()




#-----------FUNCTIONS TO RUN IN DIFFERENT THREADS ----------#
def startWebService(db_handler):
    conf={
        '/':{
        'request.dispatch':cherrypy.dispatch.MethodDispatcher(),
        'tools.sessions.on':True,
        'error_page.default': custom_error_page
        }
    }

    config=json.load(open('config-adaptor.json'))
    #host=config["serviceInfo"]["serviceDetails"][0]["serviceIP"]
    #port=config["serviceInfo"]["serviceDetails"][0]["servicePort"]
    host="0.0.0.0"
    port=80

    webService=DataForVisualization(db_handler) 
    cherrypy.tree.mount(webService,'/',conf)
    cherrypy.config.update({
        "server.socket_host": host,  
        "server.socket_port": port        
    })
    cherrypy.engine.start()
    



def startMQTTCommunication(db_handler):
    conf=json.load(open('config-adaptor.json'))

    headers = {'Accept': 'application/json'}
    url_broker=conf["catalog"]+"broker"
    r=requests.get(url_broker,headers=headers)
    r.raise_for_status()
    r=r.json()
    broker=r["IP"]
    port=r["port"]

  
    topics=[]

    #Ask for the services info of the signal processing to the catalog
    ID_sp=2
    url_sp=catalog+f"searchByService/?ID={ID_sp}" #ID=2 of SP
    sp=requests.get(url_sp,headers=headers)
    
    #If the service to which the catalog wants to communicate is not found the ADAPTOR no exception is raised and the program will continue
    if sp.status_code != 404:
        sp.raise_for_status()
        sp=sp.json()
        for service in sp["serviceDetails"]:
            if service["serviceType"]=="MQTT":
                for topic_sp in service["topic"]:
                    if "stdrr" in topic_sp:
                        topics.append((topic_sp))
    else:
        print(f"The INFLUXDB ADAPTOR cannot communicate with the service with ID: {ID_sp}")

    #Ask for the services info of the control strategy to the catalog
    ID_cs=3
    url_cs=catalog+f"searchByService/?ID={ID_cs}" #ID=3 of CS
    cs=requests.get(url_cs,headers=headers)

    #If the service to which the catalog wants to communicate is not found the ADAPTOR no exception is raised and the program will continue
    if cs.status_code != 404:
        cs.raise_for_status()
        cs=cs.json()
        for service in cs["serviceDetails"]:
            if service["serviceType"]=="MQTT":
                for topic_cs in service["topic"]:
                    if "processed_data" in topic_cs:
                        topics.append((topic_cs))
    else:
        print(f"The INFLUXDB ADAPTOR cannot communicate with the service with ID: {ID_cs}")


    if len(topics) > 0:
        clientID= "IoT_Project2324243" + str(np.random.randint(1,10000))
        mqtt_client=MQTTDataReceiver(clientID,broker,port,topics,db_handler)
        mqtt_client.startClient()
        return mqtt_client

    


if __name__=="__main__":

    print(
"""
==============================================
    Welcome to the InfluxDB Adaptor
==============================================
The following commands are available:
- CTRL+C: to exit the program
==============================================
""")

    #-----------CONFIGURATION OF DB ADAPTOR----------#
    try:
        conf=json.load(open('config-adaptor.json'))
        host = conf["InfluxDb"]["host"]
        token = conf["InfluxDb"]["token"]
        org = conf["InfluxDb"]["org"]
        bucket = conf["InfluxDb"]["bucket"]
        catalog=conf["catalog"]
        serviceInfo=conf["serviceInfo"]


        db_handler = InfluxDBHandler(host, bucket, token)

        #Headers of the requests to handle errors
        headers = {'Accept': 'application/json'}
        url_register=catalog+"registerService"
        url_update=catalog+"updateService"
    
        response = requests.post(url_register, json=serviceInfo, headers=headers)
        if response.status_code != 409: 
            response.raise_for_status() # Will raise an error for any 4xx/5xx status codes, except the 409 conflict error
            response=response.json()
            print(response["message"])
        else:
            print("The service is already present in the catalog. Proceeding to update...")

        #Once the registration of the service is done, start the webserver and the MQTT communication
        startWebService(db_handler)
        mqtt_client = startMQTTCommunication(db_handler)

        while True:
            response = requests.put(url_update, json=serviceInfo, headers=headers)
            response.raise_for_status()  # Will raise an error for any 4xx/5xx status codes
            time.sleep(30)  

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors during POST or PUT requests
        body = e.response.json()
        print(f"\nHTTP {body['status']} {body['error']}URL: {e.response.url}\n")

    except json.JSONDecodeError as j:
        print(f"JSON Decode Error: {j}")
    
    except Exception as e:
        if "mqtt_client" in locals():
            if mqtt_client is not None:
                mqtt_client.stopClient()
        if cherrypy.engine.state == cherrypy.engine.states.STARTED:
            cherrypy.engine.exit()
        print(f"An exception occurred at {datetime.now()}: {e}\n {traceback.format_exc()}")
 

    except KeyboardInterrupt:
        print("Exiting program...")

        
    if "mqtt_client" in locals():
        if mqtt_client is not None:
            mqtt_client.stopClient()
    if cherrypy.engine.state == cherrypy.engine.states.STARTED:
        cherrypy.engine.exit()

        

        

    

