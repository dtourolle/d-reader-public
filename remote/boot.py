# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
from machine import Pin

alivePin = Pin(23, Pin.OUT)    # create output pin on GPIO0
alivePin.on()                 # set pin to "on" (high) level