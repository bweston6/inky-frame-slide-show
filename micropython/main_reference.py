from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7
import inky_frame
from sdcard import SDCard
import os
import random
from machine import Pin, SPI
import gc
from micropython import const
import pngdec
import time

display = PicoGraphics(DISPLAY_INKY_FRAME_7)
png = pngdec.PNG(display)

def showImage(path):
    png.open_file(path)
    png.decode(0, 0)
    display.update()

def showImageFromSDCard(path):
    led = Pin(6, Pin.OUT)
    led.value(1)
    sd_spi = SPI(0, sck = Pin(18, Pin.OUT), mosi = Pin(19, Pin.OUT), miso = Pin(16, Pin.OUT))
    sd = SDCard(sd_spi, Pin(22))
    os.mount(sd, "/sd")
    showImage("/sd/" + path)
    os.umount("/sd")
    del sd
    del sd_spi
    led.value(0)
    
def countFilesInDir(dir):
    files = os.ilistdir(dir)
    count = 0
    for file in files:
        count += 1
    return count

def showRandomImageFromSDCard():
    led = Pin(6, Pin.OUT)
    led.value(1)
    
    sd_spi = SPI(0, sck = Pin(18, Pin.OUT), mosi = Pin(19, Pin.OUT), miso = Pin(16, Pin.OUT))
    sd = SDCard(sd_spi, Pin(22))
    os.mount(sd, "/sd")
    
    print("counting files")
    fileCount = countFilesInDir("/sd")
    print(fileCount)
    
    print("reading random filename")
    randomIndex = random.randint(1, fileCount)
    files = os.ilistdir("/sd")
    for count in range(randomIndex - 1):
        next(files)
    filename = next(files)[0]
    
    print("showing " + filename)
    gc.collect()
    showImage("/sd/" + filename)
    
    os.umount("/sd")
    del sd
    del sd_spi
    led.value(0)

IDLE = const(0)
PICTURE = const(1)
TEST = const(2)

state = PICTURE

while True:
    if inky_frame.button_e.read() or (
        inky_frame.woken_by_button() and inky_frame.button_e.startup_state
    ):
        state = TEST
    else:
        state = PICTURE

    # deal with state
    if (state is PICTURE):
        print("state = PICTURE")
        state = IDLE
        showRandomImageFromSDCard()
    if (state is TEST):
        print("state = TEST")
        state = IDLE
        w, h = display.get_bounds()
        for colour in range(8):
            display.set_pen(colour)
            display.rectangle(int(colour * w / 8), 0, int(w / 8), h)
        display.update()
    
    # 6hrs
    print("Sleeping")
    inky_frame.sleep_for(6 * 60)