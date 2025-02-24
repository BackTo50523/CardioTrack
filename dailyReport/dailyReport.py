import cherrypy
from datetime import datetime
import requests
import time
import json
import pytz
import traceback
import matplotlib
matplotlib.use('Agg')   # Set the non-interactive backend for Matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import base64
import io
import pandas as pd

class DailyReport:
    exposed=True
    def __init__(self,url):
        self.url=url

    def GET(self,*path,**query):
        if len(path)==1 and path[0]=="dailyReport" and len(query)==1 and "patientID" in query:         #http://localhost:8090/dailyReport/?patientID=1
            #catalog_request_2(self.url)
            try:
                headers = {'Accept': 'application/json'}
                config=json.load(open("configurationHTTP.json"))
                influxDB_ID=config["contact_service_ID"]
                r=requests.get(self.url+"searchByService/?ID="+str(influxDB_ID),headers=headers)
                r.raise_for_status()


                message=r.json() 
                '''
                {"message": 
                       {
                        "serviceID": 7,
                        "serviceName": "InfluxDB_Adaptor",
                        "availableServices": ["REST"],
                        "serviceDetails": [
                        {
                            "serviceType": "REST",
                            "serviceIP": "localhost",
                            "servicePort":8081
                        }
                        ],
                        "timestamp": 0
                    }
                }
                '''
                flag=0
                service=message
                availableServices=service["availableServices"]
                for element in availableServices:
                    if element=="REST":
                        for element2 in service["serviceDetails"]:
                            if element2["serviceType"]=="REST":
                                service_IP=element2["serviceIP"]
                                service_port=element2["servicePort"]
                                service_URI="http://"+service_IP+":"+str(service_port)+"/database/"
                                flag=1
                                break           #out of inner for
                        if flag==1:
                            break               #out of outer for
                # print(f"\n\n{service_URI}\n\n") 
                patientID=query["patientID"]
                measureType="all"
                current_time=time.time()
                unix_end_ms=int(current_time*10**3)
                unix_start_ms=unix_end_ms-(24*60*60*10**3)
                unix_end_ns=int(current_time*10**9)
                unix_start_ns=unix_end_ns-(24*60*60*10**9)

                r=requests.get(service_URI+f"{patientID}/{measureType}?time_start={unix_start_ns}&time_end={unix_end_ns}",headers=headers)  #obtain info from influxdb adaptor for the patient in the last 24hours
                #if r.status_code == 404:
                #    output = {"Error": "Data non available"}
                #    return json.dumps(output)
                r.raise_for_status()

                data=r.json()
                output=report_creation(data,unix_start_ms,patientID)
                return json.dumps(output)
            
            except json.decoder.JSONDecodeError:
                print("\nError: expected responses in JSON\n")
                raise cherrypy.HTTPError(500,"Internal server Error\n")         
            except requests.exceptions.HTTPError:
                body=r.json()
                print(f"\nHTTP Error - {body['status']}: {body['error']}\n")
                raise cherrypy.HTTPError(body['status'],body['error'])
            except Exception as e:
                print(f"\nInternal server error: {e}\n {traceback.format_exc()}")
                raise cherrypy.HTTPError(500,"Internal server Error\n")
        else:
            print(f"\nError: Impossible to manage this URI\n")
            raise cherrypy.HTTPError(400,"Impossible to manage this URI\n")

def custom_error_page(status, message, traceback, version):
    if 'application/json' in cherrypy.request.headers.get('Accept'):
        return json.dumps({
            "status": status,
            "error": message,
        })
    else:
        raise 

