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


@override_settings(MEDIA_ROOT=MEDIA)
class Phase4DriveAndApplicationManagementTests(TestCase):
    def setUp(self):
        self.dept_bca = Department.objects.create(name="Computer Applications", code="BCA")
        self.dept_ece = Department.objects.create(name="Electronics", code="ECE")

        self.staff_user = User.objects.create_user(
            "admin_officer", email="admin@campus.edu", password="AdminPassword!1", is_staff=True
        )

        self.student1_user = User.objects.create_user(
            "student_rohit", first_name="Rohit", last_name="Verma", email="rohit@example.com", password="StudentPassword!1"
        )
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1_user,
            usn="24BCA101",
            department=self.dept_bca,
            graduation_year=2026,
            cgpa=Decimal("8.50"),
            active_backlogs=0,
            resume=SimpleUploadedFile("rohit_cv.pdf", b"%PDF-1.4 mock cv", content_type="application/pdf"),
        )

        self.student2_user = User.objects.create_user(
            "student_divya", first_name="Divya", last_name="Nair", email="divya@example.com", password="StudentPassword!2"
        )
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2_user,
            usn="24ECE202",
            department=self.dept_ece,
            graduation_year=2026,
            cgpa=Decimal("6.20"),
            active_backlogs=2,
        )

        self.company_acme = Company.objects.create(name="Acme Tech", industry="IT")
        self.company_zenith = Company.objects.create(name="Zenith Core", industry="CORE")

        self.drive1 = PlacementDrive.objects.create(
            company=self.company_acme,
            title="Software Development Engineer",
            category=PlacementDrive.Category.IT,
            job_description="Backend development with Python and Django.",
            package_lpa=Decimal("8.50"),
            minimum_cgpa=Decimal("7.00"),
            maximum_backlogs=0,
            application_deadline=timezone.now() + timedelta(days=5),
            drive_date=timezone.now() + timedelta(days=12),
            vacancies=3,
            status=PlacementDrive.Status.OPEN,
        )
        self.drive1.eligible_departments.add(self.dept_bca)

        self.drive2 = PlacementDrive.objects.create(
            company=self.company_zenith,
            title="Embedded Systems Trainee",
            category=PlacementDrive.Category.CORE,
            job_description="Firmware and embedded C programming.",
            package_lpa=Decimal("5.00"),
            minimum_cgpa=Decimal("6.00"),
            maximum_backlogs=1,
            application_deadline=timezone.now() + timedelta(days=4),
            drive_date=timezone.now() + timedelta(days=10),
            vacancies=2,
            status=PlacementDrive.Status.DRAFT,
        )

        self.app1 = Application.objects.create(
            student=self.student1_profile,
            drive=self.drive1,
            resume=SimpleUploadedFile("rohit_applied_cv.pdf", b"%PDF-1.4 mock cv", content_type="application/pdf"),
            status=Application.Status.APPLIED,
        )

    def test_admin_drive_list_view_and_filtering(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_drive_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Software Development Engineer")
        self.assertContains(r, "Embedded Systems Trainee")

        # Search by title
        r_search = self.client.get(reverse("admin_drive_list"), {"q": "Software"})
        self.assertContains(r_search, "Software Development Engineer")
        self.assertNotContains(r_search, "Embedded Systems Trainee")

        # Filter by category
        r_cat = self.client.get(reverse("admin_drive_list"), {"category": "IT"})
        self.assertContains(r_cat, "Software Development Engineer")
        self.assertNotContains(r_cat, "Embedded Systems Trainee")

        # Filter by status
        r_stat = self.client.get(reverse("admin_drive_list"), {"status": "DRAFT"})
        self.assertContains(r_stat, "Embedded Systems Trainee")
        self.assertNotContains(r_stat, "Software Development Engineer")

        # Filter by company
        r_comp = self.client.get(reverse("admin_drive_list"), {"company": self.company_acme.pk})
        self.assertContains(r_comp, "Software Development Engineer")
        self.assertNotContains(r_comp, "Embedded Systems Trainee")

    def test_admin_drive_create_and_validation(self):
        self.client.force_login(self.staff_user)
        create_url = reverse("admin_drive_create")
        r_get = self.client.get(create_url)
        self.assertEqual(r_get.status_code, 200)

        # Valid drive creation
        valid_data = {
            "company": self.company_acme.pk,
            "title": "Cloud DevOps Engineer",
            "category": "IT",
            "job_description": "Managing AWS and GCP infrastructure pipelines.",
            "package_lpa": "9.50",
            "minimum_cgpa": "7.50",
            "maximum_backlogs": "0",
            "eligible_departments": [self.dept_bca.pk],
            "application_deadline": (timezone.now() + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M"),
            "drive_date": (timezone.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M"),
            "vacancies": "2",
            "status": "OPEN",
        }
        r_post = self.client.post(create_url, valid_data)
        new_drive = PlacementDrive.objects.get(title="Cloud DevOps Engineer")
        self.assertRedirects(r_post, reverse("admin_drive_detail", kwargs={"pk": new_drive.pk}))

        # Invalid: deadline after drive date
        invalid_data = valid_data.copy()
        invalid_data["title"] = "Broken Timing Drive"
        invalid_data["application_deadline"] = (timezone.now() + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M")
        invalid_data["drive_date"] = (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        r_invalid = self.client.post(create_url, invalid_data)
        self.assertEqual(r_invalid.status_code, 200)
        self.assertContains(r_invalid, "Application deadline cannot be scheduled after the drive date")

    def test_admin_drive_detail_and_edit(self):
        self.client.force_login(self.staff_user)
        detail_url = reverse("admin_drive_detail", kwargs={"pk": self.drive1.pk})
        r_detail = self.client.get(detail_url)
        self.assertEqual(r_detail.status_code, 200)
        self.assertContains(r_detail, "Software Development Engineer")
        self.assertContains(r_detail, "24BCA101")
        self.assertContains(r_detail, "Rohit Verma")

        # Edit drive
        edit_url = reverse("admin_drive_edit", kwargs={"pk": self.drive1.pk})
        edit_data = {
            "company": self.company_acme.pk,
            "title": "Lead Software Engineer",
            "category": "IT",
            "job_description": "Updated backend requirements.",
            "package_lpa": "11.00",
            "minimum_cgpa": "7.50",
            "maximum_backlogs": "0",
            "eligible_departments": [self.dept_bca.pk],
            "application_deadline": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "drive_date": (timezone.now() + timedelta(days=12)).strftime("%Y-%m-%dT%H:%M"),
            "vacancies": "4",
            "status": "OPEN",
        }
        r_edit = self.client.post(edit_url, edit_data)
        self.assertRedirects(r_edit, detail_url)
        self.drive1.refresh_from_db()
        self.assertEqual(self.drive1.title, "Lead Software Engineer")
        self.assertEqual(float(self.drive1.package_lpa), 11.00)

    def test_admin_drive_status_change(self):
        self.client.force_login(self.staff_user)
        status_url = reverse("admin_drive_status", kwargs={"pk": self.drive1.pk})

        # Change to CLOSED
        r = self.client.post(status_url, {"status": "CLOSED"})
        self.assertRedirects(r, reverse("admin_drive_detail", kwargs={"pk": self.drive1.pk}))
        self.drive1.refresh_from_db()
        self.assertEqual(self.drive1.status, "CLOSED")

        # Change to COMPLETED
        self.client.post(status_url, {"status": "COMPLETED"})
        self.drive1.refresh_from_db()
        self.assertEqual(self.drive1.status, "COMPLETED")

    def test_admin_drive_delete_safety(self):
        self.client.force_login(self.staff_user)

        # Deleting drive with applications is BLOCKED
        delete_url1 = reverse("admin_drive_delete", kwargs={"pk": self.drive1.pk})
        r_blocked = self.client.post(delete_url1, follow=True)
        self.assertRedirects(r_blocked, reverse("admin_drive_detail", kwargs={"pk": self.drive1.pk}))
        self.assertTrue(PlacementDrive.objects.filter(pk=self.drive1.pk).exists())
        messages = list(r_blocked.context["messages"])
        self.assertTrue(any("Cannot delete" in str(m) for m in messages))

        # Deleting drive without applications SUCCEEDS
        delete_url2 = reverse("admin_drive_delete", kwargs={"pk": self.drive2.pk})
        r_success = self.client.post(delete_url2, follow=True)
        self.assertRedirects(r_success, reverse("admin_drive_list"))
        self.assertFalse(PlacementDrive.objects.filter(pk=self.drive2.pk).exists())
        messages = list(r_success.context["messages"])
        self.assertTrue(any("deleted successfully" in str(m) for m in messages))

    def test_admin_application_list_and_filters(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_application_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rohit Verma")
        self.assertContains(r, "24BCA101")
        self.assertContains(r, "Software Development Engineer")

        # Search by USN
        r_search = self.client.get(reverse("admin_application_list"), {"q": "24BCA101"})
        self.assertContains(r_search, "Rohit Verma")

        # Filter by status
        r_stat = self.client.get(reverse("admin_application_list"), {"status": "APPLIED"})
        self.assertContains(r_stat, "Rohit Verma")

        r_stat_none = self.client.get(reverse("admin_application_list"), {"status": "SELECTED"})
        self.assertNotContains(r_stat_none, "Rohit Verma")

    def test_admin_application_status_update_and_student_visibility(self):
        self.client.force_login(self.staff_user)
        status_url = reverse("admin_application_status", kwargs={"pk": self.app1.pk})

        # Update to SHORTLISTED
        r_shortlist = self.client.post(status_url, {"status": "SHORTLISTED"})
        self.assertRedirects(r_shortlist, reverse("admin_application_detail", kwargs={"pk": self.app1.pk}))
        self.app1.refresh_from_db()
        self.assertEqual(self.app1.status, Application.Status.SHORTLISTED)

        # Student views My Applications and sees updated SHORTLISTED status
        self.client.force_login(self.student1_user)
        r_student = self.client.get(reverse("recruitment:my_applications"))
        self.assertEqual(r_student.status_code, 200)
        self.assertContains(r_student, "Shortlisted")

        # Admin updates to SELECTED
        self.client.force_login(self.staff_user)
        self.client.post(status_url, {"status": "SELECTED"})
        self.app1.refresh_from_db()
        self.assertEqual(self.app1.status, Application.Status.SELECTED)

        # Student views My Applications and sees updated SELECTED status
        self.client.force_login(self.student1_user)
        r_student_selected = self.client.get(reverse("recruitment:my_applications"))
        self.assertContains(r_student_selected, "Selected")

    def test_admin_application_resume_secure_download(self):
        # Staff can download
        self.client.force_login(self.staff_user)
        resume_url = reverse("admin_application_resume", kwargs={"pk": self.app1.pk})
        r_staff = self.client.get(resume_url)
        self.assertEqual(r_staff.status_code, 200)
        self.assertEqual(r_staff["Content-Type"], "application/pdf")

        # Student cannot access admin resume endpoint
        self.client.force_login(self.student2_user)
        r_blocked = self.client.get(resume_url, follow=True)
        self.assertEqual(r_blocked.redirect_chain[-1][0], reverse("accounts:student_dashboard"))

    def test_unauthorized_student_access_blocked_from_phase4_urls(self):
        self.client.force_login(self.student1_user)
        endpoints = [
            reverse("admin_drive_list"),
            reverse("admin_drive_create"),
            reverse("admin_drive_detail", kwargs={"pk": self.drive1.pk}),
            reverse("admin_drive_edit", kwargs={"pk": self.drive1.pk}),
            reverse("admin_application_list"),
            reverse("admin_application_detail", kwargs={"pk": self.app1.pk}),
            reverse("admin_application_resume", kwargs={"pk": self.app1.pk}),
        ]
        for url in endpoints:
            r = self.client.get(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))

        post_endpoints = [
            reverse("admin_drive_delete", kwargs={"pk": self.drive1.pk}),
            reverse("admin_drive_status", kwargs={"pk": self.drive1.pk}),
            reverse("admin_application_status", kwargs={"pk": self.app1.pk}),
        ]
        for url in post_endpoints:
            r = self.client.post(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))

