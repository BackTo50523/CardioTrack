import cherrypy
import json
import time
import requests
import traceback
#caterina

def search(list,query,type):
    for element in list:
        if element[type+'ID']==int(query["ID"]):
            return(json.dumps(element))
    print(f"\nError: No {type} found for the given ID\n")
    raise cherrypy.HTTPError(404,f"Error in CATALOG: No {type} found for such ID\n")

    
def search_extended(list,query,list2,list3):
    for device in list:            
        if device["deviceID"]==int(query["ID"]):
            for patient in list2:
                for device_patient in patient["devices"]:
                    if device_patient["deviceID"]==int(query["ID"]):
                        for cardiologist in list3:
                            if cardiologist["cardiologistID"]==patient["cardiologistID"]:
                                output={"patient":patient,"cardiologist":cardiologist}
                                return json.dumps(output)
    print(f"\nError: No device found for the given ID\n")
    raise cherrypy.HTTPError(404,f"Error in CATALOG: No device found for such ID\n")

def search_chat(list,query,list2):
    for cardiologist in list:
        if cardiologist["chatID"]==int(query["ID"]):
            patients_list=[]
            for patient in list2:
                if patient["cardiologistID"]==cardiologist["cardiologistID"]:
                    patients_list.append(patient)
            output={"cardiologist":cardiologist,"patients":patients_list}
            return json.dumps(output)
    print(f"\nError: No cardiologist found for the given chat ID\n")
    raise cherrypy.HTTPError(404,f"Error in CATALOG: No cardiologist found for such chat ID\n")

        
def add(contentFile,list,body):
    contentFile[list].append(body)

def replace(contentFile,list,body,i):
    contentFile[list][i]=body

