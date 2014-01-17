# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json

from gi.repository import GLib

from gwebsockets.server import Server
from gwebsockets.server import Message

_PORT = 8080


class WebClient(object):
    def __init__(self, session):
        self._session = session
        self._session_id = None

    def send_json_message(self, data):
        self._session.send_message(json.dumps(data))

    def send_raw_message(self, data):
        self._session.send_message(data)

    def get_session_id(self):
        return self._session_id

    def set_session_id(self, value):
        self._session_id = value


class WebServer(object):
    def __init__(self):
        self._sessions = {}

        self._server = Server()
        self._server.connect('session-started', self._session_started_cb)
        self._port = self._server.start(_PORT)

    def _session_started_cb(self, server, session):
        # perhaps reject non-sugar connections
        # how do we know if a connection comes from sugar?

        client = WebClient(session)
        session.connect('handshake-completed',
                        self._handshake_completed_cb, client)
        session.connect('message-received',
                        self._message_received_cb, client)
        # maybe disconnect the signal handler once it is recieved

        if session.is_ready():
            self._add_client(session, client)

    def _add_client(self, session, client):
        url = session.get_headers().get('http_path')
        # this should be of the form '/hub/sessionID'
        if not url or not url.startswith('/hub/'):
            return
        session_id = url[5:]
        client.set_session_id(session_id)

        if session_id in self._sessions:
            self._sessions[session_id].append(client)
        else:
            self._sessions[session_id] = [client]

        client.send_json_message(
            {'type': 'init-connection',
             'peerCount': len(self._sessions[session_id])})

    def _handshake_completed_cb(self, session, client):
        self._add_client(session, client)

    def _message_received_cb(self, session, message, source):
        if message.message_type == Message.TYPE_BINARY:
            # FIXME: how to handle this?
            return

        session_id = source.get_session_id()
        if session_id is None:
            # perhaps queue
            return

        dictionary = json.loads(message.data)

        # TODO: be more strict with the protocol

        for client in self._sessions[session_id]:
            if client != source or dictionary.get('server-echo', False):
                client.send_raw_message(message.data)

    def _session_ended_cb(self, session, client):
        # FIXME: this callback is not called at all
        self._add_client(session, client)

        session_id = client.get_session_id()
        if session_id is None:
            return

        self._sessions[session_id].remove(client)
        if not self._sessions[session_id]:
            del self._sessions[session_id]


if __name__ == "__main__":
    server = WebServer()
    
    main_loop = GLib.MainLoop()
    main_loop.run()
