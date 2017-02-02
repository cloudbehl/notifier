from flask import Flask
from flask import request
from flask import Response
import logging
from multiprocessing import Event
from multiprocessing import Process
from tendrl.alerting.persistence.exceptions import EtcdError
from tendrl.alerting.exceptions import AlertingError
from tendrl.alerting.exceptions import InvalidRequest
from tendrl.alerting.notification.exceptions import InvalidHandlerConfig
from tendrl.alerting.notification.exceptions import NotificationPluginError
import yaml


LOG = logging.getLogger(__name__)
app = Flask(__name__)
plugin_manager = None
persister = None
HTTP_500_INTERNAL_SERVER_ERROR = 500

@app.route("/alerting/notification_medium/supported")
def get_handlers():
    try:
        return Response(
            plugin_manager.get_handlers(),
            mimetype='application/json'
        )
    except (
        AlertingError,
        NotificationPluginError
    ) as ex:
        return str(ex), HTTP_500_INTERNAL_SERVER_ERROR


@app.route("/alerting/notification_medium/<name>/help")
def get_config_help(name):
    try:
        return Response(
            plugin_manager.get_config_help(name),
            mimetype='application/json'
        )
    except (
        InvalidRequest,
        NotificationPluginError
    ) as ex:
        return str(ex), HTTP_500_INTERNAL_SERVER_ERROR


@app.route("/alerting/alerts")
def get_alerts(filter_criteria=None):
    try:
        if len(request.args) > 0:
            return Response(
                yaml.safe_dump(persister.get_alerts(request.args.items())),
                mimetype='application/json'
            )
        return Response(
            yaml.safe_dump(persister.get_alerts()),
            mimetype='application/json'
        )
    except EtcdError as ex:
        return str(ex), HTTP_500_INTERNAL_SERVER_ERROR


@app.route("/alerting/notification_medium/<name>/config", methods=['POST'])
def add_destination(name):
    try:
        return Response(
            plugin_manager.add_destination(name, request.data),
            mimetype='application/json'
        )
    except (
        InvalidHandlerConfig,
        NotificationPluginError
    ) as ex:
        return str(ex), HTTP_500_INTERNAL_SERVER_ERROR


@app.route("/alerting/alert_types")
def get_alert_types():
    try:
        return Response(
            yaml.safe_dump(persister.get_alert_types()),
            mimetype='application/json'
        )
    except EtcdError as ex:
        return str(ex), HTTP_500_INTERNAL_SERVER_ERROR


class APIManager(Process):

    def __init__(
        self,
        api_server_addr,
        api_server_port,
        pluginManager,
        alerting_persister
    ):
        global plugin_manager, persister
        plugin_manager = pluginManager
        persister = alerting_persister
        super(APIManager, self).__init__()
        self._complete = Event()
        self.host = api_server_addr
        self.port = api_server_port

    def run(self):
        try:
            app.run(host=self.host, port=self.port)
            while not self._complete.is_set():
                self._complete.wait(timeout=1)
        except Exception as ex:
            LOG.error('Failed to start the api server. Error %s' %
                      ex, exc_info=True)
            self.terminate()
            raise ex
