import pygame
import time

# Initialize mixer
pygame.mixer.init()

# Load audio
pygame.mixer.music.load("music.mp3")   # long track (music)
noise = pygame.mixer.Sound("rain.mp3")  # noise (shorter, but can loop)

# State trackers
music_playing = False
noise_playing = False
condition_met = False
last_condition_met = True


c = 0
def step():
    global condition_met, c
    c = (c+1)%10
    if c == 0: condition_met = not condition_met

while True:
    step()
    time.sleep(1)  # simulate a loop checking your condition
    print(condition_met, last_condition_met)

    if condition_met != last_condition_met:
        # Example: flip condition after 15 seconds
        if condition_met:
            print("Condition met → fade music out, fade noise in")

            if music_playing:
                pygame.mixer.music.fadeout(3000)
                music_playing = False

            if not noise_playing:
                noise.play(fade_ms=3000, loops=-1)  # loop noise forever
                noise_playing = True

        elif not condition_met:
            # When condition is False → fade in music
            if not music_playing:
                print("Condition false → fade music in")
                pygame.mixer.music.play(-1, fade_ms=3000)  # loop music
                music_playing = True

            # Stop noise if it was playing
            if noise_playing:
                noise.fadeout(3000)
                noise_playing = False

    last_condition_met = condition_met
