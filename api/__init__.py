try:
	from .index import app
except ModuleNotFoundError:
	app = None