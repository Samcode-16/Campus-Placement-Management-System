import tempfile
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
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


class Phase1RoleAuthenticationTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Applications", code="BCA")
        self.student_user = User.objects.create_user("student_user", password="StudentPassword123!")
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user, usn="24UG999", department=self.dept,
            graduation_year=2027, cgpa=8.5, active_backlogs=0
        )
        self.admin_user = User.objects.create_user("admin_officer", password="AdminPassword123!", is_staff=True)
        self.superuser = User.objects.create_superuser("root_admin", "root@example.com", "SuperPassword123!")

    def test_administrator_login_success(self):
        r = self.client.post(reverse("accounts:staff_login"), {
            "username": "admin_officer",
            "password": "AdminPassword123!",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin_user.pk)

    def test_student_login_success(self):
        r = self.client.post(reverse("accounts:login"), {
            "username": "student_user",
            "password": "StudentPassword123!",
        })
        self.assertRedirects(r, reverse("accounts:student_dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student_user.pk)

    def test_unauthorized_student_access_to_admin_dashboard(self):
        self.client.force_login(self.student_user)
        r = self.client.get("/admin-dashboard/", follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
        messages_list = list(r.context["messages"])
        self.assertTrue(any("Access denied" in str(m) for m in messages_list))

    def test_unauthenticated_user_access_to_admin_dashboard(self):
        r = self.client.get("/admin-dashboard/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/staff-login/", r["Location"])

    def test_superuser_access_to_admin_dashboard(self):
        self.client.force_login(self.superuser)
        r = self.client.get("/admin-dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dashboard Overview")

    def test_logout_functionality_with_message(self):
        self.client.force_login(self.student_user)
        r = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        messages_list = list(r.context["messages"])
        self.assertTrue(any("logged out" in str(m).lower() for m in messages_list))

    def test_student_registration_assigns_student_group_and_denies_admin(self):
        data = {
            "first_name": "New", "last_name": "Student", "email": "new@student.com",
            "username": "newstudent", "usn": "24UG888", "department": self.dept.pk,
            "graduation_year": 2027, "cgpa": "8.0", "active_backlogs": 0, "phone": "",
            "password1": "SecurePass123!", "password2": "SecurePass123!",
            "accept_terms": "on", "accept_privacy": "on", "accept_sharing": "on",
            "is_staff": True, "is_superuser": True,
        }
        r = self.client.post(reverse("accounts:register"), data)
        self.assertRedirects(r, reverse("accounts:student_dashboard"))
        user = User.objects.get(username="newstudent")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.groups.filter(name="Student").exists())


class Phase2AdminDashboardTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        from recruitment.models import Company, PlacementDrive, Application
        from training.models import TrainingProgram

        self.dept = Department.objects.create(name="Computer Applications", code="BCA")
        self.admin = User.objects.create_user("admin_user", password="AdminPassword123!", is_staff=True)
        self.student1 = User.objects.create_user("stu1", password="pw1")
        self.profile1 = StudentProfile.objects.create(
            user=self.student1, usn="24UG101", department=self.dept, graduation_year=2027, cgpa=8.0
        )
        self.student2 = User.objects.create_user("stu2", password="pw2")
        self.profile2 = StudentProfile.objects.create(
            user=self.student2, usn="24UG102", department=self.dept, graduation_year=2027, cgpa=7.5
        )

        self.company1 = Company.objects.create(name="Alpha Tech", industry="IT")
        self.company2 = Company.objects.create(name="Beta Fin", industry="Banking")

        self.drive1 = PlacementDrive.objects.create(
            company=self.company1, title="Software Engineer", category=PlacementDrive.Category.IT,
            job_description="Dev", package_lpa=8.0, minimum_cgpa=7.0, maximum_backlogs=0,
            application_deadline=timezone.now() + timedelta(days=5),
            drive_date=timezone.now() + timedelta(days=10),
            status=PlacementDrive.Status.OPEN,
        )
        self.drive2 = PlacementDrive.objects.create(
            company=self.company2, title="Analyst", category=PlacementDrive.Category.BANKING,
            job_description="Finance", package_lpa=6.0, minimum_cgpa=6.0, maximum_backlogs=0,
            application_deadline=timezone.now() - timedelta(days=2),
            drive_date=timezone.now() + timedelta(days=5),
            status=PlacementDrive.Status.CLOSED,
        )

        self.app1 = Application.objects.create(
            student=self.profile1, drive=self.drive1, status=Application.Status.SELECTED
        )
        self.app2 = Application.objects.create(
            student=self.profile2, drive=self.drive1, status=Application.Status.SHORTLISTED
        )

        self.training = TrainingProgram.objects.create(
            title="Full Stack Bootcamp", description="Web dev training", trainer="John",
            start_date=timezone.now().date(), end_date=(timezone.now() + timedelta(days=30)).date(),
            status=TrainingProgram.Status.UPCOMING
        )

    def test_admin_dashboard_statistics_match_database(self):
        self.client.force_login(self.admin)
        r = self.client.get("/admin-dashboard/")
        self.assertEqual(r.status_code, 200)

        ctx = r.context
        self.assertEqual(ctx["total_students"], 2)
        self.assertEqual(ctx["total_companies"], 2)
        self.assertEqual(ctx["total_drives"], 2)
        self.assertEqual(ctx["open_drives"], 1)
        self.assertEqual(ctx["total_applications"], 2)
        self.assertEqual(ctx["shortlisted_count"], 1)
        self.assertEqual(ctx["selected_count"], 1)
        self.assertEqual(ctx["total_training_programs"], 1)
        self.assertEqual(ctx["selected_students"], 1)
        self.assertEqual(ctx["non_selected_students"], 1)
        self.assertEqual(ctx["selection_rate"], 50.0)

        # Verify rendered numbers in HTML
        self.assertContains(r, ">2</strong>")
        self.assertContains(r, "50.0%")

    def test_admin_dashboard_empty_database_behavior(self):
        # Empty all test models except admin
        from recruitment.models import Company, PlacementDrive, Application
        from training.models import TrainingProgram

        Application.objects.all().delete()
        PlacementDrive.objects.all().delete()
        Company.objects.all().delete()
        TrainingProgram.objects.all().delete()
        StudentProfile.objects.all().delete()

        self.client.force_login(self.admin)
        r = self.client.get("/admin-dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total_students"], 0)
        self.assertEqual(r.context["total_applications"], 0)
        self.assertEqual(r.context["selection_rate"], 0)
        self.assertContains(r, "No student applications recorded yet")
        self.assertContains(r, "No placement drives published yet")

    def test_admin_dashboard_unauthorized_student_access_blocked(self):
        self.client.force_login(self.student1)
        r = self.client.get("/admin-dashboard/", follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
        messages = list(r.context["messages"])
        self.assertTrue(any("Access denied" in str(m) for m in messages))

    def test_admin_dashboard_unauthorized_anonymous_redirected(self):
        r = self.client.get("/admin-dashboard/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/staff-login/", r["Location"])

    def test_admin_dashboard_cards_have_management_links(self):
        self.client.force_login(self.admin)
        r = self.client.get("/admin-dashboard/")
        self.assertContains(r, reverse("admin_application_list"))
        self.assertContains(r, reverse("admin_drive_list"))
        self.assertContains(r, reverse("admin_training_list"))

    def test_admin_dashboard_charts_and_recent_activities_rendered(self):
        self.client.force_login(self.admin)
        r = self.client.get("/admin-dashboard/")
        # Chart titles
        self.assertContains(r, "Applications by Status")
        self.assertContains(r, "Placement Drives by Sector")
        self.assertContains(r, "Student Selection Ratio")
        self.assertContains(r, "Monthly Application Trends")
        # Recent activities data
        self.assertContains(r, "Alpha Tech")
        self.assertContains(r, "Software Engineer")
        self.assertContains(r, "24UG101")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class Phase3StudentAndCompanyManagementTests(TestCase):
    def setUp(self):
        from accounts.models import Department, StudentProfile
        from recruitment.models import Company, PlacementDrive
        from django.utils import timezone
        from datetime import timedelta
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.dept_bca = Department.objects.create(name="Computer Applications", code="BCA")
        self.dept_ece = Department.objects.create(name="Electronics", code="ECE")

        # Staff user
        self.staff_user = User.objects.create_user(
            "placement_officer", email="officer@college.edu", password="OfficerPass!123", is_staff=True
        )

        # Student 1 (Active, BCA, 2026, CGPA 8.5, 0 backlogs)
        self.student1_user = User.objects.create_user(
            "student_arun", first_name="Arun", last_name="Kumar", email="arun@example.com", password="StudentPass!1"
        )
        resume_content = b"%PDF-1.4 mock resume content"
        mock_file = SimpleUploadedFile("arun_resume.pdf", resume_content, content_type="application/pdf")
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1_user,
            usn="24UG101",
            department=self.dept_bca,
            graduation_year=2026,
            cgpa=8.50,
            active_backlogs=0,
            phone="9876543210",
            resume=mock_file,
        )

        # Student 2 (Inactive, ECE, 2025, CGPA 6.75, 2 backlogs)
        self.student2_user = User.objects.create_user(
            "student_bindu", first_name="Bindu", last_name="Sharma", email="bindu@example.com", password="StudentPass!2", is_active=False
        )
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2_user,
            usn="23UG202",
            department=self.dept_ece,
            graduation_year=2025,
            cgpa=6.75,
            active_backlogs=2,
            phone="9123456789",
        )

        # Company 1 (With drives - protected from deletion)
        self.company_with_drives = Company.objects.create(
            name="Alpha Corp",
            industry="IT",
            website="https://alpha.example.com",
            contact_person="HR Manager",
            contact_email="hr@alpha.example.com",
            contact_phone="9845011111",
            description="Leading software solutions provider.",
        )
        self.drive = PlacementDrive.objects.create(
            company=self.company_with_drives,
            title="Software Development Engineer",
            category="IT",
            job_description="Python and Django developer",
            package_lpa=8.50,
            minimum_cgpa=7.00,
            maximum_backlogs=0,
            drive_date=timezone.now() + timedelta(days=10),
            application_deadline=timezone.now() + timedelta(days=5),
            status="OPEN",
        )

        # Company 2 (No drives - eligible for safe deletion)
        self.company_no_drives = Company.objects.create(
            name="Beta Finance",
            industry="BANKING",
            website="https://beta.example.com",
            contact_person="Recruiter",
            contact_email="recruiter@beta.example.com",
            contact_phone="9845022222",
            description="Financial consulting firm.",
        )

    def test_student_list_renders_for_staff(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_student_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "24UG101")
        self.assertContains(r, "23UG202")
        self.assertContains(r, "Arun Kumar")
        self.assertContains(r, "Bindu Sharma")

    def test_student_list_search_by_usn_name_email(self):
        self.client.force_login(self.staff_user)
        # Search by USN
        r = self.client.get(reverse("admin_student_list"), {"q": "24UG101"})
        self.assertContains(r, "24UG101")
        self.assertNotContains(r, "23UG202")

        # Search by name
        r = self.client.get(reverse("admin_student_list"), {"q": "Bindu"})
        self.assertContains(r, "23UG202")
        self.assertNotContains(r, "24UG101")

        # Search by email
        r = self.client.get(reverse("admin_student_list"), {"q": "arun@example.com"})
        self.assertContains(r, "24UG101")
        self.assertNotContains(r, "23UG202")

    def test_student_list_filter_department_year_status(self):
        self.client.force_login(self.staff_user)
        # Filter by department BCA
        r = self.client.get(reverse("admin_student_list"), {"department": self.dept_bca.pk})
        self.assertContains(r, "24UG101")
        self.assertNotContains(r, "23UG202")

        # Filter by graduation year 2025
        r = self.client.get(reverse("admin_student_list"), {"year": 2025})
        self.assertContains(r, "23UG202")
        self.assertNotContains(r, "24UG101")

        # Filter by status: active
        r = self.client.get(reverse("admin_student_list"), {"status": "active"})
        self.assertContains(r, "24UG101")
        self.assertNotContains(r, "23UG202")

        # Filter by status: inactive
        r = self.client.get(reverse("admin_student_list"), {"status": "inactive"})
        self.assertContains(r, "23UG202")
        self.assertNotContains(r, "24UG101")

    def test_student_detail_view(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_student_detail", kwargs={"pk": self.student1_profile.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "24UG101")
        self.assertContains(r, "8.5")
        self.assertContains(r, "Class of 2026")
        self.assertContains(r, "arun@example.com")
        self.assertContains(r, reverse("admin_student_resume", kwargs={"pk": self.student1_profile.pk}))

    def test_student_edit_view_updates_record_without_password(self):
        self.client.force_login(self.staff_user)
        old_password_hash = self.student1_user.password
        edit_url = reverse("admin_student_edit", kwargs={"pk": self.student1_profile.pk})

        # GET edit page
        r_get = self.client.get(edit_url)
        self.assertEqual(r_get.status_code, 200)
        self.assertNotContains(r_get, "password1")
        self.assertNotContains(r_get, "password2")

        # POST update
        data = {
            "first_name": "Arun-Updated",
            "last_name": "Kumar-Updated",
            "email": "arun.updated@example.com",
            "department": self.dept_ece.pk,
            "graduation_year": 2026,
            "cgpa": "9.15",
            "active_backlogs": 0,
            "phone": "9998887776",
            "is_active": "on",
        }
        r_post = self.client.post(edit_url, data)
        self.assertRedirects(r_post, reverse("admin_student_detail", kwargs={"pk": self.student1_profile.pk}))

        self.student1_profile.refresh_from_db()
        self.student1_user.refresh_from_db()
        self.assertEqual(self.student1_user.first_name, "Arun-Updated")
        self.assertEqual(self.student1_user.email, "arun.updated@example.com")
        self.assertEqual(self.student1_profile.department, self.dept_ece)
        self.assertEqual(float(self.student1_profile.cgpa), 9.15)
        self.assertEqual(self.student1_profile.phone, "9998887776")
        self.assertEqual(self.student1_user.password, old_password_hash)

    def test_student_toggle_status_view(self):
        self.client.force_login(self.staff_user)
        toggle_url = reverse("admin_student_toggle_status", kwargs={"pk": self.student1_profile.pk})

        # Initially active -> toggle to inactive
        self.assertTrue(self.student1_user.is_active)
        r = self.client.post(toggle_url)
        self.assertRedirects(r, reverse("admin_student_detail", kwargs={"pk": self.student1_profile.pk}))
        self.student1_user.refresh_from_db()
        self.assertFalse(self.student1_user.is_active)

        # Toggle back to active
        r = self.client.post(toggle_url)
        self.student1_user.refresh_from_db()
        self.assertTrue(self.student1_user.is_active)

    def test_student_resume_download_authorized(self):
        self.client.force_login(self.staff_user)
        resume_url = reverse("admin_student_resume", kwargs={"pk": self.student1_profile.pk})
        r = self.client.get(resume_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_student_resume_download_missing_handled(self):
        self.client.force_login(self.staff_user)
        resume_url = reverse("admin_student_resume", kwargs={"pk": self.student2_profile.pk})
        r = self.client.get(resume_url, follow=True)
        self.assertRedirects(r, reverse("admin_student_detail", kwargs={"pk": self.student2_profile.pk}))
        messages = list(r.context["messages"])
        self.assertTrue(any("not uploaded a resume" in str(m) for m in messages))

    def test_company_list_view_and_search(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_company_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Alpha Corp")
        self.assertContains(r, "Beta Finance")

        # Search by name
        r_search = self.client.get(reverse("admin_company_list"), {"q": "Alpha"})
        self.assertContains(r_search, "Alpha Corp")
        self.assertNotContains(r_search, "Beta Finance")

    def test_company_create_view(self):
        self.client.force_login(self.staff_user)
        create_url = reverse("admin_company_create")
        r_get = self.client.get(create_url)
        self.assertEqual(r_get.status_code, 200)

        # Successful creation
        data = {
            "name": "Gamma Systems",
            "industry": "Information Technology",
            "website": "https://gamma.example.com",
            "contact_person": "Talent Lead",
            "contact_email": "careers@gamma.example.com",
            "contact_phone": "+91 9845012345",
            "description": "Global enterprise software provider.",
        }
        r_post = self.client.post(create_url, data)
        from recruitment.models import Company
        new_company = Company.objects.get(name="Gamma Systems")
        self.assertRedirects(r_post, reverse("admin_company_detail", kwargs={"pk": new_company.pk}))

        # Duplicate name rejection
        r_dup = self.client.post(create_url, data)
        self.assertEqual(r_dup.status_code, 200)
        self.assertContains(r_dup, "already registered")

    def test_company_detail_and_edit_view(self):
        self.client.force_login(self.staff_user)
        detail_url = reverse("admin_company_detail", kwargs={"pk": self.company_with_drives.pk})
        r_detail = self.client.get(detail_url)
        self.assertEqual(r_detail.status_code, 200)
        self.assertContains(r_detail, "Alpha Corp")
        self.assertContains(r_detail, "Software Development Engineer")

        # Edit company
        edit_url = reverse("admin_company_edit", kwargs={"pk": self.company_with_drives.pk})
        edit_data = {
            "name": "Alpha Corp International",
            "industry": "IT & Cloud Services",
            "website": "https://alpha.example.com",
            "contact_person": "Senior HR",
            "contact_email": "hr@alpha.example.com",
            "contact_phone": "9845011111",
            "description": "Updated description",
        }
        r_edit = self.client.post(edit_url, edit_data)
        self.assertRedirects(r_edit, detail_url)
        self.company_with_drives.refresh_from_db()
        self.assertEqual(self.company_with_drives.name, "Alpha Corp International")
        self.assertEqual(self.company_with_drives.industry, "IT & Cloud Services")

    def test_company_safe_delete_foreign_key_protection(self):
        from recruitment.models import Company
        self.client.force_login(self.staff_user)

        # Deleting company with drives is BLOCKED
        delete_url_protected = reverse("admin_company_delete", kwargs={"pk": self.company_with_drives.pk})
        r_blocked = self.client.post(delete_url_protected, follow=True)
        self.assertRedirects(r_blocked, reverse("admin_company_detail", kwargs={"pk": self.company_with_drives.pk}))
        self.assertTrue(Company.objects.filter(pk=self.company_with_drives.pk).exists())
        messages = list(r_blocked.context["messages"])
        self.assertTrue(any("Cannot delete" in str(m) for m in messages))

        # Deleting company without drives SUCCEEDS
        delete_url_safe = reverse("admin_company_delete", kwargs={"pk": self.company_no_drives.pk})
        r_success = self.client.post(delete_url_safe, follow=True)
        self.assertRedirects(r_success, reverse("admin_company_list"))
        self.assertFalse(Company.objects.filter(pk=self.company_no_drives.pk).exists())
        messages = list(r_success.context["messages"])
        self.assertTrue(any("safely deleted" in str(m) for m in messages))

    def test_unauthorized_student_access_blocked_from_phase3_urls(self):
        self.client.force_login(self.student1_user)

        endpoints = [
            reverse("admin_student_list"),
            reverse("admin_student_detail", kwargs={"pk": self.student1_profile.pk}),
            reverse("admin_student_edit", kwargs={"pk": self.student1_profile.pk}),
            reverse("admin_student_resume", kwargs={"pk": self.student1_profile.pk}),
            reverse("admin_company_list"),
            reverse("admin_company_create"),
            reverse("admin_company_detail", kwargs={"pk": self.company_with_drives.pk}),
            reverse("admin_company_edit", kwargs={"pk": self.company_with_drives.pk}),
        ]

        for url in endpoints:
            r = self.client.get(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))

        # Test POST endpoints are also blocked
        post_endpoints = [
            reverse("admin_student_toggle_status", kwargs={"pk": self.student1_profile.pk}),
            reverse("admin_company_delete", kwargs={"pk": self.company_no_drives.pk}),
        ]
        for url in post_endpoints:
            r = self.client.post(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))



