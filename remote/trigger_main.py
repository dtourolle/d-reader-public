from machine import Pin
import time
from IMU import IMU

import ulab

import bluetooth
from ble_advertising import advertising_payload

#ampy --port COM4 --baud 115200 put main.py

alivePin = Pin(23, Pin.OUT)    # create output pin on GPIO0
killPin = Pin(19, Pin.IN)  
time.sleep(2)
alivePin.on()

from micropython import const
import struct

_IRQ_CENTRAL_CONNECT                 = const(1 << 0)
_IRQ_CENTRAL_DISCONNECT              = const(1 << 1)
_IRQ_GATTS_WRITE                     = const(1 << 2)
# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_TEMP_CHAR = (bluetooth.UUID(0x2A6E), bluetooth.FLAG_READ|bluetooth.FLAG_NOTIFY,)
_ENV_SENSE_SERVICE = (_ENV_SENSE_UUID, (_TEMP_CHAR,),)

# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)


## Plan

# master programs
## key controller service
## learn service (use power key to start motion learning)
## analyse service
## bluetooth coms

class watchSensor:

    def __init__(self,alivePin=23,buttonPin=19,ble=bluetooth.BLE(),rxbuf=100,name='ereader-trigger'):
        self.IMU = IMU()
        self.alivePin = Pin(alivePin, Pin.OUT)
        self.alivePin.on()
        self.buttonPin = Pin(buttonPin, Pin.IN)
        self.press_time=0
        self._ble=ble
        self._handler = None
        self._ble.active(True)
        self._ble.irq(handler=self._irq)

        ((self._handle,),) = self._ble.gatts_register_services((_ENV_SENSE_SERVICE,))
        self._connections = set()
        self._payload = advertising_payload(name=name, services=[_ENV_SENSE_UUID], appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER)
        
        self._advertise()
        self.w = 0.05
        self.w1 = 1.0 - self.w
        self.EMA = ulab.array(2*[0])
        self.EMV = ulab.array(2*[0.1])
        self.EMV_min = ulab.array([5e-2, 0.1]) * 4
        self.trigger = ulab.array(2*[False])>1
        self.threshold = ulab.array(2*[8])
        self._payload = advertising_payload(name=name, services=[_ENV_SENSE_UUID])

    def update_motion(self):
        v= self.IMU.read_accelerometer_gyro_data() 
        temp = v*v
        temp = ulab.array([sum(temp[:3]),sum(temp[:3])])
        diff =  temp - self.EMA
        diff2 = diff*diff
        self.EMA = self.EMA + diff*self.w
        self.EMV = (self.EMV + diff2*self.w)*self.w1
        self.EMV[self.EMV<self.EMV_min]=self.EMV_min
        scale = (diff2/self.EMV)
        
        self.trigger = scale > self.threshold



    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _, = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _, = data
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()

    def _advertise(self, interval_us=500000):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)

    def set_temperature(self, temp_deg_c, notify=False):
        # Data is sint16 in degrees Celsius with a resolution of 0.01 degrees Celsius.
        # Write the local value, ready for a central to read.
        self._ble.gatts_write(self._handle, struct.pack('b', temp_deg_c))
        if notify:
            for conn_handle in self._connections:
                # Notify connected centrals to issue a read.
                self._ble.gatts_notify(conn_handle, self._handle)

    def check_button(self):

        if self.buttonPin.value():
            self.press_time +=0.1
        if self.press_time!=0 and self.buttonPin.value()==0:
            self.press_time = 0
        if self.press_time > 2:
            return True
        else:
            return False


    def close(self):
        for conn_handle in self._connections:
            self._ble.gap_disconnect(conn_handle)
        self._connections.clear()

    def exit(self):
        self.alivePin.off()

    def run(self):
        cool_down = False
        cool_time = 0
        self.set_temperature(0)
        while True:
            self.update_motion()
            if self.check_button():
                self.exit()
            trigger= max(self.trigger)
            if trigger== True and cool_down == False:
                cool_down = True

                print("triggered!!!")
                print("V",self.EMV)
                print("A",self.EMA)
                self.set_temperature(1)
                time.sleep(0.025)

            if cool_down:
                cool_time+=0.1
            
            if cool_time > 2:
                cool_time=0
                cool_down = False
                self.set_temperature(0)
            time.sleep(0.09)



w = watchSensor()
w.run()


