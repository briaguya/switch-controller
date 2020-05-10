#!/usr/bin/env python3


import argparse
from contextlib import contextmanager

import sdl2
import sdl2.ext
import struct
import binascii
import serial
import math
import os
import time

from tqdm import tqdm

curses_available = False

try:
    import curses
    curses_available = True
except ImportError:
    pass


class KeyboardContext(object):
    def __enter__(self):
        if curses_available:
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            self.stdscr.nodelay(True)
        return self

    def __exit__(self, *args):
        if curses_available:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()

    def getch(self):
        if curses_available:
            return self.stdscr.getch()
        else:
            return curses.ERR


def enumerate_controllers():
    print('Controllers connected to this system:')
    for n in range(sdl2.SDL_NumJoysticks()):
        name = sdl2.SDL_JoystickNameForIndex(n)
        if name is not None:
            name = name.decode('utf8')
        print(n, ':', name)
    print('Note: These are numbered by connection order. Numbers will change if you unplug a controller.')


def get_controller(c):
    try:
        n = int(c, 10)
        return sdl2.SDL_GameControllerOpen(n)
    except ValueError:
        for n in range(sdl2.SDL_NumJoysticks()):
            name = sdl2.SDL_JoystickNameForIndex(n)
            if name is not None:
                name = name.decode('utf8')
                if name == c:
                    return sdl2.SDL_GameControllerOpen(n)
        raise Exception('Controller not found: %s'.format(c))


buttonmapping = [
    sdl2.SDL_CONTROLLER_BUTTON_X, # Y
    sdl2.SDL_CONTROLLER_BUTTON_A, # B
    sdl2.SDL_CONTROLLER_BUTTON_B, # A
    sdl2.SDL_CONTROLLER_BUTTON_Y, # X
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER, # L
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, # R
    sdl2.SDL_CONTROLLER_BUTTON_INVALID, # ZL
    sdl2.SDL_CONTROLLER_BUTTON_INVALID, # ZR
    sdl2.SDL_CONTROLLER_BUTTON_BACK, # SELECT
    sdl2.SDL_CONTROLLER_BUTTON_START, # START
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK, # LCLICK
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK, # RCLICK
    sdl2.SDL_CONTROLLER_BUTTON_GUIDE, # HOME
    sdl2.SDL_CONTROLLER_BUTTON_INVALID, # CAPTURE
]

axismapping = [
    sdl2.SDL_CONTROLLER_AXIS_LEFTX, # LX
    sdl2.SDL_CONTROLLER_AXIS_LEFTY, # LY
    sdl2.SDL_CONTROLLER_AXIS_RIGHTX, # RX
    sdl2.SDL_CONTROLLER_AXIS_RIGHTY, # RY
]

hatmapping = [
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP, # UP
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT, # RIGHT
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN, # DOWN
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT, # LEFT
]

hatcodes = [8, 0, 2, 1, 4, 8, 3, 8, 6, 7, 8, 8, 5, 8, 8]

axis_deadzone = 10000
trigger_deadzone = 0


def controller_states(controller_id):

    sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER)

    controller = get_controller(controller_id)

    try:
        print('Using "{:s}" for input.'.format(
            sdl2.SDL_JoystickName(sdl2.SDL_GameControllerGetJoystick(controller)).decode('utf8')))
    except AttributeError:
        print('Using controller {:s} for input.'.format(controller_id))

    while True:
        for n, b in enumerate(buttonmapping):
            blarg = sdl2.SDL_GameControllerGetButton(controller, b)<<n
            x = 3


        buttons = sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n, b in enumerate(buttonmapping)])
        buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT)) > trigger_deadzone) << 6
        buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT)) > trigger_deadzone) << 7

        hat = hatcodes[sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(hatmapping)])]

        rawaxis = [sdl2.SDL_GameControllerGetAxis(controller, n) for n in axismapping]
        axis = [((0 if abs(x) < axis_deadzone else x) >> 8) + 128 for x in rawaxis]

        rawbytes = struct.pack('>BHBBBB', hat, buttons, *axis)
        yield binascii.hexlify(rawbytes) + b'\n'


