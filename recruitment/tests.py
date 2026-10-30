from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department, StudentProfile
from .models import Application, Company, PlacementDrive

import tempfile

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class ApplicationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name="Computer Applications", code="BCA")
        cls.other_dept = Department.objects.create(name="Commerce", code="BCOM")
        cls.user = User.objects.create_user("stu", password="pw12345!", first_name="Stu")
        cls.student = StudentProfile.objects.create(
            user=cls.user, usn="U1", department=cls.dept,
            graduation_year=2027, cgpa=Decimal("7.50"), active_backlogs=0,
        )
        cls.staff = User.objects.create_user("officer", password="pw12345!", is_staff=True)
        cls.company = Company.objects.create(name="Acme", industry="IT")
        cls.drive = cls._drive("Developer")

    @classmethod
    def _drive(cls, title, **kw):
        defaults = dict(
            company=cls.company, title=title, category="IT", job_description="Build things",
            package_lpa=5, minimum_cgpa=7, maximum_backlogs=0,
            application_deadline=timezone.now() + timedelta(days=3),
            drive_date=timezone.now() + timedelta(days=10),
            status=PlacementDrive.Status.OPEN,
        )
        defaults.update(kw)
        return PlacementDrive.objects.create(**defaults)

    def resume(self, name="cv.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    # --- role separation -------------------------------------------------
    def test_student_cannot_use_staff_login(self):
        r = self.client.post(reverse("accounts:staff_login"), {"username": "stu", "password": "pw12345!"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_cannot_use_student_login(self):
        r = self.client.post(reverse("accounts:login"), {"username": "officer", "password": "pw12345!"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_student_login_redirects_to_student_dashboard(self):
        r = self.client.post(reverse("accounts:login"), {"username": "stu", "password": "pw12345!"})
        self.assertRedirects(r, reverse("accounts:student_dashboard"))

    def test_staff_login_redirects_to_staff_dashboard(self):
        r = self.client.post(reverse("accounts:staff_login"), {"username": "officer", "password": "pw12345!"})
        self.assertRedirects(r, reverse("accounts:staff_dashboard"))

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("recruitment:placement_drives"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_student_blocked_from_officer_pages(self):
        self.client.force_login(self.user)
        for name in ("accounts:staff_dashboard", "recruitment:manage_applications"):
            r = self.client.get(reverse(name), follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))

    def test_staff_blocked_from_student_pages(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("recruitment:my_applications"), follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:staff_dashboard"))

    # --- applying --------------------------------------------------------
    def test_student_can_apply_with_resume(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("recruitment:apply", args=[self.drive.pk]), {"resume": self.resume()})
        self.assertRedirects(r, reverse("recruitment:my_applications"))
        self.assertEqual(Application.objects.filter(student=self.student, drive=self.drive).count(), 1)

    def test_apply_requires_resume(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("recruitment:apply", args=[self.drive.pk]), {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)

    def test_rejects_bad_file_type(self):
        self.client.force_login(self.user)
        bad = SimpleUploadedFile("cv.exe", b"x")
        self.client.post(reverse("recruitment:apply", args=[self.drive.pk]), {"resume": bad})
        self.assertEqual(Application.objects.count(), 0)

    def test_cannot_apply_twice(self):
        self.client.force_login(self.user)
        url = reverse("recruitment:apply", args=[self.drive.pk])
        self.client.post(url, {"resume": self.resume()})
        self.client.post(url, {"resume": self.resume()})
        self.assertEqual(Application.objects.count(), 1)

    def test_low_cgpa_blocked_server_side(self):
        hard = self._drive("Hard", minimum_cgpa=9)
        self.client.force_login(self.user)
        self.client.post(reverse("recruitment:apply", args=[hard.pk]), {"resume": self.resume()})
        self.assertEqual(Application.objects.count(), 0)

    def test_department_restriction(self):
        d = self._drive("Commerce only")
        d.eligible_departments.add(self.other_dept)
        self.assertTrue(d.eligibility_issues(self.student))
        self.assertFalse(self.drive.eligibility_issues(self.student))

    def test_backlog_limit(self):
        self.student.active_backlogs = 2
        self.assertTrue(self.drive.eligibility_issues(self.student))

    def test_closed_or_expired_drive_blocked(self):
        closed = self._drive("Closed", status=PlacementDrive.Status.CLOSED)
        expired = self._drive("Expired", application_deadline=timezone.now() - timedelta(hours=1))
        self.client.force_login(self.user)
        for d in (closed, expired):
            self.client.post(reverse("recruitment:apply", args=[d.pk]), {"resume": self.resume()})
        self.assertEqual(Application.objects.count(), 0)

    def test_draft_hidden_from_students(self):
        draft = self._drive("Secret", status=PlacementDrive.Status.DRAFT)
        self.client.force_login(self.user)
        r = self.client.get(reverse("recruitment:placement_drives"))
        self.assertNotContains(r, "Secret")

    # --- withdraw / review ----------------------------------------------
    def _applied(self):
        return Application.objects.create(student=self.student, drive=self.drive, resume="x.pdf")

    def test_withdraw_then_reapply(self):
        app = self._applied()
        self.client.force_login(self.user)
        self.client.post(reverse("recruitment:withdraw", args=[app.pk]))
        app.refresh_from_db()
        self.assertEqual(app.status, "WITHDRAWN")
        self.client.post(reverse("recruitment:apply", args=[self.drive.pk]), {"resume": self.resume()})
        app.refresh_from_db()
        self.assertEqual(app.status, "APPLIED")
        self.assertEqual(Application.objects.count(), 1)

    def test_withdraw_needs_post(self):
        app = self._applied()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("recruitment:withdraw", args=[app.pk])).status_code, 405)

    def test_cannot_withdraw_someone_elses_application(self):
        app = self._applied()
        other = User.objects.create_user("o", password="pw12345!")
        StudentProfile.objects.create(user=other, usn="U2", department=self.dept, graduation_year=2027, cgpa=8)
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("recruitment:withdraw", args=[app.pk])).status_code, 404)

    def test_officer_can_shortlist(self):
        app = self._applied()
        self.client.force_login(self.staff)
        self.client.post(reverse("recruitment:update_status", args=[app.pk]), {"status": "SHORTLISTED"})
        app.refresh_from_db()
        self.assertEqual(app.status, "SHORTLISTED")

    def test_student_cannot_change_status(self):
        app = self._applied()
        self.client.force_login(self.user)
        self.client.post(reverse("recruitment:update_status", args=[app.pk]), {"status": "SELECTED"})
        app.refresh_from_db()
        self.assertEqual(app.status, "APPLIED")

    def test_officer_page_renders_with_data(self):
        self._applied()
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("recruitment:manage_applications")), "U1")
