import os
import time

from machine import Pin, SPI
import sdcard
import inky_frame
from inky_frame import button_a, button_c, button_e
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7 as DISPLAY
import pngdec

IMAGE_DIR = "/sd/images"


def mount_sd():
    sd_spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
    sd = sdcard.SDCard(sd_spi, Pin(22))
    os.mount(sd, "/sd")


def list_images():
    files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(".png")]
    return sorted(files)


def show(graphics, png, path):
    graphics.set_pen(1)
    graphics.clear()
    try:
        png.open_file(path)
        png.decode(0, 0)
    except OSError as e:
        graphics.set_pen(4)
        graphics.text(f"cannot decode {path}: {e}", 10, 10, 780, 2)
    graphics.update()


def main():
    graphics = PicoGraphics(DISPLAY)
    graphics.set_font("bitmap8")
    png = pngdec.PNG(graphics)

    graphics.set_pen(1)
    graphics.clear()
    graphics.update_pen(6, 255, 109, 0)
    graphics.set_pen(0)
    graphics.text("mounting SD...", 20, 20, 760, 3)
    graphics.update()

    mount_sd()
    images = list_images()
    if not images:
        graphics.clear()
        graphics.text("no PNGs found in " + IMAGE_DIR, 20, 20, 760, 3)
        graphics.update()
        return

    index = 0
    show(graphics, png, f"{IMAGE_DIR}/{images[index]}")
    while True:
        if button_a.read():
            index = (index - 1) % len(images)
            show(graphics, png, f"{IMAGE_DIR}/{images[index]}")
            time.sleep(0.5)
        if button_c.read():
            index = (index + 1) % len(images)
            show(graphics, png, f"{IMAGE_DIR}/{images[index]}")
            time.sleep(0.5)
        if button_e.raw():
            inky_frame.turn_off()
            return
        time.sleep(0.05)


main()
