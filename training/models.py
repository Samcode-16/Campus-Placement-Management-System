
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import StudentProfile


class TrainingProgram(models.Model):

    class Mode(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline"
        HYBRID = "HYBRID", "Hybrid"

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        ONGOING = "ONGOING", "Ongoing"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    title = models.CharField(max_length=150)
    description = models.TextField()
    trainer = models.CharField(max_length=100)
    mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.OFFLINE
    )
    start_date = models.DateField()
    end_date = models.DateField()
    capacity = models.PositiveIntegerField(default=30)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.UPCOMING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-start_date"]


class TrainingEnrollment(models.Model):

    class CompletionStatus(models.TextChoices):
        ENROLLED = "ENROLLED", "Enrolled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        DROPPED = "DROPPED", "Dropped"

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.PROTECT,
        related_name="training_enrollments"
    )
    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.PROTECT,
        related_name="enrollments"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    assessment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    completion_status = models.CharField(
        max_length=12,
        choices=CompletionStatus.choices,
        default=CompletionStatus.ENROLLED
    )

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "program"],
                name="unique_student_training_enrollment"
            )
        ]

    def __str__(self):
        return f"{self.student.usn} - {self.program.title}"


class TrainingAttendance(models.Model):

    class AttendanceStatus(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"

    enrollment = models.ForeignKey(
        TrainingEnrollment,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )
    session_date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT
    )
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-session_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "session_date"],
                name="unique_enrollment_attendance_date"
            )
        ]

    def __str__(self):
        return (
            f"{self.enrollment.student.usn} - "
            f"{self.session_date} - {self.status}"
        )
