import time

import inky_layout
from inky_frame import button_b
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7 as DISPLAY

CHART_SECONDS = 180


def draw_ramp(graphics):
    black, white = 0, 1
    for i in range(inky_layout.RAMP_STEPS):
        x, y, w, h = inky_layout.ramp_step_rect(i)
        level = inky_layout.RAMP_LEVELS[i]
        err_row = [0.0] * (w + 1)
        for ry in range(h):
            err_next = [0.0] * (w + 1)
            reverse = ry & 1
            cols = range(w - 1, -1, -1) if reverse else range(w)
            for rx in cols:
                old = (level / 255.0) * 255 + err_row[rx]
                new = white if old >= 127.5 else black
                graphics.set_pen(new)
                graphics.pixel(x + rx, y + ry)
                err = old - (255.0 if new == white else 0.0)
                if reverse:
                    err_row[rx - 1] += err * 7 / 16 if rx > 0 else 0
                    err_next[rx] += err * 5 / 16
                    err_next[rx + 1] += err * 3 / 16 if rx < w - 1 else 0
                    err_next[rx - 1] += err * 1 / 16 if rx > 0 else 0
                else:
                    err_row[rx + 1] += err * 7 / 16 if rx < w - 1 else 0
                    err_next[rx] += err * 5 / 16
                    err_next[rx - 1] += err * 3 / 16 if rx > 0 else 0
                    err_next[rx + 1] += err * 1 / 16 if rx < w - 1 else 0
            err_row = err_next


def draw_chart(graphics, order):
    for slot, pen in enumerate(order):
        x, y, w, h = inky_layout.cell_rect(slot)
        graphics.set_pen(pen)
        graphics.rectangle(x, y, w, h)
    draw_ramp(graphics)
    graphics.update()


def wait_for_advance(seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if button_b.read():
            return
        time.sleep(0.05)


def main():
    graphics = PicoGraphics(DISPLAY)
    graphics.set_font("bitmap8")
    print("Probe charts: place panel flat on scanner glass for each chart.")
    print("Chart B appears after chart A (button B skips ahead).")
    for name in sorted(inky_layout.CHARTS):
        order = inky_layout.CHARTS[name]
        print(f"displaying chart {name}, slot order {order}")
        draw_chart(graphics, order)
        wait_for_advance(CHART_SECONDS)
    graphics.set_pen(1)
    graphics.clear()
    graphics.update()
    print("done")


main()
