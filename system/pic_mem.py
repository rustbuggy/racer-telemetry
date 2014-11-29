import logging
log = logging.getLogger(__name__)

#import time
#from PIL import Image


class PicEntry:
	def __init__(self, pic, readytime, metadata):
		self.pic = pic
		self.readytime = readytime
		self.metadata = metadata



class PicMem:
	def __init__(self):
		#self.indexvals = [] # indexval fields from appended PicEntry objects?
		#self.indexvals_level2 = [] # after every 100 entries in self.indexvals, the next indexval is also appended to this list.
		#self.indexval_count_per_level = 100
		#self.pics = [] # PicEntry objects

		self.start_time = None
		self.end_time = None

		self.pic_index = [] # PicEntry objects

		self.used_memory = 0

	def append_pic(self, readytime, binarypic, metadata):
		""" indexval can be a float. every next indexval HAS to be larger than the last."""
		if not self.start_time:
			self.start_time = readytime

		if self.pic_index and self.pic_index[-1].readytime == readytime:
			log.info("pic with index %i already in pic_mem. dropping the new pic.", readytime)
		else:
			self.end_time = readytime
			pic = PicEntry(binarypic, readytime, metadata)
			self.pic_index.append(pic)
			self.used_memory += len(binarypic)

		#if len(self.indexvals) % self.indexval_count_per_level == 0:
		#	self.indexvals_level2.append()
		#self.indexvals.append(indexval)

	def get_by_timestamp(self, timestamp):
		i = self._get_nearest_index(timestamp)
		if i:
			pic_entry = self.pic_index[i]
			return pic_entry.pic
		else:
			return None

	def _get_nearest_index(self, timestamp):
		""" return index of the nearest pic, None if no pics in index """
		# scan self.pic_index list
		if not self.pic_index:
			return None

		if len(self.pic_index) < 2:
			return 0

		# try to guess a good starting-point for our picture search
		start_index = int(float(len(self.pic_index)) / (self.end_time - self.start_time) * \
				(timestamp - self.start_time))

		#print "start_index", start_index

		if start_index < 0:
			return 0
			pic = self.pic_index[0]
		elif start_index >= len(self.pic_index):
			return len(self.pic_index) - 1
		else:
			pic = self.pic_index[start_index]
			i = start_index
			if pic.readytime > timestamp:
				# pic is right of the timestamp. search left.
				while 1:
					i -= 1
					if i < 0:
						# no pic left of the timestamp exists
						return 0
					prev = pic
					pic = self.pic_index[i]
					if pic.readytime <= timestamp:
						# find which is closer to timestamp
						if prev.readytime - timestamp < timestamp - pic.readytime:
							return i + 1
						else:
							return i
			else:
				# pic is left of the timestamp. search right.
				while 1:
					i += 1
					if i >= len(self.pic_index):
						# no pic right of the timestamp exists
						return len(self.pic_index) - 1
					prev = pic
					pic = self.pic_index[i]
					if pic.readytime >= timestamp:
						# find which is closer to timestamp
						if pic.readytime - timestamp > timestamp - prev.readytime:
							return i - 1
						else:
							return i
