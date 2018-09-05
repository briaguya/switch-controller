#!/usr/bin/env python3


import argparse

import sdl2
import sdl2.ext
import struct
import binascii
import serial
import time

from tqdm import tqdm

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

axis_deadzone = 1000
trigger_deadzone = 0

def get_state(ser, controller):
    buttons = sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(buttonmapping)])
    buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT)) > trigger_deadzone) << 6
    buttons |=  (abs(sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT)) > trigger_deadzone) << 7

    hat = hatcodes[sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(hatmapping)])]

    rawaxis = [sdl2.SDL_GameControllerGetAxis(controller, n) for n in axismapping]
    axis = [((0 if abs(x) < axis_deadzone else x) >> 8) + 128 for x in rawaxis]

    rawbytes = struct.pack('>BHBBBB', hat, buttons, *axis)
    return binascii.hexlify(rawbytes)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--controller', type=str, default='0', help='Controller to use. Default: 0.')
    parser.add_argument('-b', '--baud-rate', type=int, default=115200, help='Baud rate. Default: 115200.')
    parser.add_argument('-p', '--port', type=str, default='/dev/ttyUSB0', help='Serial port. Default: /dev/ttyUSB0.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-l', '--list-controllers', action='store_true', help='Display a list of controllers attached to the system.')
    group.add_argument('-R', '--record', type=str, default=None, help='Record events to file. Default: replay.txt.')
    group.add_argument('-P', '--playback', type=str, default=None, help='Play back events from file. Default: replay.txt.')
    

    args = parser.parse_args()

    controller = None
    replay = None

    if args.playback is None:

        sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER)

        if args.list_controllers:
            enumerate_controllers()
            exit(0)

        controller = get_controller(args.controller)
        try:
            print('Using "{:s}" for input.'.format(sdl2.SDL_JoystickName(sdl2.SDL_GameControllerGetJoystick(controller)).decode('utf8')))
        except AttributeError:
            print('Using controller {:s} for input.'.format(args.controller))

        if args.record is not None:
            replay = open(args.record, 'wb')

    else:
        replay = open(args.playback, 'rb')


    ser = serial.Serial(args.port, args.baud_rate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=None)
    print('Using {:s} at {:d} baud for comms.'.format(args.port, args.baud_rate))

    with tqdm(unit=' update') as pbar:

        while True:

            for event in sdl2.ext.get_events():
                # we have to fetch the events from SDL in order for the controller
                # state to be updated.
                pass

            if args.playback is not None:
                message = replay.readline()
            else:
                message = get_state(ser, controller)
                if replay is not None:
                    replay.write(message + b'\n')
            ser.write(message + b'\n')

            while True:
                # wait for the arduino to request another state.
                response = ser.read(1)
                if response == b'U':
                    break
                elif response == b'X':
                    print('Arduino reported buffer overrun.')

            # update speed meter on console.
            pbar.update()
