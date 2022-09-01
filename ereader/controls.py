
from time import sleep
import threading


import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
from time import time
from bluepy.btle import UUID, Peripheral
#import bluetooth
#trigger MACV adress : 80:7D:3A:C5:29:1E
class check_gpio:
    
    def __init__(self):
        self.meanings = {26:'up',13:'left',22:'down',19:'right',27:'power'}
        self.last_key = None
        self.new_press = False
        self.last_press = None
        self.ble_last_press = None
        self.running=True
        GPIO.setmode(GPIO.BCM)
        for button in self.meanings.keys():
            GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True
        self.ble_button = None
        self.dev=None
        self.char=None
        #try:
        #    self.dev = Peripheral("80:7D:3A:C5:29:1E", 'public')
        #    self.char = self.dev.getCharacteristics()[-1]
        #except:

        self.press_time = None
        self.thread_ble = None

        if self.dev:
            self.state = self.dev.getState()
        else:
            self.state='disc'
        #self.thread_ble_state = threading.Thread(target=self.ble_state_update, args=())
        #self.thread_ble_state.start()
        
        self.thread_ble_press =  threading.Thread(target=self.ble_button_checker, args=())
        self.thread_ble_press.start()
        self.thread.start()

    def run(self):
        while self.running:
            for button in self.meanings.keys():
                if (self.last_press == None) and (GPIO.input(button) == GPIO.HIGH):
                    self.last_key = button
                    self.last_press = button
                    self.new_press = True
                if GPIO.input(button) == GPIO.LOW and self.last_press == button:
                    self.last_press = None

                    sleep(0.01)

            if self.char is not None:
                if self.ble_button is not None and self.ble_last_press == None:
                    self.last_key = self.ble_button
                    self.ble_last_press = self.ble_button
                    print("Bluetooth press")
                elif self.ble_button is None and self.ble_last_press is not None:
                    self.ble_last_press = None
                    

                    
            sleep(0.05)

    def ble_button_checker(self):

        while self.dev is not None:
            sleep(0.1)
            try:
                if self.char is not None:
                    bluetooth=list(self.char.read())[0]
                    if bluetooth==1:
                        self.ble_button  = 'up'
                    else:
                        self.ble_button  = None
                        #print(self.last_key)
            except:
                self.dev = None
                self.char= None
        
    def read_out(self):
        self.new_press = False
        key = self.last_key
        self.last_key = None
        return self.meanings.get(key,key)


    def connect_ble(self):
        tries =0
        while (self.dev is None) and tries<10:
            print("searching_bluetooth")
            try:
            
                self.dev = Peripheral("80:7d:3a:c5:29:1e",'public')
                self.char = self.dev.getCharacteristics()[-1]
                print("ble connected")
                self.thread_ble_press =  threading.Thread(target=self.ble_button_checker, args=())
                self.thread_ble_press.start()
            
            except:
                print("ble fail")
                self.dev = None
                self.char = None
            tries+=1
            sleep(5)
        self.thread_ble = None

    def ble_state_update(self):

        while self.running:
            sleep(5)
            if hasattr(self.dev,'getState'):
                try:
                    self.state= self.dev.getState()
                except:
                    pass
            else:
                self.state='disc'
            
            if self.state == 'disc':
                self.dev = None
                self.char = None
                #try:
                #    self.thread_ble.join()
                #except:
                #    pass
                #self.thread_ble = threading.Thread(target=self.connect_ble, args=())
                #self.thread_ble.start()



            #self.state = 'disc'

            

    def ble_state(self):
        return self.state

    def stop(self):
        self.running = False



