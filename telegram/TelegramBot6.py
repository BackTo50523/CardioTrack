import numpy as np
from MyMQTT import *
import json
import time
from datetime import datetime
import requests
import telepot
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup
from telepot.loop import MessageLoop
import base64
import io
from telegram import Bot, InputFile
import cherrypy
import traceback



class Subscriber():
    def __init__(self,broker,port,topic,bot,conf):
        self.clientID = "IoT_Project2324243" + str(np.random.randint(1,10000))        
        self.mqtt_client = MyMQTT(self.clientID, broker, port, self)
        self.topic=topic
        self.last_alerts = {} #Last alerts are saved
        self.alert_timeout = 5 * 60
        self.bot=bot
        self.url_catalog=conf["catalog"]

    def startSim(self):
        self.mqtt_client.start()
        self.mqtt_client.mySubscribe(self.topic)

    def stopSim(self):
        self.mqtt_client.stop()

    def notify(self, topic, msg):
        """Management of MQTT notifies"""
        '''
        data received:
        {
        "alert":{0/1}
        "measurement":{senML_HEARTRATE/senML_BLOODS/senML_BLOODP/}
        }
        '''
        try: 
            message = json.loads(msg)
            
            measurement = message.get("measurement")
            deviceID = measurement["bn"]
            r=requests.get(self.url_catalog+"searchByDeviceExtended/?ID="+str(deviceID))
            r.raise_for_status()
            r=r.json()
            chatID=r["cardiologist"]["chatID"]
            patientName=r["patient"]["patientName"]

            m = measurement["e"][0] 
            measurement_type = m.get("n")  
            value = m.get("v")  
            unit = m.get("u") 

            notification = (f"*ALERT!*\n\n"
                            f"*Patient*: {patientName}\n"
                            f"*Measurement*: {measurement_type}\n"
                            f"*Value*: {value} {unit}\n")
            self.bot.sendMessage(chatID, text=notification, parse_mode="Markdown")
            print(f"An alert was received from {topic} at {datetime.now()}.Notification sent to Chat ID: {chatID}")

        except json.JSONDecodeError as j:
            print(f"JSONDecodeError: {j}")
        except Exception as e:
            print(f"\nFor this message [{message}] the following exception occurred: {e}\n {traceback.format_exc()}")
        

