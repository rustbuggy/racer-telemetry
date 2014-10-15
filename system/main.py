import logging
#logg = logging.getLogger(__name__)
logg = logging.getLogger("main")
if __name__=="__main__":
	logging.basicConfig(level=logging.NOTSET, format="%(asctime)s %(name)s %(levelname)-5s: %(message)s")


import sys
import time
import math
import datetime
import argparse
import struct
import serial
import ctypes

from sdl2 import *
from OpenGL.GL import *

sys.path.append('extlib/common/python/lib')

import hdlc


parser = argparse.ArgumentParser(description="RustTelemetry", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", type=str, default="/dev/tty.usbserial-A8008iwL", help="usb serial port device eg. /dev/ttyUSB0")
args = parser.parse_args()



try:
	s = serial.Serial(args.port, 57600, timeout=0);
	s.flushInput()
	s.flushOutput()
except:
	logg.exception("using fake serial")
	class DummySerial:
		def read(self, n): return ""
		def write(self, data): pass
	s = DummySerial()


# header bytes
BC_TELEMETRY = 0x00
CB_MOTOR_COMMAND = 0x01


def send_packet(data):
	data = hdlc.add_checksum(data)
	data = hdlc.escape_delimit(data)
	s.write(data)


class Telemetry:
	""" Read telemetry from the given serial port. """
	def __init__(self, serial):
		self.serial = serial # opened serial port. here used for reading ONLY.
		self.parser = hdlc.HdlcChecksummed()

	def tick(self, dt):
		# read serial
		data = self.serial.read(200)
		self.parser.put(data)

		for packet in self.parser:
			header, = struct.unpack("<B", packet[:1])
			if header == BC_TELEMETRY:
				left, right, front_left, front_right = struct.unpack("<BBBB", packet[1:])
				#llog.info("l %u r %u fl %u fr %u", left, right, front_left, front_right)
				# TODO: create channels. append every sample.


class BuggyDrive:
	def __init__(self, serial):
		self.serial = serial # opened serial port. here used for sending ONLY.
		self.thrust_max = 10.
		self.thrust_min = -10.
		self.steering_max = 45. # degrees
		self.steering_min = -self.steering_max

		self.steering_max_pwm = 140.
		self.steering_min_pwm = 40.
		self.thrust_max_pwm = 135.
		self.thrust_min_pwm = 255.

		self.steering_cur = 0. # current front wheel steering pos degrees
		self.thrust_cur = 0.

	def tick(self, dt):
		# send motor commands
		steering_pwm = self._steering_to_servopwm(self.steering_cur)
		drive_pwm = self._thrust_to_motorpwm(self.thrust_cur)
		motor_command = struct.pack("<BBB", CB_MOTOR_COMMAND, steering_pwm, drive_pwm)
		self._send_packet(motor_command)

	def handle_controls(self, dt, keys):
		acceleration = 5.
		friction_deceleration = .5 # deceleration when no accelerate button is pressed
		steering_speed = 20. # degrees per second
		steering_back_speed = 20. # how fast to restore the zero-steer if no left/right button is pressed

		if keys[SDL_SCANCODE_LEFT] or keys[SDL_SCANCODE_RIGHT]:
			if keys[SDL_SCANCODE_LEFT]:
				self.steering_cur -= steering_speed * dt
			if keys[SDL_SCANCODE_RIGHT]:
				self.steering_cur += steering_speed * dt
		else:
			self.steering_cur = self._ease_linear_to(0, self.steering_cur, dt * steering_back_speed)

		if keys[SDL_SCANCODE_UP] or keys[SDL_SCANCODE_DOWN]:
			if keys[SDL_SCANCODE_UP]:
				self.thrust_cur += acceleration * dt
			if keys[SDL_SCANCODE_DOWN]:
				self.thrust_cur -= acceleration * dt
		else:
			self.thrust_cur = self._ease_linear_to(0, self.thrust_cur, dt * friction_deceleration)

		# limits

		self.steering_cur = min(self.steering_cur, self.steering_max)
		self.steering_cur = max(self.steering_cur, self.steering_min)

		self.thrust_cur = min(self.thrust_cur, self.thrust_max)
		self.thrust_cur = max(self.thrust_cur, self.thrust_min)

	def _send_packet(self, data):
		data = hdlc.add_checksum(data)
		data = hdlc.escape_delimit(data)
		logg.info("snd %02i: %s", len(data), data.encode("hex").upper())
		self.serial.write(data)

	def _ease_linear_to(self, dest, src, amount):
		if dest >= src:
			return src + amount if src + amount < dest else dest
		else:
			return src - amount if src - amount > dest else dest

	def _thrust_to_motorpwm(self, speed):
		motorpwm = self.thrust_min_pwm + (self.thrust_cur - self.thrust_min) / (self.thrust_max - self.thrust_min) * (self.thrust_max_pwm - self.thrust_min_pwm)
		assert motorpwm < 256.
		assert motorpwm > 134.
		return motorpwm

	def _steering_to_servopwm(self, angle):
		servopwm = self.steering_min_pwm + (self.steering_cur - self.steering_min) / (self.steering_max - self.steering_min) * (self.steering_max_pwm - self.steering_min_pwm)
		assert servopwm < 141.
		assert servopwm > 39.
		return servopwm


class Main:
	def __init__(self, serial):
		self.serial = serial
		self.w = 800
		self.h = 600
		self.keys = None

		self.buggy_drive = BuggyDrive(self.serial)
		self.telemetry = Telemetry(self.serial)

	def _init(self):
		pass

	def run(self):
		""" this is the entry-point """

		logg.info("initializing sdl")
		if SDL_Init(SDL_INIT_VIDEO) != 0:
			logg.error(SDL_GetError())
			return -1

		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4);

		logg.info("creating window")
		window = SDL_CreateWindow(b"telemetry/drive", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, self.w, self.h, SDL_WINDOW_OPENGL)
		if not window:
			logg.error(SDL_GetError())
			return -1

		logg.info("creating context for the window")
		context = SDL_GL_CreateContext(window)

		glClearColor(0., 0., 0., 1.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

		if SDL_GL_SetSwapInterval(-1):
			logg.error(SDL_GetError())
			if SDL_GL_SetSwapInterval(1):
				logg.error("SDL_GL_SetSwapInterval: %s", SDL_GetError())
				logg.error("vsync failed completely. will munch cpu for lunch.")

		self.keys = SDL_GetKeyboardState(None)
		self._init()

		#
		# init done. start the mainloop!
		#

		logg.info("starting mainloop")
		last_t = time.time()

		event = SDL_Event()
		running = True
		while running:
			while SDL_PollEvent(ctypes.byref(event)) != 0:
				if event.type == SDL_QUIT:
					running = False

				if event.type == SDL_KEYDOWN:
					if event.key.keysym.scancode == SDL_SCANCODE_ESCAPE:
						running = False

				if event.type == SDL_WINDOWEVENT:
					if event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED:
						self.w, self.h = event.window.data1, event.window.data2

			t = time.time()
			self._tick(t - last_t)
			last_t = t

			#glFinish()
			SDL_GL_SwapWindow(window)
			#SDL_Delay(10)

		SDL_GL_DeleteContext(context)
		SDL_DestroyWindow(window)
		SDL_Quit()
		logg.info("quit ok")

	def _tick(self, dt):
		self.telemetry.tick(dt)
		self.buggy_drive.handle_controls(dt, self.keys)
		self.buggy_drive.tick(dt)


# example on how to show a message box. of course we'll need it someday!
#SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR,
#                     "Missing file",
#                     "File is missing. Please reinstall the program.",
#                     None);

def main(py_path):
	w = Main(s)
	w.run()


if __name__=="__main__":
	main()
	sys.exit(w.run())
