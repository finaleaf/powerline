# -*- coding: utf-8 -*-

import os

from powerline.lib import memoize

# Weather condition code descriptions available at http://developer.yahoo.com/weather/#codes
weather_conditions_codes = {
	u'〇': [25, 34],
	u'⚑': [24],
	u'☔': [5, 6, 8, 9, 10, 11, 12, 35, 40, 45, 47],
	u'☁': [26, 27, 28, 29, 30, 44],
	u'❅': [7, 13, 14, 15, 16, 17, 18, 41, 42, 43, 46],
	u'☈': [0, 1, 2, 3, 4, 37, 38, 39],
	u'〰': [19, 20, 21, 22, 23],
	u'☼': [32, 36],
	u'☾': [31, 33],
}


def _urllib_read(url):
	try:
		import urllib.error
		import urllib.request
		try:
			return urllib.request.urlopen(url).read().decode('utf-8')
		except urllib.error.HTTPError:
			return
	except ImportError:
		import urllib2
		try:
			return urllib2.urlopen(url).read()
		except urllib2.HTTPError:
			return


def _urllib_urlencode(string):
	try:
		import urllib.parse
		return urllib.parse.urlencode(string)
	except ImportError:
		import urllib
		return urllib.urlencode(string)


def hostname(only_if_ssh=False):
	import socket
	if only_if_ssh and not os.environ.get('SSH_CLIENT'):
		return None
	return socket.gethostname()


def user():
	user = os.environ.get('USER')
	euid = os.geteuid()
	return [{
			'contents': user,
			'highlight_group': 'user' if euid != 0 else ['superuser', 'user'],
		}]


def branch():
	from powerline.lib.vcs import guess
	repo = guess(os.path.abspath(os.getcwd()))
	if repo:
		return repo.branch()
	return None


def cwd(dir_shorten_len=None, dir_limit_depth=None):
	import re
	try:
		cwd = os.getcwdu()
	except AttributeError:
		cwd = os.getcwd()
	home = os.environ.get('HOME')
	if home:
		cwd = re.sub('^' + re.escape(home), '~', cwd, 1)
	cwd_split = cwd.split(os.sep)
	cwd_split_len = len(cwd_split)
	if cwd_split_len > dir_limit_depth + 1:
		del(cwd_split[0:-dir_limit_depth])
		cwd_split.insert(0, u'⋯')
	cwd = [i[0:dir_shorten_len] if dir_shorten_len and i else i for i in cwd_split[:-1]] + [cwd_split[-1]]
	ret = []
	if not cwd[0]:
		cwd[0] = '/'
	for part in cwd:
		if not part:
			continue
		ret.append({
			'contents': part,
			})
	ret[-1]['highlight_group'] = ['cwd:current_folder', 'cwd']
	return ret


def date(format='%Y-%m-%d'):
	from datetime import datetime
	return datetime.now().strftime(format)


@memoize(600, persistent=True)
def external_ip(query_url='http://ipv4.icanhazip.com/'):
	return _urllib_read(query_url).strip()


def uptime(format='{days:02d}d {hours:02d}h {minutes:02d}m'):
	try:
		import psutil
		from datetime import datetime
		seconds = (datetime.now() - datetime.fromtimestamp(psutil.BOOT_TIME)).seconds
	except ImportError:
		try:
			with open('/proc/uptime', 'r') as f:
				seconds = int(float(f.readline().split()[0]))
		except IOError:
			return None
	minutes, seconds = divmod(seconds, 60)
	hours, minutes = divmod(minutes, 60)
	days, hours = divmod(hours, 24)
	return format.format(days=int(days), hours=hours, minutes=minutes)


@memoize(1800, persistent=True)
def weather(unit='c', location_query=None):
	import json

	if not location_query:
		try:
			location = json.loads(_urllib_read('http://freegeoip.net/json/' + external_ip()))
			location_query = ','.join([location['city'], location['region_name'], location['country_name']])
		except ValueError:
			return None
	query_data = {
		'q':
			'use "http://github.com/yql/yql-tables/raw/master/weather/weather.bylocation.xml" as we;'
			'select * from we where location="{0}" and unit="{1}"'.format(location_query, unit),
		'format': 'json'
	}
	url = 'http://query.yahooapis.com/v1/public/yql?' + _urllib_urlencode(query_data)
	response = json.loads(_urllib_read(url))
	condition = response['query']['results']['weather']['rss']['channel']['item']['condition']
	condition_code = int(condition['code'])
	icon = u'〇'
	for icon, codes in weather_conditions_codes.items():
		if condition_code in codes:
			break
	return [
			{
			'contents': icon + ' ',
			'highlight_group': ['weather_condition_' + icon, 'weather_condition', 'weather'],
			},
			{
			'contents': '{0}°{1}'.format(condition['temp'], unit.upper()),
			'highlight_group': ['weather_temp_cold' if int(condition['temp']) < 0 else 'weather_temp_hot', 'weather_temp', 'weather'],
			'draw_divider': False,
			},
		]


def system_load(format='{avg:.1f}', threshold_good=1, threshold_bad=2):
	import multiprocessing
	cpu_count = multiprocessing.cpu_count()
	ret = []
	for avg in os.getloadavg():
		normalized = avg / cpu_count
		if normalized < threshold_good:
			hl = 'system_load_good'
		elif normalized < threshold_bad:
			hl = 'system_load_bad'
		else:
			hl = 'system_load_ugly'
		ret.append({
			'contents': format.format(avg=avg),
			'highlight_group': [hl, 'system_load'],
			'draw_divider': False,
			})
	ret[0]['draw_divider'] = True
	ret[0]['contents'] += ' '
	ret[1]['contents'] += ' '
	return ret


def cpu_load_percent(measure_interval=.5):
	try:
		import psutil
	except ImportError:
		return None
	cpu_percent = int(psutil.cpu_percent(interval=measure_interval))
	return u'{0}%'.format(cpu_percent)


def network_load(interface='eth0', measure_interval=1, suffix='B/s', binary_prefix=False):
	import time
	from powerline.lib import humanize_bytes

	def get_bytes():
		try:
			import psutil
			io_counters = psutil.network_io_counters(pernic=True)
			if_io = io_counters.get(interface)
			if not if_io:
				return None
			return (if_io.bytes_recv, if_io.bytes_sent)
		except ImportError:
			try:
				with open('/sys/class/net/{interface}/statistics/rx_bytes'.format(interface=interface), 'rb') as file_obj:
					rx = int(file_obj.read())
				with open('/sys/class/net/{interface}/statistics/tx_bytes'.format(interface=interface), 'rb') as file_obj:
					tx = int(file_obj.read())
				return (rx, tx)
			except IOError:
				return None

	b1 = get_bytes()
	if b1 is None:
		return None
	time.sleep(measure_interval)
	b2 = get_bytes()
	return u'⬇ {rx_diff} ⬆ {tx_diff}'.format(
		rx_diff=humanize_bytes((b2[0] - b1[0]) / measure_interval, suffix, binary_prefix).rjust(8),
		tx_diff=humanize_bytes((b2[1] - b1[1]) / measure_interval, suffix, binary_prefix).rjust(8),
		)


def virtualenv():
	return os.path.basename(os.environ.get('VIRTUAL_ENV', '')) or None
