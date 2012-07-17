# RESTServer imports
from MiniREST.RESTServer import RESTServer, responseCodes, responseTypes
class RESTCommunicator(RESTServer):
	"""RESTCommunicator - creates a new RESTCommunicator instance.
	Extends RESTServer with custom functions.

	"""

	def __init__(self, rcubic, bind='0.0.0.0', port=8002, *args, **kwargs):
		"""Create a RESTCommunicator. Call 'start' to start the server.

		Keyword arguments:
		bind -- the address to which the server binds (default '0.0.0.0')
		port -- the port on which the server listens (default 8002)
		portRange -- choose first available port to listen on

		"""
		super(RESTCommunicator, self).__init__(bind, port, *args, **kwargs)
		self.registerFunction('progress', self._progress, token=True)
		self.registerFunction('reclone', self._reclone, token=True)
		self.registerFunction('reschedule', self._reschedule, token=True)
		self.registerFunction('manualOverride', self._manualOverride, token=True)
		self.registerFunction('supported', self._supported, token=True)
		self.features = ['progress', 'reclone', 'reschedule', 'manualOverride']
		self.rcubic = rcubic

	def _progress(self, env, start_response, post):
		"""Reponds to a 'progress' request and calls rcubic._updateProgress(..)

		Keyword arguments:
		env -- expects a 'data' list TODO: paramaters

		"""
		resp = self.rcubic._updateProgress(post['scriptName'], post['version'], post['kind'], post['message'])
		start_response(responseCodes[200], responseTypes['plaintext'])
		return str(resp)

	def _reclone(self, env, start_response, post):
		"""Responds to a 'reclone' request and calls rcubic._initGit()

		Keyword arguments:
		env -- doesn't expect any paramaters

		"""
		resp = self.rcubic._initGit()
		start_response(responseCodes[200], responseTypes['plaintext'])
		return str(resp)

	def _reschedule(self, env, start_response, post):
		"""Reponds to a 'reschedule' request and calls rcubic.reschedule(scriptName)

		Keyword argument:
		env -- expects a 'scriptName'

		"""
		scriptName = post['scriptName']
		resp = self.rcubic.reschedule(scriptName)
		start_response(responseCodes[200], responseTypes['plaintext'])
		if not resp:
			return str(False)
		return str(True)

	def _manualOverride(self, env, start_response, post):
		"""Responds to a 'manualOverride' request and calls rcubic.manualOverride(scriptName)

		Keyword argument:
		env -- expects a scriptName

		"""
		scriptName = post['scriptName']
		resp = self.rcubic.manualOverride(scriptName)
		start_response(responseCodes[200], responseTypes['plaintext'])
		if not resp:
			return str(False)
		return str(True)

	def _supported(self, env, start_response, post):
		"""Responds to a requested asking if a feature is supported

		Keyword argument:
		env -- expects a 'feature'

		"""
		feature = post['feature']
		start_response(responseCodes[200], responseTypes['plaintext'])
		if feature in self.features:
			return str(True)
		else:
			return str(False)
