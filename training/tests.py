from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Department, StudentProfile
from training.models import TrainingEnrollment, TrainingProgram


class Phase5TrainingManagementTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Applications", code="BCA")

        self.staff_user = User.objects.create_user(
            "training_admin", email="training@campus.edu", password="AdminPass!123", is_staff=True
        )

        self.student_user = User.objects.create_user(
            "student_sam", email="sam@example.com", password="StudentPass!123"
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            usn="24BCA501",
            department=self.dept,
            graduation_year=2026,
            cgpa=8.20,
        )

        # Program 1 (With enrollments - protected from deletion)
        self.program_with_enrollment = TrainingProgram.objects.create(
            title="Full-Stack Web Development Bootcamp",
            trainer="TechCorp Academy",
            mode=TrainingProgram.Mode.HYBRID,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            capacity=40,
            status=TrainingProgram.Status.UPCOMING,
            description="Comprehensive MERN & Django stack development.",
        )
        self.enrollment = TrainingEnrollment.objects.create(
            student=self.student_profile,
            program=self.program_with_enrollment,
            attendance_percentage=95.0,
            assessment_score=88.5,
            completion_status=TrainingEnrollment.CompletionStatus.IN_PROGRESS,
        )

        # Program 2 (No enrollments - can be deleted safely)
        self.program_no_enrollment = TrainingProgram.objects.create(
            title="Cloud and DevOps Engineering Workshop",
            trainer="AWS Solutions Architect",
            mode=TrainingProgram.Mode.ONLINE,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=20),
            capacity=50,
            status=TrainingProgram.Status.UPCOMING,
            description="AWS cloud foundations, CI/CD, and Docker containerization.",
        )

    def test_admin_training_list_renders_and_filters_and_searches(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(reverse("admin_training_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Full-Stack Web Development Bootcamp")
        self.assertContains(r, "Cloud and DevOps Engineering Workshop")

        # Search by title
        r_search = self.client.get(reverse("admin_training_list"), {"q": "Full-Stack"})
        self.assertContains(r_search, "Full-Stack Web Development Bootcamp")
        self.assertNotContains(r_search, "Cloud and DevOps Engineering Workshop")

        # Filter by mode
        r_mode = self.client.get(reverse("admin_training_list"), {"mode": "ONLINE"})
        self.assertContains(r_mode, "Cloud and DevOps Engineering Workshop")
        self.assertNotContains(r_mode, "Full-Stack Web Development Bootcamp")

        # Filter by status
        r_status = self.client.get(reverse("admin_training_list"), {"status": "UPCOMING"})
        self.assertContains(r_status, "Full-Stack Web Development Bootcamp")
        self.assertContains(r_status, "Cloud and DevOps Engineering Workshop")

    def test_admin_training_create_and_validation(self):
        self.client.force_login(self.staff_user)
        create_url = reverse("admin_training_create")
        r_get = self.client.get(create_url)
        self.assertEqual(r_get.status_code, 200)

        # Valid creation
        valid_data = {
            "title": "Machine Learning with Python",
            "trainer": "Dr. Ananya Sharma",
            "mode": "OFFLINE",
            "status": "UPCOMING",
            "start_date": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
            "end_date": (date.today() + timedelta(days=25)).strftime("%Y-%m-%d"),
            "capacity": "35",
            "description": "Supervised learning, deep neural nets, and scikit-learn.",
        }
        r_post = self.client.post(create_url, valid_data)
        new_prog = TrainingProgram.objects.get(title="Machine Learning with Python")
        self.assertRedirects(r_post, reverse("admin_training_detail", kwargs={"pk": new_prog.pk}))

        # Invalid: start date after end date
        invalid_data = valid_data.copy()
        invalid_data["title"] = "Broken Timing Training"
        invalid_data["start_date"] = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        invalid_data["end_date"] = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
        r_invalid = self.client.post(create_url, invalid_data)
        self.assertEqual(r_invalid.status_code, 200)
        self.assertContains(r_invalid, "cannot be scheduled after the end date")

    def test_admin_training_detail_and_edit(self):
        self.client.force_login(self.staff_user)
        detail_url = reverse("admin_training_detail", kwargs={"pk": self.program_with_enrollment.pk})
        r_detail = self.client.get(detail_url)
        self.assertEqual(r_detail.status_code, 200)
        self.assertContains(r_detail, "Full-Stack Web Development Bootcamp")
        self.assertContains(r_detail, "24BCA501")
        self.assertContains(r_detail, "95")

        # Edit program
        edit_url = reverse("admin_training_edit", kwargs={"pk": self.program_with_enrollment.pk})
        edit_data = {
            "title": "Full-Stack Web Development Bootcamp (Advanced)",
            "trainer": "TechCorp Senior Academy",
            "mode": "HYBRID",
            "status": "ONGOING",
            "start_date": self.program_with_enrollment.start_date.strftime("%Y-%m-%d"),
            "end_date": self.program_with_enrollment.end_date.strftime("%Y-%m-%d"),
            "capacity": "45",
            "description": "Updated syllabus with Next.js and Docker.",
        }
        r_edit = self.client.post(edit_url, edit_data)
        self.assertRedirects(r_edit, detail_url)
        self.program_with_enrollment.refresh_from_db()
        self.assertEqual(self.program_with_enrollment.title, "Full-Stack Web Development Bootcamp (Advanced)")
        self.assertEqual(self.program_with_enrollment.capacity, 45)

    def test_admin_training_status_change(self):
        self.client.force_login(self.staff_user)
        status_url = reverse("admin_training_status", kwargs={"pk": self.program_with_enrollment.pk})

        r = self.client.post(status_url, {"status": "ONGOING"})
        self.assertRedirects(r, reverse("admin_training_detail", kwargs={"pk": self.program_with_enrollment.pk}))
        self.program_with_enrollment.refresh_from_db()
        self.assertEqual(self.program_with_enrollment.status, "ONGOING")

    def test_admin_training_delete_safety(self):
        self.client.force_login(self.staff_user)

        # Deleting program with enrollments is BLOCKED
        delete_url1 = reverse("admin_training_delete", kwargs={"pk": self.program_with_enrollment.pk})
        r_blocked = self.client.post(delete_url1, follow=True)
        self.assertRedirects(r_blocked, reverse("admin_training_detail", kwargs={"pk": self.program_with_enrollment.pk}))
        self.assertTrue(TrainingProgram.objects.filter(pk=self.program_with_enrollment.pk).exists())
        messages = list(r_blocked.context["messages"])
        self.assertTrue(any("Cannot delete" in str(m) for m in messages))

        # Deleting program without enrollments SUCCEEDS
        delete_url2 = reverse("admin_training_delete", kwargs={"pk": self.program_no_enrollment.pk})
        r_success = self.client.post(delete_url2, follow=True)
        self.assertRedirects(r_success, reverse("admin_training_list"))
        self.assertFalse(TrainingProgram.objects.filter(pk=self.program_no_enrollment.pk).exists())
        messages = list(r_success.context["messages"])
        self.assertTrue(any("deleted successfully" in str(m) for m in messages))

    def test_unauthorized_student_access_blocked_from_training_admin_urls(self):
        self.client.force_login(self.student_user)
        endpoints = [
            reverse("admin_training_list"),
            reverse("admin_training_create"),
            reverse("admin_training_detail", kwargs={"pk": self.program_with_enrollment.pk}),
            reverse("admin_training_edit", kwargs={"pk": self.program_with_enrollment.pk}),
        ]
        for url in endpoints:
            r = self.client.get(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))

        post_endpoints = [
            reverse("admin_training_delete", kwargs={"pk": self.program_with_enrollment.pk}),
            reverse("admin_training_status", kwargs={"pk": self.program_with_enrollment.pk}),
        ]
        for url in post_endpoints:
            r = self.client.post(url, follow=True)
            self.assertEqual(r.redirect_chain[-1][0], reverse("accounts:student_dashboard"))
            messages = list(r.context["messages"])
            self.assertTrue(any("Access denied" in str(m) for m in messages))