def report_creation(data,unix_start_ms,patientID):
    data_bp=[];data_RR_dev=[];data_HR=[];data_bs=[];alerts=[]
    for element in data:
        if element["iox::measurement"]=="BP":
            if "bp_systolic" in element.keys() and element["bp_systolic"] is not None:
                value_trunc=int(element["bp_systolic"]*10)/10
                data_bp.append(value_trunc)
        elif element["iox::measurement"]=="BS":
            if "bs" in element.keys() and element["bs"] is not None:
                value_trunc=int(element["bs"]*10)/10
                data_bs.append(value_trunc)
        elif element["iox::measurement"]=="ECG":
            if "stdrr" in element.keys() and element["stdrr"] is not None:
                value_trunc=int(element["stdrr"]*10)/10
                data_RR_dev.append(value_trunc)
            if "hr" in element.keys() and element["hr"] is not None:
                value_trunc=int(element["hr"]*10)/10
                data_HR.append(value_trunc)        
        if element["alert"]=="1" and element["alert"] is not None:
            alerts.append(element["time"])

    alerts_hour=[0]*24
    total_alerts=len(alerts)
    if total_alerts!=0:
        for element in alerts:
            for j in range(24):
                if element>(unix_start_ms+j*60*60*10**3) and element<(unix_start_ms+(j+1)*60*60*10**3):
                    alerts_hour[j]+=1
                    break
        alerts_hour_percentage = []
        for i in range(24):
            alerts_hour_percentage.append(alerts_hour[i] * 100 / total_alerts)    

    filename="report_"+datetime.today().strftime("%d-%m-%Y")+"_"+str(patientID)+".pdf"
    list_data=[data_HR,data_RR_dev,data_bp,data_bs]
    title=["Heart rate","R-R distance stdev","Blood Pressure","Blood Saturation"]
    unit=["beats/min","ms","mmHg","%"]

    pdf_buffer = io.BytesIO()
    with PdfPages(pdf_buffer) as pdf:
        for i in range(len(list_data)):
            data=list_data[i]
            if len(data)!=0:
                plt.figure(figsize=(10, 6))
                sns.histplot(data, bins=30, kde=False, color='skyblue', edgecolor='black')  # Histogram with 30 bins
                plt.title(title[i])
                plt.xlabel(unit[i])
                plt.ylabel('Frequency')
                pdf.savefig()  # saves the graph on the PDF
                plt.close()
        if total_alerts!=0:
            italy_timezone=pytz.timezone('Europe/Rome')
            intervals=[]
            for j in range(24):
                hour_start=unix_start_ms/1000+j*60*60
                hour_end=unix_start_ms/1000+(j+1)*60*60
                x_start=datetime.fromtimestamp(hour_start, tz=italy_timezone)
                x_end=datetime.fromtimestamp(hour_end, tz=italy_timezone)
                h_m_start=x_start.strftime("%H:%M")
                h_m_end=x_end.strftime("%H:%M")
                intervals.append(h_m_start+" - "+h_m_end)
            
            plt.figure(figsize=(10, 6))
            sns.barplot(x=intervals, y=alerts_hour_percentage, color='skyblue', edgecolor='black')
            plt.title("Number of alerts")
            plt.xlabel("Past hours")
            plt.ylabel('Frequency (%)')
            plt.xticks(rotation=45)
            plt.tight_layout()              #to make everything fit in the page
            #plt.show()
            pdf.savefig()  # saves the graph on the PDF
            plt.close()

    # Move to the beginning of the PDF buffer to read its content
    pdf_buffer.seek(0)

    # Base64 encode the PDF data
    pdf_data = pdf_buffer.read()
    base64_pdf = base64.b64encode(pdf_data).decode("utf-8")

    # Create a JSON object with the base64 PDF data
    output={"filename": filename,"filedata": base64_pdf}
    return output
    

if __name__=="__main__":

    config=json.load(open("configurationHTTP.json"))
    url=config["catalog"]
    conf={
        '/':{
            'tools.sessions.on':True,
            'request.dispatch':cherrypy.dispatch.MethodDispatcher(),
            'error_page.default': custom_error_page
        }
    }

    cherrypy.tree.mount(DailyReport(url),'/',conf)
    cherrypy.config.update({'server.socket_host':"0.0.0.0"})
    cherrypy.config.update({'server.socket_port':80})
    cherrypy.engine.start()

    headers = {'Accept': 'application/json'}
    serviceInfo=config["serviceInfo"]
    serviceInfo["timestamp"]=time.time()
    url_register=url+"registerService"
    url_update=url+"updateService"
    try:
        response = requests.post(url_register, json=serviceInfo, headers=headers)
        if response.status_code != 409: 
            response.raise_for_status() # Will raise an error for any 4xx/5xx status codes, except the 409 conflict error
            response=response.json()
            print(response["message"])
        else:
            print("The service is already present in the catalog. Proceeding to update...")

        while True:
            response = requests.put(url_update, json=serviceInfo, headers=headers)
            response.raise_for_status()  # Will raise an error for any 4xx/5xx status codes
            time.sleep(30)  

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors during POST or PUT requests
        body = e.response.json()
        print(f"\nHTTP Error - {body['status']}: {body['error']}\nURL: {url}\nDevice Info: {serviceInfo}\n")
    except json.decoder.JSONDecodeError as e:
        print(f"\nJSON Decode error: {e}\n")
    except KeyboardInterrupt:
        print("\nExiting server...\n")
    except:
        if cherrypy.engine.state==cherrypy.engine.states.STARTED:
            cherrypy.engine.exit()
        raise

    if cherrypy.engine.state==cherrypy.engine.states.STARTED:
        cherrypy.engine.exit()