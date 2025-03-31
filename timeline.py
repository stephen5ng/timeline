#!/usr/bin/env python

# Standard library imports
import asyncio
import math
import os
import platform
import re
import string
import sys
from functools import reduce
from typing import Callable, List, Tuple, Optional, Dict
import json

# Third-party imports
import aiomqtt
from PIL import Image, ImageDraw
import pygame
import pygame.gfxdraw
from pygame import Color
import pygame.freetype
from pyvidplayer2 import Video
import textrect

# Local imports
from pygameasync import Clock
from get_key import get_key
import my_inputs
import hub75

# Constants
SCALING_FACTOR: int = 9
SCREEN_WIDTH: int = 128
SCREEN_HEIGHT: int = 128
MQTT_SERVER: str = os.environ.get("MQTT_SERVER", "localhost")
FPS: int = 30

# To convert the video to a smaller size:
# ffmpeg -i images/dinosaurs.mov -vf "scale=96:96:force_original_aspect_ratio=increase,crop=128:128" \
# -c:a copy images/dinosaurs_128.mov

class TimelineGame:
    def __init__(self):
        self.quit_app: bool = False
        self.video: Optional[Video] = None
        self.events: List[Dict[str, float | str]] = []
        self.clock: Optional[Clock] = None
        self.display_surface: Optional[pygame.Surface] = None
        self.screen: Optional[pygame.Surface] = None
        self.font_guess: Optional[pygame.freetype.Font] = None
        self.font_small: Optional[pygame.freetype.Font] = None
        self.textrecter: Optional[textrect.TextRectRenderer] = None
        self.letters: str = ""
        self.guess: str = ""
        self.current_position: int = 0
        self.last_direction: int = 0
        self.start_movement: int = 0
        self.angle: int = 0
        self.last_position: int = 0

    def load_timeline_data(self, filepath: str) -> List[Dict[str, float | str]]:
        """Load timeline data from JSON file."""
        with open(filepath, 'r') as file:
            return json.load(file)

    def draw_pie(self, surface: pygame.Surface, color: Color, center: Tuple[int, int], 
                 radius: int, start_angle: float, end_angle: float) -> None:
        """Draw a pie slice on the surface."""
        large_size = (radius*8, radius*8)
        pil_image = Image.new("RGBA", large_size)
        draw = ImageDraw.Draw(pil_image)
        draw.pieslice([(0, 0), large_size], start=start_angle, end=end_angle, fill=tuple(color))
        pil_image = pil_image.resize((radius*2, radius*2), resample=Image.Resampling.LANCZOS)

        data = pil_image.tobytes()
        s = pygame.image.frombytes(data, pil_image.size, pil_image.mode).convert_alpha()
        surface.blit(s, center)

    def format_date(self, line_date: float) -> str:
        """Format the date for display."""
        if line_date < 0:
            if line_date < -1e9:
                return f"{-line_date / 1e9} bya"
            elif line_date < -1e6:
                return f"{-line_date / 1e6} mya"
            return f"{int(line_date)}"
        return str(int(line_date))

    def handle_key_input(self, key: str, keydown: bool) -> None:
        """Handle keyboard input."""
        if keydown:
            self.start_movement = pygame.time.get_ticks()
            self.last_direction = 1 if key == "right" else -1 if key == "left" else 0
        elif not keydown:
            self.last_direction = 0

        if key == "quit":
            self.quit_app = True
        elif key == "escape":
            self.guess = ""
        elif key == "backspace":
            self.guess = self.guess[:-1]
        elif len(key) == 1:
            self.guess += key

        self.current_position = max(0, min(self.current_position + self.last_direction, len(self.events)-1))

    async def run_game(self) -> None:
        """Main game loop."""
        self.events = self.load_timeline_data("timeline.json")
        self.video = None
        self.clock = Clock()
        
        pygame.freetype.init()
        self.display_surface = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        
        self.font_guess = pygame.freetype.Font("raize-13.pcf", 13)
        self.font_small = pygame.freetype.Font("scientifica-11.bdf", 11)
        self.textrecter = textrect.TextRectRenderer(
            self.font_small, pygame.Rect(0, 0, 128, 64), Color("green"))
        
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), flags=pygame.SRCALPHA)
        self.screen = self.screen.convert_alpha()

        while not self.quit_app:
            self.angle = (self.angle + 1) % 360
            
            self.screen.fill((0, 0, 0))
            if self.video:
                if not self.video.active:
                    self.video.restart()
                self.video.draw(self.screen, (0, 0), force_draw=True)

            # Update video when position changes
            if self.current_position != self.last_position:
                current_event = self.events[self.current_position]
                if "video" in current_event:
                    self.video = Video(current_event["video"], use_pygame_audio=True)
                else:
                    self.video = None
                self.last_position = self.current_position

            # Draw pie animations
            smaller = 10
            self.draw_pie(self.screen, Color(0, 80, 0, 30), 
                         (32+smaller, 32+smaller), 32-smaller, 270, self.angle/10)
            smaller = 20
            self.draw_pie(self.screen, Color(80, 80, 0, 100), 
                         (32+smaller, 32+smaller), 32-smaller, 270, self.angle/40)
            self.draw_pie(self.screen, Color(80, 0, 0, 50), 
                         (32, 32), 32, 270, self.angle)

            # Draw timeline
            show_cursor = (pygame.time.get_ticks()*2 // 1000) % 2 == 0
            print_guess = self.guess + ("_" if show_cursor else " ")
            current_event = self.events[self.current_position]
            date = current_event["date"]
            description = current_event["description"]
            disp_date = self.format_date(date)

            rendered = self.textrecter.render(f"{disp_date}: {description}")
            self.screen.blit(rendered, (0, 3))

            # Draw timeline indicator
            pygame.draw.line(self.screen, Color("orange"), (0, 0), (128, 0))
            pygame.draw.circle(self.screen, Color("red"), (self.current_position+90, 1), 1)

            # Handle input
            for key, keydown in get_key():
                self.handle_key_input(key, keydown)

            # Update display
            hub75.update(self.screen)
            pygame.transform.scale(self.screen,
                self.display_surface.get_rect().size, dest_surface=self.display_surface)
            pygame.display.update()
            
            await self.clock.tick(FPS)

async def trigger_events_from_mqtt(subscribe_client: aiomqtt.Client, game: TimelineGame) -> None:
    """Handle MQTT events."""
    async for message in subscribe_client.messages:
        if message.topic.matches("password_game/quit"):
            game.quit_app = True

async def main() -> None:
    """Main entry point."""
    game = TimelineGame()
    async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
        await subscribe_client.subscribe("#")
        subscribe_task = asyncio.create_task(
            trigger_events_from_mqtt(subscribe_client, game),
            name="mqtt subscribe handler")

        await game.run_game()
        subscribe_task.cancel()
        pygame.quit()

if __name__ == "__main__":
    if platform.system() != "Darwin":
        my_inputs.get_key()

    hub75.init()
    pygame.init()

    asyncio.run(main())
