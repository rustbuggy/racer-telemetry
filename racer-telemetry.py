import logging
log = logging.getLogger("racer-telemetry")
logging.basicConfig(level=logging.NOTSET, format="%(asctime)s %(name)s %(levelname)-5s: %(message)s")

import os
import sys
import time

__version__ = "0.1.0"

if sys.hexversion < 0x2070000:
	print "python version >=2.7 required. you have", sys.version
	sys.exit(1)


# if under py2exe, sys.path[0] is sometimes really wrong. here's a foolproof way to get the exe dir.
# http://www.py2exe.org/index.cgi/WhereAmI
if hasattr(sys, "frozen"):
	# this only works with pyinstaller.
	g_py_path = sys._MEIPASS
	#g_py_path = os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))
	# if frozen, enable source/hybrid distribution.. (meaning we can use python source files with the
	# standalone exe without having to have python installed)
	#sys.path.insert(0, os.path.normpath(g_py_path))
else:
	g_py_path = sys.path[0] # can't use os.path.dirname. last dir is without the slash :S


# TODO: need this?
#os.environ["PYSDL2_DLL_PATH"] = g_py_path


#import system.logging_setup as logging_setup

log_folder = os.path.join(g_py_path, "./log")
t = time.time()

#logging_setup.start_logging_system(t, log_folder, "log-racer-telemetry.txt")

# print introductory lines
log.info("")
log.info("racer-telemetry start. version %s", __version__)
#log.info("git hash %s", GITREV)

log.info("log file: %s", os.path.normpath(os.path.join(log_folder, "log-racer-telemetry.txt")))

utc = time.gmtime(t)
log.info("utc        : " + time.asctime( utc               ))
log.info("local time : " + time.asctime( time.localtime(t) ))
log.info("------------------------------------------------------------------------------")
log.info("")

# ---------------------------------------------------------------------------

# run the program

try:
	import system.main
	system.main.main(g_py_path)
except:
	logging.exception("")


# print some closing lines

ts  = t
t   = time.time()
utc = time.gmtime(t)
total_time = t - ts

log.info("")
log.info("------------------------------------------------------------------------------")
log.info("utc        : " + time.asctime( utc                ))
log.info("local time : " + time.asctime( time.localtime(t)  ))
log.info("total time : %i days %i hours %i minutes %i seconds",
		total_time // (60*60*24), total_time // (60*60) % 24,
		total_time // 60 % 60, total_time % 60)

# try to make a faster exit
sys.exit()
