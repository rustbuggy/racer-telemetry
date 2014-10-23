"""
Handle controls (joystick, keyboard) and send drive commands to the given serial port.
"""

import logging
logg = logging.getLogger(__name__)

import struct
from sdl2 import *
import hdlc

from buggy_packets import *


class CruiseControl:
	""" Buggy cruise control """
	def __init__(self):
		self.automatic = AUTOMATIC_DEFAULT
		self.steering = STEERING_PWM_DEFAULT
		self.drive = DRIVING_PWM_DEFAULT

	def motorcommand(self):
		return struct.pack("<BBBB", CB_MOTOR_COMMAND, self.automatic, self.steering, self.drive)


class BuggyDrive:
	def __init__(self, conf, serial):
		""" serial - opened serial port object """
		self.conf = conf
		self.serial = serial
		self.cruise_control = CruiseControl()

	def _send_packet(self, data):
		data = hdlc.add_checksum(data)
		data = hdlc.escape_delimit(data)
		self.serial.write(data)

	def tick(self, dt):
		pass

	def handle_controls(self, dt, keys):
		pass

	def event_sdl(self, event):
		if event.type == SDL_KEYDOWN:
			keypressed = False
			if event.key.keysym.scancode == SDL_SCANCODE_SPACE:
				self.cruise_control.automatic = 1
				self.cruise_control.steering = STEERING_PWM_DEFAULT # center
				self.cruise_control.drive = 113
				keypressed = True
			elif event.key.keysym.scancode == SDL_SCANCODE_A:
				self.cruise_control.automatic = 1
				self.cruise_control.steering = STEERING_PWM_DEFAULT # center
				self.cruise_control.drive = self.cruise_control.drive + 1
				keypressed = True
				logg.info("speed %u", self.cruise_control.drive)
			elif event.key.keysym.scancode == SDL_SCANCODE_Z:
				self.cruise_control.automatic = 1
				self.cruise_control.steering = STEERING_PWM_DEFAULT # center
				self.cruise_control.drive = self.cruise_control.drive - 1
				keypressed = True
				logg.info("speed %u", self.cruise_control.drive)
			else:
				# full stop
				self.cruise_control.automatic = 0
				self.cruise_control.steering = STEERING_PWM_DEFAULT
				self.cruise_control.drive = DRIVING_PWM_DEFAULT
				keypressed = True

			if keypressed:
				self._send_packet(self.cruise_control.motorcommand())


# unused at the moment

class BuggyDriveX:
	def __init__(self, conf, serial):
		self.conf = conf
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

		self.log_raw_data = False

	def tick(self, dt):
		# send motor commands
		automatic = 0
		steering_pwm = self._steering_to_servopwm(self.steering_cur)
		drive_pwm = self._thrust_to_motorpwm(self.thrust_cur)
		motor_command = struct.pack("<BBBB", CB_MOTOR_COMMAND, automatic, steering_pwm, drive_pwm)
		#self._send_packet(motor_command)

	def event_sdl(self, event):
		joy_axis_changed = False
		if event.type == SDL_JOYAXISMOTION:
			if event.jaxis.axis == self.conf.joystick_roll_axis:
				joy_axis_changed = True
				roll_axis = int16_to_float(event.jaxis.value)
			elif event.jaxis.axis == self.conf.joystick_pitch_axis:
				joy_axis_changed = True
				pitch_axis = int16_to_float(event.jaxis.value)
			logg.info("axis %i val %5.2f" % (event.jaxis.axis, int16_to_float(event.jaxis.value)))

		if event.type == SDL_JOYBUTTONDOWN:
			logg.info("joy button %i pressed", event.jbutton.button)

		#if joy_axis_changed:
		#	logg.info("pitch %5.2f roll %5.2f" % (pitch_axis, roll_axis))

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
		if self.log_raw_data:
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
