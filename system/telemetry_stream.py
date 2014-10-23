"""
Read telemetry data from the given serial port and save it in internal graph_channel objects.
"""

import logging
log = logging.getLogger(__name__)

import struct

import hdlc
from aniplot import graph_channel
from buggy_packets import *


class TelemetryStream:
	""" Read telemetry from the given serial port. """
	def __init__(self, serial):
		self.serial = serial # opened serial port. here used for reading ONLY.
		self.parser = hdlc.HdlcChecksummed()
		self.graph_channels = []
		self.all_channels = []

		maxvals = 1.
		maxvals_raw = 1.

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="left", color=(1., 0.8, 0.8, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="right", color=(0.8, 1., 0.8, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="front_left", color=(0.8, 0.8, 1.0, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="front_right", color=(1., 0.8, 0.2, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="front", color=(.2, 0.2, 1.0, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="speed_pwm", color=(1.0, 1.0, 1.0, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=maxvals, value_max_raw=maxvals_raw, legend="steer_pwm", color=(0., 1.0, 0.3, 1.0))
		self.graph_channels.append(ch)
		self.all_channels.append(ch)

		ch = self._create_channel(frequency=60, value_min=-180., value_min_raw=-180., value_max=180., value_max_raw=180., legend="mc_angle", color=(.2, 0.2, 1.0, 1.0))
		self.all_channels.append(ch)
		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=10., value_max_raw=10., legend="mc_dist", color=(.2, 0.2, 1.0, 1.0))
		self.all_channels.append(ch)
		ch = self._create_channel(frequency=60, value_min=0., value_min_raw=0., value_max=10., value_max_raw=10., legend="steer_pwm", color=(1.0, 1.0, 1.0, 1.0))
		self.all_channels.append(ch)

		#self.ch2 = self.aniplot.create_channel(frequency=5, value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=255., legend="slow data", color=QtGui.QColor(0, 238, 0))

	def get_telemetry_channels(self):
		return self.all_channels

	def get_graphing_telemetry_channels(self):
		return self.graph_channels

	def tick(self, dt):

		#t = time.time()
		#self.graph_channels[0].append( math.sin(t / 0.1) )
		#self.graph_channels[1].append( math.sin(t / 0.1324) )


		# read serial
		data = self.serial.read(200)
		self.parser.put(data)

		for packet in self.parser:
			header, = struct.unpack("<B", packet[:1])
			if header == BC_TELEMETRY:
				time, left, right, front_left, front_right, front, mc_x, mc_y, mc_dist, mc_angle, steer_pwm, speed_pwm = struct.unpack("<Iiiiiiiiiiii", packet[1:])

				d = 1. / 65535 / 100.
				self.all_channels[0].append(left * d)
				self.all_channels[1].append(right * d)
				self.all_channels[2].append(front_left * d)
				self.all_channels[3].append(front_right * d)
				self.all_channels[4].append(front * d)
				self.all_channels[5].append(speed_pwm * d)
				self.all_channels[6].append(steer_pwm * d)

				self.all_channels[7].append(-mc_angle / 65535. + 90.)
				self.all_channels[8].append(mc_dist * d)

				#print("l %3.2f r %3.2f fl %3.2f fr %3.2f f %3.2f" % (left / FIX_DIV, right / FIX_DIV, front_left / FIX_DIV, front_right / FIX_DIV, front / FIX_DIV))
				#logg.info("mc(%.2f, %.2f; %.2f, %.2f)\tsteer: %3u drive: %3u\n" % (mc_x / FIX_DIV, mc_y / FIX_DIV, mc_dist / FIX_DIV, mc_angle / FIX_DIV, steerPwm, speedPwm))

	def _create_channel(self, frequency=1000, value_min=0., value_min_raw=0., value_max=5., value_max_raw=255., legend="graph", unit="V", color=(0.5, 1., 0.5, 1.)):
		''' Returns GraphChannel object.

			"frequency"     : sampling frequency
			"value_min"     : is minimum real value, for example it can be in V
			"value_min_raw" : is minimum raw value from ADC that corresponds to real "value_min"
			"value_max"     : is maximum real value, for example it can be in V
			"value_max_raw" : is maximum raw value from ADC that corresponds to real "value_max"

			For example with 10 bit ADC with AREF of 3.3 V these values are: value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=1023.

			Use case:
				plotter = AniplotWidget()
				ch1 = plotter.create_channel(frequency=1000, value_min=0., value_min_raw=0., value_max=5., value_max_raw=255.)
				ch2 = plotter.create_channel(frequency=500, value_min=0., value_min_raw=0., value_max=3.3, value_max_raw=1023.)
				plotter.start()

				while 1:
					sample1 = some_source1.get()
					sample2 = some_source2.get()
					if sample1:
						ch1.append(sample1)
					if sample2:
						ch2.append(sample2)

			Data can be appended also with custom timestamp: ch1.append(sample1, time.time())
		'''
		channel = graph_channel.GraphChannel(frequency=frequency, legend=legend, unit=unit, color=color)
		channel.set_mapping(value_min=value_min, value_min_raw=value_min_raw, value_max=value_max, value_max_raw=value_max_raw)
		return channel
