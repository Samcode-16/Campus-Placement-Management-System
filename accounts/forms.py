import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from recruitment.forms import validate_resume_file

from .models import Department, StudentProfile


class _LoginFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autofocus": True, "placeholder": "Your username"}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password", "placeholder": "Your password"}
        )


class StudentLoginForm(_LoginFormMixin, AuthenticationForm):
    """Only student accounts may log in here."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or not hasattr(user, "student_profile"):
            raise forms.ValidationError(
                "This is not a student account. "
                "Placement officers should use the Placement Officer login.",
                code="not_student",
            )


class StaffLoginForm(_LoginFormMixin, AuthenticationForm):
    """Only staff accounts may log in here."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                "This account does not have placement officer access. "
                "Students should use the Student login.",
                code="not_staff",
            )


class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    usn = forms.CharField(max_length=20, label="USN / Register No.")
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    graduation_year = forms.IntegerField(min_value=2000, max_value=2100)
    cgpa = forms.DecimalField(
        max_digits=4, decimal_places=2, min_value=0, max_value=10, label="CGPA"
    )
    active_backlogs = forms.IntegerField(min_value=0, initial=0)
    phone = forms.CharField(max_length=15, required=False)

    # Consent: each box is separate and unticked by default, as GDPR requires.
    accept_terms = forms.BooleanField(
        error_messages={"required": "You must accept the Terms and Conditions to create an account."}
    )
    accept_privacy = forms.BooleanField(
        error_messages={"required": "Please confirm that you have read the Privacy Policy."}
    )
    accept_sharing = forms.BooleanField(
        error_messages={"required": "Your profile must be shareable with companies you apply to. Without this you cannot apply to drives."}
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hints = {
            "first_name": {"autocomplete": "given-name"},
            "last_name": {"autocomplete": "family-name"},
            "email": {"autocomplete": "email", "placeholder": "you@example.com"},
            "username": {"autocomplete": "username", "placeholder": "Choose a username"},
            "usn": {"placeholder": "e.g. 24UG00101"},
            "graduation_year": {"placeholder": "e.g. 2027"},
            "cgpa": {"placeholder": "e.g. 8.25"},
            "phone": {"inputmode": "tel", "autocomplete": "tel", "placeholder": "Optional"},
            "password1": {"autocomplete": "new-password"},
            "password2": {"autocomplete": "new-password"},
        }
        for name, attrs in hints.items():
            self.fields[name].widget.attrs.update(attrs)

        self.fields["accept_terms"].label = format_html(
            'I have read and agree to the <a href="{}" target="_blank" rel="noopener">Terms and Conditions</a>.',
            reverse("terms"),
        )
        self.fields["accept_privacy"].label = format_html(
            'I have read the <a href="{}" target="_blank" rel="noopener">Privacy Policy</a> and the '
            '<a href="{}" target="_blank" rel="noopener">DPDP Act Notice</a>, and I understand how my '
            "personal data is collected, used and protected.",
            reverse("privacy"),
            reverse("dpdp"),
        )
        self.fields["accept_sharing"].label = format_html(
            "I understand that my profile, academic details and resume will be shared with companies "
            'for the drives I apply to (<a href="{}#sharing" target="_blank" rel="noopener">details</a>).',
            reverse("privacy"),
        )

    field_order = [
        "first_name", "last_name", "email", "username",
        "usn", "department", "graduation_year", "cgpa",
        "active_backlogs", "phone", "password1", "password2",
        "accept_terms", "accept_privacy", "accept_sharing",
    ]

    def clean_usn(self):
        usn = self.cleaned_data["usn"].strip().upper()
        if StudentProfile.objects.filter(usn=usn).exists():
            raise forms.ValidationError("A student with this USN is already registered.")
        return usn

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        StudentProfile.objects.create(
            user=user,
            usn=self.cleaned_data["usn"],
            department=self.cleaned_data["department"],
            graduation_year=self.cleaned_data["graduation_year"],
            cgpa=self.cleaned_data["cgpa"],
            active_backlogs=self.cleaned_data["active_backlogs"],
            phone=self.cleaned_data["phone"],
            consent_accepted_at=timezone.now(),
            consent_version=settings.POLICY_VERSION,
        )
        return user


class StudentProfileForm(forms.ModelForm):
    """Students may update contact details and resume only.
    Academic data (CGPA, backlogs) is maintained by the placement office."""

    class Meta:
        model = StudentProfile
        fields = ("phone", "resume")
        labels = {"phone": "Phone number", "resume": "Resume"}
        help_texts = {
            "phone": "Recruiters use this number to reach you.",
            "resume": "PDF, DOC or DOCX, up to 2 MB. Uploading a new file replaces the old one.",
        }
        widgets = {
            "phone": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "e.g. 9845012345"}),
            "resume": forms.FileInput(attrs={"accept": ".pdf,.doc,.docx"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not re.fullmatch(r"\+?[0-9 \-]{8,15}", phone):
            raise forms.ValidationError("Enter a valid phone number (8 to 15 digits).")
        return phone

    def clean_resume(self):
        return validate_resume_file(self.cleaned_data.get("resume"))
