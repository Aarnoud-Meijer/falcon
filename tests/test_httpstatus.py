# -*- coding: utf-8

import pytest

import falcon
from falcon.http_status import HTTPStatus
import falcon.testing as testing

from _util import create_app  # NOQA


@pytest.fixture(params=[True, False])
def client(request):
    app = create_app(asgi=request.param)
    app.add_route('/status', TestStatusResource())
    return testing.TestClient(app)


@pytest.fixture(params=[True, False])
def hook_test_client(request):
    app = create_app(asgi=request.param)
    app.add_route('/status', TestHookResource())
    return testing.TestClient(app)


def before_hook(req, resp, resource, params):
    raise HTTPStatus(falcon.HTTP_200,
                     headers={'X-Failed': 'False'},
                     body='Pass')


def after_hook(req, resp, resource):
    resp.status = falcon.HTTP_200
    resp.set_header('X-Failed', 'False')
    resp.body = 'Pass'


def noop_after_hook(req, resp, resource):
    pass


class TestStatusResource:

    @falcon.before(before_hook)
    def on_get(self, req, resp):
        resp.status = falcon.HTTP_500
        resp.set_header('X-Failed', 'True')
        resp.body = 'Fail'

    def on_post(self, req, resp):
        resp.status = falcon.HTTP_500
        resp.set_header('X-Failed', 'True')
        resp.body = 'Fail'

        raise HTTPStatus(falcon.HTTP_200,
                         headers={'X-Failed': 'False'},
                         body='Pass')

    @falcon.after(after_hook)
    def on_put(self, req, resp):
        # NOTE(kgriffs): Test that passing a unicode status string
        # works just fine.
        resp.status = '500 Internal Server Error'
        resp.set_header('X-Failed', 'True')
        resp.body = 'Fail'

    def on_patch(self, req, resp):
        raise HTTPStatus(falcon.HTTP_200, body=None)

    @falcon.after(noop_after_hook)
    def on_delete(self, req, resp):
        raise HTTPStatus(falcon.HTTP_200,
                         headers={'X-Failed': 'False'},
                         body='Pass')


class TestHookResource:

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_500
        resp.set_header('X-Failed', 'True')
        resp.body = 'Fail'

    def on_patch(self, req, resp):
        raise HTTPStatus(falcon.HTTP_200,
                         body=None)

    def on_delete(self, req, resp):
        raise HTTPStatus(falcon.HTTP_200,
                         headers={'X-Failed': 'False'},
                         body='Pass')


class TestHTTPStatus:
    def test_raise_status_in_before_hook(self, client):
        """ Make sure we get the 200 raised by before hook """
        response = client.simulate_request(path='/status', method='GET')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_in_responder(self, client):
        """ Make sure we get the 200 raised by responder """
        response = client.simulate_request(path='/status', method='POST')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_runs_after_hooks(self, client):
        """ Make sure after hooks still run """
        response = client.simulate_request(path='/status', method='PUT')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_survives_after_hooks(self, client):
        """ Make sure after hook doesn't overwrite our status """
        response = client.simulate_request(path='/status', method='DELETE')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_empty_body(self, client):
        """ Make sure passing None to body results in empty body """
        response = client.simulate_request(path='/status', method='PATCH')
        assert response.text == ''


class TestHTTPStatusWithMiddleware:

    def test_raise_status_in_process_request(self, hook_test_client):
        """ Make sure we can raise status from middleware process request """
        client = hook_test_client

        class TestMiddleware:
            def process_request(self, req, resp):
                raise HTTPStatus(falcon.HTTP_200,
                                 headers={'X-Failed': 'False'},
                                 body='Pass')

            # NOTE(kgriffs): Test the side-by-side support for dual WSGI and
            #   ASGI compatibility.
            async def process_request_async(self, req, resp):
                self.process_request(req, resp)

        client.app.add_middleware(TestMiddleware())

        response = client.simulate_request(path='/status', method='GET')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_in_process_resource(self, hook_test_client):
        """ Make sure we can raise status from middleware process resource """
        client = hook_test_client

        class TestMiddleware:
            def process_resource(self, req, resp, resource, params):
                raise HTTPStatus(falcon.HTTP_200,
                                 headers={'X-Failed': 'False'},
                                 body='Pass')

            async def process_resource_async(self, *args):
                self.process_resource(*args)

        # NOTE(kgriffs): Pass a list to test that add_middleware can handle it
        client.app.add_middleware([TestMiddleware()])

        response = client.simulate_request(path='/status', method='GET')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'

    def test_raise_status_runs_process_response(self, hook_test_client):
        """ Make sure process_response still runs """
        client = hook_test_client

        class TestMiddleware:
            def process_response(self, req, resp, resource, req_succeeded):
                resp.status = falcon.HTTP_200
                resp.set_header('X-Failed', 'False')
                resp.body = 'Pass'

            async def process_response_async(self, *args):
                self.process_response(*args)

        # NOTE(kgriffs): Pass a generic iterable to test that add_middleware
        #   can handle it.
        client.app.add_middleware(iter([TestMiddleware()]))

        response = client.simulate_request(path='/status', method='GET')
        assert response.status == falcon.HTTP_200
        assert response.headers['x-failed'] == 'False'
        assert response.text == 'Pass'
