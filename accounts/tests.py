from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Department, StudentProfile


class RegistrationTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Applications", code="BCA")

    def data(self, **extra):
        d = {
            "first_name": "Asha", "last_name": "Rao", "email": "a@x.com", "username": "asha",
            "usn": "24ug001", "department": self.dept.pk, "graduation_year": 2027,
            "cgpa": "8.1", "active_backlogs": 0, "phone": "",
            "password1": "Str0ng!Pass#9", "password2": "Str0ng!Pass#9",
            "accept_terms": "on", "accept_privacy": "on", "accept_sharing": "on",
        }
        d.update(extra)
        return d

    def test_register_creates_user_and_profile_and_logs_in(self):
        r = self.client.post(reverse("accounts:register"), self.data())
        self.assertRedirects(r, reverse("accounts:student_dashboard"))
        profile = StudentProfile.objects.get(user__username="asha")
        self.assertEqual(profile.usn, "24UG001")          # normalised to upper case
        self.assertFalse(profile.user.is_staff)           # self-registration never grants staff

    def test_duplicate_usn_rejected(self):
        self.client.post(reverse("accounts:register"), self.data())
        self.client.logout()
        r = self.client.post(reverse("accounts:register"), self.data(username="other"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_cgpa_rejected(self):
        r = self.client.post(reverse("accounts:register"), self.data(cgpa="11"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_home_shows_both_logins_when_anonymous(self):
        r = self.client.get("/")
        self.assertContains(r, "Student login")
        self.assertContains(r, "Officer login")


class ProfileFormTests(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="Computer Applications", code="BCA")
        self.user = User.objects.create_user("stu", password="pw12345!")
        StudentProfile.objects.create(user=self.user, usn="U1", department=dept, graduation_year=2027, cgpa=8)
        self.client.force_login(self.user)

    def test_profile_page_renders(self):
        self.assertContains(self.client.get(reverse("accounts:student_profile")), "Ready to apply?")

    def test_rejects_executable_as_resume(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile("virus.exe", b"MZ")
        r = self.client.post(reverse("accounts:student_profile"), {"phone": "", "resume": bad})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(StudentProfile.objects.get(user=self.user).resume)

    def test_rejects_bad_phone(self):
        r = self.client.post(reverse("accounts:student_profile"), {"phone": "abc"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "valid phone number")

    def test_saves_valid_phone(self):
        self.client.post(reverse("accounts:student_profile"), {"phone": "9845012345"})
        self.assertEqual(StudentProfile.objects.get(user=self.user).phone, "9845012345")


class LandingAndLoginPageTests(TestCase):
    def test_landing_shows_live_numbers_and_open_drives(self):
        from datetime import timedelta
        from django.utils import timezone
        from recruitment.models import Company, PlacementDrive
        c = Company.objects.create(name="Acme Corp", industry="IT")
        PlacementDrive.objects.create(
            company=c, title="Open Role", category="IT", job_description="x", package_lpa=5,
            application_deadline=timezone.now() + timedelta(days=2),
            drive_date=timezone.now() + timedelta(days=9), status="OPEN",
        )
        PlacementDrive.objects.create(  # expired drives must not be advertised
            company=c, title="Expired Role", category="IT", job_description="x", package_lpa=5,
            application_deadline=timezone.now() - timedelta(days=1),
            drive_date=timezone.now() + timedelta(days=9), status="OPEN",
        )
        r = self.client.get("/")
        self.assertContains(r, "Open Role")
        self.assertNotContains(r, "Expired Role")
        self.assertEqual(r.context["stats"]["open_drives"], 1)

    def test_logged_in_user_is_redirected_away_from_login_pages(self):
        Department.objects.create(name="Computer Applications", code="BCA")
        u = User.objects.create_user("officer", password="pw12345!", is_staff=True)
        self.client.force_login(u)
        for name in ("accounts:login", "accounts:staff_login"):
            r = self.client.get(reverse(name), follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:staff_dashboard"))

    def test_login_error_is_shown(self):
        r = self.client.post(reverse("accounts:login"), {"username": "nobody", "password": "x"})
        self.assertContains(r, "form-alert")

    def test_register_warns_when_no_departments(self):
        r = self.client.get(reverse("accounts:register"))
        self.assertContains(r, "no departments have been set up")

    def test_all_public_pages_render(self):
        for name in ("home", "accounts:login", "accounts:staff_login", "accounts:register"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class ConsentAndLegalPageTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Applications", code="BCA")

    def data(self, **extra):
        d = {
            "first_name": "Asha", "last_name": "Rao", "email": "a@x.com", "username": "asha",
            "usn": "24ug001", "department": self.dept.pk, "graduation_year": 2027,
            "cgpa": "8.1", "active_backlogs": 0, "phone": "",
            "password1": "Str0ng!Pass#9", "password2": "Str0ng!Pass#9",
            "accept_terms": "on", "accept_privacy": "on", "accept_sharing": "on",
        }
        d.update(extra)
        return d

    def test_registration_records_consent_date_and_version(self):
        from django.conf import settings
        self.client.post(reverse("accounts:register"), self.data())
        p = StudentProfile.objects.get(user__username="asha")
        self.assertIsNotNone(p.consent_accepted_at)
        self.assertEqual(p.consent_version, settings.POLICY_VERSION)

    def test_each_consent_box_is_required(self):
        for box in ("accept_terms", "accept_privacy", "accept_sharing"):
            data = self.data(username="u_" + box)
            del data[box]
            r = self.client.post(reverse("accounts:register"), data)
            self.assertEqual(r.status_code, 200, box)
            self.assertFalse(User.objects.filter(username="u_" + box).exists(), box)

    def test_register_page_links_to_policies(self):
        r = self.client.get(reverse("accounts:register"))
        self.assertContains(r, reverse("terms"))
        self.assertContains(r, reverse("privacy"))

    def test_legal_pages_are_public_and_use_configured_details(self):
        from django.conf import settings
        for name in ("privacy", "terms", "dpdp"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200, name)
            self.assertContains(r, settings.INSTITUTION_NAME)
            self.assertContains(r, settings.PRIVACY_CONTACT_EMAIL)
            self.assertContains(r, settings.POLICY_VERSION)

    def test_privacy_policy_covers_gdpr_and_dpdp(self):
        r = self.client.get(reverse("privacy"))
        for phrase in ("GDPR", "DPDP Act", "Data Fiduciary", "Data Protection Board", "Withdraw consent"):
            self.assertContains(r, phrase)

    def test_dpdp_notice_has_the_required_parts(self):
        r = self.client.get(reverse("dpdp"))
        for phrase in ("section 5", "Data Principal", "withdraw consent", "Data Protection Board of India",
                       "Eighth Schedule", "at least one year", "72 hours"):
            self.assertContains(r, phrase)

    def test_consent_request_links_to_dpdp_notice(self):
        self.assertContains(self.client.get(reverse("accounts:register")), reverse("dpdp"))

    def test_footer_links_on_landing_and_app_pages(self):
        self.assertContains(self.client.get("/"), reverse("privacy"))
        u = User.objects.create_user("stu", password="pw12345!")
        StudentProfile.objects.create(user=u, usn="U9", department=self.dept, graduation_year=2027, cgpa=8)
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse("accounts:student_dashboard")), reverse("terms"))

    def test_profile_shows_consent_record(self):
        self.client.post(reverse("accounts:register"), self.data())
        r = self.client.get(reverse("accounts:student_profile"))
        self.assertContains(r, "You accepted the Terms and Conditions")


class FooterTests(TestCase):
    def test_public_footer_has_links_contact_and_year(self):
        from django.conf import settings
        from django.utils import timezone
        r = self.client.get("/")
        for url in (reverse("privacy"), reverse("terms"), reverse("dpdp"),
                    reverse("accounts:login"), reverse("accounts:staff_login")):
            self.assertContains(r, f'href="{url}"')
        self.assertContains(r, f"mailto:{settings.PRIVACY_CONTACT_EMAIL}")
        self.assertContains(r, str(timezone.now().year))

    def test_app_footer_has_help_link(self):
        from django.conf import settings
        dept = Department.objects.create(name="CA", code="BCA")
        u = User.objects.create_user("stu", password="pw12345!")
        StudentProfile.objects.create(user=u, usn="U7", department=dept, graduation_year=2027, cgpa=8)
        self.client.force_login(u)
        r = self.client.get(reverse("accounts:student_dashboard"))
        self.assertContains(r, "Contact placement office")
        self.assertContains(r, f"mailto:{settings.PRIVACY_CONTACT_EMAIL}")