ssctf_button_mapping = [
    'KEY_Y', # Y
    'KEY_B', # B
    'KEY_A', # A
    'KEY_X', # X
    '?', # L
    '?', # R
    '?', # ZL
    '?', # ZR
    '?', # SELECT
    '?', # START
    '?', # LCLICK
    '?', # RCLICK
    '?', # HOME
    '?', # CAPTURE
]

ssctf_hatmapping = [
    'KEY_DUP', # UP
    'KEY_DRIGHT', # RIGHT
    'KEY_DDOWN', # DOWN
    'KEY_DLEFT', # LEFT
]

def create_playback_file_from_ssctf(filename):
    x = 3
    try:
        with open(filename, 'r') as ssctf_file:
            # the first line should be a header
            header = ssctf_file.readline()
            if header == 'ssctf 0.0.1\n':
                # if we have this header, we can pretend we're good

                # get the total lines by reading the last line
                # example last line:
                # '6760 KEY_X;KEY_DRIGHT;KEY_B 0;0 0;0'

                # make a dictionary of the ssctf line numbers to their button data
                ssctf_lines = {}

                for ssctf_file_line in ssctf_file:
                    items = ssctf_file_line.split()
                    key, values = int(items[0]), [items[1].split(';'), *items[2:]]
                    ssctf_lines[key] = values
                    total_lines = key

                with open('playbackfile', 'wb') as playbackfile:
                    for line_number in range(total_lines):
                        buttons = 0
                        hat = 8
                        rx = 128
                        ry = 128
                        lx = 128
                        ly = 128

                        if line_number in ssctf_lines:
                            # we have inputs for this line, get them
                            ssctf_line = ssctf_lines[line_number]
                            ssctf_buttons = ssctf_line[0]
                            #
                            # for n, b in enumerate(ssctf_button_mapping):
                            #     if b in ssctf_buttons:
                            #         x = 3
                            #
                            #     blarg = 3
                            # #
                            buttons = sum([(b in ssctf_buttons) << n for n, b in enumerate(ssctf_button_mapping)])
                            hat = hatcodes[sum([(b in ssctf_buttons) << n for n, b in enumerate(ssctf_hatmapping)])]

                        rawbytes = struct.pack('>BHBBBB', hat, buttons, lx, ly, rx, ry)
                        playbackfile.write(binascii.hexlify(rawbytes) + b'\n')

    except FileNotFoundError:
        print("Warning: replay file not found: {:s}".format(filename))

    return "playbackfile"




def replay_states(filename):
    # by default just playback the file we got
    playback_filename = filename

    # but if we have a ssctf file
    replay_extension = os.path.splitext(filename)[-1].lower()
    if replay_extension == ".ssctf":
        playback_filename = create_playback_file_from_ssctf(filename)

    try:
        with open(playback_filename, 'rb') as replay:
            yield from replay.readlines()
    except FileNotFoundError:
        print("Warning: replay file not found: {:s}".format(playback_filename))

def example_macro():
    buttons = 0
    hat = 8
    rx = 128
    ry = 128
    for i in range(240):
        lx = int((1.0 + math.sin(2 * math.pi * i / 240)) * 127)
        ly = int((1.0 + math.cos(2 * math.pi * i / 240)) * 127)
        rawbytes = struct.pack('>BHBBBB', hat, buttons, lx, ly, rx, ry)
        yield binascii.hexlify(rawbytes) + b'\n'


