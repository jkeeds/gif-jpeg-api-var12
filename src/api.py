"""Nine Bottle HTTP API routes from variant 12, with XML and Basic Auth."""

import base64
import binascii
import hmac
import xml.etree.ElementTree as element_tree

from bottle import Bottle, HTTPResponse, request, response


PREFIX = "/core/api/stable"


def xml_document(payload):
    """Serialize one row or a list of rows into the required XML format."""
    root = element_tree.Element("response")
    container = element_tree.SubElement(root, "items")
    records = payload if isinstance(payload, list) else [payload]
    for record in records:
        item = element_tree.SubElement(container, "item")
        for name, value in record.items():
            child = element_tree.SubElement(item, name)
            child.text = "" if value is None else str(value)
            if value is None:
                child.set("null", "true")
    return element_tree.tostring(root, encoding="unicode")


def _is_authorized(header, username, password):
    """Validate HTTP Basic credentials with constant-time comparisons."""
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True)
        provided = decoded.decode("utf-8")
        candidate_user, candidate_password = provided.split(":", 1)
    except (ValueError, UnicodeError, binascii.Error):
        return False
    return (
        hmac.compare_digest(candidate_user, username)
        and hmac.compare_digest(candidate_password, password)
    )


def wrap_result(action):
    """Map a model operation to an HTTP response in XML format."""
    try:
        result = action()
        if result is None:
            return HTTPResponse(
                "<response><error>Not found</error></response>",
                status=404, content_type="application/xml",
            )
        return xml_document(result)
    except (TypeError, ValueError):
        return HTTPResponse(
            "<response><error>Bad request</error></response>",
            status=400, content_type="application/xml",
        )


def required_id(name="id"):
    """Read and validate a numeric identifier from the query string."""
    value = request.query.get(name)
    if value is None:
        raise ValueError(f"Missing parameter: {name}")
    identifier = int(value)
    if identifier <= 0:
        raise ValueError("Identifier must be positive")
    return identifier


def register_participant_routes(app, store):
    """Bind three Participant endpoints."""

    @app.post(PREFIX + "/add-participant")
    def add_participant():
        return wrap_result(lambda: store.participant_add(
            request.query.get("locale", "ru"),
            request.query.get("platform", "web"),
        ))

    @app.get(PREFIX + "/read-participant")
    def read_participant():
        return wrap_result(lambda: store.participant_read(
            locale=request.query.get("locale"),
            platform=request.query.get("platform"),
        ))

    @app.get(PREFIX + "/retrieve-participant")
    def retrieve_participant():
        return wrap_result(lambda: store.participant_retrieve(required_id()))


def register_assignment_routes(app, store, service):
    """Bind three Assignment endpoints."""

    @app.post(PREFIX + "/add-assignment")
    def add_assignment():
        return wrap_result(lambda: service.add_assignment(
            required_id("participant"),
            request.query.get("input", ""),
            request.query.get("tags", ""),
        ))

    @app.get(PREFIX + "/read-assignment/<participant:int>")
    def read_assignment(participant):
        return wrap_result(lambda: store.assignment_read(
            participant=participant, stage=request.query.get("stage"),
        ))

    @app.get(PREFIX + "/retrieve-assignment")
    def retrieve_assignment():
        return wrap_result(lambda: store.assignment_retrieve(required_id()))


def register_result_routes(app, store):
    """Bind Result lookup endpoints."""

    @app.get(PREFIX + "/read-result/<assignment:int>")
    def read_result(assignment):
        return wrap_result(lambda: store.result_read(
            assignment=assignment, stage=request.query.get("stage"),
        ))

    @app.get(PREFIX + "/retrieve-result")
    def retrieve_result():
        return wrap_result(lambda: store.result_retrieve(required_id()))


def create_app(service, username, password):
    """Create Bottle app, authentication hooks, and all API endpoints."""
    app = Bottle()

    @app.hook("before_request")
    def authenticate():
        if not _is_authorized(
            request.headers.get("Authorization"), username, password
        ):
            raise HTTPResponse(
                "<response><error>Unauthorized</error></response>",
                status=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="GIF API"',
                    "Content-Type": "application/xml; charset=utf-8",
                },
            )

    @app.hook("after_request")
    def response_type():
        response.content_type = "application/xml; charset=utf-8"

    register_participant_routes(app, service.store)
    register_assignment_routes(app, service.store, service)
    register_result_routes(app, service.store)
    app.get(PREFIX + "/read-report")(
        lambda: wrap_result(service.store.report_read)
    )
    return app
