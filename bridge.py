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
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, #R
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
    sdl2.SDL_CONTROLLER_AXIS_LEFTX,
    sdl2.SDL_CONTROLLER_AXIS_LEFTY,
    sdl2.SDL_CONTROLLER_AXIS_RIGHTX,
    sdl2.SDL_CONTROLLER_AXIS_RIGHTY,
]


def get_state(ser, controller):
    buttons = sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(buttonmapping)])
    buttons |=  (0x01<<6) if sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT) else 0
    buttons |=  (0x01<<7) if sdl2.SDL_GameControllerGetAxis(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT) else 0
    dpad = [0]*4
    dpad[0] = sdl2.SDL_GameControllerGetButton(controller, sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP)
    dpad[1] = sdl2.SDL_GameControllerGetButton(controller, sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT)
    dpad[2] = sdl2.SDL_GameControllerGetButton(controller, sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN)
    dpad[3] = sdl2.SDL_GameControllerGetButton(controller, sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT)
    if (dpad == [1,0,0,0]):
        hat = 0
    elif (dpad == [1,1,0,0]):
        hat = 1
    elif (dpad == [0,1,0,0]):
        hat = 2
    elif (dpad == [0,1,1,0]):
        hat = 3
    elif (dpad == [0,0,1,0]):
        hat = 4
    elif (dpad == [0,0,1,1]):
        hat = 5
    elif (dpad == [0,0,0,1]):
        hat = 6
    elif (dpad == [1,0,0,1]):
        hat = 7
    elif (dpad == [0,0,0,0]):
        hat = 8
    rawaxis = [sdl2.SDL_GameControllerGetAxis(controller, n) for n in axismapping]
    axis = [((0 if abs(x) < 1000 else x) >> 8) + 128 for x in rawaxis]

    bytes = struct.pack('>BHBBBB', hat, buttons, *axis)
    return binascii.hexlify(bytes)


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
            sent = False
            for event in sdl2.ext.get_events():
                # we have to fetch the events from SDL in order for the controller
                # state to be updated. we may also want to conditionally run an
                # immediate update on certain events, so as to avoid dropping
                # very fast button presses. this is why the "sent" variable exists.
                # for now though, just pass.
                pass

            if not sent:
                if args.playback is not None:
                    message = replay.readline()
                else:
                    message = get_state(ser, controller)
                    if replay is not None:
                        replay.write(message + b'\n')
                ser.write(message + b'\n')

            while True:
                response = ser.read(1)
                if response == b'U':
                    break
                elif response == b'X':
                    print('Arduino reported buffer overrun.')

            pbar.update()
