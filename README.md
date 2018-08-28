# switch-controller

Lets you control a switch from your Linux Box

## Hardware
* Board with either a ATmega16u2 or ATmega32u4
	* E.g. A blank [Arduino Uno Rev3](https://store.arduino.cc/usa/arduino-uno-rev3) or an [Adafruit ItsyBitsy 32u4](https://www.adafruit.com/product/3677)
* USB to Serial Converter
	* E.g. Another blank [Arduino Uno Rev3](https://store.arduino.cc/usa/arduino-uno-rev3) or an [Adafruit CP2104 Friend](https://www.adafruit.com/product/3309)

## To build and flash firmware onto an Arduino Uno Rev3:
* You will need packages `dfu-programmer` and `avr-gcc`.
	* To install these on a Mac with [homebrew](https://brew.sh):
		```
		brew install dfu-programmer
		brew tap osx-cross/avr
		brew install avr-gcc
		```

* Update `MCU` in the makefile to match your chip, either `MCU = atmega16u2` or `MCU = atmega32u4`.
* `make`
* Follow the [DFU mode directions](https://www.arduino.cc/en/Hacking/DFUProgramming8U2) to flash `Joystick.hex` onto the 16u2 of your Arduino UNO R3.  Abridged instructions:
	* Jumper RESET and GND of the 16u2
	<img src="https://www.arduino.cc/en/uploads/Hacking/Uno-front-DFU-reset.png" width="300">

	```
	sudo dfu-programmer atmega16u2 erase
	sudo dfu-programmer atmega16u2 flash Joystick.hex
	sudo dfu-programmer atmega16u2 reset
	```
* Install python libraries `pyserial` and `evdev`
	```
	pip install pyserial
	pip install evdev
	```
* Edit `controller/gamepad-control-relay.py` to match your input and serial devices, as well as to match the bindings of your controller.  Included bindings are for a wired PS3 Dualshock 3.
* Run `python controller/gamepad-control-relay.py`
	* If using a PS3 controller you may need to press the PS button before the controller sends any inputs.


<img src="https://i.imgur.com/tpXzxPR.jpg" width="400">

## Credit and Thanks
* Thanks to @wchill for his work
* Thanks to https://github.com/ebith/Switch-Fightstick and https://github.com/mfosse/switch-controller