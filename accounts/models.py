from django.db import models
from django.contrib.auth.models import User


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ["name"]


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )

    usn = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="students"
    )

    graduation_year = models.PositiveSmallIntegerField()
    cgpa = models.DecimalField(max_digits=4, decimal_places=2)
    active_backlogs = models.PositiveSmallIntegerField(default=0)

    phone = models.CharField(max_length=15, blank=True)
    resume = models.FileField(
        upload_to="resumes/",
        blank=True
    )

    # Proof that the student accepted the Terms and Privacy Policy at sign-up.
    consent_accepted_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usn} - {self.user.get_full_name()}"

    class Meta:
        ordering = ["usn"]