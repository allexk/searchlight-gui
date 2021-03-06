__author__ = 'akalinin'

import json
import os
import sys
import tempfile
from scidb.scidb_http import SciDBConnection
from ConfigParser import SafeConfigParser, NoOptionError
import shutil
import threading

# Flask application
import flask
app = flask.Flask("searchlight")
app.config.from_pyfile("flask.cfg")

# create a logger
import logging
logger = logging.getLogger('searchlight')
logger_stream_handler = logging.StreamHandler()
logger_stream_handler.setFormatter(
    logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(logger_stream_handler)
logger.setLevel(logging.INFO)
# logging.getLogger().addHandler(logger_stream_handler)
# logging.getLogger().setLevel(logging.DEBUG)
del logger_stream_handler

# to debug requests/responses
# try:
#     import http.client as http_client
# except ImportError:
#     # Python 2
#     import httplib as http_client
# http_client.HTTPConnection.debuglevel = 1

# Some default params (TODO: put them as params)
SYNOPSIS_RESOLUTIONS = ['1x1000', '1x100']
TASK_ARRAY = "mimic"
TASK_LIB = 'searchlight_mimic'
TASK_FUN = 'MimicAvg'


class SearchlightError(RuntimeError):
    """Searchlight exception."""
    pass


class SciDBConnectionConfig(object):
    def __init__(self, config_path):
        self._read_config(config_path)
        self.scidb = SciDBConnection(self.host, self.http_port, self.user,
                                     self.password)
        super(SciDBConnectionConfig, self).__init__()

    def _read_config(self, config_path):
        config = SafeConfigParser()
        config.read(config_path)

        # standard params
        self.host = config.get('scidb', 'host')
        self.user = config.get('scidb', 'user')
        self.http_port = int(config.get('scidb', 'http_port'))
        self.scidb_port = int(config.get('scidb', 'scidb_port'))
        try:
            self.shared_dir = config.get('scidb', 'shared_dir')
        except NoOptionError:
            self.shared_dir = None

        # password we get from the specified file
        password_path = config.get('scidb', 'passwd_file')
        try:
            with open(password_path, 'rb') as password_file:
                self.password = password_file.read().strip()
        except IOError:
            logger.error('SciDB password file not found: ' + password_path)


class SciDBQueryOnline(SciDBConnectionConfig):
    def __init__(self, config_path):
        super(SciDBQueryOnline, self).__init__(config_path)
        self.logger = logging.getLogger('searchlight.scidb_query')
        self.scidb_query_params = None
        self.query_array = None
        self.cancelled = False
        self.error = None
        self.results = []

    def prepare_query(self, array, sample_arrays, task_name, task_fun,
                      task_params_file):
        self.scidb_query_params = {'array': array,
                                   'sample_arrays': sample_arrays,
                                   'task_name': task_name,
                                   'task_fun': task_fun,
                                   'task_params_file': task_params_file
                                   }

    def start_query(self):
        if not self.scidb_query_params:
            self.logger.error('run_query() is called before prepare_query()')
            self.error = RuntimeError("query not inited")
            return
        try:
            # connect
            self.logger.info('connecting to %s:%d' %
                             (self.host, self.http_port))
            self.scidb.connect()
            # upload the query file
            task_params_file = self.scidb_query_params['task_params_file']
            self.logger.info('uploading task file ' + task_params_file)
            if self.shared_dir:
                # copy locally
                shutil.copy(task_params_file, self.shared_dir)
                scidb_task_file = os.path.join(self.shared_dir,
                                               os.path.basename(
                                                   task_params_file))
            else:
                # remote copy (curl via scidb shim)
                scidb_task_file = self.scidb.upload(task_params_file)
            self.logger.info('upload finished: ' + scidb_task_file)
            # create the query
            sample_arrays_str = ', '.join(
                ['depart(%s)' % x
                 for x in self.scidb_query_params['sample_arrays']])
            query_str = "searchlight(depart(%s), %s, '%s:%s:%s')" %\
                        (self.scidb_query_params['array'],
                         sample_arrays_str,
                         self.scidb_query_params['task_name'],
                         self.scidb_query_params['task_fun'],
                         scidb_task_file)
            # query (via scidb4py)
            self.logger.info('querying with: ' + query_str)
            self.query_array = iter(self.scidb.query_interactive(query_str))
        except:
            self.logger.error('could not start query: ' + str(sys.exc_info()))
            self.error = sys.exc_info()

    def next_result(self):
        if not self.query_array:
            self.logger.info('no current array, possible run_query() error...')
            self._finish_query()
            self.error = RuntimeError("query not started")
            return None
        try:
            if self.cancelled:
                self.logger.info('query cancelled by user')
                try:
                    self.scidb.cancel_query()
                except:
                    pass
                self._finish_query()
            else:
                (pos, val) = self.query_array.next()
                # assume the only attribute -- the result string
                res = self._parse_str_result(str(val[0]))
                self.results.append(res)
                return res
        except StopIteration:
            # close the connection
            self.logger.info('no more results: query finished')
            self._finish_query()
        return None

    def cancel_query(self):
        self.cancelled = True

    def _finish_query(self):
        if self.query_array:
            self.logger.info('closing SciDB connection')
            try:
                self.scidb.close()
            except:
                pass

    def get_result(self, ind):
        if ind < 0 or ind > len(self.results):
            raise ValueError("result index out of bounds")
        return self.results[ind]

    @staticmethod
    def _parse_str_result(res_str):
        """Parses result into a dict.

        A waveform result is traditionally (id, start, len)
        """
        res = {}
        for r in res_str.strip().split(', '):
            (name, val) = r.split('=')
            res[name] = int(val)
        return res

    def __del__(self):
        self._finish_query()


class MockSciDBQueryOnline(SciDBQueryOnline):
    def __init__(self, config_path):
        super(MockSciDBQueryOnline, self).__init__(config_path)
        self.logger = logging.getLogger('searchlight.mock_scidb_query')

    def start_query(self):
        if not self.scidb_query_params:
            self.logger.error('run_query() is called before prepare_query()')
            self.error = RuntimeError("query not inited")
            return
        try:
            # connect
            self.logger.info('connecting to %s:%d' %
                             (self.host, self.http_port))
            # upload the query file
            task_params_file = self.scidb_query_params['task_params_file']
            self.logger.info('uploading task file ' + task_params_file)
            if self.shared_dir:
                # copy locally
                shutil.copy(task_params_file, self.shared_dir)
                scidb_task_file = os.path.join(self.shared_dir,
                                               os.path.basename(
                                                   task_params_file))
            else:
                # remote copy (curl via scidb shim)
                scidb_task_file = "<remote_file>"
            self.logger.info('upload finished: ' + scidb_task_file)
            # create the query
            sample_arrays_str = ', '.join(
                ['depart(%s)' % x
                 for x in self.scidb_query_params['sample_arrays']])
            query_str = "searchlight(depart(%s), %s, '%s:%s:%s')" %\
                        (self.scidb_query_params['array'],
                         sample_arrays_str,
                         self.scidb_query_params['task_name'],
                         self.scidb_query_params['task_fun'],
                         scidb_task_file)
            # query (via scidb4py)
            self.logger.info('querying with: ' + query_str)
            self.query_array = iter(["id=0, time=1, len=5", "id=1, time=10, len=50",
                                     "id=0, time=20, len=55"])
        except:
            self.logger.error('could not start query: ' + str(sys.exc_info()))
            self.error = sys.exc_info()

    def next_result(self):
        if not self.query_array:
            self.logger.info('no current array, possible run_query() error...')
            self._finish_query()
            self.error = RuntimeError("query not started")
            return None
        try:
            if self.cancelled:
                self.logger.info('query cancelled by user')
                self._finish_query()
            else:
                val = self.query_array.next()
                # assume the only attribute -- the result string
                res = self._parse_str_result(str(val))
                self.results.append(res)
                return res
        except StopIteration:
            # close the connection
            self.logger.info('no more results: query finished')
            self._finish_query()
        return None

    def cancel_query(self):
        self.cancelled = True

    def _finish_query(self):
        if self.query_array:
            self.logger.info('closing SciDB connection')

    def get_result(self, ind):
        if ind < 0 or ind > len(self.results):
            raise ValueError("result index out of bounds")
        return self.results[ind]

    @staticmethod
    def _parse_str_result(res_str):
        """Parses result into a dict.

        A waveform result is traditionally (id, start, len)
        """
        res = {}
        for r in res_str.strip().split(', '):
            (name, val) = r.split('=')
            res[name] = int(val)
        return res

    def __del__(self):
        self._finish_query()


class QueryJSONParamsHandler(object):
    """
    Class to handle getting/serializing query params via JSON.

    When working with params this class assumes path-like syntax, e.g.,
    mimic.sl.db. All paths are directed to the mimic JSON element.
    For example, a.b will retrieve mimic.a.b.
    """
    def __init__(self, f):
        self.query_json = json.load(f)

    def set_params(self, params):
        for (param, val) in params.iteritems():
            param_path = param.split('.')
            param_ref = self.get_param(param_path[:-1])
            param_ref[param_path[-1]] = val

    def get_param(self, path):
        if isinstance(path, str):
            path = path.split('.')
        #  param_val = self.query_json['mimic']
        param_val = self.query_json
        for step in path:
            param_val = param_val[step]
        return param_val

    def dump_to_temp(self):
        (fd, name) = tempfile.mkstemp(dir="tmp")
        with os.fdopen(fd, 'wb') as f:
            json.dump(self.query_json, f, sort_keys=True, indent=4,
                      separators=(',', ': '))
        return name


class SciDBWaveformQuery(SciDBConnectionConfig):
    def __init__(self, config_path):
        super(SciDBWaveformQuery, self).__init__(config_path)
        self.logger = logging.getLogger('searchlight.scidb_waveform')

    def get_waveform(self, array, signal, record_id, start, length):
        self.logger.info('Connecting to SciDB (waveform)...')
        res = []
        try:
            query = 'between(%s, %d, %d, %d, %d)' % (array, record_id, start,
                                                     record_id,
                                                     start + length - 1)
            self.logger.info('Retrieving waveform: ' + query)
            res_array = self.scidb.query_interactive(query)
            current_pos = start
            for (coords, attrs) in res_array:
                pos = int(coords['tick'])  # the timeline coordinate
                for i in range(current_pos, pos):
                    # empty elements -- assume 0
                    res.append(0.0)
                current_pos = pos + 1
                res.append(float(attrs[signal]))
            self.logger.info('Closing waveform SciDB connection...')
            self.scidb.close()
        except:
            # Cannot do anything about it. Just return empty waveform
            self.logger.error(str(sys.exc_info()))
        return res


class MockSciDBWaveformQuery(SciDBConnectionConfig):
    def get_waveform(self, array, signal, record_id, start, length):
        import random
        return [random.randint(50, 100) for _ in range(length)]


class QueryHandler(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._id = 0
        self._queries = {}

    def set_query(self, query):
        with self._lock:
            qid = str(self._id)
            self._id += 1
            self._queries[qid] = query
        logger.info("query registered: " + str(qid))
        return qid

    def get_query(self, query_id):
        with self._lock:
            if query_id not in self._queries:
                raise SearchlightError("no query: " + str(query_id))
            return self._queries[query_id]

    def remove_query(self, qid):
        with self._lock:
            if qid in self._queries:
                logger.info("removed query: " + str(qid))
                del self._queries[qid]
            else:
                logger.warning("no query with id: " + str(qid))
global_query_handler = QueryHandler()


def cleanup_current_query():
    if flask.session.get("query_id"):
        query_id = flask.session["query_id"]
        logger.info("cleaning up query: " + query_id)
        global_query_handler.remove_query(query_id)
        del flask.session["query_id"]


def json_try_int(js):
    for key in js.keys():
        try:
            val_i = int(js[key])
            js[key] = val_i
        except ValueError:
            pass


@app.errorhandler(SearchlightError)
def respond_with_error(err):
    cleanup_current_query()
    return flask.make_response(str(err), 400, None)


@app.route('/')
def root():
    return app.send_static_file('searchlight.html')


@app.route('/js/<path:filepath>')
def send_js(filepath):
    return flask.send_from_directory('static/js', filepath)


@app.route('/css/<path:filepath>')
def send_css(filepath):
    return flask.send_from_directory('static/css', filepath)

@app.route('/fonts/<path:filepath>')
def send_fonts(filepath):
    return flask.send_from_directory('static/fonts', filepath)


@app.route("/query", methods=['POST'])
def start_query():
    # cleanup the previous query
    cleanup_current_query()

    # parse JSON request
    query_json = flask.request.get_json()
    if query_json is None:
        raise SearchlightError("Expecting JSON query")
    json_try_int(query_json)
    logger.debug("Got JSON request: " + str(query_json))
    with open("mimic_tmpl.json", "rb") as f:
        query_handler = QueryJSONParamsHandler(f)
    query_handler.set_params(query_json)
    query_file = query_handler.dump_to_temp()

    # create SciDB query
    sl_query = SciDBQueryOnline("config.ini")
    synopsis_arrays = ['_'.join([TASK_ARRAY,
                                 query_handler.get_param("mimic.signal"),
                                 syn_res]) for syn_res in SYNOPSIS_RESOLUTIONS]
    sl_query.prepare_query(TASK_ARRAY, synopsis_arrays, TASK_LIB, TASK_FUN,
                           query_file)
    sl_query.start_query()

    # response
    if not sl_query.error:
        query_id = global_query_handler.set_query(sl_query)
        flask.session["query_id"] = query_id
        return "OK"
    else:
        cleanup_current_query()
        raise SearchlightError("Exception when running the query")


@app.route("/result", methods=['GET'])
def next_result():
    if not flask.session.get("query_id"):
        raise SearchlightError("No active query")

    # get the next result (might block for a while)
    sl_query = global_query_handler.get_query(flask.session.get("query_id"))
    res_dict = sl_query.next_result()
    if not res_dict:
        cleanup_current_query()
        if sl_query.error:
            raise SearchlightError("Unexpected query error")
        else:
            res_dict = {"eof": True}
    else:
        res_dict = {"result": res_dict, "eof": False}
    return flask.jsonify(res_dict)


@app.route("/waveform", methods=["GET"])
def waveform():
    # parse params
    query_params = dict()
    for p in ["signal", "id", "time", "len"]:
        if p in flask.request.args:
            query_params[p] = flask.request.args[p]
        else:
            raise SearchlightError("missing parameter " + p)
    json_try_int(query_params)
    logger.debug("Got request: " + str(query_params))

    # Get waveform
    waveform_getter = SciDBWaveformQuery("config.ini")
    res = waveform_getter.get_waveform(TASK_ARRAY, query_params["signal"],
                                       query_params["id"], query_params["time"],
                                       query_params["len"])
    if len(res) > 0:
        return flask.jsonify({"waveform": res})
    else:
        raise SearchlightError("cannot retrieve waveform")


@app.route("/cancel", methods=['POST'])
def cancel_query():
    if not flask.session.get("query_id"):
        raise SearchlightError("No active query")

    # cancel and return immediately
    try:
        sl_query = global_query_handler.get_query(flask.session.get("query_id"))
        sl_query.cancel_query()
    except SearchlightError:
        # ignore, nothing fatal here
        pass
    #sl_query.next_result()  # this will propagate cancel to SciDB
    #cleanup_current_query()
    return "OK"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)
