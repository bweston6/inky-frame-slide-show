# Inky Frame 7.3 photo frame: show a random image from the SD card every 6
# hours, then cut power completely (RTC alarm wakes the board). The frame's
# A-E buttons are not reachable in this installation; the RESET button on the
# back doubles as a "next photo" control - it reruns this script, which draws
# a fresh random image before sleeping again. Images must be 800x480 indexed
# PNGs produced by pipeline/process.py - they already contain exact pen codes,
# so pngdec's dither is a pass-through.

import gc
import os
import random

import inky_frame
import pngdec
from machine import SPI, Pin
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7 as DISPLAY
from sdcard import SDCard

INTERVAL_MINUTES = 6 * 60
SD_MOUNT = "/sd"

# Our pipeline encodes orange as (255,109,0) because nominal orange is not an
# exact match in pngdec's dither cache; re-point pen 6 at that code so it
# renders as pure pigment instead of an orange/yellow micro-pattern.
ORANGE_PNG_CODE = (255, 109, 0)

graphics = PicoGraphics(DISPLAY)
png = pngdec.PNG(graphics)
# Apply once at startup: every decode inherits the corrected orange.
graphics.update_pen(6, *ORANGE_PNG_CODE)


def mount_sd():
    spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
    sd = SDCard(spi, Pin(22))
    os.mount(sd, SD_MOUNT)
    return sd


def list_images():
    try:
        names = os.listdir(SD_MOUNT)
    except OSError:
        return []
    return sorted(f for f in names if f.lower().endswith(".png"))


def show_message(text):
    graphics.set_pen(1)
    graphics.clear()
    graphics.set_pen(0)
    graphics.text(text, 10, 10, 780, 2)
    graphics.update()


def show_random_image(files):
    # Try a few draws so one corrupt file can't blank a whole 6-hour cycle.
    for attempt in range(3):
        path = SD_MOUNT + "/" + files[random.randrange(len(files))]
        print("showing", path)
        try:
            png.open_file(path)
            png.decode(0, 0)
        except (OSError, ValueError) as e:
            print("failed:", e)
            if attempt == 2:
                raise
        else:
            graphics.update()
            return


def go_to_sleep():
    inky_frame.led_busy.off()
    print("sleeping for", INTERVAL_MINUTES, "minutes")
    inky_frame.sleep_for(INTERVAL_MINUTES)


def main():
    # Activity light on while we work (SD access + png decode take a while).
    inky_frame.led_busy.on()
    sd = None
    try:
        sd = mount_sd()
        files = list_images()
        if not files:
            show_message("no images on sd card")
        else:
            print(len(files), "images")
            gc.collect()
            show_random_image(files)
    except Exception as e:
        print("error:", e)
        try:
            show_message("sd card error")
        except Exception:
            pass
    finally:
        try:
            if sd is not None:
                os.umount(SD_MOUNT)
        except OSError:
            pass
        del sd
        gc.collect()

    go_to_sleep()


main()
