#!/usr/bin/python3

import time
import signal
import os
import threading

# Config Variables
###########################

PRINTDATA = True
LOGDIR = "logs"

###########################

# setup handling of external stop signal
threads = []

def ctrl_c(signal, frame):
    print("Stopping threads...")
    for thread in threads:
        thread.setStop()
        thread.saveCSV()
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

inpDevices = open("mice.config", "r")
mice = {}
for dev in inpDevices:
    dev = dev.rstrip()
    if len(dev) <=1:
        continue
    miceId = dev.split('/')[-1]
    mice[miceId] = open(dev, 'rb')

if len(mice) == 0:
    print("No devices found in mice.config")
    print("\tadd full paths of mice one per line")
    print("\tuse \"ls -la /dev/input/by-path\" to list available mice")
    exit()

#csv = open('output.csv', "w")

######################################

def millis():
    return round(time.time()*1000)

class mouseThread(threading.Thread):
    def __init__(self, dev_handle, dev_name):
        threading.Thread.__init__(self)
        self.dev_handle = dev_handle
        self.dev_name = dev_name
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
            for reading in self.readings:
                csv.write(str(reading[0])+','+str(reading[1])+','+str(reading[2])+'\n')
        print("\nSaved csv for ", self.dev_name,"\n")
        

# create and start a thread for every mice
for key in mice.keys():
    threads.append(mouseThread(mice[key], key))
for thread in threads:
    thread.start()
print("Multi-reader started (reading", len(mice), "devices, debug output",PRINTDATA,")")