class TeleBot:
    def __init__(self, conf, bot):
        self.bot = bot
        self.state = {} 
        self.settings=conf
        self.url = conf["endpoints"]
        self.catalog = conf['catalog']
        self.headers = {'Accept': 'application/json'}  
    '''def load_chat_ids(self):
        try:
            with open('configuration_telegram.json', 'r') as file:
                config = json.load(file)
                return config["chatIDs"]
        except (FileNotFoundError, json.JSONDecodeError):
            return '''

    #COMMAND /start
    def start_command(self, chat_ID):
        r= requests.get(self.url["getByChatID"]+ str(chat_ID), headers=self.headers) 
        if r.status_code==404:
            self.state[chat_ID] = {'step': 'get_doc_name'}
            self.bot.sendMessage(chat_ID, "Welcome to the Heart monitoring Bot.\nPlease enter your name and surname:")
            return 
        r.raise_for_status()
        r=r.json()
        name = r["cardiologist"]["cardiologistName"]
        surname = name.split()[-1]  
        self.bot.sendMessage(chat_ID, f"Welcome back Dr. {surname}! You are already registered.")
        return    

    #COMMAND /addpatient
    def add_patient_command(self, chat_ID):
        self.state[chat_ID] = {'step': 'get_patient_name'}
        self.bot.sendMessage(chat_ID, "Adding a new patient. Please enter the patient's name:")

    #COMMAND /viewpatientlist
    def view_patients_command(self, chat_ID,cardPatientList):      
        patients = cardPatientList["patients"]
        if len (patients)==0:
            self.bot.sendMessage(chat_ID, "Empty patient list. \nFirst add patients with /addpatient")
            return
        #Request to the catalog to connect to the dashboard
        dashboardID=self.settings["contact_service_ID"]["dashboard"]
        r=requests.get(self.catalog+"searchByService/?ID="+str(dashboardID),headers=self.headers)
        if r.status_code==404:
            link=False
            pass
            #self.bot.sendMessage(chat_ID, message, parse_mode="Markdown")
        #r.raise_for_status()
        else:
            service=r.json() 
            key=0
            availableServices=service["availableServices"]
            for element in availableServices:
                if element=="REST":
                    for element2 in service["serviceDetails"]:
                        if element2["serviceType"]=="REST":
                            service_IP=element2["serviceIP"]
                            service_port=element2["servicePort"]
                            service_URI="http://"+service_IP+":"+str(service_port)+"/"
                            link =True
                            key=1
                            break           
                    if key==1:
                        break     
            
        message = "Patients list:\n"
        for i, patient in enumerate(patients, start=1):
            if link:            
                link = service_URI + f"dashboard/?patient={patient['patientID']}"
            devices_list=[]
            for device in patient['devices']:
                devices_list.append(f"{device['measurement']} (ID: {device['deviceID']})")
            devices = ", ".join(devices_list)
            
            message += f"\n*{i}. {patient['patientName']}*  \n"
            message += f"    ID: {patient['patientID']}\n"
            message += f"    Gender: {patient['patientGender']}\n"
            message += f"    Date of Birth: {patient['patientDoB']}\n"
            message += f"    Devices: {devices}\n"
            message += f"    Last Update: {patient['lastUpdate']}\n"
            message += f"    Dashboard: {link}\n" if link else "   Dashboard: Not available\n"
        self.bot.sendMessage(chat_ID, message, parse_mode="Markdown") 

    def dailyreport_command(self, chat_ID,cardPatientList):
        self.state[chat_ID] = {'step': 'get_patient_dr'}
        patients= cardPatientList["patients"]
        message = "Patients list:\n"
        for i, patient in enumerate(patients, start=1):
                message += f"{i}. {patient['patientName']}\n"
        self.bot.sendMessage(chat_ID, f"Enter the number of the patient for which you want to ask for the daily report \n{message}")    
    
    def handle_user_input(self, chat_ID, message):       

        if len(self.state)>0:
            user_state = self.state[chat_ID]

        #-----------------------------------
        #   Cardiologist registration
        #-----------------------------------
            if user_state['step'] == 'get_doc_name':
                name_parts = message.split()  
                if len(name_parts) < 2:
                    self.bot.sendMessage(chat_ID, "Please provide both your first name and last name (separated by a space).")
                    return
                user_state['doc_name'] = message
                user_state['step'] = 'get_doc_email'
                self.bot.sendMessage(chat_ID, "Please enter your email:")
                return
                
            elif user_state['step'] == 'get_doc_email':
                if "@" not in message or "." not in message: 
                    self.bot.sendMessage(chat_ID, "Invalid email address, please digit it correctly.")
                    return
                user_state['email'] = message
                self.registerCardiologist(chat_ID)
                del user_state
                return
        
        cardPatientList=self.get_cardPatient(chat_ID)
        if cardPatientList == 0:
            return
        patients = cardPatientList["patients"]
        cardiologist=cardPatientList["cardiologist"]
        

        #-----------------------------------
        #   Cardiologist unsubscription
        #-----------------------------------
        if user_state['step'] == 'confirm_unsubscribe' and message.strip().upper() == 'YES':
            self.remove(chat_ID, "cardiologist", cardiologist["cardiologistID"])

        #MODIFICA    
        elif user_state['step'] == 'confirm_unsubscribe' and message.strip().upper() != 'YES':
            self.bot.sendMessage(chat_ID, "Unsubscribe cancelled.")
            del user_state

        #-----------------------------------
        #   Cardiologist editing
        #-----------------------------------
        elif user_state['step'] == 'edit_cardiologist':            
            field = message
            if field == '1':                
                user_state['field_to_update'] = 'cardiologistName'
            elif field == '2':
                user_state['field_to_update'] = 'cardiologistEmail'
            else:
                self.bot.sendMessage(chat_ID, "Invalid choice, please select one from suggested values.")
                return            
            user_state['step'] = 'waiting_new_value'
            self.bot.sendMessage(chat_ID, f"Enter the new {user_state['field_to_update']}:")

        elif user_state['step'] == 'waiting_new_value':
            updated_val = message
            user_state['updated_value'] = updated_val
            user_state['step'] = 'update_cardiologist_value'
            self.updateCardiologist(chat_ID, 'new_value',cardiologist)
            del user_state

        #-----------------------------------
        #   Patient daily report
        #-----------------------------------
        elif user_state['step'] ==  'get_patient_dr':
            #MODIFICA
            try:
                num_patient = int(message)
                user_state['patient_number'] = num_patient
            except ValueError:
                self.bot.sendMessage(chat_ID, "Invalid number. The input must be an integer.")

            if num_patient <= len(patients):
                patient_dr = patients[num_patient-1]
                patientID = patient_dr['patientID']
                self.get_daily_report(chat_ID, patientID)
            else:
                self.bot.sendMessage(chat_ID, "Invalid number. Please enter a number from the list.")

        
        #-----------------------------------
        #   Patient registration
        #-----------------------------------
        elif user_state['step'] == 'get_patient_name':
            user_state['patient_name'] = message.strip()
            self.bot.sendMessage(chat_ID, "Please enter the patient's surname:")
            user_state['step'] = 'get_patient_surname'

        elif user_state['step'] == 'get_patient_surname':
            user_state['patient_surname'] = message.strip()
            self.bot.sendMessage(chat_ID, "Please enter the patient's gender (M/F):")
            user_state['step'] = 'get_patient_gender'

        elif user_state['step'] == 'get_patient_gender':
            if message.strip() not in ["m", "f", "F", "M"]:
                self.bot.sendMessage(chat_ID, "Invalid gender. Please enter 'M' or 'F':")
                return
            user_state['patient_gender'] = message.upper()
            self.bot.sendMessage(chat_ID, "Please enter the patient's date of birth (DD-MM-YYYY):")
            user_state['step'] = 'get_patient_dob'

        elif user_state['step'] == 'get_patient_dob':
            try:
                datetime.strptime(message.strip(), "%d-%m-%Y")
                user_state['patient_dob'] = message.strip()
            except ValueError:
                self.bot.sendMessage(chat_ID, "Invalid date. Try again:")
                return            
            self.bot.sendMessage(chat_ID, "Please enter the ECG device ID [mandatory]:")
            user_state['step'] = 'get_ecg_id'

        elif user_state['step'] == 'get_ecg_id':
            if not message.isdigit():
                self.bot.sendMessage(chat_ID, "Invalid ECG ID. Please enter a numeric value:")
                return
            
            user_state['devices_list'] = [{"measurement": "ECG", "deviceID": int(message)}]            
            self.bot.sendMessage(chat_ID, "Patient data saved! Now registering the patient...")
            self.addPatient(chat_ID,cardiologist["cardiologistID"]) 
            return

        elif user_state['step'] == 'get_bp_id':
            if message.lower() == 'none':
                bp_id = ""
            elif message.isdigit():
                bp_id = int(message)
            else:
                self.bot.sendMessage(chat_ID, "Invalid BP ID. Please enter a numeric value or 'None':")
                return

            user_state['devices_list'].append({"measurement": "BP", "deviceID": bp_id})
            self.bot.sendMessage(chat_ID, "Please enter the Blood Saturation device ID or type 'None':")
            user_state['step'] = 'get_bs_id'

        elif user_state['step'] == 'get_bs_id':
            if message.lower() == 'none':
                bs_id = ""
            elif message.isdigit():
                bs_id = int(message)
            else:
                self.bot.sendMessage(chat_ID, "Invalid BS ID. Please enter a numeric value or 'None':")
                return

            user_state['devices_list'].append({"measurement": "BS", "deviceID": bs_id})
            self.bot.sendMessage(chat_ID, "Please confirm device registration. Type 'YES' to proceed or 'NO' to modify:")
            user_state['step'] = 'confirm_device_update'

        elif user_state['step'] == 'confirm_device_update':
            if message.strip().upper() == 'YES':
                patient_data = user_state['patient_data']
                patient_data['devices'] =  user_state['devices_list']            
                response = requests.put(self.url["updatePatient"], json=patient_data, headers=self.headers)
                response.raise_for_status()

                self.bot.sendMessage(chat_ID, "Devices saved successfully!")
                user_state.clear()  
            else:
                self.bot.sendMessage(chat_ID, "Let's try again. Please enter the ECG device ID:")
                user_state['step'] = 'get_ecg_id'
            
        #-----------------------------------
        #   Patient deleting
        #-----------------------------------       
        elif user_state['step'] == 'selecting_patient_delete':
            #MODIFICA
            try:
                num_patient = int(message)
                if num_patient <= len(patients):
                    patient_to_delete = patients[num_patient-1]
                    user_state['patient_to_delete'] = patient_to_delete['patientName']
                    user_state['step'] = 'confirm_elimination_pz'
                    self.bot.sendMessage(chat_ID, f"Are you sure to remove {patient_to_delete['patientName']}? Type 'YES' to confirm")
                else:
                    self.bot.sendMessage(chat_ID, "Invalid number. Please enter a number from the list.")
            except ValueError:
                self.bot.sendMessage(chat_ID, "Invalid ID: ID must be an integer")

        elif user_state['step'] == 'confirm_elimination_pz'and message.strip().upper() == 'YES':

            id = next(p['patientID'] for p in patients if p['patientName'] == user_state['patient_to_delete'])
            self.remove(chat_ID, "patient", id)  
                
        elif user_state['step'] == 'confirm_elimination_pz'and message.strip().upper() != 'YES':
            self.bot.sendMessage(chat_ID, "Elimination cancelled.")
            del user_state
            
        #-----------------------------------
        #   Patient editing
        #-----------------------------------    
        elif user_state['step'] == 'selecting_patient_update':
            #MODIFICA
            try:
                num_patient = int(message)
                if num_patient <= len(patients):
                    patient_to_update = patients[num_patient-1]
                    user_state['patient_to_update'] = patient_to_update
                    user_state['step'] = 'selecting_field_update'
                    self.bot.sendMessage(chat_ID, "What do you want to edit? \n1.Name\n2.Date of birth \n3.ECG ID \n4.BP ID \n5.BS ID\n6. Cardiologist  \nSelect an option by number")
                else:
                    self.bot.sendMessage(chat_ID, "Invalid number. Please enter a number from the list.")
            except ValueError:
                self.bot.sendMessage(chat_ID, "Invalid ID: ID must be an integer")

        elif user_state['step'] == 'selecting_field_update':
            field = message
            try:
                if int(field) >= 1 and int(field) <= 5:
                    if field == '1':                
                        user_state['field_to_update'] = 'patientName'
                    elif field == '2':
                        user_state['field_to_update'] = 'patientDoB'
                    elif field in ['3', '4', '5']:
                        measurement_map = {'3': 'ECG', '4': 'BP', '5': 'BS'}
                        user_state['field_to_update'] = measurement_map[field]

                    user_state['step'] = 'waiting_new_patient_value'
                    self.bot.sendMessage(chat_ID, f"Enter the updated value:")  
            
                elif field == '6':
                    user_state['field_to_update'] = 'cardiologistID'
                    message = "Available cardiologists:\n"
                    r=requests.get(self.settings["catalog"]+"allCardiologists", headers=self.headers)
                    r.raise_for_status()
                    cardiologists=r.json()
                    cardiologists= [c for c in cardiologists if c["chatID"]!=chat_ID]
                    self.state[chat_ID]["valid_IDs"]=[c["cardiologistID"] for c in cardiologists]
                    for i, c in enumerate(cardiologists, start=1):            
                        message += f"    ID: {c['cardiologistID']}\n"
                        message += f"    Name: {c['cardiologistName']}\n"
                    self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                    self.bot.sendMessage(chat_ID, f"{message}\ninsert the ID of the new patient's cardiologist")
                else:
                    self.bot.sendMessage(chat_ID, "Invalid choice, please select one from suggested values.")
                    return            
            except ValueError:
                self.bot.sendMessage(chat_ID, "Invalid choice")

        elif user_state['step'] == 'waiting_new_patient_value':
            updated_val = message
            user_state['updated_value'] = updated_val
            user_state['step'] = 'update_patient_value'
            self.updatePatient(chat_ID, 'new_value',patients)
            del user_state
        else:
            self.bot.sendMessage(chat_ID, "Invalid command or action.")

    def registerCardiologist(self, chat_ID):            
        doc_name = self.state[chat_ID].get('doc_name')
        doc_email = self.state[chat_ID].get('email')
        cardiologist_id = self.generate_cardiologist_id()
        last_update = datetime.now().strftime('%d-%m-%Y')     
        body = {
            "cardiologistName": doc_name,
            "cardiologistEmail": doc_email,
            "cardiologistID": cardiologist_id,
            "chatID": chat_ID,
            "lastUpdate": last_update
        }

        response = requests.post(self.url["addCardiologist"], json=body, headers=self.headers)
        response.raise_for_status()  
        response=response.json()
        self.bot.sendMessage(chat_ID, response["message"])
        
    #COMMAND /editpersonaldata or /unsubscribe
    def updateCardiologist(self, chat_ID, message, cardiologist_info):
        if message == '/unsubscribe':                                            
            self.bot.sendMessage(chat_ID, "Are you sure you want to unsubscribe? Type 'YES' to confirm.")                   
            self.state[chat_ID]= {'step': 'confirm_unsubscribe'}                        
        elif message == '/editpersonaldata':
            self.bot.sendMessage(chat_ID, "What do you want to edit? \n1.Name \n2.Email \nSelect an option by number")
            self.state[chat_ID]= {'step':'edit_cardiologist'}                           
        elif message == 'new_value':
            key = self.state[chat_ID]['field_to_update']   
            value = self.state[chat_ID]['updated_value']
            

            if key == 'cardiologistName':
                name_parts = value.split()
                if len(name_parts) < 2:
                    self.bot.sendMessage(chat_ID, "The name must contain both first name and last name.")
                    self.state[chat_ID]['step'] = 'waiting_new_value'
                    return

            elif key == 'cardiologistEmail':
                if "@" not in value or "." not in value:
                    self.bot.sendMessage(chat_ID, "Invalid email address. Please enter a valid email.")
                    self.state[chat_ID]['step'] = 'waiting_new_value'
                    return

            cardiologist_info[key] = value
            response = requests.put(self.url["updateCardiologist"], json=cardiologist_info, headers=self.headers)
            response.raise_for_status()
            r=response.json()
            self.bot.sendMessage(chat_ID, r["message"])

    def addPatient(self, chat_ID, cardiologistID):
        user_state = self.state[chat_ID]    
        patient_name = user_state.get('patient_name')
        patient_surname = user_state.get('patient_surname')   
        patient_gender = user_state.get('patient_gender')
        patient_dob = user_state.get('patient_dob')
        patient_id = self.generate_patient_id()
        devices = user_state.get('devices_list')
        patient_data = {
            "patientName": f"{patient_name} {patient_surname}",
            "patientID": patient_id,  
            "patientGender": patient_gender,
            "patientDoB": patient_dob,
            "devices": devices, 
            "cardiologistID": cardiologistID,  
            "lastUpdate": datetime.now().strftime("%d-%m-%Y")
        }
        response = requests.post(self.url["addPatient"], json=patient_data, headers=self.headers)
        response.raise_for_status()  
        message = response.json()
        if "message" in message.keys():
            self.bot.sendMessage(chat_ID, message["message"])
        
        self.bot.sendMessage(chat_ID, "Patient registered successfully! Now, please enter the Blood Pressure device ID or type 'None':")
        user_state['step'] = 'get_bp_id'
        user_state['patient_data'] = patient_data

    def updatePatient(self, chat_ID, message,patients): 
        if  len(patients)==0:
            self.bot.sendMessage(chat_ID, 'Your patient list is still empty. \nPlease, add your patients first')
            return

        elif message == '/deletepatient': 
            message = "Choose the patient to delete by entering the corresponding number:\n"
            for i, patient in enumerate(patients, start=1):
                message += f"{i}. {patient['patientName']}\n" 

            self.bot.sendMessage(chat_ID, message)                  
            self.state[chat_ID] = {'step': 'selecting_patient_delete' }  

        elif message == '/updatepatient': 
            message = "Choose the patient to update by entering the corresponding number:\n"
            for i, patient in enumerate(patients, start=1):
                message += f"{i}. {patient['patientName']}\n" 
            self.bot.sendMessage(chat_ID, message)
            self.state[chat_ID] = {'step': 'selecting_patient_update' }

        elif message == 'new_value':
            patient_info = next(p for p in patients if p['patientName'] == self.state[chat_ID]['patient_to_update']['patientName'])                    
            key = self.state[chat_ID]['field_to_update']   
            value = self.state[chat_ID]['updated_value']

            if key == 'patientName':
                name_parts = value.split()
                if len(name_parts) < 2:
                    self.bot.sendMessage(chat_ID, "The name must contain both first name and last name.")
                    self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                    return
                patient_info[key] = value

            elif key == 'patientDoB':
                try:
                    dob = datetime.strptime(value, "%d-%m-%Y").date() 
                    today = datetime.today().date() 
                    if dob > today:  
                        self.bot.sendMessage(chat_ID, "The date of birth cannot be in the future. Please enter a valid date (DD-MM-YYYY):")
                        return
                    else:
                        self.state[chat_ID]['patient_dob'] = dob.strftime("%d-%m-%Y")
                        self.state[chat_ID]['step'] = 'get_patient_gender'
                        self.bot.sendMessage(chat_ID, "Please enter the patient's gender (M/F):")
                except ValueError:
                    self.bot.sendMessage(chat_ID, "Invalid date format. Please use DD-MM-YYYY.")
                    self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                    return
            elif key == 'cardiologistID':
                try:
                    if int(value) in self.state[chat_ID]["valid_IDs"]:
                        patient_info[key] = int(value)
                    else:
                        self.bot.sendMessage(chat_ID, "Invalid ID. Please choose an existing cardiologist ID")
                        return
                except ValueError:
                    self.bot.sendMessage(chat_ID, "Invalid ID: it must be a number")
                    self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                    return

            elif key in ['ECG', 'BP', 'BS']:
                if value.lower()!='none' and not value.isdigit() :
                    if key == 'ECG' and value.lower() == 'none':
                        self.bot.sendMessage(chat_ID, "Invalid device ID. ECG is mandatory and the ID must be a numeric value.")
                        self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                        return
                    self.bot.sendMessage(chat_ID, "Invalid device ID. It must be a numeric value.")
                    self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                    return
                try:
                    new_device_id = int(value) if value.lower() != 'none' else None
                    devices_list = patient_info.get('devices', [])
                    existing_ids = {d['deviceID'] for d in devices_list if d['deviceID']}
                    if new_device_id in existing_ids:
                        self.bot.sendMessage(chat_ID, f"Invalid device ID. The IDs must be unique.")
                        self.state[chat_ID]['step'] = 'waiting_new_patient_value'
                        return
                    updated = False
                    for device in devices_list:
                        if device['measurement'].lower() == key.lower():
                            if new_device_id is None:  
                                device['deviceID'] = ""
                            else:
                                device['deviceID'] = new_device_id  
                            updated = True
                            break 
                    if not updated and new_device_id is not None:
                        if   devices_list == "":  
                            devices_list = [{"measurement": key, "deviceID": new_device_id}] 
                        else:
                            devices_list.append({"measurement": key, "deviceID": new_device_id})
                    patient_info['devices'] = devices_list
                except ValueError: 
                    self.bot.sendMessage(chat_ID, "Invalid device ID.")
            response = requests.put(self.url["updatePatient"], json=patient_info, headers=self.headers)
            response.raise_for_status()
            message=response.json()
            self.bot.sendMessage(chat_ID, message["message"])

    def remove(self, chat_ID, entity, id):        
        if entity == "cardiologist":
            response = requests.delete(self.url["deleteCardiologist"] + str(id), headers=self.headers)
            if response.status_code==409:
                self.bot.sendMessage(chat_ID, "You must edit your patient info to allocate to another cardiologist (/updatepatient -> cardiologist) or /deletepatient") 
                return
            response.raise_for_status()  

            
        elif entity == "patient":
            response = requests.delete(self.url["deletePatient"]+str(id), headers=self.headers)
            response.raise_for_status()
        r=response.json()
        self.bot.sendMessage(chat_ID, r["message"])    

    def on_chat_message(self, msg):
        content_type, chat_type, chat_ID = telepot.glance(msg)
        commands =self.settings["telegram_commands"]
        try:
            message = msg.get('text', '')
            if message == '/start':
                self.start_command(chat_ID)
                return
            if message != '/start' and message in commands:
                cardPatientList=self.get_cardPatient(chat_ID)
                if cardPatientList != 0:
                    if message == '/editpersonaldata' or message == '/unsubscribe':
                        self.updateCardiologist(chat_ID, message, cardPatientList)
                    elif message == '/addpatient':
                        self.add_patient_command(chat_ID)
                    elif message == '/updatepatient' or message == '/deletepatient':
                        self.updatePatient(chat_ID, message,cardPatientList["patients"])
                    elif message == '/viewpatientlist':
                        self.view_patients_command(chat_ID, cardPatientList)
                    elif message == '/dailyreport':
                        self.dailyreport_command(chat_ID,cardPatientList)
            else:
                self.handle_user_input(chat_ID, message)

        except json.JSONDecodeError as j:
            print(f"JSONDecodeError: {j}")
            self.bot.sendMessage(chat_ID, f"An error occured")  
        except ValueError as v: #The value errors are personalized for the single states
            pass    
        except requests.exceptions.HTTPError as h:
            body = h.response.json()
            print(f"\nHTTP {body['status']} {body['error']}URL: {h.response.url}\n")
            self.bot.sendMessage(chat_ID, f"{body['error']}")  
        except Exception as e:
            print(f"\nFor this message [{message}] the following exception occurred: {e}\n {traceback.format_exc()}")
            self.bot.sendMessage(chat_ID, f"An error occured")    
        finally:
            self.state.pop("chat_ID", None)  

            
    def generate_cardiologist_id(self): 
        cardiologists=requests.get(self.url["allCardiologists"],headers=self.headers)
        cardiologists = cardiologists.json()
        existing_ids=[]     
        for cardiologist in cardiologists:
            existing_ids.append(cardiologist['cardiologistID'])              
        return max(existing_ids, default=0) + 1
        
    def generate_patient_id(self):
        patients=requests.get(self.url["allPatients"],self.headers)
        patients = patients.json()
        existing_ids=[]     
        for patient in patients:
            existing_ids.append(patient['patientID'])              
        return max(existing_ids, default=0) + 1

    def get_cardPatient(self,chat_ID):
        r= requests.get(self.url["getByChatID"]+ str(chat_ID), headers=self.headers)

        if r.status_code==404:
            self.bot.sendMessage(chat_ID, "Invalid command. \nYou must register first by using /start.")
            return 0
        r.raise_for_status()
        cardPatientList=r.json()
        return cardPatientList
              
    def get_daily_report(self, chatID, patientID):
        daily_report=self.settings["contact_service_ID"]["daily_report"]
        r=requests.get(self.catalog+"searchByService/?ID="+str(daily_report),headers=self.headers)
        r.raise_for_status()
        service=r.json() 
        '''
        {
        "serviceID": 1,
        "serviceName": "Daily_report",
        "availableServices": ["REST"],
        "serviceDetails": [
        {
            "serviceType": "REST",
            "serviceIP": "localhost",
            "servicePort":8090
        }
                    ],
            "timestamp": 0
        }
        '''
        key=0
        availableServices=service["availableServices"]
        for element in availableServices:
            if element=="REST":
                for element2 in service["serviceDetails"]:
                    if element2["serviceType"]=="REST":
                        service_IP=element2["serviceIP"]
                        service_port=element2["servicePort"]
                        service_URI="http://"+service_IP+":"+str(service_port)+"/"
                        key=1
                        break           
                if key==1:
                    break
            
        uri=service_URI+f"dailyReport/?patientID={patientID}"
        self.bot.sendMessage(chatID,"Generating daily report...")
        r = requests.get(uri,headers=self.headers)
        if r.status_code == 404: 
            self.bot.sendMessage(chatID,"Daily report is not available")
            return
        r.raise_for_status()
        report_data = r.json()
        #if "error" in report_data.keys():
        #    self.bot.sendMessage(chatID,report_data)
        #    return
        filename = report_data["filename"]
        filedata = base64.b64decode(report_data["filedata"])
        pdf_file = io.BytesIO(filedata)
        pdf_file.name = filename 
        report_message = (f"*Daily Report:*\n\n"                                            
                                    f"Date: {datetime.today().strftime('%d-%m-%Y')}\n"
                                    f"Check the attached PDF for details.")

        self.bot.sendDocument(chatID, document=pdf_file, caption=report_message, parse_mode="Markdown")
        print(f"Report sent to cardiologist (Chat ID: {chatID})")


