import logging
import os
import time

os.environ["BLINKA_FT232H"] = "1"

logger = logging.getLogger("pyftdi.d2xx")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
#logger.addHandler(handler)

import board
import digitalio
import adafruit_bme680
from adafruit_blinka.microcontroller.ftdi_mpsse.mpsse.pin import Pin

leds = []
for i in range(4, 16):
    led = digitalio.DigitalInOut(Pin(i))
    led.direction = digitalio.Direction.OUTPUT
    leds.append(led)

i2c = board.I2C()
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, refresh_rate=1)

logger.setLevel(logging.INFO)

index = 0
inc = 1
while True:
    leds[index].value = 1

    print(f"Temperature: {bme680.temperature:0.1f}C, Humidity: {bme680.relative_humidity:0.1f}%")
    time.sleep(1)

    leds[index].value = 0
    if index == len(leds) - 1:
        inc = -1
    elif index == 0:
        inc = 1

    index += inc