class Catalog:
    exposed=True
    def __init__(self,filename):
        self.filename=filename
    def GET(self,*path, **query):
        #retrieve info from the catalog
        contentFile=json.load(open(self.filename,"r"))     #read the catalog
        devicesList=contentFile["devicesList"]
        cardiologistsList=contentFile["cardiologistsList"]
        patientsList=contentFile["patientsList"]
        servicesList=contentFile["servicesList"]
        if len(path)==2 and path[0]=='catalog' and path[1]=='broker': # url: http://localhost:8080/catalog/broker
            return json.dumps(contentFile["broker"])
        elif len(path)==2 and path[0]=='catalog' and path[1]=='devicesBaseTopic': # url: http://localhost:8080/catalog/devicesBaseTopic
            return json.dumps(contentFile["devicesInfo"])
        elif len(path)==2 and path[0]=='catalog' and path[1]=='allDevices': # url: http://localhost:8080/catalog/allDevices
            return json.dumps(devicesList)
        elif len(path)==2 and path[0]=='catalog' and path[1]=='allCardiologists': # url: http://localhost:8080/catalog/allCardiologists
            return json.dumps(cardiologistsList)
        elif len(path)==2 and path[0]=='catalog' and path[1]=='allPatients': # url: http://localhost:8080/catalog/allPatients
            return json.dumps(patientsList)
        elif len(path)==2 and path[0]=='catalog' and path[1]=='allServices': # url: http://localhost:8080/catalog/allServices
            return json.dumps(servicesList)
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByDevice' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByDevice/?ID=1
            return (search(devicesList,query,"device"))
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByPatient' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByPatient/?ID=1
            return (search(patientsList,query,"patient"))
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByCardiologist' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByCardiologist/?ID=1
            return (search(cardiologistsList,query,"cardiologist"))
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByService' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByService/?ID=1
            return (search(servicesList,query,"service"))
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByDeviceExtended' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByDeviceExtended/?ID=1
            return (search_extended(devicesList,query,patientsList,cardiologistsList))
        elif len(path)==2 and path[0]=='catalog' and path[1]=='searchByChat' and len(query)==1 and "ID" in query: # url: http://localhost:8080/catalog/searchByChat/?ID=1
            return (search_chat(cardiologistsList,query,patientsList))
        else:
            print("\nError: Impossible to manage this URI\n")
            raise cherrypy.HTTPError(400,"Error in CATALOG: Impossible to manage this URI\n")

    def POST(self,*path,**query):
        #register new device or new users or new service
        contentFile=json.load(open(self.filename,"r"))     #read the catalog
        cardiologistsList=contentFile["cardiologistsList"]
        patientsList=contentFile["patientsList"]
        devicesList=contentFile["devicesList"]
        servicesList=contentFile["servicesList"]
        body_read=cherrypy.request.body.read()
        if len(body_read)>0:
            try:
                body_json=json.loads(body_read)
                if len(path)==2 and path[0]=='catalog' and path[1]=='addNewCardiologist': # url: http://localhost:8080/catalog/addNewCardiologist
                    '''
                    {
                        "cardiologistName": "Jake Blues",
                        "cardiologistID": 1,
                        "chatID": 123456,
                        "lastUpdate": "2020-03-30"
                    }
                    '''
                    #let's control there are no cardiologists with the specified ID in the list
                    if any(d['cardiologistID']==body_json['cardiologistID'] for d in cardiologistsList):
                        print("\nError: The cardiologist is already present in the list\n")
                        raise cherrypy.HTTPError(409,"The cardiologist is already present in the list\n") 
                    else:
                        add(contentFile,"cardiologistsList",body_json)
                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nNew cardiologist added\n")
                    return json.dumps({"message":"\nNew cardiologist added\n"})
                    
                elif len(path)==2 and path[0]=='catalog' and path[1]=='addNewPatient': # url: http://localhost:8080/catalog/addNewPatient
                    '''
                    {
                        "patientName": "Lorna Clarks",
                        "patientID": 1,
                        "devices": [
                            {
                                "measurement":"ECG",
                                "deviceID":1
                            },
                            {
                                "measurement":"bp",
                                "deviceID":1001
                            },
                            {
                                "measurement":"bs",
                                "deviceID":""
                            }
                        ],
                        "cardiologistID": 1,
                        "lastUpdate": "2020-03-30"
                    }
                    '''
                    #check if there is the cardiologistID in the cardiologistList
                    if any(d['cardiologistID']==body_json['cardiologistID'] for d in cardiologistsList):
                        # check if there is the patientID in the list already
                        if any(d['patientID']==body_json['patientID'] for d in patientsList):
                            print("\nError: The patient is already present in the list\n")
                            raise cherrypy.HTTPError(409,"The patient is already present in the list\n") 
                        else:
                            #check that there are no other devices registered with the same ID (among all devices, not just the same device type)
                            catalog_IDs=[]
                            for patient in patientsList:
                                for device in patient["devices"]:
                                    if device["deviceID"]!="":
                                        catalog_IDs.append(device["deviceID"])
                            for device in body_json['devices']:
                                if any(d==device["deviceID"] for d in catalog_IDs):
                                    print(f"\nError: The {device['measurement']} device ID is already present in the list\n")
                                    raise cherrypy.HTTPError(409,f"The {device['measurement']} device ID is already present in the list\n")  
                            add(contentFile,"patientsList",body_json)
                    else:
                        print("\nError: Impossible to add the new patient, the cardiologist ID does not match any cardiologist in the list\n")
                        raise cherrypy.HTTPError(404,"Impossible to add the new patient, the cardiologist ID does not match any cardiologist in the list\n")

                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nNew patient added\n")
                    return json.dumps({"message":"\nNew patient added\n"})
            
                elif len(path)==2 and path[0]=='catalog' and path[1]=='registerDevice': # url: http://localhost:8080/catalog/registerDevice
                    '''           # I imagine my body will be like this
                        {
                            "deviceID": 1,
                            "measureType":"ECG",
                            "availableServices": [
                                "MQTT"
                            ],
                            "servicesDetails": [
                                    {
                                        "serviceType": "MQTT",
                                        "topic": "ECG"
                                    }
                                ],
                            "timestamp":1234567890
                        }
                    ''' 
                    #check if there is the deviceID in the patientList 
                    key=body_json['measureType']
                    body_json["timestamp"]=time.time()
                    flag=0
                    for patient in patientsList:
                        for device in patient["devices"]:
                            if device["measurement"]==key:
                                if device["deviceID"]==body_json["deviceID"]:
                                    if any(d['deviceID']==body_json['deviceID'] for d in devicesList):
                                        print("\nError: The device ID is already present in the list\n")
                                        raise cherrypy.HTTPError(409,"The device ID is already present in the list\n")
                                    else:
                                        add(contentFile,"devicesList",body_json)
                                        flag=1
                    if flag==0:
                        print(f"\nError: Impossible to add the new device, the {key} device ID is not registered for any patient in the list\n")
                        raise cherrypy.HTTPError(404,f"Impossible to add the new device, the {key} device ID is not registered for any patient in the list\n")

                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nNew device added\n")
                    return json.dumps({"message":"\nNew device added\n"})
                
                elif len(path)==2 and path[0]=='catalog' and path[1]=='registerService': # url: http://localhost:8080/catalog/registerService
                    '''           # I imagine my body will be like this
                    {
                        "serviceID": 7,
                        "serviceName": "InfluxDB_Adaptor",
                        "avaibleServices": ["REST"],
                        "serviceDetails": [
                        {
                            "serviceType": "REST",
                            "serviceIP": "localhost",
                            "servicePort":8081
                        }
                        ],
                        "timestamp": 0
                    }
                    or
                    {
                        "serviceID": 7,
                        "serviceName": "InfluxDB_Adaptor",
                        "avaibleServices": ["REST"],
                        "serviceDetails": [
                        {
                            "serviceType": "MQTT",
                            "topic":["IoT_project/device/ECG/"]
                        }
                        ],
                        "timestamp": 0
                    }
                    ''' 
                    #check if there is the serviceID in the servicesList
                    body_json["timestamp"]=time.time()
                    if not any(d['serviceID']==body_json['serviceID'] for d in servicesList):
                        add(contentFile,"servicesList",body_json)
                    else:
                        print("\nError: The service is already present in the list\n")
                        raise cherrypy.HTTPError(409,"The service is already present in the list\n") 

                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nNew service added\n")
                    return json.dumps({"message":"\nNew service added\n"})
                
                else:
                    print("\nError: Impossible to manage this URI\n")
                    raise cherrypy.HTTPError(400,"Impossible to manage this URI\n")
                    
            except json.decoder.JSONDecodeError:
                print("\nError: Body must be a valid JSON\n")
                raise cherrypy.HTTPError(400,"Error in CATALOG: Body must be a valid JSON\n")
            except cherrypy.HTTPError as e:
                raise cherrypy.HTTPError(e.status,f"Error in CATALOG: {e._message}")
            except Exception as e:
                print(f"\nError: Internal server error {e}:\n{traceback.format_exc()}\n") 
                raise cherrypy.HTTPError(500,"Error in CATALOG: Internal server error\n")
        else:
            print("\nError: The body of the request is empty\n") 
            raise cherrypy.HTTPError(400,"Error in CATALOG: The body of the request is empty\n")
        
    def PUT(self,*path,**query):
        contentFile=json.load(open(self.filename,"r"))     #read the catalog
        devicesList=contentFile["devicesList"]
        cardiologistsList=contentFile["cardiologistsList"]
        patientsList=contentFile["patientsList"]
        servicesList=contentFile["servicesList"]
        body_read=cherrypy.request.body.read()
        if len(body_read)>0:
            try:
                body_json=json.loads(body_read)
                #print(str(body_json))
                if len(path)==2 and path[0]=='catalog' and path[1]=='updateCardiologist': # url: http://localhost:8080/catalog/updateCardiologist
                    '''
                    {
                        "cardiologistName": "Jake Blues",
                        "cardiologistID": 1,
                        "chatID": 123456,
                        "lastUpdate": "2020-03-30"
                    }
                    '''
                    #let's control there are cardiologists with that ID in the list
                    if not any(d['cardiologistID']==body_json['cardiologistID'] for d in cardiologistsList):
                        print("\nError: Impossible to update, the cardiologist is not present in the list\n")
                        raise cherrypy.HTTPError(404,"Impossible to update, the cardiologist is not present in the list\n")
                    else:
                        for i in range(len(cardiologistsList)):
                            if body_json['cardiologistID']==cardiologistsList[i]["cardiologistID"]:
                                replace(contentFile,"cardiologistsList",body_json,i)
                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nCardiologist updated successfully\n")
                    return json.dumps({"message":"\nCardiologist updated successfully\n"})
                
                elif len(path)==2 and path[0]=='catalog' and path[1]=='updatePatient': # url: http://localhost:8080/catalog/updatePatient
                    '''
                    {
                        "patientName": "Lorna Clarks",
                        "patientID": 1,
                        "devices": [
                            {
                                "measurement":"ECG",
                                "deviceID":1
                            },
                            {
                                "measurement":"bp",
                                "deviceID":1001
                            },
                            {
                                "measurement":"bs",
                                "deviceID":""
                            }
                        ],
                        "cardiologistID": 1,
                        "lastUpdate": "2020-03-30"
                    }
                    '''
                    #check if there is the patientID in the patientsList
                    if not any(d['patientID']==body_json['patientID'] for d in patientsList):
                        print("\nError: Impossible to update, the patient is not present in the list\n")
                        raise cherrypy.HTTPError(404,"Impossible to update, the patient is not present in the list\n")
                    else:
                        #check if there is the cardiologistID in the cardiologistList
                        if not any(d['cardiologistID']==body_json['cardiologistID'] for d in cardiologistsList):
                            print("\nError: Impossible to update the patient, the cardiologist ID does not match any cardiologist list\n")
                            raise cherrypy.HTTPError(404,"Impossible to update the patient, the cardiologist does not match any cardiologist list\n") 
                        else:
                            #check that there are no other devices registered with the same ID (among all devices, not just the same device type)

                            # create patientsList2 in which the patient to update is not present in order to control that the deviceIDs are unique
                            patientsList2=[patient for patient in patientsList if patient["patientID"]!=body_json['patientID']]

                            catalog_IDs=[]
                            for patient in patientsList2:
                                for device in patient["devices"]:
                                    if device["deviceID"]!="":
                                        catalog_IDs.append(device["deviceID"])
                            for device in body_json['devices']:
                                if any(d==device["deviceID"] for d in catalog_IDs):
                                    print(f"\nError: The {device['measurement']} device ID is already present in the list\n")
                                    raise cherrypy.HTTPError(409,f"The {device['measurement']} device ID is already present in the list - try with /updatepatient\n")  
 
                            for i in range(len(patientsList)):
                                if body_json['patientID']==patientsList[i]["patientID"]:
                                    replace(contentFile,"patientsList",body_json,i)

                            # delete any device that is not registered to patients
                            devices_to_remove=[]
                            catalog_IDs=[]
                            for patient in patientsList:
                                for device in patient["devices"]:
                                    if device["deviceID"]!="":
                                        catalog_IDs.append(device["deviceID"])
                            for device in devicesList:
                                if not any(d==device["deviceID"] for d in catalog_IDs):
                                    devices_to_remove.append(device)
                            for device in devices_to_remove:
                                devicesList.remove(device)

                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nPatient updated successfully\n")
                    return json.dumps({"message":"\nPatient updated successfully\n"})
                
                elif len(path)==2 and path[0]=='catalog' and path[1]=='updateDevice': # url: http://localhost:8080/catalog/updateDevice
                    '''           # I imagine my body will be like this
                        {
                            "deviceID": 1,
                            "measureType":"ECG",
                            "availableServices": [
                                "MQTT"
                            ],
                            "servicesDetails": [
                                    {
                                        "serviceType": "MQTT",
                                        "topic": "ECG"
                                    }
                                ],
                            "timestamp":1234567890
                        }
                    ''' 
                    #check if there is the deviceID in the devicesList
                    if not any(d['deviceID']==body_json['deviceID'] for d in devicesList):
                        print("\nError: Impossible to update, the device is not present in the list\n")
                        raise cherrypy.HTTPError(404,"Impossible to update, the device is not present in the list\n")
                    else:
                        key=body_json['measureType']
                        body_json["timestamp"]=time.time()
                        flag=0
                        for patient in patientsList:
                            for device in patient["devices"]:
                                if device["measurement"]==key:
                                    if device["deviceID"]==body_json["deviceID"]:
                                        for i in range(len(devicesList)):
                                            if body_json['deviceID']==devicesList[i]["deviceID"]:
                                                replace(contentFile,"devicesList",body_json,i)
                                                flag=1
                        if flag==0:
                            print(f"\nError: Impossible to update the device, the {key} device ID is not registered for any patient in the list\n")
                            raise cherrypy.HTTPError(404,f"Error: Impossible to update the device, the {key} device ID is not registered for any patient in the list\n")

                        json.dump(contentFile,open(self.filename,"w"),indent=4)
                        print("\nDevice updated successfully\n")
                        return json.dumps({"message":"\nDevice updated successfully\n"})
                
                elif len(path)==2 and path[0]=='catalog' and path[1]=='updateService': # url: http://localhost:8080/catalog/updateService
                    '''           # I imagine my body will be like this
                    {
                        "serviceID": 7,
                        "serviceName": "InfluxDB_Adaptor",
                        "avaibleServices": ["REST"],
                        "serviceDetails": [
                        {
                            "serviceType": "REST",
                            "serviceIP": "localhost",
                            "servicePort":8081
                        }
                        ],
                        "timestamp": 0
                    }
                    or
                    {
                        "serviceID": 7,
                        "serviceName": "InfluxDB_Adaptor",
                        "avaibleServices": ["REST"],
                        "serviceDetails": [
                        {
                            "serviceType": "MQTT",
                            "topic":["IoT_project/device/ECG/"]
                        }
                        ],
                        "timestamp": 0
                    }
                    ''' 
                    body_json["timestamp"]=time.time()
                    #check if there is the serviceID in the servicesList
                    if not any(d['serviceID']==body_json['serviceID'] for d in servicesList):
                        print("\nError: Impossible to update, the service is not present in the list\n")
                        raise cherrypy.HTTPError(404,"Impossible to update, the service is not present in the list\n")
                    else:
                        for i in range(len(servicesList)):
                            if body_json['serviceID']==servicesList[i]["serviceID"]:
                                replace(contentFile,"servicesList",body_json,i)
                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nService updated successfully\n")
                    return json.dumps({"message":"\nService updated successfully\n"})
                
                else:
                    print("\nError: Impossible to manage this URI\n")
                    raise cherrypy.HTTPError(400,"Impossible to manage this URI\n")
                
            except json.decoder.JSONDecodeError:
                print("\nError: Body must be a valid JSON\n")
                raise cherrypy.HTTPError(400,"Error in CATALOG: Body must be a valid JSON\n")
            except cherrypy.HTTPError as e:
                raise cherrypy.HTTPError(e.status,f"Error in CATALOG: {e._message}")
            except Exception as e:
                print(f"\nError: Internal server error {e}:\n{traceback.format_exc()}\n")
                raise cherrypy.HTTPError(500,"Error in CATALOG: Internal server error\n")
        else:
            print("\nError: The body of the request is empty\n") 
            raise cherrypy.HTTPError(400,"Error in CATALOG: The body of the request is empty\n")
        
    def DELETE(self,*path,**query):
        #delete devices not in use
        if len(path)==2 and path[0]=='catalog' and path[1]=="delete":                  # url: http://localhost:8080/catalog/delete
            contentFile=json.load(open(self.filename,"r"))
            devicesList=contentFile["devicesList"]
            servicesList=contentFile["servicesList"]
            now=time.time()
            for element in devicesList[:]:          #copy of devicesList
                if now-element["timestamp"]>120:
                    devicesList.remove(element)
            for element in servicesList[:]:         #copy of servicesList
                if now-element["timestamp"]>120:
                    servicesList.remove(element)
            contentFile["devicesList"]=devicesList
            contentFile["servicesList"]=servicesList
            json.dump(contentFile,open(self.filename,"w"),indent=4)
            print("\nDevices list and services list updated\n")
            return json.dumps({"message":"\nDevices list and services list updated\n"})
        elif len(path)==2 and path[0]=='catalog' and path[1]=="deleteCardiologist" and len(query)==1 and "ID" in query:        # url: http://localhost:8080/catalog/deleteCardiologist/?ID=1
            contentFile=json.load(open(self.filename,"r"))
            patientsList=contentFile["patientsList"]
            cardiologistsList=contentFile["cardiologistsList"]
            cardiologistID=int(query["ID"])
            for patient in patientsList:
                if patient["cardiologistID"]==cardiologistID:
                    print("\nError: Impossible to delete this cardiologist, please update the cardiologist's patients info first\n")
                    raise cherrypy.HTTPError(409,"Error in CATALOG: Impossible to delete this cardiologist, please update the cardiologist's patients info first\n")
            for element in cardiologistsList:
                if element["cardiologistID"]==cardiologistID:
                    cardiologistsList.remove(element)
                    contentFile["cardiologistsList"]=cardiologistsList
                    json.dump(contentFile,open(self.filename,"w"),indent=4)
                    print("\nCardiologists list updated\n")
                    return json.dumps({"message":"\nCardiologists list updated\n"})
            print("\nError: No cardiologist found for the given ID\n")
            raise cherrypy.HTTPError(404,"Error in CATALOG: No cardiologist found for the given ID\n")
        
        elif len(path)==2 and path[0]=='catalog' and path[1]=="deletePatient" and len(query)==1 and "ID" in query:        # url: http://localhost:8080/catalog/deletePatient/?ID=1
            contentFile=json.load(open(self.filename,"r"))
            patientsList=contentFile["patientsList"]
            devicesList=contentFile["devicesList"]
            flag=0
            patientID=int(query["ID"])
            for element in patientsList:
                if element["patientID"]==patientID:
                    patientsList.remove(element)
                    flag=1
                    break
            if flag==0:
                print("\nError: No patient found for the given ID\n")
                raise cherrypy.HTTPError(404,"Error in CATALOG: No patient found for the given ID\n")
            
            devices_to_remove=[]
            catalog_IDs=[]
            for patient in patientsList:
                for device in patient["devices"]:
                    if device["deviceID"]!="":
                        catalog_IDs.append(device["deviceID"])
            for device in devicesList:
                if not any(d==device["deviceID"] for d in catalog_IDs):
                    devices_to_remove.append(device)
            for device in devices_to_remove:
                devicesList.remove(device)

            json.dump(contentFile,open(self.filename,"w"),indent=4)
            print("\nPatients list updated\n")
            return json.dumps({"message":"\nPatients list updated\n"})
        else:
            print("\nError: Impossible to manage this URI\n")
            raise cherrypy.HTTPError(400,"Error in CATALOG: Impossible to manage this URI\n")