if __name__ == "__main__":
    config_file = "configuration_telegram.json" 
    conf = json.load(open(config_file))
        
    body= conf["serviceInfo"]          
    body["timestamp"] = time.time()    
    headers = {'Accept': 'application/json'}   
    try:             
        r=requests.post(conf["endpoints"]["registerService"], json=body, headers=headers)
        if r.status_code!=409:
            r.raise_for_status() 
            response=r.json()
            print(response["message"])
        else:
            print("The service is already present in the catalog. Proceeding to update...")

        r=requests.get(conf["endpoints"]["getBroker"],headers=headers)
        r.raise_for_status()
        r=r.json()
        broker=r["IP"]
        port=r["port"]

        id_serv=conf["contact_service_ID"]["control_strategy"]
        url_service=conf['catalog']+'searchByService/?ID='+str(id_serv)
        r1=requests.get(url_service,headers=headers)
        topic = []
        if r1.status_code !=404:
            r1.raise_for_status()
            r1=r1.json()
        
            for service in r1["serviceDetails"]:
                if service["serviceType"]=="MQTT":
                    for item in service["topic"]:
                        if "alert" in item:
                            topic.append(item)
        else:
            print(f"\nThe TELEGRAM SERVICE cannot communicate with the service with ID: {id_serv}\n")
         
        botistance=telepot.Bot(conf["token"]) 
        bot = TeleBot(conf, botistance)     
        subscriber_client=Subscriber(broker,port,topic,botistance,conf)
        subscriber_client.startSim()

        MessageLoop(bot.bot, bot.on_chat_message).run_as_thread()    
        print("Bot is now listening for messages...")
        
        while True:
            r=requests.put(conf["endpoints"]["updateService"],json=body, headers=headers)
            r.raise_for_status()
            print("Service updated")
            time.sleep(30)

    except requests.exceptions.HTTPError as e:
        body = e.response.json()
        print (f"\nHTTP Error - {body['status']}: {body['error']}") 
 
    except Exception as e:
        if "mqtt_client" in locals():
            subscriber_client.stopSim()
        print (f"\nThe following exception occurred: {e}:\n{traceback.format_exc()}")  

    except KeyboardInterrupt:
        print("Exiting program...")

    if "mqtt_client" in locals():
        subscriber_client.stopSim()


