from django.contrib.auth import get_user_model
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class LoginRequiredMiddlewareAccessTests(TestCase):
    """验证全站登录中间件的公开路由与受保护路由边界。"""

    def setUp(self):
        site, _created = Site.objects.get_or_create(
            id=1,
            defaults={"domain": "testserver", "name": "testserver"},
        )
        flatpage = FlatPage.objects.create(
            url="/about/site/",
            title="关于 TMS",
            content="关于页面内容",
            registration_required=False,
        )
        flatpage.sites.add(site)

    def test_anonymous_user_can_access_public_entry_pages(self):
        public_urls = [
            reverse("home"),
            reverse("robots_txt"),
            reverse("accounts:login"),
            reverse("accounts:signup"),
            "/about/site/",
        ]

        for url in public_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_anonymous_user_is_redirected_from_account_home_to_login(self):
        protected_url = reverse("accounts:home")

        response = self.client.get(protected_url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={protected_url}",
        )

    def test_anonymous_user_is_redirected_from_permission_view_to_login(self):
        protected_url = reverse("accounts:user_list")

        response = self.client.get(protected_url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={protected_url}",
        )

    def test_authenticated_user_without_profile_permission_gets_forbidden(self):
        user = User.objects.create_user("plain-auth-user", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:user_list"))

        self.assertEqual(response.status_code, 403)


class RememberMeLoginTests(TestCase):
    """验证登录页“记住我”勾选框的会话有效期行为。"""

    def setUp(self):
        self.user = User.objects.create_user("remember-me-user", password="testpass123")

    def test_login_without_remember_me_expires_on_browser_close(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "remember-me-user", "password": "testpass123"},
        )

        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_login_with_remember_me_keeps_default_session(self):
        self.client.post(
            reverse("accounts:login"),
            {
                "username": "remember-me-user",
                "password": "testpass123",
                "remember_me": "on",
            },
        )

        self.assertFalse(self.client.session.get_expire_at_browser_close())
