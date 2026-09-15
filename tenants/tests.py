from types import SimpleNamespace

from django.http import HttpResponse
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from .middleware import RootStoreRedirectMiddleware


class RootStoreRedirectMiddlewareTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.middleware = RootStoreRedirectMiddleware(lambda request: HttpResponse('home'))

	def test_authenticated_tenant_user_is_sent_to_store(self):
		request = self.factory.get('/', HTTP_HOST='x.localhost:8000')
		request.user = SimpleNamespace(is_authenticated=True, tenant_id=7)
		request.tenant = SimpleNamespace(id=7)

		response = self.middleware(request)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response['Location'], '/loja/')

	def test_anonymous_user_with_valid_tenant_goes_to_store(self):
		request = self.factory.get('/', HTTP_HOST='x.localhost:8000')
		request.user = SimpleNamespace(is_authenticated=False, tenant_id=None)
		request.tenant = SimpleNamespace(id=7)

		response = self.middleware(request)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response['Location'], '/loja/')

	def test_authenticated_user_from_another_tenant_receives_404(self):
		request = self.factory.get('/', HTTP_HOST='x.localhost:8000')
		request.user = SimpleNamespace(is_authenticated=True, tenant_id=8)
		request.tenant = SimpleNamespace(id=7)

		with self.assertRaises(Http404):
			self.middleware(request)

	def test_unknown_tenant_receives_404(self):
		request = self.factory.get('/', HTTP_HOST='x.localhost:8000')
		request.user = SimpleNamespace(is_authenticated=False, tenant_id=None)
		request.tenant = None

		with self.assertRaises(Http404):
			self.middleware(request)
