#!/usr/bin/env python

import aiomqtt
import asyncio
from functools import reduce
import math
import os
import platform
import pygame
from pygame import Color
import pygame.freetype
import re
import string
import sys
from typing import Callable

from pygameasync import Clock
from get_key import get_key
import my_inputs
import hub75

SCALING_FACTOR = 9
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 32

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")

MATRIX = [
    "APOC",
    "CHOI",
    "CYPHER",
    "DOZER",
    "DUFOUR",
    "MORPHEUS",
    "MOUSE",
    "NEO",
    "ORACLE",
    "RHINEHEART",
    "SMITH",
    "SWITCH",
    "TANK",
    "TRINITY",
]

LOST = [4, 8, 15, 16, 23, 42]

SEVERANCE = [
    "MARK",
    "HELLY",
    "IRVING",
    "PETEY",
    "DYLAN",
    "HUANG",
    "CASEY",
    ]

def load_text_file_to_array(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:  # Use utf-8 encoding for broader character support
        lines = file.readlines()  # Read all lines into a list
        lines = [line.strip().upper() for line in lines]
    return lines

palindromes = load_text_file_to_array("palindromes5.txt")

def read_lines_from_file(filepath):
    with open(filepath, 'r') as file:  # 'r' for reading
        lines = file.readlines()
        lines = [line.strip() for line in lines]
        return lines

def digits(p):
    return [int(n) for n in re.findall(r"\d+", p)]

def numbers_pow(p):
    numbers = digits(p)
    sum = reduce(lambda x, y: x + y, numbers, 0) if isinstance(numbers, list) else 0
    return (sum & (sum - 1)) == 0

def is_prime(n):
    """Check if a number is prime."""
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6  # Skip even numbers and multiples of 3

    return True

def extract_roman_numerals(text):
    # Define a regex pattern for valid Roman numerals
    pattern = r'(M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3}))'

    # Use re.finditer to extract matches
    matches = re.finditer(pattern, text)

    # Extract full Roman numerals
    roman_numerals = []
    last_end = -1

    for match in matches:
        numeral = match.group(1)
        start = match.start()

        # Ensure numerals are not overlapping (prevent partial matches)
        if start > last_end:
            roman_numerals.append(numeral)
            last_end = match.end()

    return [r for r in roman_numerals if r]

def roman_to_int(s):
    roman_values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }

    total = 0
    prev_value = 0

    for char in reversed(s):  # Process from right to left
        value = roman_values[char]

        if value < prev_value:
            total -= value  # Subtractive notation (e.g., IV = 4)
        else:
            total += value

        prev_value = value  # Update previous value

    return total

def romans_product(p):
    romans = extract_roman_numerals(p)
    numbers = [roman_to_int(r) for r in romans]
    return math.prod(numbers)

rules = [("ENTER A PASSWORD", lambda p: p),
    ("MUST CONTAIN A NUMBER", lambda p: bool(re.search(r"\d", p))),
    ("AND AN UPPERCASE LETTER", lambda p: any(c.isupper() for c in p)),
    ("ALSO A SPECIAL CHAR", lambda p: any(c in string.punctuation for c in p)),
    ("AND A ROMAN NUMERAL", lambda p: extract_roman_numerals(p)),
    ("AT LEAST 5 CHARACTERS", lambda p: len(p) >= 5),
    ("CHAR FROM *THE MATRIX*", lambda p: any(character in p.upper() for character in MATRIX)),
    ("INCLUDE A PALINDROME", lambda p: any(character in p.upper() for character in palindromes)),
    ("A NUMBER FROM *LOST*", lambda p: set(digits(p)).intersection(set(LOST))),
    ("PRIME NUMBER OF VOWELS", lambda p: is_prime(1 for c in p.lower() if c in "aeiou")),
    ("NAME A SEVERANCE INNIE", lambda p: any(character in p.upper() for character in SEVERANCE)),
    ("NUMBERS SUM TO A POW OF 2", numbers_pow),
    ("ROMAN #'S MULTIPLY TO 35", lambda p: romans_product(p) == 35),
    ]

quit_app = False

async def trigger_events_from_mqtt(subscribe_client: aiomqtt.Client):
    global quit_app
    async for message in subscribe_client.messages:
        if message.topic.matches("password_game/quit"):
            quit_app = True

async def run_game():
    global quit_app
    lines = read_lines_from_file("hamlet.txt")

    clock = Clock()
    pygame.freetype.init()
    display_surface = pygame.display.set_mode(
       (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))

    # pygame.display.set_caption('Circus Circus')

    font_guess = pygame.freetype.Font("raize-13.pcf", 13)
    font_small = pygame.freetype.Font("scientifica-11.bdf", 11)
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    letters = rules[0][0]
    guess = ""
    current_position = 0
    last_direction = 0
    start_movement = 0
    while True:
        if quit_app:
            return
        screen.fill((0, 0, 0))
        show_cursor = (pygame.time.get_ticks()*2 // 1000) % 2 == 0
        print_guess = guess + ("_" if show_cursor else " ")
        line_surf, r = font_small.render(lines[current_position], Color("green"), Color("black"))
        screen.blit(line_surf, (0, 9-r[1]))

        pygame.draw.line(screen, Color("orange"), (0, 0), (128, 0))
        pygame.draw.circle(screen, Color("green"), (current_position, 1), 1)

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
            elif key == "quit":
                return
            elif key == "escape":
                guess = ""
            elif key == "backspace":
                guess = guess[:-1]
            elif len(key) == 1:
                guess += key

        current_position += last_direction

        for rule in rules:
            if not rule[1](guess):
                letters = rule[0]
                break
            else:
                letters = "THANK YOU"

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