# def make_delete_request():
#     while True:
#         time.sleep(120)  
#         response = requests.delete('http://localhost:8080/catalog/delete')


'''Beginning in version 3.1, you may also provide a function or other callable as
an error_page entry. It will be passed the same status, message, traceback and
version arguments that are interpolated into templates::

    def error_page_402(status, message, traceback, version):
        return "Error %s - Well, I'm very sorry but you haven't paid!" % status
    cherrypy.config.update({'error_page.402': error_page_402})

Also in 3.1, in addition to the numbered error codes, you may also supply
"error_page.default" to handle all codes which do not have their own error_page
entry.'''

def custom_error_page(status, message, traceback, version):
    if 'application/json' in cherrypy.request.headers.get('Accept'):
        return json.dumps({
            "status": status,
            "error": message,
        })
    else:
        raise

if __name__=="__main__":
    conf={
            '/':{
            'request.dispatch':cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on':True,
            'error_page.default':custom_error_page
        }
    }

    filename="catalog7.json"
    cherrypy.tree.mount(Catalog(filename),'/',conf)
    cherrypy.config.update({'server.socket_port':80})
    cherrypy.config.update({'server.socket_host':"0.0.0.0"})
    # delete_thread = threading.Thread(target=make_delete_request)
    # delete_thread.daemon = True  # Thread is a "daemon", it ends when the main ends
    # delete_thread.start()
    cherrypy.engine.start()
    #cherrypy.engine.block()
    try:
        while True:
            time.sleep(120)  
            response = requests.delete('http://0.0.0.0:80/catalog/delete')
    except KeyboardInterrupt:
        print("\nExiting server...\n")

    if cherrypy.engine.state==cherrypy.engine.states.STARTED:
        cherrypy.engine.exit()
    

