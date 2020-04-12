#!/usr/bin/env python3


import argparse
from contextlib import contextmanager

import sdl2
import sdl2.ext
import struct
import binascii
import serial
import math
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
    # sdl2.SDL_CONTROLLER_BUTTON_BACK, # SELECT
    sdl2.SDL_CONTROLLER_BUTTON_INVALID, # SELECT
    sdl2.SDL_CONTROLLER_BUTTON_START, # START
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK, # LCLICK
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK, # RCLICK
    sdl2.SDL_CONTROLLER_BUTTON_GUIDE, # HOME
    # sdl2.SDL_CONTROLLER_BUTTON_INVALID, # CAPTURE
    sdl2.SDL_CONTROLLER_BUTTON_BACK, # CAPTURE
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
        buttons = sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(buttonmapping)])
        buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT)) > trigger_deadzone) << 6
        buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT)) > trigger_deadzone) << 7

        hat = hatcodes[sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(hatmapping)])]

        rawaxis = [sdl2.SDL_GameControllerGetAxis(controller, n) for n in axismapping]
        axis = [((0 if abs(x) < axis_deadzone else x) >> 8) + 128 for x in rawaxis]

        rawbytes = struct.pack('>BHBBBB', hat, buttons, *axis)
        yield binascii.hexlify(rawbytes) + b'\n'


def replay_states(filename):
    try:
        with open(filename, 'rb') as replay:
            yield from replay.readlines()
    except FileNotFoundError:
        print("Warning: replay file not found: {:s}".format(filename))

def example_macro():
    # todo: figure out actual logic here because this is hacky af
    buttons_dict = {
        'not_pressed': 0,
        'zr': 128,
        'capture': 8192,
        'a': 4,
        'x': 8,
        'l': 16
    }

    hats_dict = {
        'dpad_up': 0,
        'dpad_right': 2,
        'not-pressed': 8,
        'dpad_left': 6
    }

    # todo: figure out opening it
    # switch_controller_input_sequence = [
    #     {'buttons': buttons_dict['a']},
    #     {'buttons': buttons_dict['not_pressed'], 'press_duration': 200},
    #     {'buttons': buttons_dict['a']},
    #     {'buttons': buttons_dict['not_pressed'], 'press_duration': 20},
    #     {'hat': hats_dict['dpad_up'], 'press_duration': 20},
    #     {'buttons': buttons_dict['not_pressed'], 'press_duration': 20},
    #     {'buttons': buttons_dict['a']},
    #     {'buttons': buttons_dict['not_pressed'], 'press_duration': 200},
    #     {'buttons': buttons_dict['x']},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'hat': hats_dict['dpad_up'], 'press_duration': 20},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'hat': hats_dict['dpad_right'], 'press_duration': 20},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'buttons': buttons_dict['a']},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'buttons': buttons_dict['l']},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'buttons': buttons_dict['l']},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'buttons': buttons_dict['l']},
    #     {'buttons': buttons_dict['not_pressed']},
    #     {'buttons': buttons_dict['capture'], 'press_duration': 20},
    #     {'buttons': buttons_dict['not_pressed']},
    # ]

    hues = range(30)
    vividities = range(15)
    brightnesses = range(15)

    switch_controller_input_sequence = []
    # assume starting at the bottom left of h/v/b
    for vividness in vividities:


        # since we're starting in the bottom left, loop brightness first
        for brightness in brightnesses:
            switch_controller_input_sequence.extend([
                {'buttons': buttons_dict['not_pressed'], 'press_duration': 10},
                {'buttons': buttons_dict['capture'], 'press_duration': 20},
                {'buttons': buttons_dict['not_pressed'], 'press_duration': 10},
                {'hat': hats_dict['dpad_right'], 'press_duration': 10},
                {'hat': hats_dict['not-pressed'], 'press_duration': 10},
            ])

        # after looping through all brightnesses, bring the brightness cursor back to zero
        for brightness in brightnesses:
            switch_controller_input_sequence.extend([
                {'hat': hats_dict['dpad_left'], 'press_duration': 10},
                {'hat': hats_dict['not-pressed'], 'press_duration': 10},
            ])

        # hop up to vividness
        switch_controller_input_sequence.extend([
            {'hat': hats_dict['dpad_up'], 'press_duration': 10},
            {'hat': hats_dict['not-pressed'], 'press_duration': 10},
            {'hat': hats_dict['dpad_right'], 'press_duration': 10},
            {'hat': hats_dict['not-pressed'], 'press_duration': 10},
            {'hat': hats_dict['dpad_down'], 'press_duration': 10},
            {'hat': hats_dict['not-pressed'], 'press_duration': 10},
        ])


    lx = 128
    ly = 128
    rx = 128
    ry = 128
    hat = hats_dict['not-pressed']
    buttons = buttons_dict['not_pressed']
    press_duration = 50
    for switch_controller_input in switch_controller_input_sequence:
        if 'buttons' in switch_controller_input:
            buttons = switch_controller_input['buttons']

        if 'press_duration' in switch_controller_input:
            press_duration = switch_controller_input['press_duration']

        if 'hat' in switch_controller_input:
            hat = switch_controller_input['hat']

        rawbytes = struct.pack('>BHBBBB', hat, buttons, lx, ly, rx, ry)
        for blarg in range(press_duration):
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

    macros = {
        'c': example_macro()
    }
    # if args.load_macros is not None:
    #     with open(args.load_macros) as f:
    #         for line in f:
    #             line = line.strip().split(maxsplit=2)
    #             if len(line) == 2:
    #                 macros[line[0]] = line[1]

    with KeyboardContext() as kb:

        ser = serial.Serial(args.port, args.baud_rate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None)
        print('Using {:s} at {:d} baud for comms.'.format(args.port, args.baud_rate))

        with InputStack(args.record) as input_stack:

            if args.playback is None or args.dontexit:
                live = controller_states(args.controller)
                next(live)
                input_stack.push(live)
            if args.playback is not None:
                input_stack.push(replay_states(args.playback))

            with tqdm(unit=' updates', disable=args.quiet) as pbar:
                try:

                    while True:

                        for event in sdl2.ext.get_events():
                            # we have to fetch the events from SDL in order for the controller
                            # state to be updated.

                            # example of running a macro when a joystick button is pressed:
                            if event.type == sdl2.SDL_JOYBUTTONDOWN:
                               # if we click in the left stick
                               if event.jbutton.button == 11:
                                   input_stack.push(example_macro())
                            # or play from file:
                            #        input_stack.push(replay_states(filename))

                            pass

                        try:
                            c = chr(kb.getch())

                            # if c in macros:
                            #     input_stack.push(macros[c])
                                # input_stack.push(replay_states(macros[c]))
                            # elif c.lower() in macros:
                            #     input_stack.macro_start(macros[c.lower()])
                            # elif c == ' ':
                            #     input_stack.macro_end()
                        except ValueError:
                            pass

                        try:
                            message = next(input_stack)
                            ser.write(message)
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
