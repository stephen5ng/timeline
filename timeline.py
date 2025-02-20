#!/usr/bin/env python

import aiomqtt
import asyncio
from functools import reduce
import math
import os
from PIL import Image, ImageDraw
import platform
import pygame
import pygame.gfxdraw
from pygame import Color
import pygame.freetype
from pyvidplayer2 import Video
import re
import string
import sys
import textrect
from typing import Callable

from pygameasync import Clock
from get_key import get_key
import my_inputs
import hub75

SCALING_FACTOR = 9
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 96

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")

def load_text_file_to_array(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:  # Use utf-8 encoding for broader character support
        lines = file.readlines()  # Read all lines into a list
        lines = [line.strip().upper() for line in lines]
    return lines

def read_lines_from_file(filepath):
    with open(filepath, 'r') as file:  # 'r' for reading
        lines = file.readlines()
        lines = [line.strip() for line in lines]
        return lines

quit_app = False

def draw_pie(surface, color, center, radius, start_angle, end_angle):
    large_size = (radius*8, radius*8)
    print(f"center {center}")
    pil_image = Image.new("RGBA", large_size)
    draw = ImageDraw.Draw(pil_image)
    draw.pieslice([(0, 0), large_size], start=start_angle, end=end_angle, fill=tuple(color))
    pil_image = pil_image.resize((radius*2, radius*2), resample=Image.Resampling.LANCZOS)

    data = pil_image.tobytes()
    s = pygame.image.fromstring(data, pil_image.size, pil_image.mode).convert_alpha()
    # s.set_alpha(color.a)
    surface.blit(s, center)

async def trigger_events_from_mqtt(subscribe_client: aiomqtt.Client):
    global quit_app
    async for message in subscribe_client.messages:
        if message.topic.matches("password_game/quit"):
            quit_app = True

async def run_game():
    global quit_app
    vid = Video("images/dinosaursRko0LigjmAQ_trimmed_64.mov", use_pygame_audio=True)
    print(f"size: {vid.current_size}")
    lines = read_lines_from_file("timeline.txt")

    clock = Clock()
    pygame.freetype.init()
    display_surface = pygame.display.set_mode(
       (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))

    font_guess = pygame.freetype.Font("raize-13.pcf", 13)
    font_small = pygame.freetype.Font("scientifica-11.bdf", 11)
    textrecter = textrect.TextRectRenderer(font_small,
        pygame.Rect(0, 0, 128, 64), Color("green"))
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), flags=pygame.SRCALPHA)
    screen = screen.convert_alpha()
    letters = ""
    guess = ""
    current_position = 0
    last_direction = 0
    start_movement = 0
    angle = 0
    while True:
        angle += 1
        angle = angle % 360
        if quit_app:
            return
        screen.fill((0, 0, 0))
        if not vid.active:
            vid.restart()
        vid.draw(screen, (32, 32), force_draw=True)
        smaller = 10
        draw_pie(screen, Color(0, 80, 0, 30), (32+smaller, 32+smaller), 32-smaller, 270, angle/10)
        smaller = 20
        draw_pie(screen, Color(80, 80, 0, 100), (32+smaller, 32+smaller), 32-smaller, 270, angle/40)
        draw_pie(screen, Color(80, 0, 0, 50), (32, 32), 32, 270, angle)

        show_cursor = (pygame.time.get_ticks()*2 // 1000) % 2 == 0
        print_guess = guess + ("_" if show_cursor else " ")
        current_line = lines[current_position][:60]
        # print(f"current line: {current_line}")
        date, description = current_line.split(':')
        line_date = float(date)
        disp_date = ""
        if line_date < 0:
            if line_date < -1e9:
                frac_part = -line_date / 1e9
                disp_date = f"{frac_part} bya"
            elif line_date < -1e6:
                frac_part = -line_date / 1e6
                disp_date = f"{frac_part} mya"
            else:
                disp_date = "{:.0f}".format(int(line_date))
        else:
            disp_date = int(line_date)
            print(f"{disp_date} {line_date}")
        rendered = textrecter.render(f"{disp_date}: {description}")
        screen.blit(rendered, (0, 3))

        pygame.draw.line(screen, Color("orange"), (0, 0), (128, 0))
        pygame.draw.circle(screen, Color("red"), (current_position+90, 1), 1)

        for key, keydown in get_key():
            print(f"{key}, {keydown}")
            if keydown:
                start_movement = pygame.time.get_ticks()
                if key == "right":
                    last_direction = 1
                elif key == "left":
                    last_direction = -1
            elif not keydown:
                last_direction = 0
            if key == "quit":
                return
            elif key == "escape":
                guess = ""
            elif key == "backspace":
                guess = guess[:-1]
            elif len(key) == 1:
                guess += key

            current_position += last_direction
            current_position = min(current_position, len(lines)-1)
            current_position = max(current_position, 0)
        hub75.update(screen)
        pygame.transform.scale(screen,
        display_surface.get_rect().size, dest_surface=display_surface)
        pygame.display.update()
        await clock.tick(30)

async def main():
    async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
        await subscribe_client.subscribe("#")
        subscribe_task = asyncio.create_task(
            trigger_events_from_mqtt(subscribe_client),
            name="mqtt subscribe handler")

        await run_game()
        subscribe_task.cancel()
        pygame.quit()

if __name__ == "__main__":
    if platform.system() != "Darwin":
        my_inputs.get_key()

    hub75.init()
    pygame.init()

    asyncio.run(main())