class InputStack(object):
    def __init__(self, recordfilename=None):
        self.l = []
        self.recordfilename = recordfilename
        self.recordfile = None
        self.macrofile = None

    def __enter__(self):
        if self.recordfilename is not None:
            self.recordfile = open(self.recordfilename, 'wb')
        return self

    def __exit__(self, *args):
        if self.recordfile is not None:
            self.recordfile.close()
        self.macro_end()

    def macro_start(self, filename):
        if self.macrofile is None:
            self.macrofile = open(filename, 'wb')
        else:
            print('ERROR: Already recording a macro.')

    def macro_end(self):
        if self.macrofile is not None:
            self.macrofile.close()
            self.macrofile = None

    def push(self, it):
        self.l.append(it)

    def pop(self):
        self.l.pop()

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            try:
                message = next(self.l[-1])
                if self.recordfile is not None:
                    self.recordfile.write(message)
                if self.macrofile is not None:
                    self.macrofile.write(message)
                return message
            except StopIteration:
                self.l.pop()
            except IndexError:
                raise StopIteration


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list-controllers', action='store_true', help='Display a list of controllers attached to the system.')
    parser.add_argument('-c', '--controller', type=str, default='0', help='Controller to use. Default: 0.')
    parser.add_argument('-b', '--baud-rate', type=int, default=115200, help='Baud rate. Default: 115200.')
    parser.add_argument('-p', '--port', type=str, default='/dev/ttyUSB0', help='Serial port. Default: /dev/ttyUSB0.')
    parser.add_argument('-R', '--record', type=str, default=None, help='Record events to file.')
    parser.add_argument('-P', '--playback', type=str, default=None, help='Play back events from file.')
    parser.add_argument('-d', '--dontexit', action='store_true', help='Switch to live input when playback finishes, instead of exiting. Default: False.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Disable speed meter. Default: False.')
    parser.add_argument('-M', '--load-macros', type=str, default=None, help='Load in-line macro definition file. Default: None')

    args = parser.parse_args()

    if args.list_controllers:
        sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER)
        enumerate_controllers()
        exit(0)

    macros = {}

    if args.load_macros is not None:
        with open(args.load_macros) as f:
            for line in f:
                line = line.strip().split(maxsplit=2)
                if len(line) == 2:
                    macros[line[0]] = line[1]

    with KeyboardContext() as kb:

        ser = serial.Serial(args.port, args.baud_rate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None)
        print('Using {:s} at {:d} baud for comms.'.format(args.port, args.baud_rate))

        with InputStack(args.record) as input_stack:

            if args.playback is None or args.dontexit:
                live = controller_states(args.controller)
                next(live)
                input_stack.push(live)
            if args.playback is not None:
                x = 3
                input_stack.push(replay_states(args.playback))

            with tqdm(unit=' updates', disable=args.quiet) as pbar:
                try:
                    # let's see if we can wrap this in some timing
                    startPlay = time.time()
                    frame_count = 0
                    fps = 60

                    while True:

                        # commenting this out so we don't look at the controller during playback
                        # for event in sdl2.ext.get_events():
                        #     # we have to fetch the events from SDL in order for the controller
                        #     # state to be updated.
                        #
                        #     # example of running a macro when a joystick button is pressed:
                        #     #if event.type == sdl2.SDL_JOYBUTTONDOWN:
                        #     #    if event.jbutton.button == 1:
                        #     #        input_stack.push(example_macro())
                        #     # or play from file:
                        #     #        input_stack.push(replay_states(filename))
                        #
                        #     pass

                        # try:
                        #     c = chr(kb.getch())
                        #     if c in macros:
                        #         input_stack.push(replay_states(macros[c]))
                        #     elif c.lower() in macros:
                        #         input_stack.macro_start(macros[c.lower()])
                        #     elif c == ' ':
                        #         input_stack.macro_end()
                        # except ValueError:
                        #     pass

                        nowPlay = time.time()
                        if nowPlay - startPlay > frame_count / fps:
                            try:
                                message = next(input_stack)
                                ser.write(message)
                                frame_count += 1
                            except StopIteration:
                                break

                        # update speed meter on console.
                        pbar.set_description('Sent {:s}'.format(message[:-1].decode('utf8')))
                        pbar.update()

                        while True:
                            # wait for the arduino to request another state.
                            response = ser.read(1)
                            if response == b'U':
                                break
                            elif response == b'X':
                                print('Arduino reported buffer overrun.')

                except KeyboardInterrupt:
                    print('\nExiting due to keyboard interrupt.')
