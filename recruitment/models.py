
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import Department, StudentProfile


class Company(models.Model):
    name = models.CharField(max_length=150, unique=True)
    industry = models.CharField(max_length=100)
    website = models.URLField(blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class PlacementDrive(models.Model):
    class Category(models.TextChoices):
        IT = "IT", "IT Drives"
        CORE = "CORE", "Core Engineering"
        BANKING = "BANKING", "Banking & Finance"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        COMPLETED = "COMPLETED", "Completed"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="drives"
    )
    title = models.CharField(max_length=150)
    category = models.CharField(
        max_length=10,
        choices=Category.choices
    )
    job_description = models.TextField()
    package_lpa = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    minimum_cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10)
        ]
    )
    maximum_backlogs = models.PositiveSmallIntegerField(default=0)
    eligible_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="placement_drives"
    )
    application_deadline = models.DateTimeField()
    drive_date = models.DateTimeField()
    vacancies = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_accepting_applications(self):
        """A drive accepts applications only while OPEN and before the deadline."""
        return (
            self.status == self.Status.OPEN
            and self.application_deadline >= timezone.now()
        )

    def eligibility_issues(self, student):
        """Return a list of reasons why `student` is NOT eligible (empty = eligible)."""
        issues = []
        if student.cgpa < self.minimum_cgpa:
            issues.append(
                f"Minimum CGPA required is {self.minimum_cgpa} (yours is {student.cgpa})."
            )
        if student.active_backlogs > self.maximum_backlogs:
            issues.append(
                f"Maximum {self.maximum_backlogs} active backlog(s) allowed "
                f"(you have {student.active_backlogs})."
            )
        allowed = {d.pk for d in self.eligible_departments.all()}  # uses prefetch if present
        if allowed and student.department_id not in allowed:
            issues.append("Your department is not eligible for this drive.")
        return issues

    def __str__(self):
        return f"{self.company.name} - {self.title}"

    class Meta:
        ordering = ["-drive_date"]


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        SHORTLISTED = "SHORTLISTED", "Shortlisted"
        SELECTED = "SELECTED", "Selected"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.PROTECT,
        related_name="applications"
    )
    drive = models.ForeignKey(
        PlacementDrive,
        on_delete=models.PROTECT,
        related_name="applications"
    )
    resume = models.FileField(
        upload_to="application_resumes/",
        blank=True
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.APPLIED
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "drive"],
                name="unique_student_drive_application"
            )
        ]

    def __str__(self):
        return f"{self.student.usn} - {self.drive.title}"


class InterviewRound(models.Model):
    class RoundType(models.TextChoices):
        APTITUDE = "APTITUDE", "Aptitude Test"
        TECHNICAL = "TECHNICAL", "Technical Interview"
        HR = "HR", "HR Interview"
        GROUP_DISCUSSION = "GD", "Group Discussion"
        OTHER = "OTHER", "Other"

    class Result(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CLEARED = "CLEARED", "Cleared"
        FAILED = "FAILED", "Failed"

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="interview_rounds"
    )
    round_type = models.CharField(
        max_length=10,
        choices=RoundType.choices
    )
    scheduled_at = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
        default=Result.PENDING
    )
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.application} - {self.get_round_type_display()}"

    class Meta:
        ordering = ["scheduled_at"]


class PlacementOffer(models.Model):
    application = models.OneToOneField(
        Application,
        on_delete=models.PROTECT,
        related_name="offer"
    )
    offered_package_lpa = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    offer_date = models.DateField()
    joining_date = models.DateField(null=True, blank=True)
    accepted = models.BooleanField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"Offer - {self.application.student.usn}"

    class Meta:
        ordering = ["-offer_date"]
