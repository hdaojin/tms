from django.contrib.auth import get_user_model
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse

from accounts.services.registration import issue_registration_invitation
from core.utils.invitation import invitation_code_digest


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


class SignupTests(TestCase):
    def test_superuser_can_copy_signup_link_and_valid_code_together(self):
        self.client.force_login(User.objects.create_superuser("invite-admin"))
        url = reverse("accounts:generate_invitation")
        response = self.client.post(url, {"hours": 2, "max_uses": 1}, secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title"], "新用户注册")
        signup_url = f"https://testserver{reverse('accounts:signup')}"
        code = response.context["code"]
        self.assertEqual(response.context["issued_invitation"].code_digest, invitation_code_digest(code))
        self.assertContains(
            response, f"注册链接：{signup_url}\n邀请码：{code}",
        )
        self.assertContains(response, 'data-copy-target="#registration-invitation"')
        self.assertNotContains(self.client.get(url), code)

    def test_same_name_signup_does_not_collect_disambiguation(self):
        User.objects.create_user("existing-user", last_name="张", first_name="伟")
        actor = User.objects.create_superuser("signup-invite-admin")
        _, code = issue_registration_invitation(actor=actor, hours=2, max_uses=1)
        url = reverse("accounts:signup")

        self.assertNotContains(self.client.get(url), 'name="name_disambiguation"')
        response = self.client.post(url, {
            "username": "new-user",
            "last_name": "张",
            "first_name": "伟",
            "password1": "R7-unique-test-password",
            "password2": "R7-unique-test-password",
            "invitation_code": code,
            "name_disambiguation": "旧表单提交的备注",
        })

        self.assertTemplateUsed(response, "accounts/signup_done.html")
        user = User.objects.get(username="new-user")
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.name_disambiguation, "")


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
