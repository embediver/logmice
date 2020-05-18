#!/usr/bin/python3

import time
import signal
import os
import threading
import paho.mqtt.client as mqtt
import json

# Config Variables
###########################

PRINTDATA = False           # whether to print movements to stdout or not
LOGDATA = True              # whether to create csv files or not
LOGDIR = "logs"             # relative path where csv files will be dropped
COMPLETE_PATH_NAMES = False # switch between full path names or assigned numbers,
                            #   numbers will be assigned using the ordering in mice.config starting at 0

MQTT_ENABLE = True
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "test/logmice"
MQTT_MSG_INTERVAL = 0.5 # value in seconds

###########################

# setup handling of external stop signal
threads = []

def ctrl_c(signal, frame):
    print("Stopping threads...")
    for thread in threads:
        thread.setStop()
        if LOGDATA:
            thread.saveCSV()
    mqttHandler.setStop()
    mqttHandler.join()
    exit()
signal.signal(signal.SIGINT, ctrl_c)

# Config setup
####################################

if "mice.config" not in os.listdir("."):
    print("missing config: create a mice.config and add mice")
    print("\tadd full paths of mice one per line")
    print("\tuse \"ls -la /dev/input/by-path\" to list available mice")
    exit()

if LOGDIR not in os.listdir("."):
    os.mkdir(LOGDIR)

# parse config and create file deskriptors for all devices
inpDevices = open("mice.config", "r")
mice = {}
for dev in inpDevices:
    dev = dev.rstrip()
    if len(dev) <=1:
        continue
    if COMPLETE_PATH_NAMES:
        miceId = dev.split('/')[-1]
        mice[miceId] = open(dev, 'rb')
    else:
        mice[str(len(mice))] = open(dev, 'rb')

if len(mice) == 0:
    print("No devices found in mice.config")
    print("\tadd full paths of mice one per line")
    print("\tuse \"ls -la /dev/input/by-path\" to list available mice")
    exit()


# MQTT Setup
######################################

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker! status code:", rc)

class mqttThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True
        self.mqttcl = mqtt.Client()
        self.mqttcl.on_connect = on_connect
        
        self.mqttcl.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqttcl.loop_start()
    def run(self):
        summed = {}
        data = {}

        while self.running:
            for thread in threads:
                data[thread.dev_name] = thread.getNewValues()
            for mouse in data:
                if len(data[mouse]) == 0: # skip when nothing available
                    if mouse in summed:
                        del summed[mouse] # delete key to not send old data
                    continue
                dx = dy = 0
                for update in data[mouse]: # sum up all movements
                    dx += update[1]
                    dy += update[2]
                # append to dict
                summed[mouse] = {"ms": data[mouse][-1][0], "dx": dx, "dy": dy}

            if len(summed) > 0: # only send an update when data is available
                self.mqttcl.publish(MQTT_TOPIC, json.dumps(summed))
            time.sleep(MQTT_MSG_INTERVAL)

        self.mqttcl.disconnect()


    def setStop(self):
        self.running = False
# end of mqtt thread class


# Thread implementation for Mouse reading
######################################

def millis():
    return round(time.time()*1000)

class mouseThread(threading.Thread):
    def __init__(self, dev_handle, dev_name):
        threading.Thread.__init__(self)
        self.dev_handle = dev_handle
        self.dev_name = dev_name
        self.lock = threading.Lock()
        self.cursor = 0
    def run(self):
        self.running = True
        self.readings = []


        starttime = millis()
        while self.running:
            # read the mice and immediatly take the time of the event
            status, dx, dy = tuple(c for c in self.dev_handle.read(3))
            now = millis() - starttime

            # break if thread was asked to stop
            # (unfortunate there is no easy way (in python) to stop reading a char device until some data comes in and returns the read call)
            if not self.running:
                break
            
            def to_signed(n):
                return n - ((0x80 & n) << 1)
                
            dx = to_signed(dx)
            dy = to_signed(dy)
            with self.lock:
                self.readings.append((now, dx, dy))
            if PRINTDATA:
                print(self.dev_name, dx, dy)
        print("thread for", self.dev_name, "stopped")

    def setStop(self):
        self.running = False

    def saveCSV(self):
        if len(self.readings) == 0:
            print("\nNo data to save for ", self.dev_name, "!\n")
            return
        with open(LOGDIR+"/"+self.dev_name+".csv", 'w') as csv:
            with self.lock:
                for reading in self.readings:
                    csv.write(str(reading[0])+','+str(reading[1])+','+str(reading[2])+'\n')
        print("\nSaved csv for ", self.dev_name,"\n")
        
    def getNewValues(self):
        with self.lock:
            current = self.cursor
            self.cursor = len(self.readings)
            return self.readings[current:]
# end of mouse thread class

# create and start a thread for every mouse
for key in mice.keys():
    threads.append(mouseThread(mice[key], key))
for thread in threads:
    thread.start()

if MQTT_ENABLE:
    mqttHandler = mqttThread()
    mqttHandler.start()
print("Multi-reader started (reading", len(mice), "devices, debug output",PRINTDATA,")")
