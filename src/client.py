"""HTTP API client with method names derived from variant 12 URL paths."""

import base64
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


BASE_ROUTE = "/core/api/stable"


class ApiClient:
    """Call all nine routes using HTTP Basic Auth and parse XML responses."""

    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        raw = f"{username}:{password}".encode("utf-8")
        self.authorization = "Basic " + base64.b64encode(raw).decode("ascii")

    def _request(self, method, route, **params):
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{BASE_ROUTE}{route}"
        if query:
            url += "?" + query
        req = urllib.request.Request(
            url, method=method, headers={
                "Authorization": self.authorization,
                "Accept": "application/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            root = ET.fromstring(response.read())
        rows = []
        for item in root.findall("./items/item"):
            row = {}
            for child in item:
                row[child.tag] = (
                    None if child.get("null") == "true" else child.text or ""
                )
            rows.append(row)
        return rows

    def core_api_stable_add_participant(self, locale="ru", platform="web"):
        return self._request(
            "POST", "/add-participant", locale=locale, platform=platform,
        )[0]

    def core_api_stable_read_participant(self, **filters):
        return self._request("GET", "/read-participant", **filters)

    def core_api_stable_retrieve_participant(self, identifier):
        rows = self._request("GET", "/retrieve-participant", id=identifier)
        return rows[0]

    def core_api_stable_add_assignment(self, participant, input_name, tags=""):
        return self._request(
            "POST", "/add-assignment", participant=participant,
            input=input_name, tags=tags,
        )[0]

    def core_api_stable_read_assignment(self, participant, **filters):
        return self._request(
            "GET", f"/read-assignment/{participant}", **filters,
        )

    def core_api_stable_retrieve_assignment(self, identifier):
        rows = self._request("GET", "/retrieve-assignment", id=identifier)
        return rows[0]

    def core_api_stable_read_result(self, assignment, **filters):
        return self._request(
            "GET", f"/read-result/{assignment}", **filters,
        )

    def core_api_stable_retrieve_result(self, identifier):
        rows = self._request("GET", "/retrieve-result", id=identifier)
        return rows[0]

    def core_api_stable_read_report(self):
        return self._request("GET", "/read-report")
