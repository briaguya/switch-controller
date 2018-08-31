#!/usr/bin/env python3


import argparse

import sdl2
import sdl2.ext
import struct
import binascii
import serial
import time

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
    sdl2.SDL_CONTROLLER_BUTTON_Y, # Y
    sdl2.SDL_CONTROLLER_BUTTON_B, # B
    sdl2.SDL_CONTROLLER_BUTTON_A, # A
    sdl2.SDL_CONTROLLER_BUTTON_X, # X
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER, # L
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, #R
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK, # ZL
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK, # ZR
    sdl2.SDL_CONTROLLER_BUTTON_BACK, # SELECT
    sdl2.SDL_CONTROLLER_BUTTON_START, # START
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK, # LCLICK
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK, # RCLICK
    sdl2.SDL_CONTROLLER_BUTTON_GUIDE, # HOME
    sdl2.SDL_CONTROLLER_BUTTON_GUIDE, # CAPTURE
]



def send_state(ser, controller):
    buttons = sum([sdl2.SDL_GameControllerGetButton(controller, b)<<n for n,b in enumerate(buttonmapping)])
    hat = 0
    lx = (sdl2.SDL_GameControllerGetAxis(controller, 0) >> 8) + 128
    ly = (sdl2.SDL_GameControllerGetAxis(controller, 1) >> 8) + 128
    rx = (sdl2.SDL_GameControllerGetAxis(controller, 2) >> 8) + 128
    ry = (sdl2.SDL_GameControllerGetAxis(controller, 3) >> 8) + 128

    bytes = struct.pack('>BHBBBB', hat, buttons, lx, ly, rx, ry)
    message = binascii.hexlify(bytes)
    ser.write(message + b'\n')


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list-controllers', action='store_true', help='Display a list of controllers attached to the system.')
    parser.add_argument('-c', '--controller', type=str, default='0', help='Controller to use. Default: 0.')
    parser.add_argument('-b', '--baud-rate', type=int, default=115200, help='Baud rate. Default: 57600.')
    parser.add_argument('-p', '--port', type=str, default='/dev/ttyUSB0', help='Serial port. Default: /dev/ttyUSB0.')

    args = parser.parse_args()

    sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER)

    if args.list_controllers:
        enumerate_controllers()
        exit(0)


    controller = get_controller(args.controller)
    try:
        print('Using "{:s}" for input.'.format(sdl2.SDL_JoystickName(sdl2.SDL_GameControllerGetJoystick(controller)).decode('utf8')))
    except AttributeError:
        print('Using controller {:s} for input.'.format(args.controller))

    ser = serial.Serial(args.port, args.baud_rate)
    print('Using {:s} at {:d} baud for comms.'.format(args.port, args.baud_rate))

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
            send_state(ser, controller)

        time.sleep(0.005)
